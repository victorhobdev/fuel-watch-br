from datetime import datetime, timezone
import unittest

from fuelwatch.historical_events import classify_event, generate_historical_events


class HistoricalEventTests(unittest.TestCase):
    def benchmark(self):
        return {'benchmark_version': 'v1', 'uf': 'RJ', 'produto': 'GASOLINA', 'moeda': 'BRL',
        'unidade': 'litro', 'median': '6.790000', 'week_start': '2026-06-22',
        'available_for_lab_at_utc': '2026-11-14T00:00:00+00:00', 'maximum_reference_age_days': 180}

    def test_finite_fixture_has_unique_ids_late_missing_stale_and_transition(self):
        events = generate_historical_events('00000000-0000-4000-8000-000000000001', datetime(2026,11,15,tzinfo=timezone.utc), self.benchmark())
        self.assertEqual(len(events), len({e['event_id'] for e in events}))
        self.assertEqual(sum(e['is_late_fixture'] for e in events), 10)
        self.assertEqual(sum(e['benchmark_status'] == 'missing_benchmark' for e in events), 5)
        self.assertEqual(sum(e['benchmark_status'] == 'stale_benchmark' for e in events), 5)
        self.assertEqual(sum(e['benchmark_status'] == 'above_threshold' for e in events), 1)
        self.assertEqual(sum(e['alert_score'] for e in events), 1)
        self.assertTrue(all(e['alert_score']==0 for e in events if e['benchmark_status'] in {'missing_benchmark','stale_benchmark'}))

    def test_threshold_is_strict_and_units_cannot_mix(self):
        b = self.benchmark()
        e = {'benchmark_version':'v1','uf':'RJ','produto':'GASOLINA','moeda':'BRL','unidade':'litro',
             'event_time':'2026-11-15T00:00:00+00:00','preco':'7.469'}
        self.assertEqual(classify_event(e,b), 'within_threshold')
        self.assertEqual(classify_event({**e,'preco':'7.470'},b), 'above_threshold')
        self.assertEqual(classify_event({**e,'unidade':'m3'},b), 'missing_benchmark')
        self.assertEqual(classify_event({**e,'event_time':'2026-11-13T00:00:00+00:00'},b), 'benchmark_not_yet_available')
