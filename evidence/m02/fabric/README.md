# Evidências Fabric do M02

O JSON `ibge/ebaf83ac-c2c2-46cc-b162-05187c469f64.json` foi fornecido pelo usuário após executar o notebook 03 no Fabric. O escape Markdown da URL foi removido; os demais valores foram preservados. O agente conferiu o retorno localmente, sem consultar a tabela remotamente.

Resultado: `ibge_reference_validated`, 92 municípios, nenhuma chave normalizada ambígua, hash do snapshot e hash do manifesto iguais aos aprovados no pacote local. A referência foi criada em `ref_municipio_ibge`; o caminho dos bytes originais preservados também consta da auditoria. O modo de origem é upload do snapshot oficial preservado, não uma nova chamada REST no Fabric.

Runtime observado nesse retorno: Spark `4.1.1.5.5.20260929.238183312`, Python `3.13.11`. Execução em 12/11/2026, 19:30:19–19:30:40 (America/Sao_Paulo); os timestamps originais são mantidos em UTC no JSON.

## Primeira Silver

O JSON `silver/8405ed03-35cb-4c6b-979b-731e8833235f.json` também foi fornecido pelo usuário, após executar o notebook 04 no Fabric. Seus valores foram preservados, sem consulta remota independente pelo agente. A conferência local com o manifesto aprovado está em `silver-validation.json`.

Resultado: `silver_validated`, tabela `silver_preco_coletado`, versão Delta 0, 8.052 coletas, 502 postos e 27 municípios. Os hashes ANP/IBGE/manifesto e o recorte conferem. As contagens fecham: 422.418 = 414.366 fora do recorte + 8.052 selecionadas; as selecionadas são todas aceitas, sem inválidas, duplicatas excedentes ou conflitos nessa fatia. A comparação integral com o Parquet local não encontrou linhas de negócio ausentes nem adicionais nos 13 campos. Conforme o código aprovado, a comparação também verifica os tipos, ignorando apenas nullability.

O fixture distribuído retornou `fixture_validated`: 14 entregas = 9 aceitas + 2 inválidas + 1 duplicata excedente + 2 linhas conflitantes. As inválidas foram verificadas em `lab_m02_quarantine`, separada dos dados oficiais. Um preço sintético incomum permaneceu aceito. Na fatia oficial, os 26 sinais IQR foram preservados, com limites decimais `5.4050` e `7.7650`.

Runtime informado: Spark `4.1.1.5.5.20260929.238183312`, Python `3.13.11`. Execução em 12/11/2026, 19:37:09–19:38:13 (America/Sao_Paulo), aproximadamente 63,75 segundos; é duração da execução, não um benchmark controlado.

| Bloco | Estado | Evidência |
| --- | --- | --- |
| Referência IBGE no Fabric | COMPLETO | JSON do notebook 03, hashes aprovados, 92 municípios |
| Fixture e primeira Silver no Fabric | COMPLETO | JSON do notebook 04, versão 0 e comparação integral local |
| Repetição Silver no Fabric | COMPLETO | Segundo JSON: Delta 0 → 1, `same_business_as_previous=true`, mesmas contagens e comparação local sem diferenças |
| M02 | COMPLETO | Cinco dos cinco critérios aceitos em 12/11/2026 |

## Repetição Silver e fechamento do M02

O segundo JSON, `silver/5f55cb03-9bee-47d0-bdac-72385578e338.json`, foi fornecido pelo usuário após repetir o notebook 04. Foram removidos apenas os delimitadores Markdown externos da mensagem; os valores foram preservados. A conferência com a primeira execução e o manifesto está em `silver-replay-validation.json`. O agente não consultou a tabela remotamente.

Resultado: `silver_validated`, `previous_delta_version=0`, `silver_delta_version=1` e `same_business_as_previous=true`. O código aprovado fixa a versão anterior com time travel e usa `EXCEPT ALL` nas duas direções nos 13 campos de negócio, antes e depois da publicação. Assim, o aceite cobre valores e multiplicidades, além da contagem. A comparação com o Parquet local também retornou sem diferenças.

Permanecem 8.052 coletas, 502 postos, 27 municípios e 26 sinais IQR. Hashes ANP/IBGE/manifesto, recorte, limites IQR e categorias são iguais à primeira execução. O fixture distribuído passou novamente, mantendo as inválidas em quarentena sintética separada. Execução em 12/11/2026, 19:46:18–19:47:20 (America/Sao_Paulo), aproximadamente 62,03 segundos; não é um benchmark controlado.

Os cinco critérios M02 foram aceitos. Isso demonstra repetição dos mesmos snapshots; não demonstra republicação oficial, correção histórica, backfill, promoção entre camadas ou recuperação de publicação, que pertencem aos marcos seguintes. SKU, região e expiração exata do trial continuam sem evidência, como pendências operacionais do roadmap.

Somente documentação, auditorias recebidas e conferências locais foram alteradas neste fechamento. O bundle e os notebooks aprovados permanecem intactos. O próximo marco é M03: o laboratório sintético já foi executado localmente; implementação e execução de seu notebook Fabric continuam pendentes. Parar a sessão 04 ao concluir; não iniciar uma segunda sessão em paralelo.
