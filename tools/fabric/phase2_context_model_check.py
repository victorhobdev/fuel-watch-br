"""Confere medidas de contexto e a proteção contra mistura de períodos/produtos."""
import json
from datetime import datetime,timezone
from client import ROOT,environment_config
from powerbi import request
from evidence import write_json
c=environment_config();rebuild='--rebuild' in __import__('sys').argv
s=json.loads((ROOT/('.local/phase2-rebuild/bi-history/binding.json' if rebuild else '.local/phase2-bi-history/binding.json')).read_text())
expected=json.loads((ROOT/'evidence/phase2/context/population-answers-fabric.json').read_text())['answers']
def query(dax):
 r=request('POST',f"groups/{c['workspace_id']}/datasets/{s['semantic_model_id']}/executeQueries",{'queries':[{'query':dax}],'serializerSettings':{'includeNulls':True}})
 assert 'error' not in r and 'error' not in r['results'][0],r
 return r['results'][0]['tables'][0]['rows']
checks=[]
for e in expected:
 dax='EVALUATE CALCULATETABLE(ROW("n",[Municipios contexto],"preco",[Mediana preco municipal contexto],"cobertura",[Cobertura por 100mil]),TREATAS({"GASOLINA"},Produtos[Combustivel]),TREATAS({2025},\'Anos contexto\'[Ano]),TREATAS({"'+e['porte_populacional']+'"},Populacao[Porte]))'
 a=query(dax)[0]
 assert a['[n]']==e['municipios']
 assert abs(a['[preco]']-e['mediana_municipios'])<0.000001
 assert abs(a['[cobertura]']-e['mediana_postos_por_100mil'])<0.000001
 checks.append({'porte':e['porte_populacional'],'actual':a})
 print('DAX contexto reconciliado:',e['porte_populacional'],flush=True)
guard=query('EVALUATE ROW("preco",[Mediana preco municipal contexto])')[0]
assert guard.get('[preco]') is None,guard
write_json(ROOT/('evidence/phase2/deployment/rebuild-context-model-check.json' if rebuild else 'evidence/phase2/context/model-check.json'),{'status':'context_dax_reconciled','environment':'fabric_rebuild' if rebuild else 'fabric','workspace_id':c['workspace_id'],'checked_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'mixed_context_price_blank':True})
