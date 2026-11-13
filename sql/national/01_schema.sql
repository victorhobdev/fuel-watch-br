-- Nacional: objetos separados do baseline RJ. Executar no Warehouse.
IF SCHEMA_ID('gold_br') IS NULL EXEC('CREATE SCHEMA gold_br');
GO
IF OBJECT_ID('gold_br.stage_coleta') IS NULL
CREATE TABLE gold_br.stage_coleta (
    cnpj varchar(14) NOT NULL, cnpj_origem varchar(80) NOT NULL,
    produto varchar(80) NOT NULL, data_coleta date NOT NULL,
    preco_venda decimal(10,3) NOT NULL, moeda varchar(3) NOT NULL,
    unidade varchar(30) NOT NULL, uf varchar(2) NOT NULL,
    municipio_ibge varchar(7) NOT NULL, municipio_origem varchar(200) NOT NULL,
    revenda_observada varchar(1000) NOT NULL, bandeira_observada varchar(300) NOT NULL,
    preco_incomum_iqr bit NOT NULL
);
IF OBJECT_ID('gold_br.stage_manifest') IS NULL
CREATE TABLE gold_br.stage_manifest (
    batch_id varchar(80) NOT NULL, scope_id varchar(100) NOT NULL,
    source_sha256 varchar(64) NOT NULL, ibge_sha256 varchar(64) NOT NULL,
    silver_delta_version bigint NOT NULL, is_synthetic bit NOT NULL,
    expected_rows bigint NOT NULL, expected_stations bigint NOT NULL,
    expected_municipalities bigint NOT NULL, expected_unusual bigint NOT NULL,
    source_table varchar(128) NOT NULL, snapshot_id varchar(80) NOT NULL
);
IF OBJECT_ID('gold_br.dim_data') IS NULL
CREATE TABLE gold_br.dim_data (
    data_sk int NOT NULL, data date NOT NULL, inicio_semana_iso date NOT NULL,
    ano_iso int NOT NULL, semana_iso int NOT NULL
);
IF OBJECT_ID('gold_br.dim_municipio') IS NULL
CREATE TABLE gold_br.dim_municipio (
    municipio_ibge varchar(7) NOT NULL, nome varchar(200) NOT NULL, uf varchar(2) NOT NULL
);
IF OBJECT_ID('gold_br.dim_produto') IS NULL
CREATE TABLE gold_br.dim_produto (
    produto_sk int NOT NULL, produto varchar(80) NOT NULL, moeda varchar(3) NOT NULL, unidade varchar(30) NOT NULL
);
IF OBJECT_ID('gold_br.dim_posto') IS NULL
CREATE TABLE gold_br.dim_posto (
    posto_sk varchar(25) NOT NULL, cnpj varchar(14) NOT NULL,
    revenda_observada varchar(1000) NOT NULL, bandeira_observada varchar(300) NOT NULL,
    municipio_ibge varchar(7) NOT NULL, uf varchar(2) NOT NULL,
    observado_desde date NOT NULL, observado_ate date NULL
);
IF OBJECT_ID('gold_br.fato_preco_coletado') IS NULL
CREATE TABLE gold_br.fato_preco_coletado (
    posto_sk varchar(25) NOT NULL, data_sk int NOT NULL, produto_sk int NOT NULL,
    municipio_ibge varchar(7) NOT NULL, cnpj_origem varchar(80) NOT NULL,
    municipio_origem varchar(200) NOT NULL, preco_venda decimal(10,3) NOT NULL,
    preco_incomum_iqr bit NOT NULL, batch_id varchar(80) NOT NULL
);
IF OBJECT_ID('gold_br.publication') IS NULL
CREATE TABLE gold_br.publication (
    batch_id varchar(80) NOT NULL, scope_id varchar(100) NOT NULL,
    source_sha256 varchar(64) NOT NULL, ibge_sha256 varchar(64) NOT NULL,
    silver_delta_version bigint NOT NULL, is_synthetic bit NOT NULL,
    published_at_utc datetime2(6) NOT NULL, rows_published bigint NOT NULL,
    source_table varchar(128) NOT NULL, snapshot_id varchar(80) NOT NULL
);

IF OBJECT_ID('gold_br.expected_posto') IS NULL
CREATE TABLE gold_br.expected_posto (posto_sk varchar(25),cnpj varchar(14),revenda_observada varchar(1000),bandeira_observada varchar(300),municipio_ibge varchar(7),uf varchar(2),observado_desde date,observado_ate date);
IF OBJECT_ID('gold_br.expected_weekly') IS NULL
CREATE TABLE gold_br.expected_weekly (inicio_semana_iso date,ano_iso int,semana_iso int,municipio_ibge varchar(7),produto varchar(80),moeda varchar(3),unidade varchar(30),coletas bigint,postos_observados bigint,soma_precos decimal(18,3),preco_minimo decimal(18,3),preco_maximo decimal(18,3),precos_incomuns bigint);
