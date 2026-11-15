"""Relatorio nacional PBIR: panorama e comparacoes com dimensoes compartilhadas."""
import base64
import json
import sys
from client import ROOT, request, definition_operation,environment_config
from evidence import write_json

history = '--history' in sys.argv
rebuild = '--rebuild' in sys.argv
assert not rebuild or history
c = environment_config()
folder = ROOT / ('.local/phase2-rebuild/bi-history' if rebuild else ('.local/phase2-bi-history' if history else '.local/phase2-bi'))
binding = folder / 'binding.json'
state = json.loads(binding.read_text())
schema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/'
pages = ['nacional_panorama', 'nacional_comparacoes']
if history:
    pages.append('postos_comuns')
    pages.append('contexto')
parts = {
    'definition.pbir': {'$schema': schema+'definitionProperties/2.0.0/schema.json', 'version':'4.0', 'datasetReference':{'byConnection':{'connectionString':'semanticmodelid='+state['semantic_model_id']}}},
    'definition/version.json': {'$schema':schema+'definition/versionMetadata/1.0.0/schema.json','version':'2.0.0'},
    'definition/report.json': {'$schema':schema+'definition/report/3.1.0/schema.json','themeCollection':{'baseTheme':{'name':'CY25SU12','reportVersionAtImport':{'visual':'2.5.0','report':'3.1.0','page':'2.3.0'},'type':'SharedResources'}},'resourcePackages':[{'name':'SharedResources','type':'SharedResources','items':[{'name':'CY25SU12','path':'BaseThemes/CY25SU12.json','type':'BaseTheme'}]}]},
    'definition/pages/pages.json': {'$schema':schema+'definition/pagesMetadata/1.0.0/schema.json','pageOrder':pages,'activePageName':pages[0]}}

def projection(entity, name, measure=False):
    return {'field':{('Measure' if measure else 'Column'):{'Expression':{'SourceRef':{'Entity':entity}},'Property':name}},'queryRef':entity+'.'+name,'nativeQueryRef':name}

def visual(page, name, kind, x, y, width, height, query, title, filter_config=None):
    title_properties = {'show': {'expr': {'Literal': {'Value': 'true'}}},
                        'text': {'expr': {'Literal': {'Value': "'"+title.replace("'","''")+"'"}}}}
    config = {
        '$schema':schema+'definition/visualContainer/2.0.0/schema.json','name':name,
        'position':{'x':x,'y':y,'z':len(parts),'height':height,'width':width,'tabOrder':len(parts)},
        'visual':{'visualType':kind,'query':{'queryState':query},'drillFilterOtherVisuals':True,
            'visualContainerObjects':{'title':[{'properties':title_properties}]}}}
    if filter_config:
        config['filterConfig'] = filter_config
    parts[f'definition/pages/{page}/visuals/{name}/visual.json'] = config

def slicer_filter(entity, column, selected):
    alias = 's'
    field = {'Column':{'Expression':{'SourceRef':{'Source':alias}},'Property':column}}
    literal = {'Literal':{'Value':("'"+selected.replace("'", "''")+"'") if isinstance(selected,str) else str(selected)+'L'}}
    return {'filter':{'Version':2,'From':[{'Name':alias,'Entity':entity,'Type':0}],
        'Where':[{'Condition':{'In':{'Expressions':[field],'Values':[[literal]]}},
            'Annotations':{'filterExpressionMetadata':{'expressions':[field],
                'decomposedIdentities':{'values':[[{'0':[literal]}]],'columns':[{'value':field}]},
                'valueMap':[{'0':str(selected)}]}}}]}}

def configure_slicer(page, name, entity, column, mode='Dropdown', selected=None, sync_group=None):
    key = f'definition/pages/{page}/visuals/{name}/visual.json'
    item = parts[key]
    item['position']['height'] = 112 if mode == 'Between' else 80
    item['visual']['objects'] = {'data':[{'properties':{'mode':{'expr':{'Literal':{'Value':f"'{mode}'"}}}}}]}
    if selected is not None:
        item['visual']['objects']['general'] = [{'properties':{'filter':slicer_filter(entity,column,selected)}}]
    if sync_group:
        item['visual']['syncGroup'] = {'groupName':sync_group,'fieldChanges':True,'filterChanges':True}
    item['visual']['visualContainerObjects']['padding'] = [{'properties':{
        'top':{'expr':{'Literal':{'Value':'8D'} }},'bottom':{'expr':{'Literal':{'Value':'8D'} }},
        'left':{'expr':{'Literal':{'Value':'8D'} }},'right':{'expr':{'Literal':{'Value':'8D'} }} }}]

def top_n_stations_filter():
    station = {'Column':{'Expression':{'SourceRef':{'Source':'p'}},'Property':'Posto'}}
    ranking = {'Aggregation':{'Expression':{'Column':{'Expression':{'SourceRef':{'Source':'d'}},
        'Property':'desvio_percentual'}},'Function':4}}
    subquery = {'Version':2,'From':[{'Name':'d','Entity':'Precos','Type':0}],
        'Select':[{'Column':{'Expression':{'SourceRef':{'Source':'d'}},'Property':'Posto'},'Name':'field'}],
        'OrderBy':[{'Direction':2,'Expression':ranking}],'Top':100}
    return {'filters':[{'name':'top_100_stations_by_weekly_uf_deviation',
        'field':{'Column':{'Expression':{'SourceRef':{'Entity':'Precos'}},'Property':'Posto'}},
        'type':'TopN','filter':{'Version':2,'From':[
            {'Name':'subquery','Expression':{'Subquery':{'Query':subquery}},'Type':2},
            {'Name':'p','Entity':'Precos','Type':0}],
            'Where':[{'Condition':{'In':{'Expressions':[station],
                'Table':{'SourceRef':{'Source':'subquery'}}}}}]},'howCreated':'User'}]}

def measure(name):
    return projection('Precos', name, True)

for page, title in zip(pages, ['Panorama nacional', 'Postos e bandeiras']):
    parts[f'definition/pages/{page}/page.json'] = {'$schema':schema+'definition/page/2.0.0/schema.json','name':page,'displayName':title,'displayOption':'FitToPage','height':1000,'width':1440}
    period_text = 'ANP 2024–jun 2026' if history else 'ANP jan–jun 2026'
    parts[f'definition/pages/{page}/visuals/header/visual.json'] = {
        '$schema':schema+'definition/visualContainer/2.0.0/schema.json','name':'header',
        'position':{'x':24,'y':8,'z':0,'height':70,'width':1392,'tabOrder':0},
        'visual':{'visualType':'textbox','objects':{'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':'Fuel Watch BR | '+title+' | '+period_text,'textStyle':{'fontSize':'20pt'}}]},{'textRuns':[{'value':'Selecione um combustível para preços. Líquidos: R$/litro; GNV: R$/m³. Cobertura observada da pesquisa; comparação descritiva.','textStyle':{'fontSize':'11pt'}}]}]}}]}}}
    for index,(entity,column,label) in enumerate([('Produtos','Combustivel','Combustível'),('Estados','UF','UF'),('Semanas','Semana','Semana'),('Marcas','Bandeira','Bandeira')]):
        visual(page,'filter_'+str(index),'slicer',24+index*354,85,336,115,{'Values':{'projections':[projection(entity,column)]}},label)
        configure_slicer(page,'filter_'+str(index),entity,column,
            mode='Between' if entity=='Semanas' else 'Dropdown',
            selected='GASOLINA' if entity=='Produtos' else None,
            sync_group='FuelSync' if entity=='Produtos' else 'UfSync' if entity=='Estados' else None)

p = pages[0]
for i,(name,title) in enumerate([('Coletas','Coletas preservadas'),('Postos','Postos observados'),('Municipios observados','Municípios observados'),('Media por coleta','Média por coleta — unidade selecionada')]):
    visual(p,'kpi_'+str(i),'card',24+i*354,215,336,110,{'Values':{'projections':[measure(name)]}},title)
visual(p,'evolucao','lineChart',24,345,810,310,{'Category':{'projections':[projection('Semanas','Semana')]},'Y':{'projections':[measure('Mediana posto semana')]}},'Mediana dos postos por semana — combustível selecionado')
visual(p,'cidades','tableEx',855,345,561,620,{'Values':{'projections':[projection('Cidades','Municipio'),measure('Coletas'),measure('Postos'),measure('Mediana municipal semanal')]}},'Cobertura e mediana municipal semanal')
visual(p,'cobertura','tableEx',24,680,810,285,{'Values':{'projections':[projection('Produtos','Combustivel'),projection('Produtos','Unidade'),measure('Coletas'),measure('Comparacoes elegiveis'),measure('Percentual acima')]}},'Elegibilidade: referência de UF exige ao menos 10 postos')
p = pages[1]
visual(p,'postos','tableEx',24,220,900,745,{'Values':{'projections':[projection('Precos','Posto'),projection('Cidades','Municipio'),measure('Maior desvio semanal da UF'),measure('Diferenca UF mediana'),measure('Semanas elegiveis'),measure('Persistencia acima')]}},'100 postos com maior desvio semanal da mediana da UF; persistência exige quatro semanas elegíveis',top_n_stations_filter())
parts[f'definition/pages/{p}/visuals/postos/visual.json']['visual']['query']['sortDefinition'] = {'sort':[{'field':measure('Maior desvio semanal da UF')['field'],'direction':'Descending'}],'isDefaultSort':False}
visual(p,'bandeiras','barChart',945,220,471,450,{'Category':{'projections':[projection('Marcas','Bandeira')]},'Y':{'projections':[measure('Diferenca contextual bandeira')]}},'Bandeiras: diferença da mediana municipal no mesmo contexto')
visual(p,'contextos','tableEx',945,690,471,275,{'Values':{'projections':[projection('Marcas','Bandeira'),measure('Contextos de bandeira')]}},'Contextos comparáveis — município/produto/semana')

if history:
    p = 'postos_comuns'
    parts[f'definition/pages/{p}/page.json'] = {'$schema':schema+'definition/page/2.0.0/schema.json','name':p,'displayName':'Postos comuns','displayOption':'FitToPage','height':1000,'width':1440}
    parts[f'definition/pages/{p}/visuals/header/visual.json'] = {
        '$schema':schema+'definition/visualContainer/2.0.0/schema.json','name':'header',
        'position':{'x':24,'y':8,'z':0,'height':100,'width':1392,'tabOrder':0},
        'visual':{'visualType':'textbox','objects':{'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':'Postos comuns | primeiros semestres consecutivos','textStyle':{'fontSize':'20pt'}}]},{'textRuns':[{'value':'Selecione um combustível e ano atual. Cada posto tem o mesmo peso; preços nominais. Ausência de coleta não é preço zero. Mudanças na amostra e cobertura ainda importam.','textStyle':{'fontSize':'11pt'}}]}]}}]}}}
    for i,(entity,column,label) in enumerate([('Produtos','Combustivel','Combustível'),('Periodos','Ano atual','Ano atual'),('Estados','UF','UF')]):
        visual(p,'filter_'+str(i),'slicer',24+i*464,120,440,115,{'Values':{'projections':[projection(entity,column)]}},label)
        configure_slicer(p,'filter_'+str(i),entity,column,selected=(
            'GASOLINA' if entity=='Produtos' else 2026 if entity=='Periodos' else None),
            sync_group='FuelSync' if entity=='Produtos' else 'UfSync' if entity=='Estados' else None)
    for i,(name,title) in enumerate([('Postos comparaveis','Postos comuns'),('Preco anterior postos comuns','Preço médio anterior por posto'),('Preco atual postos comuns','Preço médio atual por posto'),('Variacao postos comuns','Variação nominal')]):
        visual(p,'kpi_'+str(i),'card',24+i*354,250,336,110,{'Values':{'projections':[projection('Postos comuns',name,True)]}},title)
    visual(p,'estados','tableEx',24,370,1392,620,{'Values':{'projections':[projection('Estados','UF'),projection('Postos comuns','Postos comparaveis',True),projection('Postos comuns','Preco anterior postos comuns',True),projection('Postos comuns','Preco atual postos comuns',True),projection('Postos comuns','Variacao postos comuns',True)]}},'Comparação por UF — posto e localidade presentes nos dois períodos')

if history:
    p='contexto'
    parts[f'definition/pages/{p}/page.json']={'$schema':schema+'definition/page/2.0.0/schema.json','name':p,'displayName':'Contexto e cobertura','displayOption':'FitToPage','height':1000,'width':1440}
    parts[f'definition/pages/{p}/visuals/header/visual.json']={
        '$schema':schema+'definition/visualContainer/2.0.0/schema.json','name':'header',
        'position':{'x':24,'y':8,'z':0,'height':110,'width':1392,'tabOrder':0},
        'visual':{'visualType':'textbox','objects':{'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':'Contexto municipal | população e cobertura meteorológica','textStyle':{'fontSize':'20pt'}}]},{'textRuns':[{'value':'População: selecione combustível e ano; mediana por município, referência em julho. Cobertura climática: todo o histórico 2024–jun/2026, independente desses filtros. Associação descritiva; população não pondera preços.','textStyle':{'fontSize':'11pt'}}]}]}}]}}}
    for i,(entity,column,title) in enumerate([('Produtos','Combustivel','Combustível — população'),('Anos contexto','Ano','Ano — população')]):
        visual(p,'filter_'+str(i),'slicer',24+i*700,130,670,110,{'Values':{'projections':[projection(entity,column)]}},title)
        configure_slicer(p,'filter_'+str(i),entity,column,selected='GASOLINA' if entity=='Produtos' else 2026,
            sync_group='FuelSync' if entity=='Produtos' else None)
    visual(p,'populacao','tableEx',24,265,1392,320,{'Values':{'projections':[projection('Populacao','Porte'),projection('Populacao','Municipios contexto',True),projection('Populacao','Mediana preco municipal contexto',True),projection('Populacao','Cobertura por 100mil',True)]}},'Porte e preço: cobertura indica postos pesquisados, não todos os existentes')
    visual(p,'clima','tableEx',24,610,1392,320,{'Values':{'projections':[projection('Clima','Cobertura climatica'),projection('Clima','Municipios semanas clima',True)]}},'Cobertura meteorológica de todo o histórico — mínimo de 80% das horas por variável')

for path,obj in parts.items():
    write_json(folder/'report'/path,obj)
payload={'definition':{'parts':[{'path':path,'payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(obj,ensure_ascii=False).encode()).decode()} for path,obj in parts.items()]}}
base=f"workspaces/{c['workspace_id']}/reports"
report_name='Fuel Watch BR Histórico' if history else 'Fuel Watch BR Nacional'
if not state.get('report_id'):
    matches=[x for x in request('GET',base).json()['value'] if x['displayName']==report_name]
    assert len(matches)<=1
    item=matches[0] if matches else definition_operation(base,{'displayName':report_name,**payload})
    state['report_id']=item['id'];write_json(binding,state)
else:
    definition_operation(base+'/'+state['report_id']+'/updateDefinition',payload)
actual=definition_operation(base+'/'+state['report_id']+'/getDefinition')
write_json(folder/'report-readback.json',actual)
assert set(parts)<=set(x['path'] for x in actual['definition']['parts'])
print('National report definition read back; rendering pending',flush=True)
