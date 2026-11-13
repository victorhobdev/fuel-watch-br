-- PREPARADO M07: somente no Warehouse do projeto, nunca evidencia de teste do leitor.
IF ISNULL(HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL'),0) <> 1
    THROW 51701, 'Executar setup somente como autor com CONTROL no Warehouse.', 1;
IF SCHEMA_ID('lab_m07') IS NULL EXEC('CREATE SCHEMA lab_m07');
IF OBJECT_ID('lab_m07.access_fixture') IS NOT NULL
    THROW 51700, 'Fixture M07 ja existe; inspecionar antes de recriar.', 1;
CREATE TABLE lab_m07.access_fixture (
    fixture_id int NOT NULL,
    uf varchar(2) NOT NULL,
    preco_sintetico decimal(10,3) NOT NULL,
    contato_ficticio varchar(100) MASKED WITH (FUNCTION='email()') NULL,
    is_synthetic bit NOT NULL
);
INSERT INTO lab_m07.access_fixture VALUES
    (1,'RJ',6.100,'rj@synthetic.invalid',1),
    (2,'SP',7.200,'sp@synthetic.invalid',1);
GO
CREATE FUNCTION lab_m07.allow_uf(@uf varchar(2))
RETURNS TABLE WITH SCHEMABINDING
AS RETURN SELECT 1 AS access_granted
WHERE @uf='RJ' OR HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL')=1;
GO
CREATE SECURITY POLICY lab_m07.uf_filter
ADD FILTER PREDICATE lab_m07.allow_uf(uf) ON lab_m07.access_fixture
WITH (STATE=ON);
GO
-- Executar primeiro com AUTOR e depois com LEITOR_RJ, em conexoes reais distintas.
SELECT USER_NAME() AS database_user, IS_MEMBER('db_owner') AS is_db_owner;
SELECT fixture_id,uf,preco_sintetico,contato_ficticio,is_synthetic
FROM lab_m07.access_fixture ORDER BY fixture_id;
-- Esperado leitor: somente fixture_id=1, uf=RJ, contato rXXX@XXXX.com, sem db_owner.
-- A03 leitor: UPDATE lab_m07.access_fixture SET preco_sintetico=preco_sintetico WHERE 1=0;
-- Nao executar como AUTOR e interpretar como negacao do leitor.
