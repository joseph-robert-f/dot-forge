"""`printkit measure` input rules and report states, without FreeCAD."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from printkit.common import ForgeError, load_json, write_json
from printkit.cli import main
from printkit import measure as ms
from test_printability import box, write

EXAMPLES = Path(__file__).parents[1] / 'examples/v2'
STEP = b'ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n'


def block_intent():
    intent = load_json(EXAMPLES / 'mounting-plate/intent.json')
    intent['envelope'] = {'size_mm': [20, 10, 5], 'tolerance_mm': 0.05}
    intent['features'] = [{'id': 'bottom', 'kind': 'planar_face', 'normal': '-z', 'offset': 'min',
                           'min_area_mm2': 190, 'tolerance_mm': 0.05, 'source': 'flat bottom'}]
    intent.pop('volume_mm3', None)
    return intent


def block_measure(size=(20, 10, 5)):
    x, y, z = size
    return {'valid': True, 'closed': True, 'solid_count': 1, 'shell_count': 1, 'size_mm': list(size),
            'origin_mm': [0, 0, 0], 'volume_mm3': x * y * z, 'area_mm2': 2 * (x * y + y * z + x * z),
            'face_count': 6, 'edge_count': 12, 'cylinders': [],
            'planes': [{'normal': '-z', 'offset_mm': 0, 'area_mm2': x * y}]}


def fake_measurer(size=(20, 10, 5), mesh_size=None, other=0, mesh='pass', deflection=0.05):
    def run(run_dir, discover=None):
        run = Path(run_dir)
        for folder in ('native', 'exports', 'logs'):
            (run / folder).mkdir()
        write_json(run / 'native/measure.json', block_measure(size))
        write(box(*(mesh_size or size)), run / 'exports', 'model.stl')
        source = {'status': 'pass', 'surfaces': {'plane': 6, 'cylinder': 0, 'other': other},
                  'mesh': {'status': mesh, 'triangle_budget': 10000, 'tried_deflections_mm': [0.05, 0.1, 0.2]}}
        if mesh == 'pass':
            source['mesh'].update(linear_deflection_mm=deflection, triangles=12)
        write_json(run / 'native/source.json', source)
        return {'status': 'pass', 'source': source, 'metrics': {}, 'provenance': {'measurer': 'fake'}}
    return run


class MeasureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.step = self.root / 'part.step'
        self.step.write_bytes(STEP)

    def tearDown(self):
        self.tmp.cleanup()

    def measure(self, measurer=None, **kwargs):
        with mock.patch.object(ms.freecad_plan, 'measure_step', measurer or fake_measurer()):
            return ms.measure_part(self.step, self.root / 'run', **kwargs)

    def test_refuses_files_that_are_not_step(self):
        cases = {'part.stl': STEP, 'bad.step': b'solid x\nendsolid x\n'}
        for name, data in cases.items():
            path = self.root / name
            path.write_bytes(data)
            with self.assertRaises(ForgeError):
                ms.read_step(path)
        with self.assertRaises(ForgeError):
            ms.read_step(self.root / 'missing.step')
        link = self.root / 'link.step'
        link.symlink_to(self.step)
        with self.assertRaises(ForgeError):
            ms.read_step(link)
        with mock.patch.object(ms, 'MAX_STEP_BYTES', 10), self.assertRaises(ForgeError):
            ms.read_step(self.step)
        self.assertEqual(ms.read_step(self.step), STEP)

    def test_intent_must_be_confirmed(self):
        intent = block_intent()
        intent['confirmation'] = {'status': 'draft'}
        with self.assertRaises(ForgeError):
            self.measure(intent=intent)
        self.assertFalse((self.root / 'run').exists())

    def test_without_intent_reports_measurement_only(self):
        report = self.measure()
        self.assertEqual(report['intent_state'], 'not_checked')
        self.assertEqual(report['overall_state'], 'measured')
        self.assertEqual(report['geometry_state'], 'geometry_validated')
        self.assertEqual(report['measurement']['faces'], {'plane': 6, 'cylinder': 0, 'other': 0, 'total': 6})
        self.assertNotIn('conformance', report)
        self.assertEqual(load_json(self.root / 'run/report.json'), report)
        self.assertEqual((self.root / 'run/input/part.step').read_bytes(), STEP)
        self.assertIn('input/part.step', report['artifacts'])

    def test_with_intent_checks_like_a_build(self):
        report = self.measure(intent=block_intent())
        self.assertEqual(report['intent_state'], 'conforms')
        self.assertEqual(report['overall_state'], 'needs_review')
        self.assertIn('five_view_review', report['person_checks'])
        self.assertIn('intent.json', report['artifacts'])

    def test_wrong_size_blocks(self):
        report = self.measure(fake_measurer(size=(25, 10, 5)), intent=block_intent())
        self.assertEqual(report['intent_state'], 'blocked')
        self.assertEqual(report['overall_state'], 'blocked')

    def test_mesh_that_disagrees_with_the_solid_blocks(self):
        report = self.measure(fake_measurer(mesh_size=(20, 10, 7)))
        self.assertEqual(report['geometry_state'], 'blocked')
        self.assertEqual(report['overall_state'], 'blocked')

    def test_mesh_over_budget_is_unknown_and_blocks_an_intent(self):
        report = self.measure(fake_measurer(mesh='over_budget'), intent=block_intent())
        self.assertEqual(report['geometry_state'], 'unknown')
        self.assertEqual(report['mesh_validation']['status'], 'not_run')
        self.assertEqual(report['intent_state'], 'conforms')
        self.assertEqual(report['overall_state'], 'blocked')

    def test_warns_about_unmeasurable_surfaces_and_coarse_mesh(self):
        report = self.measure(fake_measurer(other=4, deflection=0.2))
        self.assertEqual(len(report['warnings']), 2)
        self.assertIn('4 of 6 faces', report['warnings'][0])

    def test_failed_measurement_keeps_a_blocked_report(self):
        def broken(run_dir, discover=None):
            raise ForgeError('FreeCAD could not read or measure the STEP file.', 4, 'step_unreadable')
        with self.assertRaises(ForgeError):
            self.measure(broken)
        report = load_json(self.root / 'run/report.json')
        self.assertEqual(report['overall_state'], 'blocked')
        self.assertEqual(report['failure']['code'], 'step_unreadable')

    def test_cli_exit_codes(self):
        with mock.patch.object(ms.freecad_plan, 'measure_step', fake_measurer()), \
             mock.patch('sys.stdout'):
            self.assertEqual(main(['measure', str(self.step), '--output', str(self.root / 'a')]), 0)
            intent = self.root / 'intent.json'
            write_json(intent, block_intent())
            self.assertEqual(main(['measure', str(self.step), '--output', str(self.root / 'b'),
                                   '--intent', str(intent)]), 5)
        with mock.patch.object(ms.freecad_plan, 'measure_step', fake_measurer(size=(25, 10, 5))), \
             mock.patch('sys.stdout'):
            self.assertEqual(main(['measure', str(self.step), '--output', str(self.root / 'c'),
                                   '--intent', str(intent)]), 4)
            self.assertEqual(main(['measure', str(self.root / 'nope.step'), '--output', str(self.root / 'd')]), 2)


if __name__ == '__main__':
    unittest.main()
