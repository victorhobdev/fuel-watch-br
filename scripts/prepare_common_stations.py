"""Referencia local independente dos postos comuns entre primeiros semestres."""
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fuelwatch.analytics import row_hash

source = ROOT / 'data/artifacts/history/publication/reference.parquet'
frame = pd.read_parquet(source, columns=['data_coleta', 'cnpj', 'uf', 'municipio_ibge',
                                         'produto', 'moeda', 'unidade', 'preco_venda'])
date = pd.to_datetime(frame.data_coleta)
frame = frame.loc[date.dt.month <= 6].copy()
frame['ano'] = date.loc[frame.index].dt.year
frame['mills'] = frame.preco_venda.map(lambda x: int(x * 1000))
key = ['cnpj', 'uf', 'municipio_ibge', 'produto', 'moeda', 'unidade']
annual = frame.groupby(['ano', *key], as_index=False).agg(coletas=('mills', 'size'), mills=('mills', 'sum'))
previous = annual.rename(columns={'ano': 'ano_anterior', 'coletas': 'coletas_anterior', 'mills': 'mills_anterior'})
current = annual.rename(columns={'ano': 'ano_atual', 'coletas': 'coletas_atual', 'mills': 'mills_atual'})
previous['ano_atual'] = previous.ano_anterior + 1
pairs = previous.merge(current, on=['ano_atual', *key], validate='one_to_one')
columns = ['ano_anterior', 'ano_atual', *key, 'coletas_anterior', 'coletas_atual', 'soma_anterior', 'soma_atual']
for period in ['anterior', 'atual']:
    pairs['soma_' + period] = pairs['mills_' + period].map(lambda x: str(Decimal(int(x)) / 1000))
pairs = pairs[columns]
kinds = ['int', 'int', *(['str'] * 6), 'int', 'int', 'decimal', 'decimal']
hashes = sorted(row_hash(row, kinds) for row in pairs.itertuples(index=False, name=None))
out = ROOT / 'data/artifacts/analytics-history/common-stations'
out.mkdir(parents=True, exist_ok=True)
pairs.to_parquet(out / 'reference.parquet', index=False)
summary = {'columns': columns, 'kinds': kinds, 'rows': len(pairs),
           'business_sha256': hashlib.sha256('\n'.join(hashes).encode()).hexdigest(),
           'by_period': {str(k): int(v) for k, v in pairs.groupby('ano_atual').size().items()}}
(out / 'reference.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
print(json.dumps(summary, ensure_ascii=False), flush=True)
