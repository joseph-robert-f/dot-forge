"""Adapter contracts; optional actual Blender acceptance is explicit."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from printkit.adapters import blender
from printkit.adapters.base import AdapterError, RuntimeUnavailable


class AdapterTests(unittest.TestCase):
    def test_lock_has_commit_hashes_license(self):
        pin=blender.lock()
        self.assertEqual(len(pin['commit']),40)
        self.assertEqual(pin['license'],'GPL-3.0-or-later')
        self.assertIn('builder_cli/commands.py',pin['files'])
        self.assertTrue(all(len(h)==64 for h in pin['files'].values()))

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AdapterError):blender.verify_upstream(tmp)

    def test_no_silent_lane_a_substitution(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(blender,'discover',return_value={'lane-a-character':'incompatible','lane_a_reason':'requires 4.5.12'}):
                with self.assertRaisesRegex(RuntimeUnavailable,'4.5.12'):
                    blender.generate({'generator_id':'lane-a-character'},tmp)
            self.assertFalse((Path(tmp)/'native/model.blend').exists())

    def test_missing_runtime_is_unavailable(self):
        report=blender.discover('/nonexistent/blender')
        self.assertEqual(report['status'],'unavailable')
        self.assertEqual(report['smoke_status'],'not_run')

    def test_request_file_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);request={'generator_id':'calibration-block','parameters':{}}
            original=json.dumps(request,separators=(',',':'))+'\n'
            (run/'request.json').write_text(original)
            (run/'native').mkdir();(run/'native/reopen.json').write_text('{"status":"pass"}');(run/'native/generation.json').write_text('{}')
            cap={'calibration-block':'unverified','version':'4.3.2','binary_sha256':'a'*64}
            with patch.object(blender,'discover',return_value=cap), patch.object(blender,'_run',return_value={}):
                blender.generate(request,run)
            self.assertEqual((run/'request.json').read_text(),original)

    def test_source_tamper_and_unpinned_module_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'blender').mkdir()
            module=root/'blender/__init__.py';module.write_text('')
            pin={'commit':'a'*40,'repository':'https://example.invalid','license':'GPL-3.0-or-later',
                 'files':{'blender/__init__.py':hashlib.sha256(b'').hexdigest()}}
            with patch.object(blender,'lock',return_value=pin):
                self.assertEqual(blender.verify_upstream(root)['status'],'pass')
                (root/'blender/evil.py').write_text('')
                with self.assertRaises(AdapterError):blender.verify_upstream(root)
                (root/'blender/evil.py').unlink();module.write_text('# tampered')
                with self.assertRaises(AdapterError):blender.verify_upstream(root)

    def test_upstream_rejects_root_package_native_extension_and_symlink(self):
        import hashlib
        for contaminant in ('json/__init__.py','json.so','other/malicious.py','stray.dat'):
            with self.subTest(contaminant=contaminant), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'blender').mkdir();(root/'blender/__init__.py').write_text('')
                pin={'commit':'a'*40,'repository':'https://example.invalid','license':'GPL-3.0-or-later',
                     'files':{'blender/__init__.py':hashlib.sha256(b'').hexdigest()}}
                extra=root/contaminant;extra.parent.mkdir(parents=True,exist_ok=True);extra.write_text('')
                with patch.object(blender,'lock',return_value=pin):
                    with self.assertRaises(AdapterError):blender.verify_upstream(root)
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp);actual=parent/'actual';actual.mkdir();(actual/'__init__.py').write_text('')
            root=parent/'source';root.mkdir();(root/'blender').symlink_to(actual,target_is_directory=True)
            pin={'files':{'blender/__init__.py':hashlib.sha256(b'').hexdigest()}}
            with patch.object(blender,'lock',return_value=pin):
                with self.assertRaises(AdapterError):blender.verify_upstream(root)
            alias=parent/'alias';alias.symlink_to(root,target_is_directory=True)
            with self.assertRaises(AdapterError):blender.verify_upstream(alias)

    def test_all_review_views_declared(self):
        self.assertEqual(set(blender.VIEWS),{'front','side','back','top','oblique'})

    @unittest.skipUnless(os.environ.get('PRINTKIT_INTEGRATION')=='1','explicit native integration test')
    def test_native_golden_and_mascot(self):
        for model in ('calibration-block','geometric-mascot'):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                request={'generator_id':model,'parameters':{'width_mm':20,'depth_mm':12,'height_mm':30}}
                result=blender.generate(request,tmp)
                self.assertEqual(result['native_checks']['status'],'pass')
                for actual,expected in zip(result['native_checks']['stl_dimensions_mm'],[20,12,30]):
                    self.assertAlmostEqual(actual,expected,places=4)
                preview=blender.render(request,tmp)
                self.assertEqual(len(preview['views']),5)
                for view in preview['views']:
                    self.assertTrue((Path(tmp)/view).read_bytes().startswith(b'\x89PNG'))


if __name__=='__main__':unittest.main()
