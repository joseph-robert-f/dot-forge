"""Independent regression review of portable deliverable selection."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from printkit import bundle, orchestrator
from printkit.common import ForgeError
import test_workflow


class BundleScopeReviewTests(unittest.TestCase):
    setUp = test_workflow.WorkflowTests.setUp

    def test_excluded_large_runtime_file_is_never_opened(self):
        orchestrator.run_all(self.request, self.run)
        cache = self.run / '.cache/mesa_shader_cache/blob'
        cache.parent.mkdir(parents=True)
        with cache.open('wb') as stream:
            stream.truncate(bundle.MAX_BUNDLE + 1)
        unrelated = self.run / 'private-notes.txt'
        unrelated.write_text('not a deliverable')
        forbidden = {cache, unrelated}
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            if path in forbidden:
                raise AssertionError('Excluded file bytes were accessed: ' + str(path))
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded_open):
            bundle.verify_run(self.run)
            result = bundle.create_bundle(self.run)
        with zipfile.ZipFile(self.run.parent / result['bundle']) as archive:
            self.assertNotIn('.cache/mesa_shader_cache/blob', archive.namelist())
            self.assertNotIn('private-notes.txt', archive.namelist())

    def test_nested_envelope_named_files_are_selected(self):
        orchestrator.run_all(self.request, self.run)
        for name in ('source/manifest.json', 'logs/COMPLETE'):
            with self.subTest(name=name):
                path = self.run / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('unlisted deliverable')
                with self.assertRaises(ForgeError):
                    bundle.verify_run(self.run)
                path.unlink()

    def test_extra_zip_names_rejected_before_materialization(self):
        names = ['.cache/mesa_shader_cache/blob', 'private-notes.txt', 'upstream/request.json',
                 'exports//secret.txt', './request.json', 'source/../private.txt']
        for index, name in enumerate(names):
            with self.subTest(name=name):
                archive_path = self.run.parent / f'case-{index}.zip'
                with zipfile.ZipFile(archive_path, 'w') as archive:
                    archive.writestr(name, b'never materialize this')
                with patch('printkit.bundle.tempfile.TemporaryDirectory',
                           side_effect=AssertionError('Invalid ZIP reached materialization')):
                    with self.assertRaises(ForgeError):
                        bundle.verify_bundle(archive_path)

    def test_symlink_inside_excluded_cache_rejected(self):
        orchestrator.run_all(self.request, self.run)
        cache = self.run / '.cache'
        cache.mkdir()
        (cache / 'link').symlink_to(self.run / 'request.json')
        with self.assertRaises(ForgeError):
            bundle.verify_run(self.run)
