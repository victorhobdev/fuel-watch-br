"""Gera T-SQL nacional reutilizando o nucleo dimensional revisado."""
from pathlib import Path
import re
out=Path('sql/national');schema=Path('sql/warehouse/01_schema.sql').read_text(encoding='utf8').replace('lab_m04','gold_br');schema=schema[schema.index("IF SCHEMA_ID"):];schema+='''
IF OBJECT_ID('gold_br.expected_posto') IS NULL
CREATE TABLE gold_br.expected_posto (posto_sk varchar(25),cnpj varchar(14),revenda_observada varchar(1000),bandeira_observada varchar(300),municipio_ibge varchar(7),uf varchar(2),observado_desde date,observado_ate date);
IF OBJECT_ID('gold_br.expected_weekly') IS NULL
CREATE TABLE gold_br.expected_weekly (inicio_semana_iso date,ano_iso int,semana_iso int,municipio_ibge varchar(7),produto varchar(80),moeda varchar(3),unidade varchar(30),coletas bigint,postos_observados bigint,soma_precos decimal(18,3),preco_minimo decimal(18,3),preco_maximo decimal(18,3),precos_incomuns bigint);
''';(out/'01_schema.sql').write_text('-- Nacional: objetos separados do baseline RJ. Executar no Warehouse.\n'+schema,encoding='utf8')
views=Path('sql/warehouse/02_station_history.sql').read_text(encoding='utf8').replace('lab_m04','gold_br').replace('CREATE VIEW ','CREATE OR ALTER VIEW ').replace('1 AS produto_sk','r.produto_sk').replace('JOIN gold_br.dim_data d ON s.data_coleta = d.data;','JOIN gold_br.dim_data d ON s.data_coleta = d.data\nJOIN gold_br.dim_produto r ON s.produto=r.produto AND s.moeda=r.moeda AND s.unidade=r.unidade;');(out/'02_views.sql').write_text('-- Nacional: produto_sk por produto/moeda/unidade; nao constante.\n'+views[re.search(r'(?m)^CREATE OR ALTER VIEW gold_br\.', views).start():],encoding='utf8')
publish=Path('sql/warehouse/03_publish_gold.sql').read_text(encoding='utf8').replace('lab_m04','gold_br');publish=publish[publish.index('CREATE OR ALTER PROCEDURE'):]
publish=publish.replace("        DELETE FROM gold_br.dim_produto;\n        INSERT INTO gold_br.dim_produto VALUES (1, 'GASOLINA', 'BRL', 'litro');\n", '')
a=publish.index('        IF EXISTS (SELECT 1 FROM gold_br.stage_coleta WHERE produto');b=publish.index('        IF EXISTS (SELECT cnpj, produto',a)
publish=publish[:a]+'''        IF EXISTS (SELECT 1 FROM gold_br.stage_coleta s LEFT JOIN gold_br.dim_produto r
            ON s.produto=r.produto AND s.moeda=r.moeda AND s.unidade=r.unidade
            WHERE r.produto_sk IS NULL OR s.preco_venda<=0 OR s.data_coleta<CAST('2026-01-01' AS date) OR s.data_coleta>CAST('2026-06-30' AS date))
            THROW 51805, 'Produto/unidade/periodo nacional invalido.', 1;
'''+publish[b:]
needle='        BEGIN TRANSACTION;';replacements='''
        DELETE FROM gold_br.dim_data;
        INSERT INTO gold_br.dim_data
            SELECT CAST(data_sk AS int),CAST(data AS date),CAST(inicio_semana_iso AS date),CAST(ano_iso AS int),CAST(semana_iso AS int)
            FROM lh_fuelwatch.dbo.br_transfer_calendar WHERE run_id=@batch_id;
        DELETE FROM gold_br.dim_municipio;
        INSERT INTO gold_br.dim_municipio SELECT municipio_ibge,nome,uf FROM lh_fuelwatch.dbo.ref_municipio_ibge_brasil WHERE run_id=@batch_id;
        DELETE FROM gold_br.dim_produto;
        INSERT INTO gold_br.dim_produto SELECT CAST(DENSE_RANK() OVER (ORDER BY produto,moeda,unidade) AS int),produto,moeda,unidade
            FROM (SELECT DISTINCT produto,moeda,unidade FROM gold_br.stage_coleta) p;
        IF (SELECT COUNT_BIG(*) FROM gold_br.dim_data)<>181 OR (SELECT COUNT_BIG(*) FROM gold_br.dim_produto)<>6
            THROW 51806, 'Dimensoes nacionais incompletas.', 1;
''';publish=publish.replace(needle,needle+replacements,1)
# Associacao SCD2 e semanal devem coincidir integralmente com referencias locais independentes.
needle='        COMMIT TRANSACTION;';validation='''        IF (SELECT COUNT_BIG(*) FROM gold_br.dim_posto)<>(SELECT COUNT_BIG(*) FROM gold_br.expected_posto)
            OR EXISTS (SELECT * FROM gold_br.dim_posto EXCEPT SELECT * FROM gold_br.expected_posto)
            OR EXISTS (SELECT * FROM gold_br.expected_posto EXCEPT SELECT * FROM gold_br.dim_posto)
            THROW 51807, 'Historico nacional diverge da referencia independente.', 1;
        IF EXISTS (SELECT * FROM gold_br.stage_business_bytes EXCEPT SELECT * FROM gold_br.published_business_bytes)
            OR EXISTS (SELECT * FROM gold_br.published_business_bytes EXCEPT SELECT * FROM gold_br.stage_business_bytes)
            THROW 51808, 'Negocio nacional divergiu depois dos joins dimensionais.', 1;
        IF (SELECT COUNT_BIG(*) FROM gold_br.fato_preco_coletado)<>(SELECT COUNT_BIG(*) FROM gold_br.stage_coleta)
            THROW 51809, 'Associacao nacional alterou cardinalidade.', 1;
        IF (SELECT COUNT_BIG(*) FROM gold_br.preco_semanal)<>(SELECT COUNT_BIG(*) FROM gold_br.expected_weekly)
            OR EXISTS (SELECT inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns FROM gold_br.preco_semanal EXCEPT SELECT * FROM gold_br.expected_weekly)
            OR EXISTS (SELECT * FROM gold_br.expected_weekly EXCEPT SELECT inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns FROM gold_br.preco_semanal)
            THROW 51810, 'Agregacao nacional diverge da referencia independente.', 1;
''';publish=publish.replace(needle,validation+needle,1);(out/'03_publish.sql').write_text('-- Publicacao nacional transacional; uma tentativa por vez.\n'+publish,encoding='utf8')
with (out/'02_views.sql').open('a',encoding='utf8') as stream:
 stream.write('''
CREATE OR ALTER VIEW gold_br.cobertura_iqr AS
SELECT b.uf,b.produto,b.moeda,b.unidade,d.inicio_semana_iso,COUNT_BIG(*) AS coletas,
    COUNT(DISTINCT b.cnpj) AS postos,
    CAST(CASE WHEN COUNT_BIG(*)>=20 AND COUNT(DISTINCT b.cnpj)>=5 THEN 1 ELSE 0 END AS bit) AS iqr_avaliado
FROM gold_br.business_published b JOIN gold_br.dim_data d ON b.data_coleta=d.data
GROUP BY b.uf,b.produto,b.moeda,b.unidade,d.inicio_semana_iso;

CREATE OR ALTER VIEW gold_br.coletas AS
SELECT b.*,m.nome AS municipio_ibge_nome,d.inicio_semana_iso,q.iqr_avaliado,
    CASE WHEN q.iqr_avaliado=0 THEN 'nao_avaliado'
         WHEN b.preco_incomum_iqr=1 THEN 'incomum_valido' ELSE 'valido_sem_sinal' END AS classificacao_preco
FROM gold_br.business_published b
JOIN gold_br.dim_municipio m ON b.municipio_ibge=m.municipio_ibge
JOIN gold_br.dim_data d ON b.data_coleta=d.data
JOIN gold_br.cobertura_iqr q ON b.uf=q.uf AND b.produto=q.produto AND b.moeda=q.moeda
    AND b.unidade=q.unidade AND d.inicio_semana_iso=q.inicio_semana_iso;
''')
print('National SQL generated; not yet executed')
