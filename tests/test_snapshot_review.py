"""Independent synthetic filesystem regressions for source snapshot containment."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from printkit import snapshot
from printkit.common import ForgeError


class SnapshotReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo'
        self.root.mkdir()
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'safe.py').write_bytes(b'controlled source\n')
        self.target = self.base / 'snapshot'
        self.outside = self.base / 'synthetic-outside'
        self.outside.mkdir()
        self.marker = self.outside / 'marker'
        self.marker.write_bytes(b'SYNTHETIC-OUTSIDE-MARKER')

    def copy(self):
        return snapshot.copy_source_snapshot(self.root, self.target)

    def refused(self):
        with self.assertRaises(ForgeError) as raised:
            self.copy()
        self.assertEqual(raised.exception.finding, 'unsafe_source_snapshot')
        self.assertEqual(self.marker.read_bytes(), b'SYNTHETIC-OUTSIDE-MARKER')

    def test_regular_source_copy_and_omissions(self):
        (self.root / 'README.md').write_text('reviewed')
        (self.root / 'secret-unselected').write_text('not selected')
        (self.root / 'src' / '__pycache__').mkdir()
        (self.root / 'src' / '__pycache__' / 'cache.pyc').write_text('cache')
        (self.root / 'src' / 'run.sh').write_text('executable')
        (self.root / 'src' / 'run.sh').chmod(0o755)
        self.copy()
        self.assertEqual((self.target / 'src' / 'safe.py').read_bytes(), b'controlled source\n')
        self.assertTrue((self.target / 'src' / 'run.sh').stat().st_mode & 0o100)
        self.assertFalse((self.target / 'secret-unselected').exists())
        self.assertFalse((self.target / 'src' / '__pycache__').exists())

    def test_nested_file_link_rejected(self):
        (self.root / 'src' / 'linked').symlink_to(self.marker)
        self.refused()

    def test_nested_directory_link_rejected(self):
        (self.root / 'src' / 'linked').symlink_to(self.outside, target_is_directory=True)
        self.refused()

    def test_selected_directory_link_rejected(self):
        (self.root / 'docs').symlink_to(self.outside, target_is_directory=True)
        self.refused()

    def test_selected_root_file_link_rejected(self):
        (self.root / 'README.md').symlink_to(self.marker)
        self.refused()

    def test_root_link_rejected(self):
        link = self.base / 'root-link'
        link.symlink_to(self.root, target_is_directory=True)
        self.root = link
        self.refused()

    def test_source_ancestor_link_rejected(self):
        link = self.base / 'parent-link'
        link.symlink_to(self.base, target_is_directory=True)
        self.root = link / 'repo'
        self.refused()

    def test_destination_link_rejected(self):
        self.target.symlink_to(self.outside, target_is_directory=True)
        self.refused()
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()), ['marker'])

    def test_destination_ancestor_link_rejected(self):
        link = self.base / 'dest-link'
        link.symlink_to(self.outside, target_is_directory=True)
        self.target = link / 'snapshot'
        self.refused()
        self.assertFalse((self.outside / 'snapshot').exists())

    def test_hard_link_rejected(self):
        os.link(self.marker, self.root / 'src' / 'hardlink')
        self.refused()

    def test_fifo_rejected(self):
        os.mkfifo(self.root / 'src' / 'fifo')
        self.refused()

    def test_ignored_name_does_not_hide_link(self):
        (self.root / 'src' / 'hidden.pyc').symlink_to(self.marker)
        self.refused()

    def test_selected_type_mismatch_rejected(self):
        (self.root / 'README.md').mkdir()
        self.refused()

    def test_file_post_stat_link_swap_never_reads_marker(self):
        real_stat, real_read = os.stat, os.read
        source = self.root / 'src' / 'safe.py'
        marker_inode = self.marker.stat().st_ino
        swapped = False
        def swapping_stat(name, *args, **kwargs):
            nonlocal swapped
            result = real_stat(name, *args, **kwargs)
            if name == 'safe.py' and kwargs.get('dir_fd') is not None and not swapped:
                swapped = True
                source.unlink()
                source.symlink_to(self.marker)
            return result
        def guarded_read(fd, amount):
            self.assertNotEqual(os.fstat(fd).st_ino, marker_inode, 'Outside marker was read')
            return real_read(fd, amount)
        with patch.object(snapshot.os, 'stat', side_effect=swapping_stat), patch.object(snapshot.os, 'read', side_effect=guarded_read):
            self.refused()
        self.assertTrue(swapped)

    def test_directory_post_stat_link_swap_rejected(self):
        nested = self.root / 'src' / 'nested'
        nested.mkdir()
        real_stat = os.stat
        swapped = False
        def swapping_stat(name, *args, **kwargs):
            nonlocal swapped
            result = real_stat(name, *args, **kwargs)
            if name == 'nested' and kwargs.get('dir_fd') is not None and not swapped:
                swapped = True
                nested.rmdir()
                nested.symlink_to(self.outside, target_is_directory=True)
            return result
        with patch.object(snapshot.os, 'stat', side_effect=swapping_stat):
            self.refused()
        self.assertTrue(swapped)

    def test_destination_mkdir_link_swap_rejected(self):
        real_mkdir = os.mkdir
        swapped = False
        def swapping_mkdir(name, *args, **kwargs):
            nonlocal swapped
            result = real_mkdir(name, *args, **kwargs)
            if name == self.target.name and kwargs.get('dir_fd') is not None:
                swapped = True
                self.target.rmdir()
                self.target.symlink_to(self.outside, target_is_directory=True)
            return result
        with patch.object(snapshot.os, 'mkdir', side_effect=swapping_mkdir):
            self.refused()
        self.assertTrue(swapped)
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()), ['marker'])

    def test_source_root_open_link_swap_rejected(self):
        real_open = os.open
        swapped = False
        def swapping_open(name, flags, *args, **kwargs):
            nonlocal swapped
            if name == 'repo' and kwargs.get('dir_fd') is not None and not swapped:
                swapped = True
                self.root.rename(self.base / 'original-repo')
                self.root.symlink_to(self.outside, target_is_directory=True)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(snapshot.os, 'open', side_effect=swapping_open):
            self.refused()
        self.assertTrue(swapped)
        self.assertFalse(self.target.exists())

    def test_destination_file_link_inserted_before_open_rejected(self):
        real_open = os.open
        swapped = False
        def swapping_open(name, flags, *args, **kwargs):
            nonlocal swapped
            if name == 'safe.py' and flags & os.O_CREAT and not swapped:
                swapped = True
                (self.target / 'src' / 'safe.py').symlink_to(self.marker)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(snapshot.os, 'open', side_effect=swapping_open):
            self.refused()
        self.assertTrue(swapped)

    def test_file_post_stat_fifo_swap_rejected_without_read(self):
        real_stat = os.stat
        source = self.root / 'src' / 'safe.py'
        swapped = False
        def swapping_stat(name, *args, **kwargs):
            nonlocal swapped
            result = real_stat(name, *args, **kwargs)
            if name == 'safe.py' and kwargs.get('dir_fd') is not None and not swapped:
                swapped = True
                source.unlink()
                os.mkfifo(source)
            return result
        with patch.object(snapshot.os, 'stat', side_effect=swapping_stat), patch.object(snapshot.os, 'read', side_effect=AssertionError('No FIFO read allowed')):
            self.refused()
        self.assertTrue(swapped)

    def test_identity_entry_budget_counts_pre_enumerated_siblings(self):
        package = self.base / 'package'
        package.mkdir()
        (package / 'a').mkdir()
        (package / 'a' / 'first.py').write_text('first')
        (package / 'a' / 'second.py').write_text('second')
        (package / 'b.py').write_text('third')
        with patch.object(snapshot, 'MAX_ENTRIES', 3), self.assertRaises(ForgeError):
            snapshot.python_source_hashes(package)

    def test_budgets_fail_closed_without_modifying_source(self):
        for budget, value in [('MAX_BYTES', 1), ('MAX_ENTRIES', 1), ('MAX_DEPTH', 1)]:
            with self.subTest(budget=budget), patch.object(snapshot, budget, value):
                self.target = self.base / budget
                self.refused()
                self.assertEqual((self.root / 'src' / 'safe.py').read_bytes(), b'controlled source\n')

    def test_partial_failure_does_not_copy_external_bytes_or_change_source(self):
        (self.root / 'src' / 'z-link').symlink_to(self.marker)
        self.refused()
        self.assertEqual((self.target / 'src' / 'safe.py').read_bytes(), b'controlled source\n')
        self.assertFalse((self.target / 'src' / 'z-link').exists())
        self.assertEqual((self.root / 'src' / 'safe.py').read_bytes(), b'controlled source\n')


if __name__ == '__main__':
    unittest.main()
