"""Promover o candidato historico validado para Gold dimensional transacional."""
import argparse,json,re,time,uuid
from datetime import datetime,timezone
from azure.storage.filedatalake import DataLakeServiceClient
import pyodbc
from client import ROOT,request,credential,environment_config
from warehouse import connect,results
from evidence import write_json
from phase2_fingerprint import publication_fingerprint

p=argparse.ArgumentParser();p.add_argument('job_id');p.add_argument('--attempt',required=True);p.add_argument('--inject-fail',action='store_true');p.add_argument('--rebuild',action='store_true');args=p.parse_args()
assert re.fullmatch('[a-z0-9_-]+',args.attempt)
c=environment_config()
if args.rebuild:
    folder=ROOT/'.local/phase2-rebuild';target=json.loads((folder/'binding.json').read_text())
    assert c['workspace_id']==target['workspace_id'] and c['lakehouse_id']==target['lakehouse']['id']
    assert c['warehouse_id']==target['warehouse']['id']
    notebook_id=target['notebooks']['12_historico_publicacao']
    job_path=f"workspaces/{c['workspace_id']}/notebooks/{notebook_id}/jobs/execute/instances/{args.job_id}?beta=true"
    journal_folder=folder/'warehouse';journal_folder.mkdir(exist_ok=True)
    evidence_path=ROOT/'evidence/phase2/deployment'/f'rebuild-warehouse-history-{args.attempt}.json'
else:
    folder=ROOT/'.local/phase2-history';binding=json.loads((folder/'binding.json').read_text())
    notebook_id=binding['publication_notebook_id']
    job_path=f"workspaces/{c['workspace_id']}/items/{notebook_id}/jobs/instances/{args.job_id}"
    journal_folder=folder
    evidence_path=ROOT/'evidence/phase2/history'/('warehouse-'+args.attempt+'.json')
job=request('GET',job_path).json();assert job['status']=='Completed',job['status']
fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(c['workspace_id'])
def utc(s):return datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
start,end=utc(job['startTimeUtc']),utc(job['endTimeUtc']);receipts=[]
for path in fs.get_paths(path=c['lakehouse_id']+'/Files/audit/history-publication'):
    if path.name.endswith('.json'):
        receipt=json.loads(fs.get_file_client(path.name).download_file().readall())
        if start<=utc(receipt['started_at_utc'])<=utc(receipt['finished_at_utc'])<=end:receipts.append(receipt)
assert len(receipts)==1 and receipts[0]['status']=='historical_publication_candidate_validated'
audit=receipts[0];run=str(uuid.UUID(audit['run_id']))
m=json.loads((ROOT/'evidence/phase2/history/publication-reference.json').read_text(encoding='utf8'));bundle=json.loads((ROOT/'.local/phase2-history/publication-bundle.json').read_text())
assert audit['manifest_sha256']==bundle['manifest_sha256'] and audit['rows']==m['rows'] and audit['full_business_comparison_passed']
assert audit['sources']==m['sources']
journal=journal_folder/('warehouse-'+args.attempt+'.json');assert not journal.exists(),'Tentativa ja registrada: inspecionar antes de repetir'
report={'status':'started','environment':'fabric','spark_job_id':args.job_id,'run_id':run,'attempt':args.attempt,'started_at_utc':datetime.now(timezone.utc).isoformat()}
write_json(journal,report)
fields='cnpj,cnpj_origem,produto,data_coleta,preco_venda,moeda,unidade,uf,municipio_ibge,municipio_origem,revenda_observada,bandeira_observada,preco_incomum_iqr'
weekly='inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns'
try:
    with connect(c) as cn:
        cn.timeout=900;cur=cn.cursor()
        expected={'hist_transfer_manifest':1,'hist_transfer_coletas':m['rows'],'hist_transfer_calendar':m['calendar_days'],'hist_transfer_municipio':5571,'hist_expected_posto':m['station_versions'],'hist_expected_weekly':m['weekly_groups']}
        for attempt in range(30):
            try:
                for table,count in expected.items():
                    observed=cur.execute('SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.'+table+' WHERE run_id=?',run).fetchone()[0]
                    if observed!=count:raise ValueError(f'SQL visibility {table}: {observed}/{count}')
                break
            except (ValueError,pyodbc.ProgrammingError) as exc:
                if isinstance(exc,pyodbc.ProgrammingError) and not any(x in str(exc) for x in ['Invalid object name','42S02','208']):raise
                if attempt==29:raise
                print('Waiting exact historical SQL visibility',attempt+1,str(exc)[:160],flush=True);time.sleep(15)
        for batch in re.split(r'(?m)^GO\s*$',(ROOT/'sql/history/01_schema.sql').read_text(encoding='utf8')):
            if batch.strip():results(cur.execute(batch))
        for statement in (ROOT/'sql/history/02_views.sql').read_text(encoding='utf8').split('CREATE OR ALTER VIEW ')[1:]:results(cur.execute('CREATE OR ALTER VIEW '+statement))
        results(cur.execute((ROOT/'sql/history/03_publish.sql').read_text(encoding='utf8')))
        stage=f'''BEGIN TRY
        BEGIN TRANSACTION;
        IF (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id='{run}' AND source_snapshot_sha256='{bundle['manifest_sha256']}' AND expected_rows={m['rows']})<>1
            THROW 51840,'Manifesto historico nao corresponde ao run aprovado.',1;
        DELETE FROM gold_hist.stage_coleta;
        INSERT INTO gold_hist.stage_coleta SELECT {fields} FROM lh_fuelwatch.dbo.hist_transfer_coletas WHERE run_id='{run}';
        DELETE FROM gold_hist.stage_manifest;
        INSERT INTO gold_hist.stage_manifest SELECT run_id,'anp-historico-br-todos',source_snapshot_sha256,ibge_sha256,silver_delta_version,CAST(0 AS bit),expected_rows,expected_stations,expected_municipalities,expected_unusual,'hist_transfer_coletas',run_id,expected_calendar_days,expected_products,CAST(date_start AS date),CAST(date_end AS date) FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id='{run}';
        DELETE FROM gold_hist.expected_posto;
        INSERT INTO gold_hist.expected_posto SELECT posto_sk,cnpj,revenda_observada,bandeira_observada,municipio_ibge,uf,observado_desde,observado_ate FROM lh_fuelwatch.dbo.hist_expected_posto WHERE run_id='{run}';
        DELETE FROM gold_hist.expected_weekly;
        INSERT INTO gold_hist.expected_weekly SELECT {weekly} FROM lh_fuelwatch.dbo.hist_expected_weekly WHERE run_id='{run}';
        DELETE FROM gold_hist.stage_source_versions;
        '''
        # Bindings numericos/textuais nao sao interpolados: parametros ODBC.
        results(cur.execute(stage+'''COMMIT TRANSACTION;
        END TRY BEGIN CATCH IF @@TRANCOUNT>0 ROLLBACK TRANSACTION; THROW; END CATCH;'''))
        for source in m['sources']:
            results(cur.execute('INSERT INTO gold_hist.stage_source_versions VALUES (?,?,?,?,?,?)',source['source_id'],source['source_sha256'],source['csv_sha256'],source['scope']['date_start'],source['scope']['date_end'],source['counts']['accepted']))
        before=results(cur.execute('SELECT * FROM gold_hist.publication'))
        if args.inject_fail:
            before_full=publication_fingerprint(cur)
            assert before_full['business_published']['rows']>0,'Falha deve proteger uma publicacao existente'
            report['before']=before_full
            report['status']='baseline_captured_before_injected_failure'
            write_json(journal,report)
            try:results(cur.execute('EXEC gold_hist.publish_gold @batch_id=?,@inject_fail_before_commit=1',run))
            except pyodbc.Error as exc:
                assert '51999' in str(exc),'Falha diferente da injetada: '+str(exc)
            else:raise AssertionError('Falha injetada nao ocorreu')
            after=results(cur.execute('SELECT * FROM gold_hist.publication'));assert before==after
            after_full=publication_fingerprint(cur);assert before_full==after_full,'Falha alterou dados publicados'
            report.update(status='historical_gold_injected_failure_business_preserved',publication_unchanged=True,before=before_full,after=after_full)
        else:
            report['publication']=results(cur.execute('EXEC gold_hist.publish_gold @batch_id=?',run))
            totals=results(cur.execute('SELECT COUNT_BIG(*) AS coletas,COUNT(DISTINCT cnpj) AS postos,COUNT(DISTINCT municipio_ibge) AS municipios,COUNT(DISTINCT uf) AS ufs,COUNT(DISTINCT produto) AS produtos FROM gold_hist.business_published'))[0][0]
            assert totals=={'coletas':m['rows'],'postos':m['stations'],'municipios':m['municipalities'],'ufs':m['ufs'],'produtos':m['products']},totals
            # Precos/atributos de 2026H1 permanecem iguais; o IQR usa agora semanas conjuntas.
            typed=fields.split(',')[:-1]
            byte_fields=','.join(x if x in ['data_coleta','preco_venda'] else 'CAST('+x+' AS varbinary(8000)) AS '+x for x in typed)
            old='SELECT '+byte_fields+' FROM gold_br.business_published'
            new='SELECT '+byte_fields+" FROM gold_hist.business_published WHERE data_coleta>='2026-01-01'"
            compare_sql='SELECT CASE WHEN EXISTS('+old+' EXCEPT '+new+') OR EXISTS('+new+' EXCEPT '+old+') THEN 1 ELSE 0 END'
            if args.rebuild:
                old='SELECT '+byte_fields+' FROM lh_fuelwatch.dbo.silver_preco_brasil WHERE source_sha256=?'
                compare_sql='SELECT CASE WHEN EXISTS('+old+' EXCEPT '+new+') OR EXISTS('+new+' EXCEPT '+old+') THEN 1 ELSE 0 END'
                source_2026=next(s['source_sha256'] for s in m['sources'] if s['source_id']=='anp_2026_1')
                difference=cur.execute(compare_sql,source_2026,source_2026).fetchone()[0]
            else:
                difference=cur.execute(compare_sql).fetchone()[0]
            assert difference==0
            assert cur.execute("SELECT COUNT_BIG(*) FROM gold_hist.business_published WHERE data_coleta>='2026-01-01'").fetchone()[0]==422412
            report.update(status='historical_gold_validated',totals=totals,preserved_2026h1_typed_business=True,full_silver_gold_business_comparison_passed=True,full_scd2_and_weekly_comparison_passed=True)
        report.update(workspace_id=c['workspace_id'],lakehouse_id=c['lakehouse_id'],warehouse_id=c.get('warehouse_id'))
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        write_json(evidence_path,report)
except Exception as exc:
    report.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:1500]);raise
finally:
    write_json(journal,report)
print(json.dumps({'status':report['status'],'run_id':run,'totals':report.get('totals')}),flush=True)
