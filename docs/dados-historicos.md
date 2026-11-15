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
refletir mudança da amostra; o relatório separado de postos comuns compara
somente os estabelecimentos e localidades presentes nos dois períodos.
Ausência de coleta não representa preço zero.

O relatório **Fuel Watch BR Nacional** continua usando 2026H1. O relatório
separado **Fuel Watch BR Histórico** usa as visões `analise_hist` e inclui uma
página de postos comuns. Compara primeiros semestres de anos consecutivos,
com o mesmo CNPJ, produto, moeda, unidade, UF e município nos dois períodos.
Calcula a média das coletas por posto e dá o mesmo peso a cada posto na média
comparada. Bandeira não define a identidade da comparação. Um posto ausente
em qualquer período não é tratado como preço zero. A variação é nominal e não
equivale à variação ajustada pela inflação ou de todos os postos brasileiros.

O conjunto de pares foi comparado integralmente com a referência local: 22.046
combinações em 2024–2025 e 23.433 em 2025–2026. Três recortes de medidas DAX
foram reconciliados com o Warehouse; os seletores de combustível, ano e UF
estão presentes no relatório. A exportação final foi inspecionada nas quatro
páginas; a tabela estadual mostra as 27 UFs e o total sem rolagem. Os cinco
cenários operacionais já foram verificados, assim como as sete visões
`analise_hist`; consulte `history-operations.md` e os recibos em
`evidence/phase2/analytics-history/`.

Evidências: `evidence/phase2/history/warehouse-first_joint_publish.json`,
`silver-72918c9c-414e-40d0-8395-3ebdb0cb75d1.json` e
`publication-reference.json` e `evidence/phase2/deployment/rebuild-history-report-qa4.json`.
A referência de publicação é local; os demais recibos registram verificações
reais no Fabric.
