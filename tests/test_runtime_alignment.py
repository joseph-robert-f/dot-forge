"""Fail-closed native discovery; opt-in real dot-native portability acceptance.

Unit tests stub native boundaries only. PRINTKIT_DOT_INTEGRATION=1 runs actual
applications, all three full workflows, and restored-source regeneration.
"""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from printkit.adapters import blender, freecad
from printkit.common import ForgeError, load_json, write_json
from printkit.doctor import doctor
from printkit import cli

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ('calibration-block', 'geometric-mascot', 'freecad-stepped-block')
BLENDER_NATIVE = {'version': '4.3.2', 'python_version': '3.13.5',
                  'renderer': 'BLENDER_WORKBENCH', 'boolean_solvers': ['FAST', 'EXACT'],
                  'stl_import': True, 'stl_export': True}
FREECAD_NATIVE = {'version': '1.0.0', 'occ_version': '7.8.1', 'python_version': '3.13.5'}


class NativeDiscoveryAlignmentTests(unittest.TestCase):
    def blender_report(self, native=None, version='4.3.2', system='Linux', machine='x86_64', error=None):
        native = copy.deepcopy(BLENDER_NATIVE if native is None else native)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            binary = Path(tmp) / 'blender'; binary.write_bytes(b'unit-native-placeholder')
            stack.enter_context(patch.object(blender, '_binary', return_value=binary))
            stack.enter_context(patch.object(blender.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'Blender ' + version + '\n', '')))
            stack.enter_context(patch.object(blender.platform, 'system', return_value=system))
            stack.enter_context(patch.object(blender.platform, 'machine', return_value=machine))
            stack.enter_context(patch.object(blender, 'verify_upstream', side_effect=blender.AdapterError('optional source absent')))
            def probe(mode, run, *args):
                self.assertEqual(mode, 'discover')
                if error:
                    raise error
                write_json(Path(run) / 'runtime.json', native)
                return {}
            runner = stack.enter_context(patch.object(blender, '_run', side_effect=probe))
            return blender.discover(), runner.call_count

    def freecad_report(self, native=None, system='Linux', machine='x86_64'):
        native = copy.deepcopy(FREECAD_NATIVE if native is None else native)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp); binary = root / 'python3'; binary.write_bytes(b'unit-python')
            binary.chmod(0o700)
            for name in freecad.NATIVE_LIBRARIES:
                (root / name).write_bytes(b'unit-library')
            stack.enter_context(patch.object(freecad, 'PYTHON', binary))
            stack.enter_context(patch.object(freecad, 'MODULE', root / 'FreeCAD.so'))
            stack.enter_context(patch.object(freecad.platform, 'system', return_value=system))
            stack.enter_context(patch.object(freecad.platform, 'machine', return_value=machine))
            def probe(mode, run):
                self.assertEqual(mode, 'discover')
                write_json(Path(run) / 'runtime.json', native)
                return {}
            stack.enter_context(patch.object(freecad, '_run', side_effect=probe))
            return freecad.discover()

    def test_matching_blender_is_unverified_not_accepted(self):
        report, count = self.blender_report()
        self.assertEqual(count, 1)
        self.assertEqual(report['status'], 'unverified')
        self.assertEqual(report['smoke_status'], 'not_run')
        self.assertEqual(report['python_version'], '3.13.5')
        for model in FAMILIES[:2]:
            self.assertEqual(report[model], 'unverified')
        self.assertEqual(report['lane-a-character'], 'incompatible')

    def test_blender_runtime_and_capability_mismatches_fail_closed(self):
        for key, value in (('version', '4.3.1'), ('python_version', '3.12.14'),
                           ('renderer', 'BLENDER_EEVEE_NEXT'), ('stl_import', False),
                           ('stl_export', False), ('stl_import', 1)):
            with self.subTest(key=key, value=value):
                native = copy.deepcopy(BLENDER_NATIVE); native[key] = value
                report, _ = self.blender_report(native)
                self.assertEqual(report['status'], 'incompatible')
                self.assertNotIn('available', [report.get(x) for x in FAMILIES])
                self.assertEqual(report['smoke_status'], 'not_run')

    def test_blender_missing_probe_fields_fail_closed(self):
        for key in BLENDER_NATIVE:
            with self.subTest(key=key):
                native = copy.deepcopy(BLENDER_NATIVE); del native[key]
                report, _ = self.blender_report(native)
                self.assertIn(report['status'], ('incompatible', 'unavailable'))
                self.assertNotEqual(report['calibration-block'], 'available')

    def test_blender_wrong_platform_or_cli_version_cannot_probe_to_acceptance(self):
        for changes in ({'system': 'Darwin'}, {'machine': 'aarch64'}, {'version': '4.5.12 LTS'}):
            with self.subTest(changes=changes):
                report, count = self.blender_report(**changes)
                self.assertEqual(report['status'], 'incompatible')
                self.assertEqual(count, 0)
                self.assertEqual(report['calibration-block'], 'incompatible')

    def test_blender_probe_failure_cannot_preserve_unverified_capability(self):
        report, _ = self.blender_report(error=ForgeError('native discovery failed'))
        self.assertEqual(report['status'], 'unavailable')
        for model in FAMILIES[:2]:
            self.assertEqual(report[model], 'unavailable')

    def test_matching_freecad_is_unverified_not_accepted(self):
        report = self.freecad_report()
        self.assertEqual(report['status'], 'unverified')
        self.assertEqual(report['freecad-stepped-block'], 'unverified')
        self.assertEqual(report['python_version'], '3.13.5')
        self.assertEqual(report['smoke_status'], 'not_run')

    def test_freecad_version_python_occ_and_platform_mismatches_fail_closed(self):
        for key, value in (('version', '1.0.1'), ('occ_version', '7.8.2'), ('python_version', '3.12.14')):
            with self.subTest(key=key):
                native = dict(FREECAD_NATIVE); native[key] = value
                report = self.freecad_report(native)
                self.assertEqual(report['status'], 'incompatible')
                self.assertEqual(report['freecad-stepped-block'], 'incompatible')
        for changes in ({'system': 'Darwin'}, {'machine': 'aarch64'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.freecad_report(**changes)['status'], 'incompatible')

    def test_missing_freecad_python_evidence_fails_closed(self):
        native = dict(FREECAD_NATIVE); del native['python_version']
        report = self.freecad_report(native)
        self.assertEqual(report['status'], 'unavailable')
        self.assertEqual(report['freecad-stepped-block'], 'unavailable')


class RuntimeReuseAlignmentTests(unittest.TestCase):
    def test_blender_generation_and_preview_record_native_python(self):
        capability = dict(BLENDER_NATIVE, binary_sha256='a' * 64,
                          **{'calibration-block': 'unverified'})
        request = load_json(ROOT / 'examples/calibration-part/request.json')
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / 'native').mkdir(); (run / 'previews').mkdir()
            write_json(run / 'native/reopen.json', {'status': 'pass'})
            write_json(run / 'native/generation.json', {'status': 'pass'})
            for view in blender.VIEWS:
                (run / 'previews' / (view + '.png')).write_bytes(b'x' * 101)
            with patch.object(blender, 'discover', return_value=capability), patch.object(blender, '_run', return_value={}):
                generated = blender.generate(request, run)
                rendered = blender.render(request, run)
            for result in (generated, rendered):
                self.assertEqual(result['provenance']['python_version'], '3.13.5')

    def test_blender_native_python_drift_or_lost_capabilities_block_stage_reuse(self):
        from printkit import orchestrator as flow
        from printkit.common import sha256
        for artifact, finding in (('generation.json', 'runtime_changed'),
                                  ('render.json', 'preview_runtime_changed')):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as tmp:
                run = Path(tmp)
                write_json(run / 'request.json', load_json(ROOT / 'examples/calibration-part/request.json'))
                write_json(run / 'journal.json', {'request_sha256': sha256(run / 'request.json'),
                           'implementation': flow.implementation_identity(), 'stages': {}})
                write_json(run / artifact, {'provenance': {'blender_version': '4.3.2',
                           'python_version': '3.13.5', 'binary_sha256': 'a' * 64}})
                original = {'version': '4.3.2', 'python_version': '3.13.5',
                            'binary_sha256': 'a' * 64, 'status': 'unverified'}
                with patch.object(blender, 'discover', return_value=original):
                    flow.verify_identity(run)
                for change in ({'python_version': '3.12.14'}, {'python_version': None},
                               {'status': 'unavailable'}, {'status': 'incompatible'}):
                    with self.subTest(change=change), patch.object(blender, 'discover', return_value=dict(original, **change)):
                        with self.assertRaises(ForgeError) as caught:
                            flow.verify_identity(run)
                        self.assertEqual(caught.exception.finding, finding)


class DoctorAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('printkit.doctor.platform.system', return_value='Linux'))
        self.stack.enter_context(patch('printkit.doctor.platform.machine', return_value='x86_64'))
        self.blender = {'status': 'unverified', 'smoke_status': 'not_run',
                        'calibration-block': 'unverified', 'geometric-mascot': 'unverified',
                        'lane-a-character': 'incompatible'}
        self.freecad = {'status': 'unverified', 'smoke_status': 'not_run',
                        'freecad-stepped-block': 'unverified'}
        self.stack.enter_context(patch.object(blender, 'discover', side_effect=lambda: copy.deepcopy(self.blender)))
        self.stack.enter_context(patch.object(freecad, 'discover', side_effect=lambda: copy.deepcopy(self.freecad)))
        self.stack.enter_context(patch('printkit.doctor.optional_inventory', return_value={
            'slicer': {'status': 'unavailable', 'required_for_default': False}}))
        self.run = self.stack.enter_context(patch('printkit.orchestrator.run_all', return_value={
            'geometry_state': 'geometry_validated', 'overall_state': 'needs_review'}))
        self.bundle = self.stack.enter_context(patch('printkit.bundle.create_bundle', return_value={}))
        self.verify = self.stack.enter_context(patch('printkit.bundle.verify_bundle', return_value={'status': 'pass'}))
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'all-smoke'

    def test_discovery_alone_never_accepts_default_profile(self):
        for advertised in ('unverified', 'available'):
            with self.subTest(advertised=advertised):
                for model in FAMILIES[:2]: self.blender[model] = advertised
                self.freecad[FAMILIES[2]] = advertised
                report = doctor()
                self.assertEqual(report['default_profile']['name'], 'dot-native')
                self.assertEqual(report['default_profile']['status'], 'unverified')
                self.assertEqual(report['default_profile']['smoke_status'], 'not_run')
        self.run.assert_not_called(); self.bundle.assert_not_called()

    def test_all_three_families_and_bundles_are_required(self):
        report = doctor(all_smoke=self.directory)
        self.assertEqual([call.args[0]['generator_id'] for call in self.run.call_args_list], list(FAMILIES))
        self.assertEqual(self.bundle.call_count, 3)
        self.assertEqual(self.verify.call_count, 3)
        self.assertEqual(report['default_profile']['status'], 'available')
        self.assertEqual(report['default_profile']['smoke_status'], 'pass')
        self.assertEqual(report['blender']['lane-a-character'], 'incompatible')
        self.assertEqual(report['optional_tools']['slicer']['status'], 'unavailable')
        self.assertEqual([r['bundle_integrity'] for r in report['smoke_results']], ['pass'] * 3)
        self.assertEqual([r['overall_state'] for r in report['smoke_results']], ['needs_review'] * 3)

    def test_single_smoke_does_not_certify_other_families_or_profile(self):
        report = doctor(smoke=self.directory)
        self.assertEqual(report['blender']['calibration-block'], 'available')
        self.assertEqual(report['blender']['geometric-mascot'], 'unverified')
        self.assertEqual(report['default_profile']['status'], 'unverified')
        self.assertEqual(report['default_profile']['smoke_status'], 'not_run')
        self.assertEqual(self.run.call_count, 1)

    def test_each_failed_family_survives_later_successes(self):
        for failed in FAMILIES:
            with self.subTest(failed=failed):
                def run(request, path):
                    return {'geometry_state': 'blocked' if request['generator_id'] == failed else 'geometry_validated',
                            'overall_state': 'needs_review'}
                self.run.side_effect = run
                report = doctor(all_smoke=self.directory / failed)
                self.assertEqual(report['default_profile']['status'], 'blocked')
                self.assertEqual(report['default_profile']['smoke_status'], 'fail')
                item = next(r for r in report['smoke_results'] if r['generator_id'] == failed)
                self.assertEqual(item['status'], 'fail')
                backend = 'freecad' if failed == FAMILIES[2] else 'blender'
                self.assertEqual(report[backend]['status'], 'incompatible')
                self.assertEqual(report[backend][failed], 'incompatible')
                self.assertEqual(len(report['smoke_results']), 3)

    def test_smoke_exception_and_bundle_failure_remain_failures(self):
        self.run.side_effect = [ForgeError('native crash'),
                               {'geometry_state': 'geometry_validated', 'overall_state': 'needs_review'},
                               {'geometry_state': 'geometry_validated', 'overall_state': 'needs_review'}]
        self.verify.side_effect = [{'status': 'fail'}, {'status': 'pass'}]
        report = doctor(all_smoke=self.directory)
        self.assertEqual([r['status'] for r in report['smoke_results']], ['fail', 'fail', 'pass'])
        self.assertEqual(report['default_profile']['status'], 'blocked')
        self.assertEqual(report['blender']['status'], 'incompatible')

    def test_missing_blender_blocks_freecad_full_workflow(self):
        self.blender.update(status='unavailable', **{'calibration-block': 'unavailable', 'geometric-mascot': 'unavailable'})
        report = doctor(backend='freecad')
        self.assertEqual(report['freecad']['status'], 'incompatible')
        self.assertEqual(report['default_profile']['status'], 'blocked')
        self.run.assert_not_called()

    def test_existing_all_smoke_directory_rejected_before_generation(self):
        self.directory.mkdir()
        with self.assertRaises((ForgeError, FileExistsError)):
            doctor(all_smoke=self.directory)
        self.run.assert_not_called()

    def test_cli_json_exit_codes_and_all_smoke_argument(self):
        for fail in (False, True):
            with self.subTest(fail=fail), redirect_stdout(io.StringIO()) as output:
                self.run.return_value = {'geometry_state': 'blocked' if fail else 'geometry_validated',
                                         'overall_state': 'needs_review'}
                code = cli.main(['doctor', '--json', '--all-smoke', str(self.directory / str(fail))])
                report = json.loads(output.getvalue())
                self.assertEqual(code, 4 if fail else 0)
                self.assertEqual(report['default_profile']['smoke_status'], 'fail' if fail else 'pass')

    def test_cli_rejects_conflicting_smoke_modes(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(['doctor', '--smoke', 'one', '--all-smoke', 'all'])
        self.assertEqual(raised.exception.code, 2)
        self.run.assert_not_called()


@unittest.skipUnless(os.environ.get('PRINTKIT_DOT_INTEGRATION') == '1',
                     'explicit three-family native dot integration')
class DotNativeIntegrationTests(unittest.TestCase):
    def test_real_all_smoke_and_retrieved_embedded_source_regeneration(self):
        from printkit.bundle import verify_bundle, verify_run
        with tempfile.TemporaryDirectory(prefix='printkit-dot-integration-') as tmp:
            root = Path(tmp)
            report = doctor(all_smoke=root / 'smoke')
            self.assertEqual(report['default_profile']['status'], 'available', report)
            self.assertEqual(report['default_profile']['smoke_status'], 'pass', report)
            self.assertEqual(report['blender']['version'], '4.3.2')
            self.assertEqual(report['blender']['python_version'], '3.13.5')
            self.assertEqual(report['blender']['renderer'], 'BLENDER_WORKBENCH')
            self.assertEqual(set(report['blender']['boolean_solvers']), {'FAST', 'EXACT'})
            self.assertIs(report['blender']['stl_import'], True)
            self.assertIs(report['blender']['stl_export'], True)
            self.assertEqual(report['freecad']['version'], '1.0.0')
            self.assertEqual(report['freecad']['occ_version'], '7.8.1')
            self.assertEqual(report['freecad']['python_version'], '3.13.5')
            self.assertEqual([r['generator_id'] for r in report['smoke_results']], list(FAMILIES))
            for item in report['smoke_results']:
                with self.subTest(model=item['generator_id']):
                    self.assertEqual(item['status'], 'pass')
                    self.assertEqual(item['overall_state'], 'needs_review')
                    model = item['generator_id']; run = root / 'smoke' / model
                    original = run.with_suffix('.zip')
                    copied = root / ('retrieved-' + model + '.zip')
                    shutil.copyfile(original, copied)
                    self.assertEqual(verify_bundle(original)['sha256'], verify_bundle(copied)['sha256'])
                    restored = root / ('restored-' + model)
                    # Only extract the test's own freshly verified trusted bundle.
                    with zipfile.ZipFile(copied) as archive:
                        archive.extractall(restored)
                    verify_run(restored)
                    source = restored / 'source'
                    env = os.environ.copy(); env['PYTHONPATH'] = str(source / 'src')
                    env['PYTHONDONTWRITEBYTECODE'] = '1'
                    def restored_cli(*args, accepted=(0,)):
                        result = subprocess.run([sys.executable, '-S', '-B', '-m', 'printkit', *args],
                                                cwd=source, env=env, capture_output=True, text=True, timeout=600)
                        self.assertIn(result.returncode, accepted, result.stdout + '\n' + result.stderr)
                        return json.loads(result.stdout)
                    restored_cli('verify-bundle', str(copied))
                    regenerated = root / ('regenerated-' + model)
                    validation = restored_cli('run', '--request', str(restored / 'request.json'),
                                              '--output', str(regenerated), accepted=(5,))
                    self.assertEqual(validation['geometry_state'], 'geometry_validated')
                    self.assertEqual(validation['overall_state'], 'needs_review')
                    for view in blender.VIEWS:
                        preview = regenerated / 'previews' / (view + '.png')
                        self.assertGreater(preview.stat().st_size, 100)
                    if model == 'freecad-stepped-block':
                        for path in ('native/model.FCStd', 'exports/model.step'):
                            self.assertGreater((regenerated / path).stat().st_size, 0)
                    else:
                        self.assertGreater((regenerated / 'native/model.blend').stat().st_size, 0)
                    self.assertEqual(load_json(regenerated / 'native/reopen.json')['status'], 'pass')
                    restored_cli('bundle', '--run', str(regenerated))
                    checked = restored_cli('verify-bundle', str(regenerated.with_suffix('.zip')))
                    self.assertEqual(checked['status'], 'pass')
                    self.assertEqual(checked['geometry_state'], 'geometry_validated')


if __name__ == '__main__':
    unittest.main()
