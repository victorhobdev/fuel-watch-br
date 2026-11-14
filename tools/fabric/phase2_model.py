"""Modelo nacional com dimensoes compartilhadas, medianas e comparacoes contextuais."""
import base64,json,sys
from client import ROOT,request,definition_operation
from warehouse import connect,results

c=json.loads((ROOT/'.local/fabric-environment.json').read_text());folder=ROOT/'.local/phase2-bi';folder.mkdir(exist_ok=True);binding=folder/'binding.json';state=json.loads(binding.read_text()) if binding.exists() else {}
with connect(c) as cn:
 for name,query in {
  'dim_produto':'SELECT DISTINCT produto,moeda,unidade FROM analise_br.posto_semana',
  'dim_uf':'SELECT DISTINCT uf FROM analise_br.posto_semana',
  'dim_semana':'SELECT DISTINCT inicio_semana_iso FROM analise_br.posto_semana',
  'dim_cidade':"SELECT DISTINCT municipio_ibge,municipio_ibge_nome+' / '+uf AS municipio FROM analise_br.posto_semana",
  'dim_bandeira':'SELECT DISTINCT bandeira_observada FROM analise_br.posto_semana'}.items():
  results(cn.cursor().execute('CREATE OR ALTER VIEW analise_br.'+name+' AS '+query))
# (coluna de origem, nome no modelo, tipo)
dims={
 'Produtos':('dim_produto',[('produto','Combustivel','string'),('moeda','Moeda','string'),('unidade','Unidade','string')]),
 'Estados':('dim_uf',[('uf','UF','string')]),
 'Semanas':('dim_semana',[('inicio_semana_iso','Semana','dateTime')]),
 'Cidades':('dim_cidade',[('municipio_ibge','codigo','string'),('municipio','Municipio','string')]),
 'Marcas':('dim_bandeira',[('bandeira_observada','Bandeira','string')])}
common=[('produto','produto','string'),('moeda','moeda','string'),('unidade','unidade','string'),('uf','uf','string'),('inicio_semana_iso','semana','dateTime'),('municipio_ibge','municipio_ibge','string')]
facts={
 'Precos':('posicao_posto_semana',common+[('cnpj','Posto','string'),('bandeira_observada','bandeira','string'),('preco_mediano','preco_mediano','double'),('coletas','quantidade_coletas','int64'),('soma_precos','soma_precos','double'),('mediana_uf','mediana_uf','double'),('postos_referencia','postos_referencia','int64'),('benchmark_elegivel','benchmark_elegivel','boolean'),('diferenca_uf','diferenca_uf','double'),('desvio_percentual','desvio_percentual','double'),('posicao','posicao','string')]),
 'Municipios':('municipio_semana',common+[('postos_municipio','postos_municipio','int64'),('mediana_municipio','mediana_municipio','double'),('mediana_uf','mediana_uf','double'),('benchmark_elegivel','benchmark_elegivel','boolean'),('diferenca_uf','diferenca_uf','double')]),
 'Bandeiras':('bandeira_contexto',common+[('bandeira_observada','bandeira','string'),('postos_bandeira','postos_bandeira','int64'),('mediana_bandeira','mediana_bandeira','double'),('diferenca_contexto','diferenca_contexto','double')])}
price_guard='HASONEVALUE(Produtos[Combustivel]) && HASONEVALUE(Produtos[Unidade]) && HASONEVALUE(Produtos[Moeda])'
measure_specs=[
 ('Coletas','SUM(Precos[quantidade_coletas])','#,0'),
 ('Postos','DISTINCTCOUNT(Precos[Posto])','#,0'),
 ('Municipios observados','DISTINCTCOUNT(Precos[municipio_ibge])','#,0'),
 ('Media por coleta',f'IF({price_guard},DIVIDE(SUM(Precos[soma_precos]),[Coletas]))','R$ #,0.000'),
 ('Mediana posto semana',f'IF({price_guard},MEDIAN(Precos[preco_mediano]))','R$ #,0.000'),
 ('Comparacoes elegiveis','CALCULATE(COUNTROWS(Precos),Precos[benchmark_elegivel]=TRUE())','#,0'),
 ('Comparacoes acima','CALCULATE(COUNTROWS(Precos),Precos[posicao]="acima")','#,0'),
 ('Percentual acima','DIVIDE([Comparacoes acima],[Comparacoes elegiveis])','0.0%'),
 ('Diferenca UF mediana',f'IF({price_guard},MEDIAN(Precos[diferenca_uf]))','R$ #,0.000'),
 ('Mediana municipal semanal',f'IF({price_guard},CALCULATE(MEDIAN(Municipios[mediana_municipio]),Municipios[benchmark_elegivel]=TRUE()))','R$ #,0.000'),
 ('Diferenca contextual bandeira',f'IF({price_guard},MEDIAN(Bandeiras[diferenca_contexto]))','R$ #,0.000'),
 ('Contextos de bandeira','COUNTROWS(Bandeiras)','#,0'),
 ('Semanas elegiveis','CALCULATE(COUNTROWS(Precos),Precos[benchmark_elegivel]=TRUE())','#,0'),
 ('Persistencia acima',f'IF({price_guard} && HASONEVALUE(Precos[Posto]) && [Semanas elegiveis]>=4,DIVIDE([Comparacoes acima],[Semanas elegiveis]))','0.0%')]
tables=[]
for name,(item,fields) in {**dims,**facts}.items():
 columns=[{'name':alias,'sourceColumn':source,'dataType':kind,'summarizeBy':'none','isHidden': name in facts and alias!='Posto' or alias=='codigo'} for source,alias,kind in fields]
 expression=['let',f'    Source = Sql.Database("{c["warehouse_server"]}", "{c["warehouse_database"]}"),',f'    Data = Source{{[Schema="analise_br",Item="{item}"]}}[Data]','in','    Data']
 t={'name':name,'columns':columns,'partitions':[{'name':'DirectQuery','mode':'directQuery','source':{'type':'m','expression':expression}}]}
 if name=='Precos':t['measures']=[{'name':n,'expression':e,'formatString':fmt} for n,e,fmt in measure_specs]
 tables.append(t)
relationships=[]
for fact in facts:
 for dim,source,target in [('Produtos','produto','Combustivel'),('Estados','uf','UF'),('Semanas','semana','Semana'),('Cidades','municipio_ibge','codigo')]+([('Marcas','bandeira','Bandeira')] if fact in {'Precos','Bandeiras'} else []):
  relationships.append({'name':fact+'_'+dim,'fromTable':fact,'fromColumn':source,'toTable':dim,'toColumn':target,'fromCardinality':'many','toCardinality':'one','crossFilteringBehavior':'oneDirection'})
model={'compatibilityLevel':1604,'model':{'culture':'pt-BR','sourceQueryCulture':'pt-BR','defaultPowerBIDataSourceVersion':'powerBI_V3','discourageImplicitMeasures':True,'tables':tables,'relationships':relationships}}
parts=[{'path':name,'payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(obj,ensure_ascii=False).encode()).decode()} for name,obj in [('model.bim',model),('definition.pbism',{'version':'5.0','settings':{'qnaEnabled':False}})]];payload={'definition':{'format':'TMSL','parts':parts}};(folder/'model-request.private.json').write_text(json.dumps(payload,indent=2))
name='sm_fuelwatch_nacional'
if not state.get('semantic_model_id'):
 matches=[x for x in request('GET',f"workspaces/{c['workspace_id']}/semanticModels").json()['value'] if x['displayName']==name];assert len(matches)<=1
 item=matches[0] if matches else definition_operation(f"workspaces/{c['workspace_id']}/semanticModels",{'displayName':name,'description':'Observatorio nacional ANP: benchmarks por posto/semana; produtos e unidades separados',**payload});state['semantic_model_id']=item['id'];binding.write_text(json.dumps(state,indent=2))
else:
 definition_operation(f"workspaces/{c['workspace_id']}/semanticModels/{state['semantic_model_id']}/updateDefinition",payload)
readback=definition_operation(f"workspaces/{c['workspace_id']}/semanticModels/{state['semantic_model_id']}/getDefinition?format=TMSL");(folder/'model-readback.private.json').write_text(json.dumps(readback,indent=2));actual=json.loads(base64.b64decode(next(x for x in readback['definition']['parts'] if x['path']=='model.bim')['payload']));assert {t['name'] for t in actual['model']['tables']}==set(dims)|set(facts);print('National semantic model created/read back; DAX verification pending',flush=True)
