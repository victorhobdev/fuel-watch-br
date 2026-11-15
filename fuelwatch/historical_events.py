"""Classificação do laboratório sintético com benchmark histórico versionado."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid5


def classify_event(event, benchmark):
    if not benchmark or event.get('benchmark_version') != benchmark['benchmark_version']:
        return 'missing_benchmark'
    for key in ['uf', 'produto', 'moeda', 'unidade']:
        if event.get(key) != benchmark[key]:
            return 'missing_benchmark'
    stamp = datetime.fromisoformat(event['event_time'].replace('Z', '+00:00'))
    available = datetime.fromisoformat(benchmark['available_for_lab_at_utc'])
    if stamp < available:
        return 'benchmark_not_yet_available'
    reference = datetime.fromisoformat(benchmark['week_start']).replace(tzinfo=timezone.utc) + timedelta(days=7)
    if stamp - reference > timedelta(days=benchmark['maximum_reference_age_days']):
        return 'stale_benchmark'
    return 'above_threshold' if Decimal(event['preco']) > Decimal(benchmark['median']) * Decimal('1.10') else 'within_threshold'


def generate_historical_events(run_id, start, benchmark):
    if start.tzinfo is None or start.utcoffset() != timedelta(0):
        raise ValueError('Data inicial deve estar em UTC')
    if start < datetime.fromisoformat(benchmark['available_for_lab_at_utc']):
        raise ValueError('Benchmark ainda indisponível na data inicial')
    events = []
    median = Decimal(benchmark['median'])
    for i in range(1000):
        stamp = start + timedelta(seconds=i - (60 if 100 <= i < 110 else 0))
        version = benchmark['benchmark_version']
        if 980 <= i < 985:
            version = 'missing-fixture'
        if 985 <= i < 990:
            stamp += timedelta(days=181)
        price = median * (Decimal('1.20') if i == 999 else Decimal('0.90') if i % 2 else Decimal('1.00'))
        event = {'event_id': str(uuid5(UUID(run_id), str(i))), 'lab_run_id': run_id,
            'posto_id': 'SYNTHETIC_' + str(i % 10 + 1).zfill(3),
            'uf': benchmark['uf'], 'produto': benchmark['produto'], 'unidade': benchmark['unidade'],
            'moeda': benchmark['moeda'], 'event_time': stamp.isoformat(), 'sequence': i,
            'preco': str(price.quantize(Decimal('.001'))), 'is_synthetic': True,
            'is_late_fixture': 100 <= i < 110, 'benchmark_version': version}
        event['benchmark_status'] = classify_event(event, benchmark)
        event['alert_score'] = 1 if event['benchmark_status'] == 'above_threshold' else 0
        events.append(event)
    return events
