"""Relatorio nacional PBIR: panorama e comparacoes com dimensoes compartilhadas."""
import base64
import json
from client import ROOT, request, definition_operation
from evidence import write_json

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/phase2-bi'
binding = folder / 'binding.json'
state = json.loads(binding.read_text())
schema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/'
pages = ['nacional_panorama', 'nacional_comparacoes']
parts = {
    'definition.pbir': {'$schema': schema+'definitionProperties/2.0.0/schema.json', 'version':'4.0', 'datasetReference':{'byConnection':{'connectionString':'semanticmodelid='+state['semantic_model_id']}}},
    'definition/version.json': {'$schema':schema+'definition/versionMetadata/1.0.0/schema.json','version':'2.0.0'},
    'definition/report.json': {'$schema':schema+'definition/report/3.1.0/schema.json','themeCollection':{'baseTheme':{'name':'CY25SU12','reportVersionAtImport':{'visual':'2.5.0','report':'3.1.0','page':'2.3.0'},'type':'SharedResources'}},'resourcePackages':[{'name':'SharedResources','type':'SharedResources','items':[{'name':'CY25SU12','path':'BaseThemes/CY25SU12.json','type':'BaseTheme'}]}]},
    'definition/pages/pages.json': {'$schema':schema+'definition/pagesMetadata/1.0.0/schema.json','pageOrder':pages,'activePageName':pages[0]}}

def projection(entity, name, measure=False):
    return {'field':{('Measure' if measure else 'Column'):{'Expression':{'SourceRef':{'Entity':entity}},'Property':name}},'queryRef':entity+'.'+name,'nativeQueryRef':name}

def visual(page, name, kind, x, y, width, height, query, title):
    title_properties = {'show': {'expr': {'Literal': {'Value': 'true'}}},
                        'text': {'expr': {'Literal': {'Value': "'"+title.replace("'","''")+"'"}}}}
    parts[f'definition/pages/{page}/visuals/{name}/visual.json'] = {
        '$schema':schema+'definition/visualContainer/2.0.0/schema.json','name':name,
        'position':{'x':x,'y':y,'z':len(parts),'height':height,'width':width,'tabOrder':len(parts)},
        'visual':{'visualType':kind,'query':{'queryState':query},'drillFilterOtherVisuals':True,
            'visualContainerObjects':{'title':[{'properties':title_properties}]}}}

def measure(name):
    return projection('Precos', name, True)

for page, title in zip(pages, ['Panorama nacional', 'Postos e bandeiras']):
    parts[f'definition/pages/{page}/page.json'] = {'$schema':schema+'definition/page/2.0.0/schema.json','name':page,'displayName':title,'displayOption':'FitToPage','height':1000,'width':1440}
    parts[f'definition/pages/{page}/visuals/header/visual.json'] = {
        '$schema':schema+'definition/visualContainer/2.0.0/schema.json','name':'header',
        'position':{'x':24,'y':8,'z':0,'height':70,'width':1392,'tabOrder':0},
        'visual':{'visualType':'textbox','objects':{'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':'Fuel Watch BR | '+title+' | ANP jan–jun 2026','textStyle':{'fontSize':'20pt'}}]},{'textRuns':[{'value':'Selecione um combustível para preços. Líquidos: R$/litro; GNV: R$/m³. Cobertura observada da pesquisa; comparação descritiva.','textStyle':{'fontSize':'11pt'}}]}]}}]}}}
    for index,(entity,column,label) in enumerate([('Produtos','Combustivel','Combustível'),('Estados','UF','UF'),('Semanas','Semana','Semana'),('Marcas','Bandeira','Bandeira')]):
        visual(page,'filter_'+str(index),'slicer',24+index*354,85,336,115,{'Values':{'projections':[projection(entity,column)]}},label)

p = pages[0]
for i,(name,title) in enumerate([('Coletas','Coletas preservadas'),('Postos','Postos observados'),('Municipios observados','Municípios observados'),('Media por coleta','Média por coleta — unidade selecionada')]):
    visual(p,'kpi_'+str(i),'card',24+i*354,215,336,110,{'Values':{'projections':[measure(name)]}},title)
visual(p,'evolucao','lineChart',24,345,810,310,{'Category':{'projections':[projection('Semanas','Semana')]},'Y':{'projections':[measure('Mediana posto semana')]}},'Mediana dos postos por semana — combustível selecionado')
visual(p,'cidades','tableEx',855,345,561,620,{'Values':{'projections':[projection('Cidades','Municipio'),measure('Coletas'),measure('Postos'),measure('Mediana municipal semanal')]}},'Cobertura e mediana municipal semanal')
visual(p,'cobertura','tableEx',24,680,810,285,{'Values':{'projections':[projection('Produtos','Combustivel'),projection('Produtos','Unidade'),measure('Coletas'),measure('Comparacoes elegiveis'),measure('Percentual acima')]}},'Elegibilidade: referência de UF exige ao menos 10 postos')
p = pages[1]
visual(p,'postos','tableEx',24,220,900,745,{'Values':{'projections':[projection('Precos','Posto'),projection('Cidades','Municipio'),measure('Mediana posto semana'),measure('Diferenca UF mediana'),measure('Semanas elegiveis'),measure('Persistencia acima')]}},'Postos: persistência exige ao menos quatro semanas elegíveis')
visual(p,'bandeiras','barChart',945,220,471,450,{'Category':{'projections':[projection('Marcas','Bandeira')]},'Y':{'projections':[measure('Diferenca contextual bandeira')]}},'Bandeiras: diferença da mediana municipal no mesmo contexto')
visual(p,'contextos','tableEx',945,690,471,275,{'Values':{'projections':[projection('Marcas','Bandeira'),measure('Contextos de bandeira')]}},'Contextos comparáveis — município/produto/semana')

for path,obj in parts.items():
    write_json(folder/'report'/path,obj)
payload={'definition':{'parts':[{'path':path,'payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(obj,ensure_ascii=False).encode()).decode()} for path,obj in parts.items()]}}
base=f"workspaces/{c['workspace_id']}/reports"
if not state.get('report_id'):
    matches=[x for x in request('GET',base).json()['value'] if x['displayName']=='Fuel Watch BR Nacional']
    assert len(matches)<=1
    item=matches[0] if matches else definition_operation(base,{'displayName':'Fuel Watch BR Nacional',**payload})
    state['report_id']=item['id'];write_json(binding,state)
else:
    definition_operation(base+'/'+state['report_id']+'/updateDefinition',payload)
actual=definition_operation(base+'/'+state['report_id']+'/getDefinition')
write_json(folder/'report-readback.json',actual)
assert set(parts)<=set(x['path'] for x in actual['definition']['parts'])
print('National report definition read back; rendering pending',flush=True)
