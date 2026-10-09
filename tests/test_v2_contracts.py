"""v2 intent and plan contracts. No runtime needed."""
import copy
from pathlib import Path
import unittest
from printkit.common import ForgeError, canonical_hash, load_json
from printkit.intent import check_intent, summarize
from printkit.plan import check_plan

EXAMPLES = Path(__file__).parents[1] / 'examples/v2'


def example(name):
    return load_json(EXAMPLES / name / 'intent.json'), load_json(EXAMPLES / name / 'plan.json')


class IntentTests(unittest.TestCase):
    def test_examples_pass(self):
        for name in ('stepped-block', 'mounting-plate', 'knob'):
            with self.subTest(name=name):
                intent, _ = example(name)
                check_intent(intent, require_confirmed=True)
                summary = summarize(intent)
                self.assertEqual(summary['intent_sha256'], canonical_hash(intent))
                self.assertIn('envelope', summary['measured_checks'])

    def test_note_goes_to_person_not_measurement(self):
        intent, _ = example('mounting-plate')
        summary = summarize(intent)
        self.assertEqual(summary['person_checks'], ['rounded-corners'])
        self.assertNotIn('rounded-corners', summary['measured_checks'])

    def test_draft_is_refused_for_build(self):
        intent, _ = example('mounting-plate')
        intent['confirmation'] = {'status': 'draft'}
        check_intent(intent)
        with self.assertRaises(ForgeError) as caught:
            check_intent(intent, require_confirmed=True)
        self.assertEqual(caught.exception.finding, 'intent_unconfirmed')

    def test_confirmation_must_name_user(self):
        intent, _ = example('mounting-plate')
        intent['confirmation'] = {'status': 'confirmed', 'by': 'assistant'}
        with self.assertRaises(ForgeError):
            check_intent(intent)

    def test_rejects_loose_or_invalid_values(self):
        base, _ = example('stepped-block')
        edits = [
            lambda i: i.update(code='import os'),
            lambda i: i.pop('unknowns'),
            lambda i: i.update(units='in'),
            lambda i: i.update(solid_count=2),
            lambda i: i.update(solid_count=True),
            lambda i: i['envelope'].update(size_mm=[30, 24]),
            lambda i: i['envelope'].update(size_mm=[30, 24, float('nan')]),
            lambda i: i['envelope'].update(size_mm=[30, 24, 0]),
            lambda i: i['features'][0].update(kind='thread'),
            lambda i: i['features'][0].update(axis='w'),
            lambda i: i['features'][0].update(diameter_mm=0),
            lambda i: i['features'][0].update(diameter_mm='7.5'),
            lambda i: i['features'][0].update(position_mm=[7.5, 99]),
            lambda i: i['features'][0].update(depth={'depth_mm': 5}),
            lambda i: i['features'][0].update(depth={'depth_mm': 5, 'open_end': 'top'}),
            lambda i: i['features'][0].update(depth={'ends': {'min': 'outside', 'max': 'pocket'}}),
            lambda i: i['features'][0].update(depth={'ends': {'min': 'outside'}}),
            # One end must reach the outside; a hole between two voids or floors is not a requested feature.
            lambda i: i['features'][0].update(depth={'ends': {'min': 'void', 'max': 'shoulder'}}),
            lambda i: i['features'][0].update(depth={'ends': {'min': 'outside', 'max': 'void'}, 'open_end': 'max'}),
            lambda i: i['features'][0].update(depth={'ends': {'min': 'outside', 'max': 'void'}, 'depth_mm': 0}),
            lambda i: i['features'][0].update(script='x'),
            lambda i: i['features'][1].update(normal='down'),
            lambda i: i['features'][1].update(offset=99),
            lambda i: i['features'].append(copy.deepcopy(i['features'][0])),
            lambda i: i['volume_mm3'].update(min=10, max=5),
        ]
        for index, edit in enumerate(edits):
            with self.subTest(index=index):
                intent = copy.deepcopy(base)
                edit(intent)
                with self.assertRaises(ForgeError):
                    check_intent(intent)

    def test_blind_hole_accepted(self):
        intent, _ = example('stepped-block')
        intent['features'][0]['depth'] = {'depth_mm': 4, 'open_end': 'max'}
        check_intent(intent)


class PlanTests(unittest.TestCase):
    def test_examples_bound_to_their_intent(self):
        for name in ('stepped-block', 'mounting-plate', 'knob'):
            with self.subTest(name=name):
                intent, plan = example(name)
                result = check_plan(plan, intent)
                self.assertEqual(result['warnings'], [])

    def test_plan_for_other_intent_refused(self):
        intent, _ = example('stepped-block')
        _, plan = example('mounting-plate')
        with self.assertRaises(ForgeError) as caught:
            check_plan(plan, intent)
        self.assertEqual(caught.exception.finding, 'intent_mismatch')

    def test_changed_intent_breaks_binding(self):
        intent, plan = example('mounting-plate')
        intent['envelope']['size_mm'][0] = 61
        with self.assertRaises(ForgeError):
            check_plan(plan, intent)

    def test_unused_step_is_a_warning(self):
        intent, plan = example('stepped-block')
        plan['steps'].insert(0, {'id': 'spare', 'op': 'sphere', 'radius_mm': 2})
        self.assertEqual(len(check_plan(plan, intent)['warnings']), 1)

    def test_rejects_code_unknown_ops_and_bad_references(self):
        _, base = example('stepped-block')
        edits = [
            lambda p: p['steps'].append({'id': 'x', 'op': 'python', 'code': 'import os'}),
            lambda p: p['steps'][0].update(code='import os'),
            lambda p: p['steps'][0].update(id='Base!'),
            lambda p: p['steps'][1].update(id='base'),
            lambda p: p['steps'][2].update(of=['base']),
            lambda p: p['steps'][2].update(of=['base', 'base']),
            lambda p: p['steps'][2].update(of=['base', 'later']),
            lambda p: p['steps'][4].update(**{'from': 'part'}),
            lambda p: p['steps'][0].update(size_mm=[30, 24, 0]),
            lambda p: p['steps'][0].update(size_mm=[30, 24, True]),
            lambda p: p['steps'][0].update(at_mm=[0, 0, 1e9]),
            lambda p: p['steps'][3].update(axis='w'),
            lambda p: p.update(result='missing'),
            lambda p: p.update(steps=[]),
            lambda p: p.update(units='in'),
            lambda p: p.update(intent_sha256='short'),
            lambda p: p.update(extra=1),
        ]
        for index, edit in enumerate(edits):
            with self.subTest(index=index):
                plan = copy.deepcopy(base)
                edit(plan)
                with self.assertRaises(ForgeError):
                    check_plan(plan)

    def test_profiles_must_be_simple_polygons(self):
        _, plan = example('stepped-block')
        good = {'id': 'web', 'op': 'extrude', 'plane': 'xz', 'points': [[0, 0], [10, 0], [0, 10]], 'height_mm': 2}
        bowtie = dict(good, points=[[0, 0], [10, 10], [10, 0], [0, 10]])
        flat = dict(good, points=[[0, 0], [5, 0], [10, 0]])
        repeat = dict(good, points=[[0, 0], [0, 0], [10, 0], [0, 10]])
        negative = {'id': 'web', 'op': 'revolve', 'points': [[-1, 0], [5, 0], [5, 5]]}
        check_plan(dict(plan, steps=plan['steps'] + [good]))
        for step in (bowtie, flat, repeat, negative):
            with self.subTest(step=step):
                with self.assertRaises(ForgeError):
                    check_plan(dict(plan, steps=plan['steps'] + [step]))

    def test_pattern_budgets(self):
        _, plan = example('mounting-plate')
        plan['steps'][3]['count'] = 65
        with self.assertRaises(ForgeError):
            check_plan(plan)
        _, plan = example('mounting-plate')
        plan['steps'][3]['count'] = 2.0
        with self.assertRaises(ForgeError):
            check_plan(plan)
        _, plan = example('mounting-plate')
        steps = plan['steps']
        for n in range(5):
            steps.append({'id': f'p{n}', 'op': 'linear_pattern', 'target': 'drill', 'step_mm': [1, 0, 0], 'count': 64})
        with self.assertRaises(ForgeError):
            check_plan(plan)


if __name__ == '__main__':
    unittest.main()
