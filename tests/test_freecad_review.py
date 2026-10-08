"""Independent integration review: dispatch, evidence, and runtime binding."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from printkit import bundle, orchestrator as flow
from printkit.adapters import blender, freecad, registry
from printkit.adapters.base import AdapterError, RuntimeUnavailable
from printkit.common import ForgeError, sha256, write_json
from printkit.contracts import check_request
from printkit.validation import validate_mesh
from test_freecad_adapter import request
from test_generator_checks import stepped_mesh
from test_validation import stl


class FreeCADReviewTests(unittest.TestCase):
    def test_wrong_backend_or_generator_cannot_dispatch(self):
        for key, value in (('backend', 'blender'), ('backend', '__import__("os")'),
                           ('generator_id', 'calibration-block'),
                           ('export_formats', ['stl', 'blend']),
                           ('export_formats', ['stl', 'fcstd']),
                           ('generator_version', '2')):
            r = request(); r[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ForgeError):
                check_request(r)
        for backend in ('os', 'printkit.adapters.freecad', '../freecad', ''):
            with self.assertRaises(ForgeError):
                registry.adapter(backend)
        self.assertIs(registry.adapter('freecad'), freecad)

    def test_preview_rejects_unsupported_runtime_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(blender, 'discover', return_value={
                    'version': '99.0', 'calibration-block': 'incompatible'}), patch.object(blender, '_run') as execute:
                with self.assertRaises(RuntimeUnavailable):
                    blender.render(request(), tmp)
                execute.assert_not_called()

    def test_preview_records_its_own_runtime_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / 'previews').mkdir()
            for view in blender.VIEWS:
                (run / 'previews' / f'{view}.png').write_bytes(b'x' * 100)
            with patch.object(blender, 'discover', return_value={
                    'version': '4.3.2', 'binary_sha256': 'preview-binary-hash',
                    'calibration-block': 'unverified'}), patch.object(blender, '_run', return_value={}):
                result = blender.render(request(), run)
            self.assertEqual(result['provenance']['blender_version'], '4.3.2')
            self.assertEqual(result['provenance']['binary_sha256'], 'preview-binary-hash')

    def test_preview_runtime_drift_blocks_stage_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            write_json(run / 'request.json', request())
            write_json(run / 'journal.json', {'request_sha256': sha256(run / 'request.json'),
                       'implementation': flow.implementation_identity(), 'stages': {}})
            write_json(run / 'render.json', {'provenance': {
                       'blender_version': '4.3.2', 'binary_sha256': 'preview-binary-hash'}})
            original = {'version': '4.3.2', 'binary_sha256': 'preview-binary-hash'}
            with patch.object(blender, 'discover', return_value=original):
                flow.verify_identity(run)
            for field in ('version', 'binary_sha256'):
                current = dict(original); current[field] = 'changed'
                with self.subTest(field=field), patch.object(blender, 'discover', return_value=current):
                    with self.assertRaises(ForgeError):
                        flow.verify_identity(run)

    def test_native_required_artifacts_are_backend_specific(self):
        self.assertEqual(set(registry.native_artifacts(request())),
                         {'native/model.FCStd', 'exports/model.step', 'exports/model.stl'})

    def test_success_reports_cannot_hide_missing_or_empty_exports(self):
        capability = {freecad.GENERATOR: 'unverified'}
        artifacts = ('native/model.FCStd', 'exports/model.step', 'exports/model.stl')
        for missing in artifacts:
            for empty in (True, False):
                with self.subTest(missing=missing, empty=empty), tempfile.TemporaryDirectory() as tmp:
                    def fake_run(mode, run):
                        if mode == 'generate':
                            for name in artifacts:
                                if name != missing or empty:
                                    (run / name).write_bytes(b'' if name == missing else b'fixture')
                            write_json(run / 'native/generation.json', {'status': 'pass'})
                        else:
                            write_json(run / 'native/reopen.json', {'status': 'pass', 'fresh_process': True})
                        return {}
                    with patch.object(freecad, 'discover', return_value=capability), patch.object(freecad, '_run', fake_run):
                        with self.assertRaises(AdapterError):
                            freecad.generate(request(), tmp)

    def test_runtime_identity_uses_freecad_not_preview_renderer(self):
        fields = {'binary_sha256': 'a', 'native_module_sha256': 'b',
                  'native_library_sha256': {'Part.so': 'c'}, 'occ_version': '7.8.1',
                  'python_version': '3.13.5'}
        provenance = dict(fields, freecad_version='1.0.0')
        current = dict(fields, version='1.0.0')
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            write_json(run / 'request.json', request())
            write_json(run / 'journal.json', {'request_sha256': sha256(run / 'request.json'),
                       'implementation': flow.implementation_identity(), 'stages': {}})
            write_json(run / 'generation.json', {'provenance': provenance})
            with patch.object(freecad, 'discover', return_value=current), patch('printkit.adapters.blender.discover', side_effect=AssertionError('wrong backend')):
                flow.verify_identity(run)
            for field in ('version', *fields):
                changed = deepcopy(current); changed[field] = 'changed'
                with self.subTest(field=field), patch.object(freecad, 'discover', return_value=changed):
                    with self.assertRaises(ForgeError) as caught:
                        flow.verify_identity(run)
                    self.assertEqual(caught.exception.finding, 'runtime_changed')

    def test_reindexed_bundle_still_requires_all_native_exports(self):
        for missing in ('native/model.FCStd', 'exports/model.step', 'exports/model.stl'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp)
                write_json(run / 'request.json', request())
                write_json(run / 'validation.json', {'geometry_state': 'blocked'})
                write_json(run / 'metrics.json', {})
                for name in registry.native_artifacts(request()):
                    if name != missing:
                        path = run / name; path.parent.mkdir(exist_ok=True)
                        path.write_bytes(b'fixture')
                bundle.finalize(run, {'geometry_state': 'blocked'}, {})
                with self.assertRaises(ForgeError) as caught:
                    bundle.verify_run(run)
                self.assertEqual(caught.exception.finding, 'invalid_manifest')

    def test_early_mesh_failure_keeps_generator_gates_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.stl'; path.write_bytes(b'bad')
            report = validate_mesh(path, request())
        checks = {c['code']: c for c in report['checks']}
        self.assertEqual(report['geometry_state'], 'blocked')
        for code in ('generator_contract', 'generator_features', 'generator_volume'):
            self.assertEqual(checks[code]['status'], 'unknown')
            self.assertTrue(checks[code]['required'])

    def test_mesh_with_same_volume_but_displaced_hole_cannot_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'counterfeit.stl'
            path.write_bytes(stl(stepped_mesh(hole_y=.72)))
            report = validate_mesh(path, request())
        checks = {c['code']: c for c in report['checks']}
        self.assertEqual(checks['generator_volume']['status'], 'pass', report)
        self.assertEqual(checks['generator_features']['status'], 'fail', report)
        self.assertEqual(report['geometry_state'], 'blocked')

    def test_print_gates_stay_unknown(self):
        report = flow.print_assessment(request(), [20, 16, 12])
        self.assertEqual(report['state'], 'needs_review')
        self.assertEqual(report['physical_success'], 'unverified')
        self.assertTrue(all(c['status'] == 'unknown' for c in report['checks']))


if __name__ == '__main__':
    unittest.main()
