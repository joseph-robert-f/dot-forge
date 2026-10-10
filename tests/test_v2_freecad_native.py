"""Real FreeCAD runs of v2 plans. Opt-in: PRINTKIT_FREECAD_INTEGRATION=1.

These are the checks that the unit fixtures cannot make: that the fixed
interpreter builds each op, that the measurer reports what conformance
expects, and that a wrong plan is caught by the intent.
"""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from printkit.cli import main
from printkit.common import ForgeError, canonical_hash, load_json
from printkit.forge import build
from printkit.measure import measure_part
from printkit.conformance import conform
from printkit.adapters import freecad, freecad_plan

EXAMPLES = Path(__file__).parents[1] / 'examples/v2'
FIELD = Path(__file__).parents[1] / 'evals/v2/cases'


def example(name):
    return load_json(EXAMPLES / name / 'intent.json'), load_json(EXAMPLES / name / 'plan.json')


def field_case(name, attempt='001'):
    intent = 'intent.json' if attempt == '001' else f'intent-{attempt}.json'
    return load_json(FIELD / name / intent), load_json(FIELD / name / f'plan-{attempt}.json')


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

    def test_field_cases_measure_bores_and_curved_trims(self):
        """Regressions found by the field test in evals/v2."""
        # An outer wall around a bore is a boss, never an unrequested hole.
        report, _ = self.build(*field_case('tube'))
        self.assert_conforms(report)
        self.assertEqual(statuses(report)['unrequested_holes'], 'pass')
        # A side hole trimmed by two curved faces survives the STEP round trip.
        # It opens into the bore, not outside, so it is neither through nor blind.
        report, run = self.build(*field_case('shaft-collar'))
        self.assertTrue(load_json(run / 'native/reopen.json')['fresh_process'])
        self.assertEqual(statuses(report)['feature:bore'], 'pass')
        self.assertEqual(statuses(report)['feature:set-screw'], 'unknown')
        self.assertEqual(statuses(report)['unrequested_holes'], 'pass')

    def test_hole_end_kinds_build_and_catch_mistakes(self):
        # Field-test repairs: each hole names what its ends open into.
        for name in ('counterbored-spacer', 'shaft-collar'):
            with self.subTest(name=name):
                report, _ = self.build(*field_case(name, '002'))
                self.assert_conforms(report)
        report, _ = self.build(*field_case('hollow-ball', '004'))
        self.assert_conforms(report)
        # A set-screw hole that stops short of the bore ends in a floor, not a void.
        intent, _ = field_case('shaft-collar', '002')
        short = rebind(intent, load_json(FIELD / 'shaft-collar/mutants/short-tap.json'))
        report, _ = self.build(intent, short)
        self.assertEqual(statuses(report)['feature:set-screw'], 'fail')
        # A counterbore 1 mm too shallow is still a shoulder, so the depth catches it.
        intent, _ = field_case('counterbored-spacer', '002')
        shallow = rebind(intent, load_json(FIELD / 'counterbored-spacer/mutants/counterbore-4-deep.json'))
        report, _ = self.build(intent, shallow)
        self.assertEqual(statuses(report)['feature:counterbore'], 'fail')

    def test_face_area_upper_bound_catches_long_slot(self):
        intent, plan = field_case('slotted-plate', '002')
        report, _ = self.build(intent, plan)
        self.assert_conforms(report)
        long_slot = rebind(intent, load_json(FIELD / 'slotted-plate/mutants/long-slot.json'))
        report, _ = self.build(intent, long_slot)
        self.assertEqual(statuses(report)['feature:slot-wall-low'], 'fail')
        self.assertEqual(statuses(report)['feature:slot-wall-high'], 'fail')

    def test_partial_holes_measure_channels_slots_and_d_bores(self):
        for name, attempt in (('cable-clip', '002'), ('slotted-plate', '003'), ('spur-gear', '003')):
            with self.subTest(name=name):
                report, _ = self.build(*field_case(name, attempt))
                self.assert_conforms(report)
        # No mouth: the channel is a full hole, so it is not the requested partial hole.
        intent, _ = field_case('cable-clip', '002')
        report, _ = self.build(intent, rebind(intent, load_json(FIELD / 'cable-clip/mutants/no-mouth.json')))
        self.assertEqual(statuses(report)['feature:cable-channel'], 'fail')
        self.assertEqual(statuses(report)['unrequested_holes'], 'needs_review')
        intent, _ = field_case('spur-gear', '003')
        report, _ = self.build(intent, rebind(intent, load_json(FIELD / 'spur-gear/mutants/round-bore.json')))
        self.assertEqual(statuses(report)['feature:bore'], 'fail')

    def test_preview_then_approved_build(self):
        from printkit.preview import preview
        intent, plan = example('mounting-plate')
        draft = dict(intent, confirmation={'status': 'draft'})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        shown = Path(tmp.name) / 'preview'
        record = preview(draft, rebind(draft, plan), shown)
        self.assertEqual(record['state'], 'conforms')
        self.assertEqual(record['delivery'], 'not_for_delivery')
        lines = load_json(shown / 'views/lines.json')['views']
        self.assertEqual(set(lines), {'front', 'right', 'back', 'top', 'iso'})
        # The top view looks down z: its outline spans the plate, 60 x 40.
        top = [p for line in lines['top']['visible'] for p in line]
        self.assertAlmostEqual(max(p[0] for p in top) - min(p[0] for p in top), 60, places=3)
        self.assertAlmostEqual(max(p[1] for p in top) - min(p[1] for p in top), 40, places=3)
        self.assertIn('screw-hole-1', (shown / 'views/sheet.svg').read_text())
        self.assertIn('I will measure', (shown / 'preview.md').read_text())
        # The person approves; the confirmed intent and rebound plan build with that preview.
        report = build(intent, plan, Path(tmp.name) / 'final', approved_preview=shown)
        self.assert_conforms(report)
        self.assertTrue(report['approved_preview']['matches'])
        self.assertNotIn('five_view_review', report['person_checks'])
        changed = copy.deepcopy(plan)
        changed['steps'][1]['radius_mm'] = 3
        with self.assertRaises(ForgeError) as caught:
            build(intent, changed, Path(tmp.name) / 'other', approved_preview=shown)
        self.assertEqual(caught.exception.finding, 'preview_mismatch')

    def test_end_kinds_need_full_proof(self):
        # A void end must be clear across the whole aperture; a shoulder ring must be completely filled.
        script = '''
import importlib.util
import sys
spec = importlib.util.spec_from_file_location('scene', sys.argv[1])
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)
A, P = scene.App, scene.Part
def ends(shape, radius):
    low = [shape.BoundBox.XMin, shape.BoundBox.YMin, shape.BoundBox.ZMin]
    return next(c['ends'] for c in scene.cylinders(shape, low) if abs(c['radius_mm'] - radius) < 1e-6)
block = P.makeBox(20, 20, 10)
# A hole that opens into a closed pocket inside the part.
pocket = block.cut([P.makeCylinder(2, 6, A.Vector(10, 10, -1)), P.makeBox(12, 12, 3, A.Vector(4, 4, 5))])
assert ends(pocket, 2) == ['outside', 'void'], ends(pocket, 2)
# A thin rib just past the end covers part of the aperture: not proven void.
ribbed = pocket.fuse(P.makeBox(12, 1, 0.2, A.Vector(4, 10.5, 5.1))).removeSplitter()
assert ends(ribbed, 2) == ['outside', None], ends(ribbed, 2)
# A counterbore over a clearance hole has a shoulder.
cbore = block.cut([P.makeCylinder(2, 12, A.Vector(10, 10, -1)), P.makeCylinder(4, 6, A.Vector(10, 10, 5))])
assert ends(cbore, 4) == ['shoulder', 'outside'], ends(cbore, 4)
# A notch in the shoulder ring: not completely filled, so not a shoulder.
notched = cbore.cut(P.makeBox(1.5, 1, 1, A.Vector(12.5, 9.5, 4.5))).removeSplitter()
assert ends(notched, 4) == [None, 'outside'], ends(notched, 4)
'''
        with tempfile.TemporaryDirectory() as tmp:
            freecad.run_process([freecad.PYTHON, '-I', '-B', '-c', script, freecad_plan.SCRIPT],
                                tmp, Path(tmp) / 'end-kind-fixtures.log', timeout=60)

    def test_cold_measure_of_a_built_step_matches_the_build(self):
        """`measure` on a build's own STEP gives the build's intent checks, check by check."""
        for name, attempt in (('l-bracket', '001'), ('shaft-collar', '002'), ('cable-clip', '002'),
                              ('hollow-ball', '004'), ('slotted-plate', '003'), ('counterbored-spacer', '001')):
            with self.subTest(case=f'{name}-{attempt}'):
                intent, plan = field_case(name, attempt)
                built, run = self.build(intent, plan)
                measured = measure_part(run / 'exports/model.step', run.parent / 'cold', intent=intent)
                self.assertEqual(statuses(measured), statuses(built))
                self.assertEqual(measured['intent_state'], built['intent_state'])
                self.assertEqual(measured['geometry_state'], 'geometry_validated')
                self.assertEqual(load_json(run.parent / 'cold/native/measure.json')['face_count'],
                                 load_json(run / 'native/measure.json')['face_count'])

    def test_measure_takes_a_step_made_outside_the_plan_interpreter(self):
        """A plate made directly in FreeCAD: moved off the origin, with a split bottom face."""
        script = '''
import sys
sys.path.insert(0, '/usr/lib/freecad/lib')
import FreeCAD as A, Part as P
at = A.Vector(100, -50, 20)
# Two halves fused without refine: the top and bottom are each two faces.
plate = P.makeBox(30, 40, 5, at).fuse(P.makeBox(30, 40, 5, at + A.Vector(30, 0, 0)))
holes = [P.makeCylinder(2, 7, at + A.Vector(x, y, -1)) for x, y in ((6, 6), (54, 6), (6, 34), (54, 34))]
plate = plate.cut(holes)
plate.exportStep(sys.argv[1] + '/plate.step')
turned = plate.copy()
turned.rotate(at, A.Vector(0, 0, 1), 90)
turned.exportStep(sys.argv[1] + '/plate-turned.step')
'''
        intent, _ = example('mounting-plate')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            freecad.run_process([freecad.PYTHON, '-I', '-B', '-c', script, tmp], tmp, tmp / 'make.log', timeout=60)
            report = measure_part(tmp / 'plate.step', tmp / 'run', intent=intent)
            self.assertEqual(report['intent_state'], 'conforms', statuses(report))
            self.assertEqual(report['geometry_state'], 'geometry_validated')
            self.assertEqual(report['measurement']['holes'], 4)
            self.assertGreater(report['measurement']['faces']['plane'], 6)
            # The part is measured as found: turned 90 degrees, it no longer fits the intent.
            turned = measure_part(tmp / 'plate-turned.step', tmp / 'turned', intent=intent)
            self.assertEqual(turned['intent_state'], 'blocked')
            self.assertEqual(statuses(turned)['envelope'], 'fail')
            # A file that is not STEP inside is refused by FreeCAD and keeps a blocked report.
            (tmp / 'broken.step').write_text('ISO-10303-21;\nnot a model\n')
            with self.assertRaises(ForgeError):
                measure_part(tmp / 'broken.step', tmp / 'broken')
            self.assertEqual(load_json(tmp / 'broken/report.json')['overall_state'], 'blocked')

    def test_measure_sphere_over_mesh_budget_without_intent_blocks(self):
        """A fresh curved STEP cannot pass when its independent mesh check cannot run."""
        script = '''
import sys
sys.path.insert(0, '/usr/lib/freecad/lib')
import Part
Part.makeSphere(1000).exportStep(sys.argv[1] + '/sphere.step')
'''
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            freecad.run_process([freecad.PYTHON, '-I', '-B', '-c', script, tmp], tmp,
                                tmp / 'make.log', timeout=60)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(['measure', str(tmp / 'sphere.step'), '--output', str(tmp / 'run')])
            self.assertEqual(code, 4)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report['geometry_state'], 'unknown')
            self.assertEqual(report['mesh_validation']['status'], 'not_run')
            self.assertEqual(report['intent_state'], 'not_checked')
            self.assertEqual(report['overall_state'], 'blocked')
            self.assertEqual(load_json(tmp / 'run/report.json'), report)
            self.assertEqual(load_json(tmp / 'run/native/source.json')['mesh']['status'], 'over_budget')

    def test_sealed_cavity_blocks(self):
        report, run = self.build(*field_case('hollow-ball'))
        self.assertEqual(report['intent_state'], 'blocked')
        self.assertEqual(statuses(report)['native_solid'], 'fail')
        self.assertEqual(load_json(run / 'native/measure.json')['shell_count'], 2)

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

    def test_counterbore_requires_full_width_clearance_on_every_axis(self):
        for axis in 'xyz':
            for open_end in ('min', 'max'):
                with self.subTest(axis=axis, open_end=open_end):
                    index = 'xyz'.index(axis)
                    size = [20, 20, 20]
                    size[index] = 10
                    through_at, recess_at = [10, 10, 10], [10, 10, 10]
                    through_at[index] = -1
                    recess_at[index] = 5 if open_end == 'max' else -1
                    intent = {
                        'schema_version': 'intent.v1', 'ask': 'Counterbore regression fixture.', 'units': 'mm',
                        'envelope': {'size_mm': size, 'tolerance_mm': 0.01}, 'solid_count': 1,
                        'features': [{'id': 'hole', 'kind': 'hole', 'axis': axis, 'diameter_mm': 8,
                                      'position_mm': [10, 10], 'depth': 'through', 'tolerance_mm': 0.05}],
                        'unknowns': [], 'confirmation': {'status': 'confirmed', 'by': 'user'}}
                    plan = {'schema_version': 'plan.v1', 'units': 'mm', 'intent_sha256': canonical_hash(intent),
                            'steps': [
                                {'id': 'body', 'op': 'box', 'size_mm': size},
                                {'id': 'drill', 'op': 'cylinder', 'axis': axis, 'radius_mm': 2,
                                 'height_mm': 12, 'at_mm': through_at},
                                {'id': 'recess', 'op': 'cylinder', 'axis': axis, 'radius_mm': 4,
                                 'height_mm': 6, 'at_mm': recess_at},
                                {'id': 'part', 'op': 'cut', 'from': 'body', 'tools': ['drill', 'recess']}],
                            'result': 'part'}
                    report, run = self.build(intent, plan)
                    self.assertEqual(report['intent_state'], 'blocked')
                    self.assertEqual(statuses(report)['feature:hole'], 'unknown')
                    m = load_json(run / 'native/measure.json')
                    wide = next(c for c in m['cylinders'] if abs(c['radius_mm'] - 4) < 1e-6)
                    self.assertEqual(wide['ends_open'], [None, True] if open_end == 'max' else [True, None])
                    # A shoulder around a narrower through opening is not a
                    # solid blind floor, even when the recess depth matches.
                    intent['features'][0]['depth'] = {'depth_mm': 5, 'open_end': open_end}
                    self.assertEqual(conform(intent, m)['intent_state'], 'blocked')
                    # The narrower aperture really is clear through the part.
                    intent['features'][0].update(diameter_mm=4, depth='through')
                    self.assertEqual(conform(intent, m)['intent_state'], 'conforms')

    def test_aperture_obstructions_and_boolean_failures_fail_closed(self):
        # Execute the actual helper in its exact native Python, independently
        # of tessellation. A remote obstruction must not be missed by a local
        # end probe, nor an off-center intrusion by the old centerline probe.
        script = '''
import importlib.util
import sys
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('scene', sys.argv[1])
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)
A, P = scene.App, scene.Part
foot, axis = A.Vector(10, 10, 0), A.Vector(0, 0, 1)
box = P.makeBox(20, 20, 10)
clear = box.cut(P.makeCylinder(4, 12, A.Vector(10, 10, -1)))
check = lambda shape: scene.aperture_ends(shape, foot, axis, 4, (0, 5), (0, 10))
assert check(clear) == [True, True]
# A cap remote from the measured end, with a narrow hole through its center.
remote = clear.fuse(P.makeBox(20, 20, 1, A.Vector(0, 0, 8))).cut(
    P.makeCylinder(2, 12, A.Vector(10, 10, -1))).removeSplitter()
assert remote.isValid() and len(remote.Solids) == 1
assert check(remote) == [True, None]
# A thin off-center rib inside the measured span leaves its centerline clear.
rib = clear.fuse(P.makeBox(2, 8, 0.1, A.Vector(12, 6, 2))).removeSplitter()
assert rib.isValid() and len(rib.Solids) == 1
assert check(rib) == [None, None]
with patch.object(scene.Part, 'makeCylinder', side_effect=RuntimeError('failed Boolean')):
    assert check(clear) == [None, None]
with patch.object(scene, 'empty_volume', side_effect=ValueError('invalid result')):
    assert check(clear) == [None, None]
'''
        with tempfile.TemporaryDirectory() as tmp:
            freecad.run_process([freecad.PYTHON, '-I', '-B', '-c', script, freecad_plan.SCRIPT],
                                tmp, Path(tmp) / 'aperture-fixtures.log', timeout=30)

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
