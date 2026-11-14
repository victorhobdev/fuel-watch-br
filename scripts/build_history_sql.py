"""Especializa SQL dimensional ja validado para manifesto historico parametrizado."""
from pathlib import Path
root=Path(__file__).resolve().parents[1];target=root/'sql/history';target.mkdir(exist_ok=True)
def template(name):return (root/'sql/national'/name).read_text(encoding='utf8').replace('gold_br','gold_hist')
schema=template('01_schema.sql')
schema=schema.replace('snapshot_id varchar(80) NOT NULL\n);','snapshot_id varchar(80) NOT NULL,\n    expected_calendar_days bigint NOT NULL, expected_products bigint NOT NULL,\n    date_start date NOT NULL, date_end date NOT NULL\n);',1)
schema+='''
IF OBJECT_ID('gold_hist.stage_source_versions') IS NULL
CREATE TABLE gold_hist.stage_source_versions (
    source_id varchar(80) NOT NULL, source_sha256 varchar(64) NOT NULL,
    csv_sha256 varchar(64) NOT NULL, date_start date NOT NULL, date_end date NOT NULL,
    accepted_rows bigint NOT NULL
);
IF OBJECT_ID('gold_hist.source_versions') IS NULL
CREATE TABLE gold_hist.source_versions (
    source_id varchar(80) NOT NULL, source_sha256 varchar(64) NOT NULL,
    csv_sha256 varchar(64) NOT NULL, date_start date NOT NULL, date_end date NOT NULL,
    accepted_rows bigint NOT NULL
);
'''
(target/'01_schema.sql').write_text(schema,encoding='utf8')
(target/'02_views.sql').write_text(template('02_views.sql'),encoding='utf8')
publish=template('03_publish.sql').replace('br_transfer_calendar','hist_transfer_calendar').replace('ref_municipio_ibge_brasil','hist_transfer_municipio')
publish=publish.replace(')<>181 OR (SELECT COUNT_BIG(*) FROM gold_hist.dim_produto)<>6',')<>(SELECT expected_calendar_days FROM gold_hist.stage_manifest) OR (SELECT COUNT_BIG(*) FROM gold_hist.dim_produto)<>(SELECT expected_products FROM gold_hist.stage_manifest)')
publish=publish.replace("CAST('2026-01-01' AS date)",'(SELECT date_start FROM gold_hist.stage_manifest)').replace("CAST('2026-06-30' AS date)",'(SELECT date_end FROM gold_hist.stage_manifest)')
guard='''
        IF EXISTS (SELECT source_id FROM gold_hist.stage_source_versions GROUP BY source_id HAVING COUNT_BIG(*)<>1)
            THROW 51830,'Mais de uma versao ativa para o mesmo arquivo.',1;
        IF (SELECT SUM(accepted_rows) FROM gold_hist.stage_source_versions)<>(SELECT expected_rows FROM gold_hist.stage_manifest)
            THROW 51831,'Versoes nao reconciliam com as coletas.',1;
        IF EXISTS (SELECT 1 FROM gold_hist.stage_source_versions a JOIN gold_hist.stage_source_versions b
            ON a.source_id<b.source_id AND a.date_start<=b.date_end AND b.date_start<=a.date_end)
            THROW 51832,'Periodos de arquivos ativos se sobrepoem.',1;
        IF (SELECT COUNT_BIG(*) FROM gold_hist.dim_data d JOIN gold_hist.stage_source_versions v ON d.data BETWEEN v.date_start AND v.date_end)
            <>(SELECT expected_calendar_days FROM gold_hist.stage_manifest)
            THROW 51833,'Arquivos ativos nao cobrem o calendario contratado.',1;
        DELETE FROM gold_hist.source_versions;
        INSERT INTO gold_hist.source_versions SELECT * FROM gold_hist.stage_source_versions;
'''
publish=publish.replace('        IF @inject_fail_before_commit = 1',guard+'        IF @inject_fail_before_commit = 1')
publish=publish.replace("'gold_lab_published'","'historical_gold_published'")
(target/'03_publish.sql').write_text(publish,encoding='utf8')
assert ')<>181' not in publish and "'2026-01-01'" not in publish
assert 'expected_calendar_days' in schema and 'expected_products' in schema
print('Historical SQL generated: dynamic period/calendar/products; isolated gold_hist')
