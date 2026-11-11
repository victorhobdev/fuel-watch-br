# Contrato mínimo 0.1 — reconhecimento e ensaio local

Base empírica: ZIP oficial `ca-2026-01.zip`, SHA-256 `a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c`. O contrato se limita ao semestre e à fatia de `config/slice.json`. Expandir produtos ou períodos exige perfilar as novas entregas e rever unidades, layout e chaves.

## Recebimento e layout

ZIP com um CSV. O nome interno contém acentos; não deve ser usado como chave. CSV de 72.117.162 bytes, UTF-8 com BOM, delimitador `;`, aspas duplas, cabeçalho exato de 16 campos e valores decimais com vírgula. Cabeçalho diferente, falha de decodificação ou número incorreto de campos bloqueiam a leitura, pois não é seguro inferir a coluna deslocada.

| Campo da origem | Interpretação e regra inicial |
| --- | --- |
| Regiao - Sigla / Estado - Sigla | Texto; recorte por UF `RJ` |
| Municipio | Texto original + chave normalizada por UF e nome |
| Revenda | Nome observado, obrigatório na fatia |
| CNPJ da Revenda | Original preservado; canônico textual de 14 dígitos, removendo espaço externo e `.`, `/`, `-` |
| Nome da Rua / Numero Rua / Complemento / Bairro / Cep | Texto preservado no registro original; não determinam validade da coleta nesta versão |
| Produto | `GASOLINA` na fatia; diferente de `GASOLINA ADITIVADA` |
| Data da Coleta | `dd/MM/yyyy` estrito → `date`, dentro de 01/01–30/06/2026 |
| Valor de Venda | Número positivo, até 7 dígitos inteiros e 3 decimais → `decimal(10,3)` |
| Valor de Compra | Opcional; vazio em todas as 422.418 linhas observadas; não preencher com zero |
| Unidade de Medida | Origem `R$ / litro` → moeda `BRL` e unidade `litro` |
| Bandeira | Atributo observado do posto, obrigatório na fatia |

O formato de CNPJ foi validado sintaticamente; não há consulta cadastral nem verificação dos dígitos verificadores. O original conserva inclusive espaço inicial e zeros. O contrato atual não afirma suportar futuros layouts alfanuméricos. A origem recebida tem até duas casas decimais; três foram reservadas para preço com escala explícita, sem uso de float nas regras de negócio.

Não misturar GNV (`R$ / m³`) com preços por litro. Os outros produtos foram perfilados, mas suas regras de publicação não foram implementadas neste bloco.

## Granularidade, duplicatas e conflitos

Uma observação representa preço de venda coletado em um posto, para um produto, em uma data e unidade. CNPJ + produto + data da coleta não apresentou conflitos após remover seis repetições exatas no arquivo completo. A chave de negócio inicial inclui também unidade: `(cnpj, produto, data_coleta, unidade)`. A unicidade observada neste arquivo é evidência amostral, não garantia para todo o histórico.

Não há agregação semanal na saída tipada. Quando ela for criada, usar semana ISO começando na segunda-feira, com ano ISO e data de início explícitos; os limites podem atravessar o semestre. A média por município atual tem como denominador coletas, não postos nem litros vendidos.

Duplicata exata é repetição dos mesmos 16 valores originais decodificados. Dados inválidos são classificados primeiro; depois separam-se repetições exatas. Se linhas restantes compartilham chave, todas as linhas dessa chave são conflitos. Nenhuma delas é escolhida arbitrariamente. No ensaio local, um conflito bloqueia o avanço de `current.json`, preservando o resultado anterior.

## Referência municipal

Snapshot de 92 municípios do RJ obtido da API oficial em 11/11/2026, preservado por hash. A resposta HTTP trouxe `Content-Encoding: gzip`; os bytes comprimidos foram guardados, e a leitura descomprime antes de interpretar o JSON.

Chave de correspondência: UF + nome em maiúsculas, normalização Unicode NFKD sem marcas de acento e espaços normalizados. Pontuação não é apagada nem há aproximação por similaridade. Zero ou múltiplas correspondências levam a quarentena. Os 27 nomes distintos da fatia encontraram um único código cada.

O snapshot atual não comprova o estado histórico dos limites ou nomes municipais em cada data de coleta. Esse limite deve acompanhar qualquer expansão temporal.

## Validade e sinal analítico

Quarentena contém registro original, número lógico do registro CSV e motivos: data inválida/fora do semestre, preço inválido ou não positivo, precisão incompatível, CNPJ fora do formato, campo obrigatório ausente, unidade incompatível ou município sem correspondência única.

Preço positivo incomum permanece aceito. O sinal exploratório `preco_incomum_iqr` usa quartis inclusivos e cercas Q1−1,5×IQR e Q3+1,5×IQR, somente em gasolina/RJ/litro/no semestre. Não é limite de preço legal, prova de erro ou limiar universal; será reavaliado no consumo temporal. Houve 26 sinais em dados reais, nenhum deles rejeitado.

Reconciliação do escopo: `selecionados = inválidos + duplicatas exatas excedentes + linhas conflitantes após deduplicação + aceitos`. Fora do recorte é uma categoria separada de rejeição. Mudança estrutural de CSV bloqueia tudo; não se filtra uma linha deslocada silenciosamente.

## Versões, reprocessamento e publicação

Downloads preservam URL, timestamps UTC, status HTTP, Content-Encoding, hashes, tamanho e caminho relativo. A ANP não forneceu ETag nem Last-Modified nesta resposta; o controle não depende deles.

O ensaio local reconstrói toda a fatia a partir da versão completa do semestre selecionada no manifesto. Uma correção de janeiro ou uma linha removida no novo snapshot pode alterar o resultado mesmo que a maior data continue em junho. O ponteiro só avança depois de escrever e reler o Parquet e fechar contagens. Não há filtro `MAX(data_coleta)`.

A versão usada localmente é a última entrega bem-sucedida baixada para aquele source_id. Isso ainda não constitui aprovação automática de uma versão para Gold. Quando houver uma republicação real, comparar escopo, conteúdo e contagens antes de promovê-la no Fabric. Nunca tratar um arquivo parcial como snapshot completo. Arquivo completamente inválido ou vazio não substitui a consulta anterior.

O ensaio presume que a entrega da URL semestral é um snapshot completo; verifica estrutura e validade das linhas, mas ainda não detecta toda incompletude semântica de uma republicação. A comparação de cobertura entre versões e a aprovação da troca de escopo precisam existir antes de publicação no Fabric. Não houve republicação real diferente observada neste bloco.

O hash de negócio exclui run_id, horário e posição no arquivo. Uma nova execução pode ter metadados diferentes e os mesmos valores de negócio. Os artefatos antigos ficam preservados. O ensaio é serial, sem suporte a concorrência ou transação entre camadas.

## Histórico de posto

Foram observados 14 CNPJs com mais de uma bandeira na fatia. Isso ainda precisa de investigação por data antes de montar a dimensão. SCD2 deverá significar vigência de atributos observados nas coletas, não data jurídica de mudança. O início de cada versão será uma data observada; intervalos serão `[inicio, fim)`, sem sobreposição, e fatos serão associados conforme a data da coleta.

Chegadas atrasadas/correções podem exigir recalcular intervalos e reassociar fatos do escopo. Ainda não há SCD2 implementado, SK de dimensão ou associação temporal validada. Fixtures de testes são sintéticos e não demonstram transições reais.
