# Bloco inicial — evidências de 11/11/2026

## Antes e depois

Antes: pasta com Git vazio, sem commits/remoto e sem dados do projeto. Python 3.13.5, Git 2.49.0, pandas 2.3.2 e PyArrow 23.0.1 disponíveis. PySpark local ausente. Conta Azure/crédito informados pelo usuário; Fabric sem acesso configurado.

Depois: fontes reais preservadas, perfil completo reproduzível, contrato mínimo, saída local tipada, testes de regras e recuperação e notebook Bronze preparado. Nenhum workspace, capacidade, Lakehouse ou Warehouse foi criado. Nenhuma credencial foi gravada no projeto e nenhum repositório foi publicado.

| Bloco | Status | Evidência e limite |
| --- | --- | --- |
| Reconhecimento local | COMPLETO | Ferramentas e Git vazio observados nesta pasta |
| Reconhecimento cloud | PARCIAL | Fabric na tela de entrada; cache CLI com uma assinatura; consulta online bloqueada por token expirado |
| Download e perfil ANP/IBGE | COMPLETO | `evidence/source-profile.json`, manifesto e hashes |
| Contrato e primeira fatia local | COMPLETO | `evidence/local-slice.json`, Parquet e consulta por município |
| Verificação local | COMPLETO | 10 testes aprovados e hash de negócio recomputado do Parquet |
| Código do notebook Bronze | COMPLETO | Arquivo importável preparado; três células de código compiladas sintaticamente |
| Execução Bronze/Silver/Gold no Fabric | NAO_FEITO | Depende de acesso e capacidade confirmados; não confundir com saída local |

## Perfil observado

ANP: ZIP de 8.488.624 bytes com CSV de 72.117.162 bytes. UTF-8 com BOM, 16 colunas, delimitador `;`, datas `dd/MM/yyyy`, vírgula decimal. As coletas vão de 01/01 a 30/06/2026. Os 422.418 CNPJs recebidos têm espaço à esquerda, removido somente na representação canônica.

| Produto | Linhas | Unidade |
| --- | ---: | --- |
| GASOLINA | 110.925 | R$ / litro |
| ETANOL | 93.893 | R$ / litro |
| GASOLINA ADITIVADA | 86.231 | R$ / litro |
| DIESEL S10 | 77.118 | R$ / litro |
| DIESEL | 45.814 | R$ / litro |
| GNV | 8.437 | R$ / m³ |

Foram encontradas seis repetições exatas no arquivo completo. Após separá-las, não houve conflito de CNPJ/produto/data, com ou sem unidade, nessa entrega. Não houve data que falhasse no parsing do perfil. Valor de Compra está vazio em todas as linhas, coerente com a observação dos metadados da ANP sobre a disponibilidade histórica desse campo.

## Fatia executada

Gasolina comum no RJ, semestre completo: 8.052 coletas, 502 CNPJs distintos, 27 municípios. O IBGE retornou 92 municípios do RJ; houve uma correspondência por UF/nome para cada nome distinto presente na fatia. Não houve ambiguidade na referência normalizada.

Contagens: `422.418 recebidas = 414.366 fora da fatia + 8.052 selecionadas`. Na fatia: `8.052 = 0 inválidas + 0 duplicatas exatas excedentes + 0 linhas conflitantes + 8.052 aceitas`.

Preços da fatia entre R$ 5,49 e R$ 7,99 por litro. O sinal exploratório de IQR marcou 26 observações, todas mantidas. Há 14 CNPJs com múltiplas bandeiras observadas; não houve múltiplo nome de revenda por CNPJ nessa fatia. O SCD2 ainda não foi implementado.

Parquet relido e conferido: CNPJ textual, `data_coleta` como date32 e `preco_venda` como decimal(10,3), chave de negócio única em 8.052 linhas. Soma das observações dos 27 resultados por município coincide com o detalhe.

Três execuções locais reais concluídas mantiveram o hash de negócio `cf058cb4ddd6f1c323d46c2f2e795d5f11733e9a7196ec1c25f2e7b1e26869a4`. Run_ids, horários e contagens estão em `evidence/verification.json`. Os downloads também foram repetidos e identificaram conteúdo idêntico. Não houve arquivo oficial republicado com bytes diferentes durante o bloco.

## Regras e recuperação verificadas

`python -m unittest discover -s tests -v`: 10 testes aprovados; saída real em `evidence/tests-local.txt`.

Fixtures explicitamente sintéticos verificaram preservação de zeros no CNPJ e precisão decimal; parsing e quarentena com original e motivo; preço extremo aceito; duplicata distinta de conflito; município ambíguo; resposta IBGE com/sem gzip; repetição; correção antiga e remoção em snapshot completo; conflito sem avanço do ponteiro; falha de escrita e recuperação sem duplicação. Esses testes não demonstram comportamento transacional do Fabric.

Na primeira tentativa dos testes de snapshot, o sandbox negou acesso a subpastas do TEMP padrão do Windows. A raiz temporária dos testes foi direcionada para `data/test-tmp/`, dentro do workspace, com verificação do caminho resolvido antes da limpeza. A execução final passou sem necessidade de ampliar permissões para os testes.

## Arquivos e diff funcional

- `.gitignore`: dados, ambiente e segredos fora do versionamento.
- `config/`: URLs oficiais, recorte e versão do contrato.
- `scripts/download_sources.py`: preservação por hash e manifesto de downloads.
- `fuelwatch/source.py` e `scripts/profile_sources.py`: leitura estrita e perfil reproduzível.
- `fuelwatch/contract.py`: regras explícitas de observação e classificação.
- `scripts/prepare_local_slice.py`: Parquet tipado, categorias reconciliadas, snapshots locais e consulta por município.
- `tests/`: fixtures sintéticos e verificações de regras/reprocessamento/falha.
- `notebooks/01_landing_to_bronze.ipynb`: PySpark preparado, sem outputs de execução.
- `README.md`, `docs/` e `evidence/`: estado, contrato, roteiro e registros verificáveis.
- `requirements-local.txt`: versões usadas localmente, sem novas dependências instaladas no bloco.

## Limites e próximo passo seguro

O bloqueio para execução cloud é o acesso ao Fabric ainda não configurado e a capacidade não confirmada. A existência de crédito Azure não resolve essas condições automaticamente. O [roteiro Fabric](fabric-primeira-execucao.md) descreve a verificação de identidade/tenant, trial e primeira Copy activity antes de qualquer contratação.

A consulta Azure CLI ao cache precisou de execução autorizada fora do sandbox e mostrou uma assinatura padrão `Enabled`. A tentativa posterior de consultar políticas da assinatura online falhou por refresh token expirado (`AADSTS700082`); a consulta de capacidades foi interrompida antes de executar. Assim, oferta, saldo e capacidades continuam sem confirmação online. Esse reconhecimento está sanitizado em `evidence/environment.json`, sem IDs, e-mails, tokens ou nomes de assinatura.

O código PySpark recebeu apenas verificação sintática; APIs, acesso OneLake, Delta e `replaceWhere` ainda precisam de execução real. Não há Silver Delta, Gold dimensional, integração Git do workspace, segurança, implantação ou medição de desempenho demonstradas.

O ensaio local é serial e presume entrega semestral completa. A publicação Fabric precisará de comparação entre versões, marcador de versão ativa, promoção após validação e recuperação entre camadas. Correções e falhas foram exercitadas em fixtures, sem inventar correções reais da ANP. Custo de capacidade paga só será estimado quando houver oferta/região confirmadas e exigirá autorização antes de criação.
