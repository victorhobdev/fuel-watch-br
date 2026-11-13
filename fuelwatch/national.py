"""Contrato nacional: referencia oficial e regras sem alterar o baseline RJ."""
import json
from fuelwatch.contract import normalize_name

PRODUCT_UNITS = {p: 'R$ / litro' for p in ['DIESEL', 'DIESEL S10', 'ETANOL', 'GASOLINA', 'GASOLINA ADITIVADA']}
PRODUCT_UNITS['GNV'] = 'R$ / m³'
SCOPE = {'scope_id': 'anp-2026-1-br-todos', 'date_start': '2026-01-01', 'date_end': '2026-06-30',
         'contract_version': 'national-1.0', 'product_units': PRODUCT_UNITS}
IQR_KEYS = ['uf', 'produto', 'moeda', 'unidade', 'inicio_semana_iso']


def national_reference(municipalities, states):
    states_by_id = {str(s['id']): s['sigla'] for s in states}
    rows, lookup = [], {}
    for item in municipalities:
        code = str(item['id'])
        if len(code) != 7 or code[:2] not in states_by_id:
            raise ValueError('Codigo IBGE nacional invalido')
        uf = states_by_id[code[:2]]
        name = normalize_name(item['nome'])
        rows.append({'municipio_ibge': code, 'nome': item['nome'], 'uf': uf, 'nome_normalizado': name})
        lookup.setdefault((uf, name), []).append(code)
    if len({r['municipio_ibge'] for r in rows}) != len(rows) or any(len(v) != 1 for v in lookup.values()):
        raise ValueError('Referencia municipal ambigua')
    # Diferenca de apostrofo observada no arquivo ANP; alvo validado no snapshot oficial.
    target = next(r for r in rows if r['municipio_ibge'] == '4317103')
    if target['uf'] != 'RS' or target['nome_normalizado'].replace("'", '') != 'SANTANA DO LIVRAMENTO':
        raise ValueError('Revisar alias municipal contra o snapshot IBGE')
    alias = ('RS', 'SANTANA DO LIVRAMENTO')
    if alias in lookup and lookup[alias] != ['4317103']:
        raise ValueError('Alias municipal conflitante')
    lookup[alias] = ['4317103']
    return rows, lookup
