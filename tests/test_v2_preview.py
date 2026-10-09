"""Preview sheet, summary and approval rules, without FreeCAD."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from printkit.common import ForgeError, canonical_hash, load_json, sha256, write_json
from printkit.conformance import conform
from printkit import preview as pv

EXAMPLES = Path(__file__).parents[1] / 'examples/v2'


def plate():
    intent = load_json(EXAMPLES / 'mounting-plate/intent.json')
    intent['confirmation'] = {'status': 'draft'}
    plan = load_json(EXAMPLES / 'mounting-plate/plan.json')
    plan['intent_sha256'] = canonical_hash(intent)
    return intent, plan


def square(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def fake_views():
    """Outline-only projections of a 60 x 40 x 5 plate, enough to lay out a sheet."""
    v = lambda axes, box: {'axes': axes, 'visible': [square(*box)], 'hidden': []}
    return {'front': v(((1, 0, 0), (0, 0, 1), (0, -1, 0)), (0, 0, 60, 5)),
            'right': v(((0, 1, 0), (0, 0, 1), (1, 0, 0)), (0, 0, 40, 5)),
            'back': v(((-1, 0, 0), (0, 0, 1), (0, 1, 0)), (-60, 0, 0, 5)),
            'top': v(((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 60, 40)),
            'iso': v(((0.7, 0.7, 0), (-0.4, 0.4, 0.8), (0.6, -0.6, 0.6)), (0, 0, 70, 40))}


def measure():
    return {'valid': True, 'closed': True, 'solid_count': 1, 'shell_count': 1, 'size_mm': [60, 40, 5],
            'origin_mm': [0, 0, 0], 'volume_mm3': 11800, 'face_count': 14, 'edge_count': 36, 'cylinders': [],
            'planes': [{'normal': '-z', 'offset_mm': 0, 'area_mm2': 2350}]}


class PreviewTests(unittest.TestCase):
    def test_keys_ignore_confirmation_and_binding(self):
        intent, plan = plate()
        confirmed = dict(intent, confirmation={'status': 'confirmed', 'by': 'user'})
        rebound = dict(plan, intent_sha256=canonical_hash(confirmed))
        self.assertEqual(pv.intent_key(intent), pv.intent_key(confirmed))
        self.assertEqual(pv.plan_key(plan), pv.plan_key(rebound))
        changed = copy.deepcopy(intent)
        changed['features'][0]['diameter_mm'] = 4.5
        self.assertNotEqual(pv.intent_key(intent), pv.intent_key(changed))

    def test_summary_names_every_check_in_plain_words(self):
        intent, _ = plate()
        conformance = conform(intent, measure())
        checked, judged, unknown = pv.summary_lines(intent, conformance)
        lines = [line for line, _ in checked]
        self.assertIn('Overall size 60 x 40 x 5 mm (within 0.05 mm)', lines)
        self.assertIn('Hole screw-hole-1: 4 mm, along z at x 6, y 6, through', lines)
        self.assertIn('Flat face flat-bottom: facing -z at the low side, at least 2300 mm2', lines)
        self.assertEqual(judged, [f['text'] for f in intent['features'] if f['kind'] == 'note'])
        self.assertEqual(unknown, intent['unknowns'])
        text = pv.markdown(intent, conformance, 'views/sheet.png')
        self.assertIn('not for delivery', text)
        self.assertIn('Not passing yet', text)  # The fake measurement has no holes.

    def test_describes_other_depths_and_partial_holes(self):
        self.assertIn('ends shoulder and outside, 5 mm long', pv.describe(
            {'id': 'cb', 'kind': 'hole', 'axis': 'z', 'diameter_mm': 9, 'position_mm': [8, 8],
             'depth': {'ends': {'min': 'shoulder', 'max': 'outside'}, 'depth_mm': 5}}))
        self.assertIn('blind, 8 mm deep, open at the low side', pv.describe(
            {'id': 'b', 'kind': 'hole', 'axis': 'z', 'diameter_mm': 6, 'position_mm': [1, 1],
             'depth': {'depth_mm': 8, 'open_end': 'min'}}))
        self.assertIn('wall 250 to 270 degrees, 12 mm long', pv.describe(
            {'id': 'c', 'kind': 'partial_hole', 'axis': 'y', 'diameter_mm': 6.5, 'position_mm': [16, 5],
             'min_arc_deg': 250, 'max_arc_deg': 270, 'length_mm': 12}))
        self.assertIn('at 12.99 mm, at least 17 mm2 and at most 19 mm2', pv.describe(
            {'id': 'f', 'kind': 'planar_face', 'normal': '-y', 'offset': 12.9945, 'min_area_mm2': 17,
             'max_area_mm2': 19}))

    def test_sheet_has_five_views_sizes_and_hole_labels(self):
        intent, _ = plate()
        svg = pv.sheet(fake_views(), intent, measure(), conform(intent, measure()))
        for name in ('front', 'right', 'back', 'top', 'iso'):
            self.assertIn(f'>{name}</text>', svg)
        for size in ('>60<', '>40<', '>5<'):
            self.assertIn(size, svg)
        # Labelled only in the top view, the one that looks along the holes.
        self.assertEqual(sum(svg.count(f'screw-hole-{i} \u00d84<') for i in range(1, 5)), 4)
        self.assertIn('Preview, not for delivery', svg)
        self.assertNotIn('<script', svg)

    def test_approval_rejects_other_intents_plans_and_changed_files(self):
        intent, plan = plate()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'views').mkdir()
            (folder / 'views/sheet.svg').write_text('<svg/>')
            record = {'schema_version': pv.SCHEMA, 'delivery': 'not_for_delivery', 'intent_key': pv.intent_key(intent),
                      'plan_key': pv.plan_key(plan), 'solid': {}, 'files': {'views/sheet.svg': sha256(folder / 'views/sheet.svg')}}
            write_json(folder / 'preview.json', record)
            confirmed = dict(intent, confirmation={'status': 'confirmed', 'by': 'user'})
            self.assertEqual(pv.approval(folder, confirmed, dict(plan, intent_sha256=canonical_hash(confirmed)))['plan_key'],
                             record['plan_key'])
            other = copy.deepcopy(plan)
            other['steps'][1]['radius_mm'] = 3
            for bad_intent, bad_plan, code in ((confirmed, other, 'preview_mismatch'),
                                               (dict(confirmed, unknowns=[]), plan, 'preview_mismatch')):
                with self.assertRaises(ForgeError) as caught:
                    pv.approval(folder, bad_intent, bad_plan)
                self.assertEqual(caught.exception.finding, code)
            (folder / 'views/sheet.svg').write_text('<svg>edited</svg>')
            with self.assertRaises(ForgeError) as caught:
                pv.approval(folder, confirmed, plan)
            self.assertEqual(caught.exception.finding, 'preview_changed')

    def test_same_solid_is_strict(self):
        solid = {k: measure()[k] for k in ('size_mm', 'volume_mm3', 'face_count', 'edge_count')}
        self.assertTrue(pv.same_solid(solid, measure()))
        for change in ({'face_count': 15}, {'size_mm': [60, 40, 5.001]}, {'volume_mm3': 11800.1}):
            with self.subTest(change=change):
                self.assertFalse(pv.same_solid(solid, dict(measure(), **change)))


if __name__ == '__main__':
    unittest.main()
