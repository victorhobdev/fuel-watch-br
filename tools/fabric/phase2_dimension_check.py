"""Diagnostico de membros em branco sem esconder orfaos no relatorio."""
import json
from client import ROOT
from powerbi import request
from warehouse import connect, results
from evidence import write_json

c = json.loads((ROOT/'.local/fabric-environment.json').read_text())
s = json.loads((ROOT/'.local/phase2-bi/binding.json').read_text())
checks = {}
with connect(c) as cn:
    cn.timeout = 600
    for dim, view, key, modelkey, factkey in [
        ('Estados','dim_uf','uf','UF','uf'),
        ('Marcas','dim_bandeira','bandeira_observada','Bandeira','bandeira_observada'),
        ('Cidades','dim_cidade','municipio_ibge','codigo','municipio_ibge'),
        ('Produtos','dim_produto','produto','Combustivel','produto'),
        ('Semanas','dim_semana','inicio_semana_iso','Semana','inicio_semana_iso')]:
        sql = f'''SELECT COUNT_BIG(*) AS rows,
            SUM(CASE WHEN d.{key} IS NULL THEN 1 ELSE 0 END) AS orphan_rows
            FROM analise_br.posto_semana f LEFT JOIN analise_br.{view} d ON f.{factkey}=d.{key}'''
        actual = results(cn.cursor().execute(sql))[0][0]
        assert actual['orphan_rows'] == 0, (dim, actual)
        dax = f'''EVALUATE ROW("distinct", COUNTROWS(DISTINCT({dim}[{modelkey}])) ,
            "values", COUNTROWS(VALUES({dim}[{modelkey}])) ,
            "blank_fact_rows", CALCULATE(COUNTROWS(Precos), FILTER(VALUES({dim}[{modelkey}]), ISBLANK({dim}[{modelkey}]))))'''
        response = request('POST',f"groups/{c['workspace_id']}/datasets/{s['semantic_model_id']}/executeQueries",{'queries':[{'query':dax}],'serializerSettings':{'includeNulls':True}})
        assert 'error' not in response, response
        result = response['results'][0]
        assert 'error' not in result, result
        row = result['tables'][0]['rows'][0]
        assert row.get('[blank_fact_rows]') in (None, 0), (dim, row)
        additional=[]
        for fact in ['municipio_semana','bandeira_contexto']:
            if dim=='Marcas' and fact=='municipio_semana':
                continue
            sql=f'SELECT COUNT_BIG(*) AS rows,SUM(CASE WHEN d.{key} IS NULL THEN 1 ELSE 0 END) AS orphan_rows FROM analise_br.{fact} f LEFT JOIN analise_br.{view} d ON f.{factkey}=d.{key}'
            joined=results(cn.cursor().execute(sql))[0][0]
            assert joined['orphan_rows']==0,(dim,fact,joined)
            additional.append({'fact':fact,**joined})
        checks[dim]={'warehouse':actual,'other_facts':additional,'dax':row}
        print(dim, json.dumps(checks[dim],default=str),flush=True)
write_json(ROOT/'evidence/phase2/analytics/dimensions.json',{'status':'no_orphans_in_station_fact','checks':checks})
