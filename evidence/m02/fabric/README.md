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
| Repetição Silver no Fabric | NAO_FEITO | `same_business_as_previous=null` nesta primeira carga |
| M02 | PARCIAL | Quatro dos cinco critérios aceitos; repetição pendente |

Somente documentação, auditorias recebidas e conferências locais foram alteradas neste registro. O bundle e os notebooks aprovados permanecem intactos. A próxima ação depende da execução manual no Fabric: repetir o notebook 04 com o mesmo bundle e parâmetros, na mesma sessão se ainda ativa, e receber o segundo JSON. O aceite exige `same_business_as_previous=true`, contagens/cobertura estáveis e mesmos hashes; não se exige ausência de novo commit Delta ou de novos metadados de execução.
