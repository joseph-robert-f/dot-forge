"""Regression cases from independent workflow/security review; no engines needed."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from printkit import orchestrator
from printkit.common import ForgeError, load_json, sha256, write_json
from printkit.validation import validate_mesh
from test_validation import cube, stl


class SecurityReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / 'attempt'
        self.request = load_json(Path(__file__).resolve().parents[1] / 'examples/calibration-part/request.json')
        self.request['dimensions_mm'] = [20, 20, 20]
        self.request['parameters'] = dict(width_mm=20, depth_mm=20, height_mm=20)
        with patch.object(orchestrator, '_snapshot_source'):
            orchestrator.begin(self.request, self.run)
        (self.run / 'native/model.blend').write_bytes(b'trusted native fixture')
        (self.run / 'exports/model.stl').write_bytes(stl(cube((0,0,0), (20,20,20))))
        write_json(self.run / 'generation.json', {'status':'pass'})
        write_json(self.run / 'metrics.json', {'schema_version':'1'})
        orchestrator.stage_record(self.run, 'generation',
            ['native/model.blend', 'exports/model.stl', 'generation.json'],
            {'request_sha256':sha256(self.run / 'request.json')})

    def test_validate_rejects_changed_request(self):
        changed = copy.deepcopy(self.request)
        changed['generator_id'] = 'geometric-mascot'
        write_json(self.run / 'request.json', changed)
        with self.assertRaises(ForgeError):
            orchestrator.validate(self.run)

    def test_validate_rejects_changed_implementation(self):
        with patch.object(orchestrator, 'implementation_identity', return_value={'version':'changed'}):
            with self.assertRaises(ForgeError):
                orchestrator.validate(self.run)

    def test_stage_cannot_complete_without_artifact_records(self):
        journal = load_json(self.run / 'journal.json')
        journal['stages']['generation']['artifacts'] = {}
        write_json(self.run / 'journal.json', journal)
        with self.assertRaises(ForgeError):
            orchestrator.validate(self.run)

    def test_validated_bytes_cannot_change_during_validation(self):
        def replacement(path, request):
            report = validate_mesh(path, request)
            self.assertEqual(report['geometry_state'], 'geometry_validated')
            Path(path).write_bytes(b'this replacement is not an STL')
            return report
        with patch('printkit.validation.validate_mesh', side_effect=replacement):
            try:
                report = orchestrator.validate(self.run)
            except ForgeError:
                return
        self.assertEqual(report['geometry_state'], 'blocked',
                         'The report certified bytes the validator never inspected')

    def test_build_envelope_failure_blocks_overall_state(self):
        # Start a request with the same dimensioned geometry but an undersized printer.
        self.request['printer_profile'] = {'process':'fdm', 'build_envelope_mm':[10,10,10],
            'minimum_wall_mm':1, 'minimum_clearance_mm':0.2}
        write_json(self.run / 'request.json', self.request)
        journal = load_json(self.run / 'journal.json')
        journal['request_sha256'] = sha256(self.run / 'request.json')
        journal['stages']['generation']['details']['request_sha256'] = journal['request_sha256']
        write_json(self.run / 'journal.json', journal)
        report = orchestrator.validate(self.run)
        self.assertEqual(report['print_assessment']['state'], 'blocked')
        self.assertEqual(report['overall_state'], 'blocked')

class UpstreamReviewTests(unittest.TestCase):
    def test_unpinned_root_package_rejected(self):
        from printkit.adapters import blender
        from printkit.adapters.base import AdapterError
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'upstream'
            target.mkdir()
            (target / "blender").mkdir()
            (target / "blender/__init__.py").write_text("")
            pin = {"commit": "a"*40, "repository": "https://example.invalid", "license": "GPL-3.0-or-later",
                   "files": {"blender/__init__.py": hashlib.sha256(b"").hexdigest()}}
            (target / 'json').mkdir()
            # Harmless data-only fixture: this file must not become executable input.
            (target / 'json/__init__.py').write_text('# unreviewed shadow package\n')
            with patch.object(blender, "lock", return_value=pin):
                with self.assertRaises(AdapterError):
                    blender.verify_upstream(target)

class ContractReviewTests(unittest.TestCase):
    def test_large_integer_rejected_as_invalid_request(self):
        from printkit.contracts import check_request
        request = load_json(Path(__file__).resolve().parents[1] / 'examples/calibration-part/request.json')
        request['dimensions_mm'][0] = 10 ** 400
        with self.assertRaises(ForgeError):
            check_request(request)

class BundleReviewTests(unittest.TestCase):
    setUp = SecurityReviewTests.setUp
    def test_verify_run_rejects_extra_symlink_directory(self):
        from printkit.bundle import finalize, verify_run
        report = orchestrator.validate(self.run)
        finalize(self.run, {'geometry_state':report['geometry_state']}, {})
        outside = Path(self.temp.name) / 'unrelated'
        outside.mkdir()
        (outside / 'secret.txt').write_text('not an authorized artifact')
        (self.run / 'extra').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ForgeError):
            verify_run(self.run)

class LogReviewTests(unittest.TestCase):
    def test_log_sanitization_never_writes_through_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            run = base / 'run'
            (run / 'logs').mkdir(parents=True)
            outside = base / 'outside.txt'
            contents = f'This unrelated file mentions {run.resolve()}.'
            outside.write_text(contents)
            (run / 'logs/link.log').symlink_to(outside)
            try:
                orchestrator.sanitize_logs(run)
            except ForgeError:
                pass
            self.assertEqual(outside.read_text(), contents)
