import unittest
from datetime import datetime, timezone

from fuelwatch.synthetic_events import generate_events, reinjections


class SyntheticEventTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 13, tzinfo=timezone.utc)
        self.run = '00000000-0000-4000-8000-000000000010'
        self.events = generate_events(self.run, self.start)

    def test_exact_ids_units_and_reinjections(self):
        repeated = reinjections(self.events)
        self.assertEqual(len(self.events), 1000)
        self.assertEqual(len(repeated), 20)
        self.assertEqual(len({e['event_id'] for e in self.events + repeated}), 1000)
        self.assertEqual(self.events, generate_events(self.run, self.start))
        self.assertEqual(len({e['posto_id'] for e in self.events}), 10)
        self.assertTrue(all(e['is_synthetic'] and e['unidade'] == 'litro' and e['moeda'] == 'BRL' for e in self.events))
        self.assertEqual(repeated, self.events[:20])
        repeated[0]['preco'] = '999.000'
        self.assertEqual(self.events[0]['preco'], '6.100')

    def test_controlled_transition_and_out_of_order(self):
        target = [e for e in self.events if e['posto_id'] == 'SYNTHETIC_010']
        self.assertEqual({e['preco'] for e in target[:-1]}, {'6.100'})
        self.assertEqual(target[-1]['preco'], '7.500')
        self.assertEqual(sum(e['is_late_fixture'] for e in self.events), 10)
        self.assertLess(self.events[100]['event_time'], self.events[99]['event_time'])
        self.assertEqual(max(self.events, key=lambda e: e['event_time']), self.events[-1])

    def test_naive_time_and_incomplete_replay_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_events(self.run, datetime(2026, 11, 13))
        with self.assertRaises(ValueError):
            reinjections(self.events[:-1])
