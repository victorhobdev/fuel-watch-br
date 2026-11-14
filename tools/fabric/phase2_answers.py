"""Seis perguntas executadas no Warehouse e preservadas como evidencia."""
import json
from datetime import datetime,timezone
from client import ROOT
from warehouse import connect,results
from evidence import write_json
queries={
 'evolucao_uf_produto':"SELECT uf,produto,moeda,unidade,inicio_semana_iso,postos_referencia,mediana_uf FROM analise_br.referencia_uf_semana ORDER BY produto,uf,inicio_semana_iso",
 'municipios_acima':"SELECT TOP(20) * FROM analise_br.municipio_semana WHERE produto='GASOLINA' AND benchmark_elegivel=1 AND inicio_semana_iso=(SELECT MAX(inicio_semana_iso) FROM analise_br.municipio_semana WHERE produto='GASOLINA' AND benchmark_elegivel=1) ORDER BY diferenca_uf DESC,postos_municipio DESC,municipio_ibge",
 'postos_acima':"SELECT TOP(20) cnpj,uf,municipio_ibge_nome,produto,unidade,inicio_semana_iso,preco_mediano,mediana_uf,diferenca_uf,desvio_percentual FROM analise_br.posicao_posto_semana WHERE produto='GASOLINA' AND benchmark_elegivel=1 AND inicio_semana_iso=(SELECT MAX(inicio_semana_iso) FROM analise_br.posicao_posto_semana WHERE produto='GASOLINA' AND benchmark_elegivel=1) ORDER BY diferenca_uf DESC,cnpj",
 'persistencia':"SELECT TOP(20) * FROM analise_br.persistencia_posto WHERE produto='GASOLINA' AND persistencia_percentual IS NOT NULL ORDER BY persistencia_percentual DESC,semanas_com_benchmark DESC,cnpj",
 'bandeiras_contextuais':"SELECT * FROM analise_br.comparacao_bandeira WHERE produto='GASOLINA' AND contextos_comparaveis>=10 ORDER BY uf,diferenca_mediana_contextual DESC,bandeira_observada",
 'cobertura_comparacoes':"SELECT produto,unidade,posicao,COUNT_BIG(*) AS postos_semanas,SUM(coletas) AS coletas FROM analise_br.posicao_posto_semana GROUP BY produto,unidade,posicao ORDER BY produto,posicao"}
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());out=ROOT/'evidence/phase2/analytics/answers';out.mkdir(parents=True,exist_ok=True);report={}
with connect(c) as cn:
 cn.timeout=600
 for name,sql in queries.items():
  rows=results(cn.cursor().execute(sql))[0];write_json(out/(name+'.json'),rows);report[name]={'rows':len(rows),'query':sql};print('Business answer queried',name,len(rows),flush=True)
report={'status':'six_business_queries_executed','environment':'fabric','checked_at_utc':datetime.now(timezone.utc).isoformat(),'queries':report};write_json(out/'queries.json',report)
