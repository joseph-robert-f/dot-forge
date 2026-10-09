"""Real FreeCAD runs of v2 plans. Opt-in: PRINTKIT_FREECAD_INTEGRATION=1.

These are the checks that the unit fixtures cannot make: that the fixed
interpreter builds each op, that the measurer reports what conformance
expects, and that a wrong plan is caught by the intent.
"""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from printkit.common import ForgeError, canonical_hash, load_json
from printkit.forge import build

EXAMPLES = Path(__file__).parents[1] / 'examples/v2'


def example(name):
    return load_json(EXAMPLES / name / 'intent.json'), load_json(EXAMPLES / name / 'plan.json')


def rebind(intent, plan):
    plan = copy.deepcopy(plan)
    plan['intent_sha256'] = canonical_hash(intent)
    return plan


def statuses(report):
    return {c['code']: c['status'] for c in report['conformance']['checks']}


def every_op():
    """One plan that uses all 16 ops, with two through-holes the intent can find."""
    intent = {
        'schema_version': 'intent.v1', 'ask': 'Interpreter coverage part; not a user design.', 'units': 'mm',
        'envelope': {'size_mm': [40, 40, 22], 'tolerance_mm': 0.01}, 'solid_count': 1,
        'features': [
            {'id': 'hole-left', 'kind': 'hole', 'axis': 'z', 'diameter_mm': 3, 'position_mm': [4, 26],
             'depth': 'through', 'tolerance_mm': 0.01},
            {'id': 'hole-right', 'kind': 'hole', 'axis': 'z', 'diameter_mm': 3, 'position_mm': [34, 26],
             'depth': 'through', 'tolerance_mm': 0.01},
            {'id': 'flat-bottom', 'kind': 'planar_face', 'normal': '-z', 'offset': 'min', 'min_area_mm2': 1000,
             'tolerance_mm': 0.01}],
        'unknowns': [], 'confirmation': {'status': 'confirmed', 'by': 'user'}}
    steps = [
        {'id': 'base', 'op': 'box', 'size_mm': [40, 40, 10]},
        {'id': 'beveled', 'op': 'chamfer', 'target': 'base', 'size_mm': 1, 'edges': 'parallel_z'},
        {'id': 'ball', 'op': 'sphere', 'radius_mm': 30, 'at_mm': [20, 20, 5]},
        {'id': 'trimmed', 'op': 'intersect', 'of': ['beveled', 'ball']},
        {'id': 'boss', 'op': 'cylinder', 'radius_mm': 5, 'height_mm': 6.5, 'at_mm': [20, 20, 9.5]},
        {'id': 'taper', 'op': 'cone', 'radius1_mm': 4, 'radius2_mm': 2, 'height_mm': 4.5, 'at_mm': [20, 20, 15.5]},
        {'id': 'knob', 'op': 'sphere', 'radius_mm': 2, 'at_mm': [20, 20, 20]},
        {'id': 'rib', 'op': 'extrude', 'plane': 'xz', 'points': [[2, 9.5], [12, 9.5], [2, 16]],
         'height_mm': 2, 'offset_mm': 9},
        {'id': 'rib-mirror', 'op': 'mirror', 'target': 'rib', 'plane': 'yz', 'through_mm': 20},
        {'id': 'post', 'op': 'revolve', 'points': [[0, 0], [2, 0], [2, 3], [0, 3]], 'at_mm': [8, 8, 9.5]},
        {'id': 'posts', 'op': 'polar_pattern', 'target': 'post', 'axis': 'z', 'count': 4, 'about_mm': [20, 20, 0]},
        {'id': 'block', 'op': 'box', 'size_mm': [4, 4, 4]},
        {'id': 'block-moved', 'op': 'translate', 'target': 'block', 'by_mm': [30, 4, 9]},
        {'id': 'block-turned', 'op': 'rotate', 'target': 'block-moved', 'axis': 'z', 'angle_deg': 45,
         'about_mm': [32, 6, 0]},
        {'id': 'tab', 'op': 'box', 'size_mm': [6, 6, 3], 'at_mm': [17, 2, 9.5]},
        {'id': 'tab-round', 'op': 'fillet', 'target': 'tab', 'radius_mm': 1, 'edges': 'parallel_z'},
        {'id': 'body', 'op': 'union', 'of': ['trimmed', 'boss', 'taper', 'knob', 'rib', 'rib-mirror', 'posts',
                                             'block-turned', 'tab-round']},
        {'id': 'drill', 'op': 'cylinder', 'radius_mm': 1.5, 'height_mm': 12, 'at_mm': [4, 26, -1]},
        {'id': 'drills', 'op': 'linear_pattern', 'target': 'drill', 'step_mm': [30, 0, 0], 'count': 2},
        {'id': 'part', 'op': 'cut', 'from': 'body', 'tools': ['drills']},
    ]
    plan = {'schema_version': 'plan.v1', 'units': 'mm', 'intent_sha256': canonical_hash(intent),
            'steps': steps, 'result': 'part'}
    return intent, plan


@unittest.skipUnless(os.environ.get('PRINTKIT_FREECAD_INTEGRATION') == '1', 'explicit native FreeCAD integration')
class FreeCADPlanNativeTests(unittest.TestCase):
    def build(self, intent, plan):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return build(intent, plan, Path(tmp.name) / 'run'), Path(tmp.name) / 'run'

    def assert_conforms(self, report):
        self.assertEqual(report['intent_state'], 'conforms', statuses(report))
        self.assertEqual(report['geometry_state'], 'geometry_validated', report['mesh_validation']['checks'])
        self.assertEqual(report['overall_state'], 'needs_review')
        self.assertEqual(report['print_state'], 'needs_review')

    def test_examples_conform(self):
        for name in ('stepped-block', 'mounting-plate', 'knob'):
            with self.subTest(name=name):
                intent, plan = example(name)
                report, run = self.build(intent, plan)
                self.assert_conforms(report)
                reopened = load_json(run / 'native/reopen.json')
                self.assertTrue(reopened['fresh_process'])
                self.assertEqual(len(report['generation']['provenance']['script_sha256']), 64)

    def test_stepped_block_matches_v1_measurements(self):
        intent, plan = example('stepped-block')
        report, run = self.build(intent, plan)
        m = load_json(run / 'native/measure.json')
        self.assertAlmostEqual(m['volume_mm3'], .75 * 30 * 24 * 18 - 3.141592653589793 * 3.75 ** 2 * 9, places=4)
        holes = [c for c in m['cylinders'] if c['kind'] == 'void']
        self.assertEqual(len(holes), 1)
        self.assertEqual(holes[0]['ends_open'], [True, True])
        for actual, expected in zip(holes[0]['span_mm'], (0, 9)):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_plate_corners_are_not_holes(self):
        intent, plan = example('mounting-plate')
        report, run = self.build(intent, plan)
        m = load_json(run / 'native/measure.json')
        bosses = [c for c in m['cylinders'] if c['kind'] == 'boss']
        self.assertEqual(len(bosses), 4)
        self.assertTrue(all(abs(c['angle_rad'] - 3.141592653589793 / 2) < 1e-6 for c in bosses))
        self.assertEqual(statuses(report)['unrequested_holes'], 'pass')
        self.assertIn('feature:rounded-corners', report['person_checks'])

    def test_moved_hole_is_caught(self):
        intent, plan = example('stepped-block')
        plan['steps'][3]['at_mm'] = [8.5, 12, -1]
        report, _ = self.build(intent, plan)
        self.assertEqual(report['intent_state'], 'blocked')
        self.assertEqual(report['overall_state'], 'blocked')
        self.assertEqual(statuses(report)['feature:ledge-hole'], 'fail')
        self.assertEqual(statuses(report)['unrequested_holes'], 'needs_review')

    def test_blind_hole_is_measured_as_blind(self):
        intent, plan = example('stepped-block')
        intent['features'][0]['depth'] = {'depth_mm': 5, 'open_end': 'max'}
        intent['volume_mm3'] = {'min': 9300, 'max': 9600}
        intent['features'] = [f for f in intent['features'] if f['id'] != 'flat-bottom']
        plan['steps'][3].update(at_mm=[7.5, 12, 4], height_mm=6)
        report, _ = self.build(intent, rebind(intent, plan))
        self.assert_conforms(report)
        intent['features'][0]['depth'] = 'through'
        report, _ = self.build(intent, rebind(intent, plan))
        self.assertEqual(statuses(report)['feature:ledge-hole'], 'fail')

    def test_every_op_builds_and_measures(self):
        intent, plan = every_op()
        report, _ = self.build(intent, plan)
        self.assert_conforms(report)

    def test_invalid_operation_fails_closed_and_keeps_run(self):
        intent, plan = example('mounting-plate')
        plan['steps'][1]['radius_mm'] = 30  # Larger than the plate can take.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ForgeError) as caught:
                build(intent, plan, Path(tmp) / 'run')
            self.assertEqual(caught.exception.finding, 'plan_step_failed')
            self.assertEqual(caught.exception.code, 4)
            self.assertIn("'plate'", str(caught.exception))
            self.assertEqual(load_json(Path(tmp) / 'run/native/plan-failure.json')['op'], 'fillet')
            self.assertEqual(load_json(Path(tmp) / 'run/report.json')['overall_state'], 'blocked')
            self.assertTrue((Path(tmp) / 'run/logs/freecad-plan-generate.log').is_file())


if __name__ == '__main__':
    unittest.main()
