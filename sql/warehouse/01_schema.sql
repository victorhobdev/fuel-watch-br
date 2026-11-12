-- PREPARADO: executar apenas em Warehouse, após M03 aceito. Não foi executado no Fabric.
-- Primeiro laboratório isolado; nenhum objeto gold ou Lakehouse é alterado.
IF SCHEMA_ID('lab_m04') IS NULL EXEC('CREATE SCHEMA lab_m04');
GO
IF OBJECT_ID('lab_m04.stage_coleta') IS NULL
CREATE TABLE lab_m04.stage_coleta (
    cnpj varchar(14) NOT NULL, cnpj_origem varchar(80) NOT NULL,
    produto varchar(80) NOT NULL, data_coleta date NOT NULL,
    preco_venda decimal(10,3) NOT NULL, moeda varchar(3) NOT NULL,
    unidade varchar(30) NOT NULL, uf varchar(2) NOT NULL,
    municipio_ibge varchar(7) NOT NULL, municipio_origem varchar(200) NOT NULL,
    revenda_observada varchar(1000) NOT NULL, bandeira_observada varchar(300) NOT NULL,
    preco_incomum_iqr bit NOT NULL
);
IF OBJECT_ID('lab_m04.stage_manifest') IS NULL
CREATE TABLE lab_m04.stage_manifest (
    batch_id varchar(80) NOT NULL, scope_id varchar(100) NOT NULL,
    source_sha256 varchar(64) NOT NULL, ibge_sha256 varchar(64) NOT NULL,
    silver_delta_version bigint NOT NULL, is_synthetic bit NOT NULL,
    expected_rows bigint NOT NULL, expected_stations bigint NOT NULL,
    expected_municipalities bigint NOT NULL, expected_unusual bigint NOT NULL
);
IF OBJECT_ID('lab_m04.dim_data') IS NULL
CREATE TABLE lab_m04.dim_data (
    data_sk int NOT NULL, data date NOT NULL, inicio_semana_iso date NOT NULL,
    ano_iso int NOT NULL, semana_iso int NOT NULL
);
IF OBJECT_ID('lab_m04.dim_municipio') IS NULL
CREATE TABLE lab_m04.dim_municipio (
    municipio_ibge varchar(7) NOT NULL, nome varchar(200) NOT NULL, uf varchar(2) NOT NULL
);
IF OBJECT_ID('lab_m04.dim_produto') IS NULL
CREATE TABLE lab_m04.dim_produto (
    produto_sk int NOT NULL, produto varchar(80) NOT NULL, moeda varchar(3) NOT NULL, unidade varchar(30) NOT NULL
);
IF OBJECT_ID('lab_m04.dim_posto') IS NULL
CREATE TABLE lab_m04.dim_posto (
    posto_sk varchar(25) NOT NULL, cnpj varchar(14) NOT NULL,
    revenda_observada varchar(1000) NOT NULL, bandeira_observada varchar(300) NOT NULL,
    municipio_ibge varchar(7) NOT NULL, uf varchar(2) NOT NULL,
    observado_desde date NOT NULL, observado_ate date NULL
);
IF OBJECT_ID('lab_m04.fato_preco_coletado') IS NULL
CREATE TABLE lab_m04.fato_preco_coletado (
    posto_sk varchar(25) NOT NULL, data_sk int NOT NULL, produto_sk int NOT NULL,
    municipio_ibge varchar(7) NOT NULL, cnpj_origem varchar(80) NOT NULL,
    municipio_origem varchar(200) NOT NULL, preco_venda decimal(10,3) NOT NULL,
    preco_incomum_iqr bit NOT NULL, batch_id varchar(80) NOT NULL
);
IF OBJECT_ID('lab_m04.publication') IS NULL
CREATE TABLE lab_m04.publication (
    batch_id varchar(80) NOT NULL, scope_id varchar(100) NOT NULL,
    source_sha256 varchar(64) NOT NULL, ibge_sha256 varchar(64) NOT NULL,
    silver_delta_version bigint NOT NULL, is_synthetic bit NOT NULL,
    published_at_utc datetime2(6) NOT NULL, rows_published bigint NOT NULL
);
