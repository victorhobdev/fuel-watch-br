"""Referencia meteorologica horaria/semanal e join municipal sem multiplicacao."""
import json,zipfile
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1];folder=root/'data/artifacts/context';policy=json.loads((root/'config/weather.json').read_text())
m=json.loads((root/'evidence/phase2/history/publication-reference.json').read_text(encoding='utf8'))
start=pd.Timestamp(m['date_start'],tz='UTC');end=pd.Timestamp(m['date_end'],tz='UTC')+pd.Timedelta(days=1)
catalog=pd.read_parquet(folder/'station_catalog.parquet');associations=pd.read_parquet(folder/'station_associations.parquet')
selected=set(associations.station_id.dropna())
records=[json.loads(line) for line in (root/'data/manifest/downloads.jsonl').read_text(encoding='utf8').splitlines()]
frames=[];quality=[];invalid_time=[]
for year in [2024,2025,2026]:
    source=next(r for r in reversed(records) if r['source_id']=='inmet_'+str(year) and r['status'] in ['downloaded','identical_content'])
    stations=catalog.loc[(catalog.year==year)&catalog.station_id.isin(selected)]
    with zipfile.ZipFile(root/source['path']) as archive:
        for station in stations.to_dict(orient='records'):
            with archive.open(station['member']) as stream:
                raw=pd.read_csv(stream,sep=';',encoding=station['encoding'],skiprows=8,usecols=[0,1,2,7],dtype=str,keep_default_na=False)
            columns=raw.columns.tolist();assert 'UTC' in columns[1] and columns[2].upper().startswith('PRECIPITA') and 'BULBO SECO' in columns[3].upper()
            dates=pd.to_datetime(raw.iloc[:,0].str.replace('/','-',regex=False),format='%Y-%m-%d',errors='coerce',utc=True)
            hours=raw.iloc[:,1].str.replace(r'\s+','',regex=True)
            valid_time=dates.notna()&hours.str.fullmatch(r'(?:[01][0-9]|2[0-3])00UTC')&dates.dt.year.eq(year)
            if (~valid_time).any():
                bad=raw.loc[~valid_time].copy();bad['station_id']=station['station_id'];bad['source_year']=year;bad['source_record']=bad.index+10;invalid_time.append(bad)
            timestamp=dates+pd.to_timedelta(pd.to_numeric(hours.str[:2],errors='coerce'),unit='h')
            values={}
            missing={};invalid={}
            for name,column in [('precipitation_mm',columns[2]),('temperature_degC',columns[3])]:
                text=raw[column].str.strip();numeric=pd.to_numeric(text.str.replace(',','.',regex=False),errors='coerce')
                absent=text.eq('')|numeric.isin(policy['missing_numeric_sentinels'])
                good=numeric.notna()&numeric.abs().lt(float('inf'))&~absent
                if name=='precipitation_mm':good &= numeric.ge(0)
                else:good &= numeric.between(*policy['temperature_screening_degC'])
                values[name]=numeric.where(good)
                missing[name]=int(absent.sum());invalid[name]=int((~absent&~good).sum())
            frame=pd.DataFrame({'station_id':station['station_id'],'timestamp_utc':timestamp,**values,'source_year':year,'source_record':raw.index+10,'source_sha256':source['sha256']})
            within=valid_time&timestamp.ge(start)&timestamp.lt(end)
            frames.append(frame.loc[within])
            quality.append({'year':year,'station_id':station['station_id'],'source_sha256':source['sha256'],'source_member':station['member'],'received':len(raw),'within_price_window':int(within.sum()),'invalid_timestamp':int((~valid_time).sum()),'missing':missing,'invalid_measurement':invalid})
    print('Hourly meteorology parsed',year,len(stations),'stations',flush=True)
hourly=pd.concat(frames,ignore_index=True);del frames
context_key=['station_id','timestamp_utc','temperature_degC','precipitation_mm']
duplicates=int(hourly.duplicated(context_key).sum());hourly=hourly.drop_duplicates(context_key)
conflict=hourly.duplicated(['station_id','timestamp_utc'],keep=False)
hourly.loc[conflict].to_parquet(folder/'weather_hour_conflicts.parquet',index=False,coerce_timestamps='us')
conflicts=int(conflict.sum());hourly=hourly.loc[~conflict].copy()
assert not hourly.duplicated(['station_id','timestamp_utc']).any()
hourly.to_parquet(folder/'weather_hourly.parquet',index=False,coerce_timestamps='us')
if invalid_time:pd.concat(invalid_time,ignore_index=True).to_parquet(folder/'weather_invalid_timestamps.parquet',index=False)
dates=hourly.timestamp_utc.dt.tz_localize(None).dt.normalize();hourly['week_start']=dates-pd.to_timedelta(dates.dt.dayofweek,unit='d')
weekly=hourly.groupby(['station_id','week_start']).agg(reported_hours=('timestamp_utc','size'),valid_temperature_hours=('temperature_degC','count'),temperature_sum=('temperature_degC','sum'),valid_rain_hours=('precipitation_mm','count'),rain_sum=('precipitation_mm','sum')).reset_index()
def expected_hours(week):
    w=pd.Timestamp(week,tz='UTC');return int((min(w+pd.Timedelta(days=7),end)-max(w,start)).total_seconds()/3600)
weekly['expected_hours']=weekly.week_start.map(expected_hours)
assert (weekly[['valid_temperature_hours','valid_rain_hours']].max(axis=1)<=weekly.expected_hours).all()
weekly['temperature_fraction']=weekly.valid_temperature_hours/weekly.expected_hours
weekly['rain_fraction']=weekly.valid_rain_hours/weekly.expected_hours
weekly['temperature_eligible']=weekly.temperature_fraction.ge(policy['minimum_valid_hour_fraction_per_variable'])
weekly['rain_eligible']=weekly.rain_fraction.ge(policy['minimum_valid_hour_fraction_per_variable'])
weekly['mean_temperature_degC']=(weekly.temperature_sum/weekly.valid_temperature_hours).round(6).where(weekly.temperature_eligible)
weekly['observed_rain_mm']=weekly.rain_sum.round(6).where(weekly.rain_eligible)
weekly['partial_boundary_week']=weekly.expected_hours.lt(168)
weekly.week_start=weekly.week_start.dt.date
weekly.to_parquet(folder/'weather_station_weekly.parquet',index=False)
prices=pd.read_parquet(root/'data/artifacts/history/publication/reference.parquet',columns=['municipio_ibge','data_coleta','preco_venda'])
d=pd.to_datetime(prices.data_coleta);prices['week_start']=(d-pd.to_timedelta(d.dt.dayofweek,unit='d')).dt.date
municipal=prices[['municipio_ibge','week_start']].drop_duplicates();municipal['year']=pd.to_datetime(municipal.week_start).dt.isocalendar().year.astype(int)
municipal=municipal.merge(associations,on=['municipio_ibge','year'],how='left',validate='many_to_one')
assert municipal.association_status.notna().all()
weather=municipal.merge(weekly,on=['station_id','week_start'],how='left',validate='many_to_one')
weather['expected_hours']=weather.week_start.map(expected_hours)
for field in ['reported_hours','valid_temperature_hours','valid_rain_hours']:weather[field]=weather[field].fillna(0).astype('int64')
weather['temperature_fraction']=weather.valid_temperature_hours/weather.expected_hours;weather['rain_fraction']=weather.valid_rain_hours/weather.expected_hours
weather['temperature_eligible']=weather.temperature_fraction.ge(policy['minimum_valid_hour_fraction_per_variable'])
weather['rain_eligible']=weather.rain_fraction.ge(policy['minimum_valid_hour_fraction_per_variable'])
weather['partial_boundary_week']=weather.expected_hours.lt(168)
weather['coverage_status']='insufficient_both';weather.loc[weather.temperature_eligible|weather.rain_eligible,'coverage_status']='one_variable_eligible';weather.loc[weather.temperature_eligible&weather.rain_eligible,'coverage_status']='both_variables_eligible'
weather.loc[weather.reported_hours.eq(0),'coverage_status']='no_measurements';weather.loc[weather.station_id.isna(),'coverage_status']='no_eligible_station'
assert not weather.duplicated(['municipio_ibge','week_start']).any() and len(weather)==len(municipal)
weather.to_parquet(folder/'weather_municipal_weekly.parquet',index=False)
joined=prices.merge(weather,on=['municipio_ibge','week_start'],how='left',validate='many_to_one',sort=False)
assert len(joined)==len(prices) and prices.reset_index(drop=True).equals(joined[prices.columns].reset_index(drop=True))
before=sum(int(x*1000) for x in prices.preco_venda);after=sum(int(x*1000) for x in joined.preco_venda);assert before==after
report={'status':'weather_weekly_and_price_join_reference_validated_locally','fabric_executed':False,'policy':policy,'hourly_rows':len(hourly),'duplicate_context_rows':duplicates,'conflicting_hour_rows':conflicts,'station_weeks':len(weekly),'municipality_weeks':len(weather),'price_rows_before':len(prices),'price_rows_after':len(joined),'sum_price_mills_before':before,'sum_price_mills_after':after,'municipality_weeks_by_status':weather.groupby('coverage_status').size().to_dict(),'price_rows_by_status':joined.groupby('coverage_status').size().to_dict(),'station_quality':quality,'checked_at_utc':datetime.now(timezone.utc).isoformat()}
report['precipitation_interpretation']='Observed sum over valid hours; no imputation of missing hours; completeness fraction accompanies value.'
report['station_quality_counts_window']='Full source annual file; price/weather associations use the declared 2024-2026H1 window only.'
(root/'evidence/phase2/context/weather-weekly-local.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['hourly_rows','station_weeks','municipality_weeks','price_rows_before','price_rows_after','price_rows_by_status']}),flush=True)
