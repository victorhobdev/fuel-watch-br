"""Contrato do laboratorio M10; nenhuma entidade representa um posto ANP."""
from datetime import timedelta
from uuid import UUID, uuid5


def generate_events(run_id, start_utc):
    namespace = UUID(run_id)
    if start_utc.tzinfo is None or start_utc.utcoffset() != timedelta(0):
        raise ValueError('start_utc deve ter timezone UTC')
    events = []
    for index in range(1000):
        late = 100 <= index < 110
        stamp = start_utc + timedelta(seconds=index - (60 if late else 0))
        events.append({'event_id': str(uuid5(namespace, str(index))), 'lab_run_id': str(namespace),
                       'posto_id': 'SYNTHETIC_' + str(index % 10 + 1).zfill(3),
                       'produto': 'GASOLINA', 'unidade': 'litro', 'moeda': 'BRL',
                       'event_time': stamp.isoformat().replace('+00:00', 'Z'), 'sequence': index,
                       'preco': '7.500' if index == 999 else '6.100',
                       'is_synthetic': True, 'is_late_fixture': late})
    return events


def reinjections(events):
    if len(events) != 1000 or len({event['event_id'] for event in events}) != 1000:
        raise ValueError('Reinjecao exige lote original completo e unico')
    return [dict(event) for event in events[:20]]
