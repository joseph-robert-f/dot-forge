"""v2 conformance and build guards. Measurements are hand-built fixtures in the
format the FreeCAD helper writes; real native runs are not part of this suite."""
import copy
import io
import json
import math
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from printkit import cli
from printkit.common import ForgeError, load_json
from printkit.conformance import conform
from printkit.forge import build

EXAMPLES = Path(__file__).parents[1] / 'examples/v2'
HOLE_AREA = math.pi * 3.75 ** 2


def example(name):
    return load_json(EXAMPLES / name / 'intent.json'), load_json(EXAMPLES / name / 'plan.json')


def hole(position, radius=3.75, span=(0, 9), ends=(True, True), angle=2 * math.pi, axis='z', kind='void'):
    return {'axis': axis, 'radius_mm': radius, 'angle_rad': angle, 'kind': kind,
            'position_mm': list(position), 'span_mm': list(span), 'ends_open': list(ends)}


def stepped_measurement():
    """What the helper reports for the stepped-block example built as planned."""
    return {'valid': True, 'closed': True, 'solid_count': 1, 'size_mm': [30, 24, 18],
            'volume_mm3': .75 * 30 * 24 * 18 - HOLE_AREA * 9,
            'cylinders': [hole((7.5, 12))],
            'planes': [{'normal': '-z', 'offset_mm': 0, 'area_mm2': 720 - HOLE_AREA},
                       {'normal': '+z', 'offset_mm': 9, 'area_mm2': 360 - HOLE_AREA},
                       {'normal': '+z', 'offset_mm': 18, 'area_mm2': 360},
                       {'normal': '-x', 'offset_mm': 0, 'area_mm2': 216},
                       {'normal': None, 'offset_mm': None, 'area_mm2': 1}]}


def plate_measurement():
    corners = [hole(p, radius=4, span=(0, 5), angle=math.pi / 2, kind='boss') for p in ((4, 4), (56, 4), (4, 36), (56, 36))]
    holes = [hole(p, radius=2, span=(0, 5)) for p in ((6, 6), (54, 6), (6, 34), (54, 34))]
    area = 2400 - 4 * (16 - 4 * math.pi) - 4 * 4 * math.pi
    return {'valid': True, 'closed': True, 'solid_count': 1, 'size_mm': [60, 40, 5], 'volume_mm3': area * 5,
            'cylinders': corners + holes, 'planes': [{'normal': '-z', 'offset_mm': 0, 'area_mm2': area}]}


def statuses(report):
    return {c['code']: c['status'] for c in report['checks']}


class ConformanceTests(unittest.TestCase):
    def test_stepped_block_conforms(self):
        intent, _ = example('stepped-block')
        report = conform(intent, stepped_measurement())
        self.assertEqual(report['intent_state'], 'conforms', report)
        self.assertEqual(statuses(report)['feature:ledge-hole'], 'pass')
        self.assertEqual(statuses(report)['unrequested_holes'], 'pass')

    def test_plate_conforms_but_note_needs_person(self):
        intent, _ = example('mounting-plate')
        report = conform(intent, plate_measurement())
        self.assertEqual(report['intent_state'], 'conforms', report)
        self.assertEqual(report['person_checks'], ['feature:rounded-corners'])
        # Convex corner fillets are partial bosses, never counted as holes.
        self.assertEqual(statuses(report)['unrequested_holes'], 'pass')

    def test_unknowns_are_reported_not_passed(self):
        intent, _ = example('mounting-plate')
        report = conform(intent, plate_measurement())
        unknown = [c for c in report['checks'] if c['code'] == 'unknown']
        self.assertEqual(len(unknown), len(intent['unknowns']))
        self.assertTrue(all(c['status'] == 'unknown' for c in unknown))

    def test_wrong_geometry_blocks(self):
        intent, _ = example('stepped-block')
        cases = {
            'envelope': lambda m: m.update(size_mm=[30, 24, 18.5]),
            'native_solid': lambda m: m.update(solid_count=2),
            'volume': lambda m: m.update(volume_mm3=9000),
            'feature:ledge-hole': lambda m: m['cylinders'][0].update(radius_mm=3.5),
            'feature:flat-bottom': lambda m: m['planes'][0].update(area_mm2=600),
        }
        for code, edit in cases.items():
            with self.subTest(code=code):
                m = stepped_measurement()
                edit(m)
                report = conform(intent, m)
                self.assertEqual(report['intent_state'], 'blocked')
                self.assertEqual(statuses(report)[code], 'fail')

    def test_moved_hole_fails_and_names_nearest(self):
        intent, _ = example('stepped-block')
        m = stepped_measurement()
        m['cylinders'][0]['position_mm'] = [9, 12]
        check = next(c for c in conform(intent, m)['checks'] if c['code'] == 'feature:ledge-hole')
        self.assertEqual(check['status'], 'fail')
        self.assertEqual(check['actual']['nearest_hole']['position_mm'], [9, 12])
        # The moved hole is still there, so it is also reported as unrequested.
        self.assertEqual(statuses(conform(intent, m))['unrequested_holes'], 'needs_review')

    def test_blind_hole_is_not_through(self):
        intent, _ = example('stepped-block')
        m = stepped_measurement()
        m['cylinders'][0]['ends_open'] = [False, True]
        self.assertEqual(statuses(conform(intent, m))['feature:ledge-hole'], 'fail')
        intent['features'][0]['depth'] = {'depth_mm': 9, 'open_end': 'max'}
        self.assertEqual(statuses(conform(intent, m))['feature:ledge-hole'], 'pass')
        intent['features'][0]['depth'] = {'depth_mm': 9, 'open_end': 'min'}
        self.assertEqual(statuses(conform(intent, m))['feature:ledge-hole'], 'fail')
        intent['features'][0]['depth'] = {'depth_mm': 6, 'open_end': 'max'}
        self.assertEqual(statuses(conform(intent, m))['feature:ledge-hole'], 'fail')

    def test_partial_or_boss_cylinder_is_not_a_hole(self):
        intent, _ = example('stepped-block')
        for edit in ({'angle_rad': math.pi}, {'kind': 'boss'}, {'axis': 'x'}, {'axis': None}):
            with self.subTest(edit=edit):
                m = stepped_measurement()
                m['cylinders'][0].update(edit)
                self.assertEqual(statuses(conform(intent, m))['feature:ledge-hole'], 'fail')

    def test_unprobed_ends_are_unknown_not_pass(self):
        intent, _ = example('stepped-block')
        m = stepped_measurement()
        m['cylinders'][0]['ends_open'] = None
        report = conform(intent, m)
        self.assertEqual(statuses(report)['feature:ledge-hole'], 'unknown')
        self.assertEqual(report['intent_state'], 'blocked')

    def test_one_hole_cannot_satisfy_two_features(self):
        intent, _ = example('stepped-block')
        twin = copy.deepcopy(intent['features'][0])
        twin['id'] = 'second-hole'
        intent['features'].append(twin)
        report = conform(intent, stepped_measurement())
        self.assertEqual(statuses(report)['feature:ledge-hole'], 'pass')
        self.assertEqual(statuses(report)['feature:second-hole'], 'fail')

    def test_extra_hole_goes_to_person(self):
        intent, _ = example('stepped-block')
        m = stepped_measurement()
        m['cylinders'].append(hole((20, 12), radius=1, span=(9, 18)))
        report = conform(intent, m)
        self.assertEqual(report['intent_state'], 'conforms')
        self.assertIn('unrequested_holes', report['person_checks'])

    def test_malformed_measurement_rejected(self):
        intent, _ = example('stepped-block')
        for edit in (lambda m: m.pop('cylinders'), lambda m: m.update(valid='yes'),
                     lambda m: m.update(size_mm=[30, 24, float('nan')]),
                     lambda m: m['cylinders'][0].update(kind='maybe'),
                     lambda m: m['cylinders'][0].pop('radius_mm')):
            m = stepped_measurement()
            edit(m)
            with self.assertRaises(ForgeError):
                conform(intent, m)


class BuildGuardTests(unittest.TestCase):
    def test_runtime_unavailable_keeps_run_and_reports(self):
        intent, plan = example('stepped-block')
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run-001'
            with self.assertRaises(ForgeError) as caught:
                build(intent, plan, run, discover=lambda: {'status': 'unavailable', 'reason': 'no FreeCAD'})
            self.assertEqual(caught.exception.code, 3)
            report = load_json(run / 'report.json')
            self.assertEqual(report['overall_state'], 'blocked')
            self.assertEqual(report['intent_state'], 'unknown')
            self.assertEqual(load_json(run / 'plan.json'), plan)
            self.assertFalse((run / 'exports/model.stl').exists())

    def test_plan_step_failure_is_a_plan_finding(self):
        from unittest.mock import patch
        from printkit.adapters import freecad_plan
        intent, plan = example('stepped-block')
        capability = {'status': 'unverified'}

        def failing_run(mode, run):
            (Path(run) / 'native/plan-failure.json').write_text(json.dumps(
                {'status': 'fail', 'step': 'part', 'op': 'cut', 'error': 'OCCError: not done'}))
            raise ForgeError('Runtime exited 1; see retained stage log', 3, 'runtime_failed')

        with tempfile.TemporaryDirectory() as tmp, patch.object(freecad_plan, '_run', failing_run):
            with self.assertRaises(ForgeError) as caught:
                build(intent, plan, Path(tmp) / 'run', discover=lambda: capability)
            self.assertEqual((caught.exception.code, caught.exception.finding), (4, 'plan_step_failed'))
            self.assertIn("cut step 'part'", str(caught.exception))
            self.assertEqual(load_json(Path(tmp) / 'run/report.json')['failure']['code'], 'plan_step_failed')

    def test_runtime_crash_without_plan_failure_stays_runtime(self):
        from unittest.mock import patch
        from printkit.adapters import freecad_plan
        intent, plan = example('stepped-block')

        def crashing_run(mode, run):
            raise ForgeError('Runtime exited 1; see retained stage log', 3, 'runtime_failed')

        with tempfile.TemporaryDirectory() as tmp, patch.object(freecad_plan, '_run', crashing_run):
            with self.assertRaises(ForgeError) as caught:
                build(intent, plan, Path(tmp) / 'run', discover=lambda: {'status': 'unverified'})
            self.assertEqual(caught.exception.finding, 'runtime_failed')

    def test_refuses_draft_mismatch_and_reused_run(self):
        intent, plan = example('stepped-block')
        with tempfile.TemporaryDirectory() as tmp:
            draft = dict(intent, confirmation={'status': 'draft'})
            other, _ = example('mounting-plate')
            for bad_intent in (draft, other):
                with self.assertRaises(ForgeError):
                    build(bad_intent, plan, Path(tmp) / 'a')
                self.assertFalse((Path(tmp) / 'a').exists())
            used = Path(tmp) / 'used'
            used.mkdir()
            (used / 'old.txt').write_text('keep')
            with self.assertRaises(ForgeError):
                build(intent, plan, used)
            self.assertEqual((used / 'old.txt').read_text(), 'keep')


class CliTests(unittest.TestCase):
    def call(self, *argv):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = cli.main(list(argv))
        return code, json.loads(stream.getvalue())

    def test_check_commands(self):
        folder = EXAMPLES / 'mounting-plate'
        code, result = self.call('check-intent', str(folder / 'intent.json'))
        self.assertEqual((code, result['status']), (0, 'pass'))
        code, result = self.call('check-plan', str(folder / 'plan.json'), '--intent', str(folder / 'intent.json'))
        self.assertEqual((code, result['status']), (0, 'pass'))
        code, result = self.call('check-plan', str(folder / 'plan.json'), '--intent',
                                 str(EXAMPLES / 'stepped-block/intent.json'))
        self.assertEqual((code, result['code']), (2, 'intent_mismatch'))

    def test_conform_exit_codes(self):
        intent = str(EXAMPLES / 'stepped-block/intent.json')
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = Path(tmp) / 'good.json', Path(tmp) / 'bad.json'
            good.write_text(json.dumps(stepped_measurement()))
            m = stepped_measurement()
            m['size_mm'] = [31, 24, 18]
            bad.write_text(json.dumps(m))
            self.assertEqual(self.call('conform', '--intent', intent, '--measurement', str(good))[0], 0)
            self.assertEqual(self.call('conform', '--intent', intent, '--measurement', str(bad))[0], 4)

    def test_blocked_report_exits_4(self):
        self.assertEqual(cli.report_exit({'overall_state': 'blocked', 'geometry_state': 'geometry_validated'}), 4)


if __name__ == '__main__':
    unittest.main()
