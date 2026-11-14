"""Fixtures de borda no Warehouse, isolados dos dados oficiais."""
import json,re
from datetime import date,timedelta,datetime,timezone
from decimal import Decimal
from client import ROOT
from warehouse import connect,results

c=json.loads((ROOT/'.local/fabric-environment.json').read_text());rows=[]
def add(cnpj,product,unit,uf,mun,name,brand,day,price):
 rows.append((f'{cnpj:014d}',product,'BRL',unit,day-timedelta(days=day.weekday()),day,uf,mun,name,brand,'POSTO SINTETICO',Decimal(str(price)),True))
for w in range(4):
 day=date(2026,1,5)+timedelta(weeks=w)
 for i in range(1,13):
  mun='3300001' if i<=6 else '3300002' if i<=10 else '3300003';brand='BRANCA' if i%2 else 'SINTETICA'
  add(i,'GASOLINA','litro','RJ',mun,'Municipio sintetico '+mun,brand,day,i)
  if i==1:add(i,'GASOLINA','litro','RJ',mun,'Municipio sintetico '+mun,brand,day+timedelta(days=1),3)
  add(i,'GNV','m3','RJ',mun,'Municipio sintetico '+mun,brand,day,i*10)
  add(i+200,'GASOLINA','litro','MG','3100001','Municipio empate',brand,day,6)
 for i in range(1,10):add(i+100,'GASOLINA','litro','SP','3500001','Municipio cobertura','BRANCA',day,'6.100')
add(900001,'GASOLINA','litro','RJ','3300001','Municipio sintetico 3300001','BRANCA',date(2026,1,5),3)
add(900001,'GASOLINA','litro','SP','3500001','Municipio cobertura','BRANCA',date(2026,1,6),7)
checks=[]
with connect(c) as cn:
 cn.timeout=600;cur=cn.cursor();results(cur.execute("IF SCHEMA_ID('lab_analitica') IS NULL EXEC('CREATE SCHEMA lab_analitica');"))
 results(cur.execute("IF OBJECT_ID('lab_analitica.coletas') IS NULL CREATE TABLE lab_analitica.coletas(cnpj varchar(14),produto varchar(80),moeda varchar(3),unidade varchar(30),inicio_semana_iso date,data_coleta date,uf varchar(2),municipio_ibge varchar(7),municipio_ibge_nome varchar(200),bandeira_observada varchar(300),revenda_observada varchar(1000),preco_venda decimal(10,3),is_synthetic bit);"))
 assert cur.execute('SELECT COUNT_BIG(*) FROM lab_analitica.coletas WHERE is_synthetic<>1 OR is_synthetic IS NULL').fetchone()[0]==0
 results(cur.execute('DELETE FROM lab_analitica.coletas'));cur.executemany('INSERT INTO lab_analitica.coletas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
 sql=(ROOT/'sql/analytics/01_national_benchmarks.sql').read_text(encoding='utf8').replace('analise_br','lab_analitica').replace('gold_br.coletas','lab_analitica.coletas');assert 'gold_br.' not in sql and 'analise_br' not in sql
 for statement in re.split(r'(?m)^GO\s*$',sql):
  if statement.strip():results(cur.execute(statement))
 def check(name,sql,expected):
  actual=cur.execute(sql).fetchone()[0];assert actual==expected,(name,str(actual),str(expected));checks.append({'case':name,'actual':str(actual),'passed':True})
 check('posto_semana_preserva_grao', 'SELECT COUNT_BIG(*) FROM lab_analitica.posto_semana',181)
 check('mediana_posto_duas_coletas',"SELECT preco_mediano FROM lab_analitica.posto_semana WHERE cnpj='00000000000001' AND produto='GASOLINA' AND inicio_semana_iso='2026-01-05'",Decimal('2.000000'))
 check('posto_tem_um_peso_na_uf',"SELECT mediana_uf FROM lab_analitica.referencia_uf_semana WHERE uf='RJ' AND produto='GASOLINA' AND inicio_semana_iso='2026-01-05'",Decimal('6.500000'))
 check('gnv_nao_mistura_unidade',"SELECT mediana_uf FROM lab_analitica.referencia_uf_semana WHERE uf='RJ' AND produto='GNV' AND inicio_semana_iso='2026-01-05'",Decimal('65.000000'))
 check('uf_insuficiente_nao_recebe_diferenca',"SELECT COUNT_BIG(*) FROM lab_analitica.posicao_posto_semana WHERE uf='SP' AND (benchmark_elegivel=1 OR diferenca_uf IS NOT NULL OR desvio_percentual IS NOT NULL)",0)
 check('municipio_insuficiente_nao_recebe_diferenca',"SELECT COUNT_BIG(*) FROM lab_analitica.municipio_semana WHERE municipio_ibge='3300003' AND (benchmark_elegivel=1 OR diferenca_uf IS NOT NULL)",0)
 check('atributo_ambiguo_excluido',"SELECT COUNT_BIG(*) FROM lab_analitica.posicao_posto_semana WHERE cnpj='00000000900001' AND comparacao_valida=0 AND benchmark_elegivel=0 AND posicao='atributo_ambiguo'",1)
 check('empates_nao_viram_acima',"SELECT COUNT_BIG(*) FROM lab_analitica.posicao_posto_semana WHERE uf='MG' AND (posicao<>'igual' OR diferenca_uf<>0 OR desvio_percentual<>0)",0)
 check('persistencia_usa_semanas_elegiveis',"SELECT persistencia_percentual FROM lab_analitica.persistencia_posto WHERE cnpj='00000000000012' AND uf='RJ' AND produto='GASOLINA'",Decimal('100.000000'))
 check('persistencia_insuficiente_e_null',"SELECT COUNT_BIG(*) FROM lab_analitica.persistencia_posto WHERE uf='SP' AND persistencia_percentual IS NOT NULL",0)
 check('contextos_bandeira_sao_comparaveis',"SELECT COUNT_BIG(*) FROM lab_analitica.bandeira_contexto WHERE postos_bandeira<2 OR bandeiras_contexto<2 OR postos_municipio<3",0)
 check('mediana_municipal_dos_postos',"SELECT mediana_municipio FROM lab_analitica.municipio_semana WHERE municipio_ibge='3300001' AND produto='GASOLINA' AND inicio_semana_iso='2026-01-05'",Decimal('3.500000'))
r={'status':'analytical_edge_fixture_passed','environment':'fabric','synthetic_rows':len(rows),'checks':checks,'official_data_mutated':False,'checked_at_utc':datetime.now(timezone.utc).isoformat()};out=ROOT/'evidence/phase2/analytics/edge-fixture.json';out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
