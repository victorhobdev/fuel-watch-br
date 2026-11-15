"""Compara medidas DAX do painel com a visão conciliada no Warehouse."""
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal

from client import ROOT,environment_config
from evidence import write_json
from powerbi import request
from warehouse import connect, results

c = environment_config();rebuild='--rebuild' in sys.argv
state = json.loads((ROOT / ('.local/phase2-rebuild/bi-history/binding.json' if rebuild else '.local/phase2-bi-history/binding.json')).read_text())
checks = []
cases = [('GASOLINA', 2025, 'RJ'), ('GNV', 2026, 'SP'), ('ETANOL', 2026, 'MG')]
with connect(c) as cn:
    cn.timeout = 600
    for product, year, uf in cases:
        dax = ('EVALUATE CALCULATETABLE(ROW("postos", [Postos comparaveis], '
               '"anterior", [Preco anterior postos comuns], "atual", [Preco atual postos comuns]), '
               f'TREATAS({{"{product}"}}, Produtos[Combustivel]), '
               f'TREATAS({{{year}}}, Periodos[Ano atual]), TREATAS({{"{uf}"}}, Estados[UF]))')
        response = request('POST', f"groups/{c['workspace_id']}/datasets/{state['semantic_model_id']}/executeQueries",
                           {'queries': [{'query': dax}], 'serializerSettings': {'includeNulls': True}})
        assert 'error' not in response and 'error' not in response['results'][0], response
        actual = response['results'][0]['tables'][0]['rows'][0]
        sql = ("SELECT COUNT_BIG(*) AS postos, AVG(CAST(soma_anterior AS float)/coletas_anterior) AS anterior, "
               "AVG(CAST(soma_atual AS float)/coletas_atual) AS atual FROM analise_hist.postos_comuns_semestre "
               f"WHERE produto='{product}' AND ano_atual={year} AND uf='{uf}'")
        expected = results(cn.cursor().execute(sql))[0][0]
        assert actual['[postos]'] == expected['postos'] and expected['postos'] > 0, (actual, expected)
        for field in ['anterior', 'atual']:
            assert abs(Decimal(str(actual['[' + field + ']'])) - Decimal(str(expected[field]))) < Decimal('0.000001'), (actual, expected)
        checks.append({'produto': product, 'ano_atual': year, 'uf': uf, 'dax': actual, 'warehouse': expected})
        print('DAX reconciliado:', product, year, uf, flush=True)
write_json(ROOT / ('evidence/phase2/deployment/rebuild-common-model-check.json' if rebuild else 'evidence/phase2/analytics-history/common-model-check.json'),
           {'status': 'common_station_dax_reconciled', 'environment': 'fabric_rebuild' if rebuild else 'fabric','workspace_id':c['workspace_id'],
            'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks})
