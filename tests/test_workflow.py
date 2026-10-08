import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from printkit.common import ForgeError, load_json, write_json
from printkit.contracts import check_request
from printkit import orchestrator as flow
from printkit.bundle import create_bundle, verify_bundle, verify_run
from test_validation import cube, stl

ROOT=Path(__file__).resolve().parents[1]

def fake_generate(request,run):
    run=Path(run)
    (run/'native/model.blend').write_bytes(b'test-native-placeholder')
    (run/'exports/model.stl').write_bytes(stl(cube((0,0,0),tuple(request['dimensions_mm']))))
    return {'status':'pass','metrics':{},'provenance':{'test_fixture':True}}

def fake_render(request,run):
    run=Path(run)
    for name in ('front','back','side','top','oblique'):
        (run/'previews'/f'{name}.png').write_bytes(b'test-preview-placeholder')
    return {'status':'pass','visual_completeness':'unknown'}

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.run=Path(self.temp.name)/'run'
        self.request=load_json(ROOT/'examples/calibration-part/request.json')
        self.patches=[patch('printkit.adapters.blender.generate',fake_generate),patch('printkit.adapters.blender.render',fake_render)]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def test_run_bundle_retrieval_and_resume(self):
        result=flow.run_all(self.request,self.run)
        self.assertEqual(result['geometry_state'],'geometry_validated')
        self.assertEqual(result['overall_state'],'needs_review')
        self.assertEqual(flow.resume(self.run)['geometry_state'],'geometry_validated')
        bundle=create_bundle(self.run)
        self.assertEqual(verify_bundle(self.run.with_suffix('.zip'))['status'],'pass')
        self.assertEqual(bundle['bundle'],'run.zip')

    def test_interrupted_after_generation_resumes(self):
        flow.generate(self.request,self.run)
        self.assertEqual(flow.resume(self.run)['geometry_state'],'geometry_validated')
        verify_run(self.run)

    def test_interrupted_before_generation_preserved(self):
        flow.begin(self.request,self.run)
        result=flow.resume(self.run)
        self.assertEqual(result['new_attempt'],'run-retry-1')
        self.assertFalse((self.run/'COMPLETE').exists())
        self.assertTrue((self.run.parent/'run-retry-1/COMPLETE').exists())

    def test_stale_export_blocks_resume(self):
        flow.generate(self.request,self.run)
        (self.run/'exports/model.stl').write_bytes(b'corrupt')
        with self.assertRaises(ForgeError):flow.resume(self.run)

    def test_request_change_blocks_resume(self):
        flow.generate(self.request,self.run)
        request=copy.deepcopy(self.request);request['tolerance_mm']=.1
        write_json(self.run/'request.json',request)
        with self.assertRaises(ForgeError):flow.resume(self.run)

    def test_source_change_blocks_resume(self):
        flow.generate(self.request,self.run)
        with patch.object(flow,'implementation_identity',return_value={'changed':True}):
            with self.assertRaises(ForgeError):flow.resume(self.run)

    def test_corrupt_artifact_blocks_bundle(self):
        flow.run_all(self.request,self.run)
        (self.run/'native/model.blend').write_bytes(b'changed')
        with self.assertRaises(ForgeError):create_bundle(self.run)

    def test_forged_manifest_marker_rejected(self):
        flow.run_all(self.request,self.run)
        report=load_json(self.run/'manifest.json');report['provenance']['geometry_state']='print-ready'
        write_json(self.run/'manifest.json',report)
        with self.assertRaises(ForgeError):verify_run(self.run)

    def test_unlisted_file_rejected(self):
        flow.run_all(self.request,self.run)
        (self.run/'exports/extra.txt').write_text('untracked')
        with self.assertRaises(ForgeError):verify_run(self.run)

    def test_validator_crash_never_passes(self):
        flow.generate(self.request,self.run)
        with patch('printkit.validation.validate_mesh',side_effect=RuntimeError('failure')):
            result=flow.validate(self.run)
        self.assertEqual(result['geometry_state'],'blocked')
        self.assertEqual(result['checks'][0]['code'],'validator_crash')

    def test_envelope_block_and_unknown_print_features(self):
        request=copy.deepcopy(self.request)
        request['printer_profile']={'process':'fdm','build_envelope_mm':[5,5,5],'minimum_wall_mm':1,'minimum_clearance_mm':.3}
        result=flow.run_all(request,self.run)
        self.assertEqual(result['geometry_state'],'geometry_validated')
        self.assertEqual(result['print_assessment']['state'],'blocked')
        for code in ('wall_thickness','clearance','slicer_gate','physical_gate'):
            self.assertEqual(next(x for x in result['print_assessment']['checks'] if x['code']==code)['status'],'unknown')

    def test_unknown_fields_and_executable_inputs_rejected(self):
        for key,value in [('code','print(1)'),('command','sh'),('source_url','https://example.org/a.py')]:
            bad=copy.deepcopy(self.request);bad[key]=value
            with self.assertRaises(ForgeError):check_request(bad)
        bad=copy.deepcopy(self.request);bad['parameters']['width_mm']='__import__("os")'
        with self.assertRaises(ForgeError):check_request(bad)

    def test_nonfinite_bool_and_bad_versions(self):
        for value in (float('nan'),float('inf'),True,0,101):
            bad=copy.deepcopy(self.request);bad['parameters']['width_mm']=value
            with self.assertRaises(ForgeError):check_request(bad)
        bad=copy.deepcopy(self.request);bad['schema_version']='2'
        with self.assertRaises(ForgeError):check_request(bad)

    def test_duplicates_in_json_rejected(self):
        p=Path(self.temp.name)/'duplicate.json';p.write_text('{"a":1,"a":2}')
        with self.assertRaises(ForgeError):load_json(p)

if __name__=='__main__':unittest.main()
