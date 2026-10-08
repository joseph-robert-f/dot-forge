"""Portable bundles contain deliverables, never incidental runtime HOME data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from printkit import bundle, orchestrator as flow
from printkit.common import ForgeError, load_json, sha256, write_json
from test_workflow import ROOT, fake_generate, fake_render


class BundleScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / 'run'
        request = load_json(ROOT / 'examples/calibration-part/request.json')
        with patch('printkit.adapters.blender.generate', fake_generate), patch('printkit.adapters.blender.render', fake_render):
            flow.run_all(request, self.run)

    def reindex(self):
        manifest = load_json(self.run / bundle.MANIFEST)
        return bundle.finalize(self.run, manifest['provenance'], manifest['stages'])

    def test_runtime_home_and_unrelated_root_files_never_read_or_bundled(self):
        private = []
        for name in ('.cache/mesa_shader_cache/private', '.config/blender/compatibility.ini',
                     '.ssh/id_private', '.bash_history', 'unrelated-personal.txt'):
            path = self.run / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'private contents must never enter bundle')
            private.append(path)
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            if path in private:
                self.fail(f'Excluded private file was opened: {path.name}')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded_open):
            manifest = self.reindex()
            bundle.verify_run(self.run)
            bundle.create_bundle(self.run)
        self.assertEqual(manifest['schema_version'], '1')
        self.assertEqual(manifest['artifact_policy']['name'], 'deliverables-only-v1')
        with zipfile.ZipFile(self.run.with_suffix('.zip')) as archive:
            names = set(archive.namelist())
        self.assertTrue(all(path.relative_to(self.run).as_posix() not in names for path in private))
        self.assertTrue(all(path.exists() for path in private))
        required = {'request.json', 'resolved-profile.json', 'journal.json', 'generation.json',
                    'validation.json', 'render.json', 'metrics.json', 'source/pyproject.toml',
                    'source/src/printkit/bundle.py', 'native/model.blend', 'exports/model.stl',
                    'manifest.json', 'COMPLETE', 'previews/contact-sheet.html'}
        required.update(f'previews/{view}.png' for view in ('front', 'back', 'side', 'top', 'oblique'))
        self.assertTrue(required <= names, required - names)

    def test_exact_inventory_rejects_new_export(self):
        (self.run / 'exports/unlisted.stl').write_bytes(b'untracked')
        with self.assertRaises(ForgeError) as caught:
            bundle.verify_run(self.run)
        self.assertEqual(caught.exception.finding, 'manifest_inventory_mismatch')

    def test_nested_envelope_names_are_hashed_artifacts(self):
        for name in ('source/manifest.json', 'source/COMPLETE', 'exports/.partial-evidence'):
            (self.run / name).write_bytes(b'deliverable evidence')
        records = {item['path'] for item in self.reindex()['artifacts']}
        self.assertTrue({'source/manifest.json', 'source/COMPLETE', 'exports/.partial-evidence'} <= records)
        bundle.verify_run(self.run)

    def test_missing_required_artifact_cannot_be_hidden_by_reindexing(self):
        (self.run / 'native/model.blend').unlink()
        self.reindex()
        with self.assertRaises(ForgeError) as caught:
            bundle.verify_run(self.run)
        self.assertEqual(caught.exception.finding, 'invalid_manifest')

    def test_excluded_file_cannot_be_smuggled_into_manifest(self):
        path = self.run / '.private'
        path.write_bytes(b'private')
        manifest = load_json(self.run / 'manifest.json')
        manifest['artifacts'].append({'path': '.private', 'bytes': path.stat().st_size, 'sha256': sha256(path)})
        write_json(self.run / 'manifest.json', manifest)
        write_json(self.run / 'COMPLETE', {'manifest_sha256': sha256(self.run / 'manifest.json')})
        with self.assertRaises(ForgeError) as caught:
            bundle.verify_run(self.run)
        self.assertEqual(caught.exception.finding, 'invalid_manifest')

    def test_zip_rejects_excluded_extras_before_materialization(self):
        bundle.create_bundle(self.run)
        archive_path = self.run.with_suffix('.zip')
        with zipfile.ZipFile(archive_path, 'a') as archive:
            archive.writestr('.cache/private', b'private')
        with patch.object(bundle.tempfile, 'TemporaryDirectory', side_effect=AssertionError('Must reject before extraction')):
            with self.assertRaises(ForgeError) as caught:
                bundle.verify_bundle(archive_path)
        self.assertEqual(caught.exception.finding, 'unsafe_bundle')

    def test_symlinks_rejected_in_selected_and_excluded_trees(self):
        target = Path(self.temp.name) / 'outside'
        target.write_text('private')
        for name in ('exports/link', '.cache/link', 'unrelated-link'):
            with self.subTest(name=name):
                link = self.run / name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(target)
                try:
                    for check in (bundle.artifact_records, bundle.verify_run):
                        with self.assertRaises(ForgeError) as caught:
                            check(self.run)
                        self.assertEqual(caught.exception.finding, 'unsafe_artifact_path')
                finally:
                    link.unlink()

    def test_stale_selected_hash_still_rejected(self):
        (self.run / 'native/model.blend').write_bytes(b'changed')
        with self.assertRaises(ForgeError) as caught:
            bundle.verify_run(self.run)
        self.assertEqual(caught.exception.finding, 'artifact_hash_mismatch')

    def test_failure_diagnostics_and_qa_are_preserved(self):
        write_json(self.run / 'failure.json', {'stage': 'validation', 'state': 'blocked'})
        (self.run / 'logs/validation.log').write_text('blocked diagnostic')
        write_json(self.run / 'qa/manual-review.json', {'status': 'blocked'})
        records = {item['path'] for item in self.reindex()['artifacts']}
        self.assertTrue({'failure.json', 'logs/validation.log', 'qa/manual-review.json'} <= records)
        bundle.create_bundle(self.run)
        with zipfile.ZipFile(self.run.with_suffix('.zip')) as archive:
            self.assertEqual(archive.read('logs/validation.log'), b'blocked diagnostic')
