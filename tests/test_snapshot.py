"""Source snapshot regressions use only synthetic, nonprivate marker files."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from printkit.common import ForgeError
from printkit import orchestrator
from printkit.snapshot import copy_source_snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'repository'; self.root.mkdir()
        self.run = self.base/'run'; self.run.mkdir()
        self.outside = self.base/'outside-marker.txt'
        self.outside.write_text('NONPRIVATE_CONTROLLED_MARKER')
        (self.root/'docs').mkdir()
        (self.root/'README.md').write_text('Reviewed source')

    def copy(self):
        with patch.object(orchestrator, 'repository_root', return_value=self.root):
            orchestrator._snapshot_source(self.run)

    def assert_refused_without_marker(self):
        # Guard all os.read calls by inode, proving the outside target was never read.
        outside = self.outside.stat()
        original = os.read
        def guarded(fd, amount):
            info = os.fstat(fd)
            self.assertNotEqual((info.st_dev, info.st_ino), (outside.st_dev, outside.st_ino),
                                'snapshot read the outside marker target')
            return original(fd, amount)
        with patch('printkit.snapshot.os.read', side_effect=guarded):
            with self.assertRaises(ForgeError) as result:
                self.copy()
        self.assertEqual(result.exception.finding, 'unsafe_source_snapshot')
        for path in self.run.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'NONPRIVATE_CONTROLLED_MARKER', path.read_bytes())
        self.assertEqual(self.outside.read_text(), 'NONPRIVATE_CONTROLLED_MARKER')

    def test_file_link_target_never_read(self):
        (self.root/'docs/linked.txt').symlink_to(self.outside)
        self.assert_refused_without_marker()

    def test_nested_directory_link_target_never_read(self):
        directory = self.base/'outside'; directory.mkdir()
        self.outside.rename(directory/'marker.txt'); self.outside = directory/'marker.txt'
        (self.root/'docs/linked').symlink_to(directory, target_is_directory=True)
        self.assert_refused_without_marker()

    def test_selected_top_directory_link_target_never_read(self):
        (self.root/'docs').rmdir()
        directory = self.base/'outside'; directory.mkdir()
        self.outside.rename(directory/'marker.txt'); self.outside = directory/'marker.txt'
        (self.root/'docs').symlink_to(directory, target_is_directory=True)
        self.assert_refused_without_marker()

    def test_root_document_link_target_never_read(self):
        (self.root/'README.md').unlink(); (self.root/'README.md').symlink_to(self.outside)
        self.assert_refused_without_marker()

    def test_source_root_ancestor_link_refused(self):
        alias = self.base/'alias'; alias.symlink_to(self.base, target_is_directory=True)
        self.root = alias/'repository'
        self.assert_refused_without_marker()

    def test_hardlinked_source_refused(self):
        os.link(self.outside, self.root/'docs/linked.txt')
        self.assert_refused_without_marker()

    def test_fifo_refused_without_open_or_block(self):
        os.mkfifo(self.root/'docs/pipe')
        self.assert_refused_without_marker()

    def test_ordinary_source_copied_cache_omitted_mode_preserved(self):
        scripts = self.root/'scripts'; scripts.mkdir()
        (scripts/'bootstrap').write_text('#!/bin/sh\nexit 0\n'); (scripts/'bootstrap').chmod(0o755)
        cache=self.root/'docs/__pycache__';cache.mkdir();(cache/'temporary.pyc').write_bytes(b'CACHE')
        (self.root/'docs/guide.md').write_text('Useful guide')
        self.copy()
        self.assertEqual((self.run/'source/docs/guide.md').read_text(), 'Useful guide')
        self.assertEqual((self.run/'source/README.md').read_text(), 'Reviewed source')
        self.assertFalse((self.run/'source/docs/__pycache__').exists())
        self.assertEqual((self.run/'source/scripts/bootstrap').stat().st_mode & 0o777, 0o755)

    def test_size_budget_before_source_read(self):
        with (self.root/'docs/too-large.dat').open('wb') as file:
            file.truncate(33*1024*1024)
        self.assert_refused_without_marker()

    def test_destination_parent_link_refused(self):
        destination=self.base/'alias-run';destination.symlink_to(self.run, target_is_directory=True)
        with self.assertRaises(ForgeError):
            copy_source_snapshot(self.root,destination/'source')
        self.assertFalse((self.run/'source').exists())

class SourceIdentityTests(unittest.TestCase):
    def test_identity_does_not_read_python_link_target(self):
        from printkit.snapshot import python_source_hashes
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'package';root.mkdir()
            outside=Path(temporary)/'outside.py';outside.write_text('NONPRIVATE_CONTROLLED_MARKER')
            (root/'linked.py').symlink_to(outside)
            original=os.read
            def guarded(fd, size):
                self.assertNotEqual(os.fstat(fd).st_ino, outside.stat().st_ino)
                return original(fd,size)
            with patch('printkit.snapshot.os.read', side_effect=guarded), self.assertRaises(ForgeError):
                python_source_hashes(root)

    def test_identity_matches_regular_python_bytes(self):
        import hashlib
        from printkit.snapshot import python_source_hashes
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'nested').mkdir()
            (root/'a.py').write_text('alpha');(root/'nested/b.py').write_text('beta')
            (root/'README.md').write_text('not executable source')
            self.assertEqual(python_source_hashes(root),{'a.py':hashlib.sha256(b'alpha').hexdigest(),
                'nested/b.py':hashlib.sha256(b'beta').hexdigest()})

class RootResolutionTests(unittest.TestCase):
    def test_orchestrator_preserves_root_link_for_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/'repository';(root/'src/printkit').mkdir(parents=True)
            (root/'src/printkit/orchestrator.py').write_text('# synthetic source identity')
            alias=base/'alias';alias.symlink_to(root,target_is_directory=True)
            run=base/'run';run.mkdir()
            with patch.object(orchestrator,'__file__',str(alias/'src/printkit/orchestrator.py')):
                self.assertEqual(orchestrator.repository_root(),alias)
                with self.assertRaises(ForgeError):orchestrator._snapshot_source(run)
