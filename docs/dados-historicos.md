# Dados históricos nacionais disponíveis

Publicação real validada no Warehouse `wh_fuelwatch`, schema `gold_hist`:
**2.125.547 coletas, 13.030 postos e 462 municípios observados**, nas 27 UFs e
nos seis combustíveis presentes nos arquivos. Período: janeiro/2024 a junho/2026.
São quatro semestres históricos adicionais, mantendo 2026H1.

O grão continua sendo coleta individual. GNV usa BRL/m³; os demais produtos
usam BRL/litro. Não some ou tire média de preços de produtos/unidades distintos.

```sql
-- Cobertura e preços nominais por produto e ano; não mistura combustíveis.
SELECT YEAR(data_coleta) AS ano,produto,moeda,unidade,
       COUNT_BIG(*) AS coletas,COUNT(DISTINCT cnpj) AS postos_observados,
       COUNT(DISTINCT municipio_ibge) AS municipios_observados,
       AVG(preco_venda) AS media_por_coleta
FROM gold_hist.business_published
GROUP BY YEAR(data_coleta),produto,moeda,unidade
ORDER BY ano,produto;

-- Semanas e municípios: agregação derivada, sem apagar as coletas.
SELECT inicio_semana_iso,municipio_ibge,produto,moeda,unidade,
       coletas,postos_observados,preco_medio,preco_minimo,preco_maximo
FROM gold_hist.preco_semanal
WHERE produto='GASOLINA'
ORDER BY inicio_semana_iso,municipio_ibge;

-- Arquivos oficiais que compõem a publicação ativa.
SELECT * FROM gold_hist.source_versions ORDER BY date_start;

-- Histórico observado do posto, sem alegar data real de troca de bandeira.
SELECT * FROM gold_hist.dim_posto
WHERE cnpj='00002953000199'
ORDER BY observado_desde;
```

`gold_hist.coletas` acrescenta nome oficial do município, semana ISO e
classificação IQR. A classificação é calculada por UF/produto/moeda/unidade/semana
no conjunto publicado; preço incomum válido permanece disponível. Não avaliado
por cobertura insuficiente é um status próprio.

O histórico de postos possui **15.005 versões observadas**, e a agregação contém
**252.391 grupos semanais municipais**. Os joins temporais e os resultados foram
comparados integralmente com referência independente. Os 12 campos tipados de
2026H1 continuam iguais aos de `gold_br`; o sinal IQR pode mudar nas fronteiras
porque agora há observações do semestre vizinho compondo a mesma semana ISO.

Preços são nominais, sem ajuste por inflação. Diferença entre períodos pode
refletir mudança da amostra; um painel de postos comuns será explicitado nas
análises de evolução. Ausência de coleta não representa preço zero.

O relatório **Fuel Watch BR Nacional** ainda usa a publicação analítica de
2026H1 validada no F2-01. A incorporação desse histórico ao modelo e a verificação
dos cenários operacionais continuam no F2-02; não são consideradas prontas pela
mera existência das tabelas.

Evidências: `evidence/phase2/history/warehouse-first_joint_publish.json`,
`silver-72918c9c-414e-40d0-8395-3ebdb0cb75d1.json` e
`publication-reference.json`. A última é referência local; as duas primeiras
registram verificações reais no Fabric.
