"""Republicacao sintetica de arquivo antigo completo; nunca altera a fonte oficial."""
import csv,hashlib,io,json,sys,zipfile
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from fuelwatch.source import source_record,read_anp
from fuelwatch.contract import validate_row
from fuelwatch.national import national_reference

folder=ROOT/'data/artifacts/history/lab';folder.mkdir(exist_ok=True)
evidence=ROOT/'evidence/phase2/history/lab';evidence.mkdir(exist_ok=True)
summary=json.loads((ROOT/'evidence/phase2/history/reference-summary.json').read_text(encoding='utf8'))
original=next(s for s in summary['sources'] if s['source_id']=='anp_2024_1')
record,payload=source_record('anp_2024_1');raw,meta=read_anp(payload)
baseline=pd.read_parquet(ROOT/'data/artifacts/history/anp_2024_1'/original['source_sha256']/'reference.parquet')
counts=raw.groupby(['CNPJ da Revenda','Produto','Data da Coleta','Unidade de Medida']).size()
candidates=baseline.loc[(baseline.produto=='GASOLINA')&(baseline.data_coleta.map(lambda d:d.month)==1)]
target=None
for row in candidates.to_dict(orient='records'):
    key=(row['cnpj_origem'],row['produto'],row['data_coleta'].strftime('%d/%m/%Y'),'R$ / litro')
    if counts.loc[key]==1:
        target=row;break
assert target is not None
day=target['data_coleta'].strftime('%d/%m/%Y')
station_day=(raw['CNPJ da Revenda']==target['cnpj_origem'])&(raw['Data da Coleta']==day)
price_row=station_day&(raw.Produto==target['produto']);assert price_row.sum()==1
new_price=target['preco_venda']+Decimal('0.123')
raw.loc[price_row,'Valor de Venda']=format(new_price,'.3f').replace('.',',')
raw.loc[station_day,'Bandeira']='LAB_FUELWATCH_CORRECAO'
stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';',lineterminator='\n')
writer.writerow(raw.columns);writer.writerows(raw.itertuples(index=False,name=None));csv_bytes=stream.getvalue().encode('utf-8-sig')
memory=io.BytesIO()
with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as archive:
    member=zipfile.ZipInfo('lab_anp_2024_1.csv',(2024,1,1,0,0,0));member.compress_type=zipfile.ZIP_DEFLATED
    archive.writestr(member,csv_bytes)
changed_zip=memory.getvalue();sha=hashlib.sha256(changed_zip).hexdigest();version=folder/sha;version.mkdir(exist_ok=True)
(version/'lab_ca_2024_01.zip').write_bytes(changed_zip)
parsed,_=read_anp(changed_zip);assert len(parsed)==len(raw)
_,lookup=national_reference(json.loads((ROOT/'.local/national/municipios.json').read_bytes()),json.loads((ROOT/'.local/national/estados.json').read_bytes()))
scope={**original['scope'],'scope_id':'lab_anp_2024_1-br-todos'}
changed=baseline.copy();affected=(changed.cnpj==target['cnpj'])&(changed.data_coleta==target['data_coleta'])
changed.loc[affected,'bandeira_observada']='LAB_FUELWATCH_CORRECAO'
chosen=affected&(changed.produto==target['produto']);assert chosen.sum()==1
changed.loc[chosen,'preco_venda']=new_price
changed['source_sha256']=sha
for index in changed.index[affected]:
    source_index=int(changed.at[index,'source_record'])-2
    changed.at[index,'raw_json']=json.dumps(parsed.iloc[source_index].to_dict(),ensure_ascii=False)
# Validar cada registro efetivamente editado contra o mesmo contrato de producao.
for values in parsed.loc[station_day].itertuples(index=False,name=None):
    typed,reasons=validate_row(dict(zip(parsed.columns,values)),lookup,scope);assert not reasons,reasons
reference=version/'reference.parquet';changed.to_parquet(reference,index=False)
replacement={**original,'scope':scope,'source_sha256':sha,'csv_sha256':hashlib.sha256(csv_bytes).hexdigest(),'parquet_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'reference_path':reference.relative_to(ROOT).as_posix()}
sources=[replacement if s['source_id']=='anp_2024_1' else s for s in summary['sources']]
(folder/'source-summary.json').write_text(json.dumps({'is_synthetic':True,'sources':sources},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
report={'status':'old_file_correction_fixture_prepared_locally','is_synthetic':True,'fabric_executed':False,'source_id':'anp_2024_1','original_source_sha256':original['source_sha256'],'corrected_source_sha256':sha,'source_rows':len(raw),'accepted_rows':len(changed),'target':{'cnpj':target['cnpj'],'data_coleta':str(target['data_coleta']),'produto':target['produto'],'old_price':str(target['preco_venda']),'new_price':str(new_price)},'changed_price_rows':int(chosen.sum()),'changed_station_attribute_rows':int(affected.sum()),'official_inputs_modified':False,'prepared_at_utc':datetime.now(timezone.utc).isoformat()}
(evidence/'fixture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,ensure_ascii=True),flush=True)
