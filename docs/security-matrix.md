# M07 — matriz antes dos testes

Estado: **fixtures verificados no Fabric como autor; testes com leitor ainda não executados**. A consulta ao diretório de 13/11 ainda encontrou somente a conta autora do projeto. A conta autora não pode ser usada como prova de restrição de leitura.

O setup real criou duas linhas sintéticas, compilou a função/policy RLS e a máscara, criou o notebook de autorização e gravou/leu o arquivo sintético no OneLake. O autor viu RJ/SP e o contato original, conforme [evidência](../evidence/fabric/security/author-setup-2026-11-13.json). Nenhum papel foi concedido por esse setup. Isso não prova filtragem ou negação para o leitor.

## Identidades e escopo

Em 13/11 o usuário informou que não fornecerá a conta leitora agora e autorizou continuar as outras frentes. Os casos de leitor/RLS/máscara permanecem pendentes; isso não equivale a aprovação dos testes ou aceite completo do M07.

- `AUTOR`: administra somente os itens do projeto nesta execução e prepara os fixtures.
- `LEITOR_RJ`: segunda conta organizacional, sem papel administrativo, proposta como Viewer do workspace `fuelwatch-dev`, sem ReadAll adicional, Write, Reshare ou UNMASK.
- Objetos de teste: tabela `lab_m07.access_fixture`, notebook `lab_m07_permission_probe` e arquivos em `Files/lab_m07/`. As tentativas de escrita não apontam para dados oficiais.
- Contas/IDs/tokens ficam em `.local/`; a evidência versionada usa aliases. O login do leitor terá cache Azure separado do autor.

## Seis casos de acesso

| Caso | Ação com LEITOR_RJ | Resultado esperado | Evidência necessária |
|---|---|---|---|
| A01 | GET dos metadados do Lakehouse/Warehouse pela API Fabric | Permitido | HTTP 200 e identidade/role conferidas |
| A02 | SELECT Gold pelo Warehouse/TDS | Permitido | 8.052 coletas e SELECT sem privilégios de escrita |
| A03 | UPDATE no fixture SQL com `WHERE 1=0` | Negado | Erro de permissão, não erro de sintaxe/conexão; dados íntegros |
| A04 | PATCH do notebook de teste com o mesmo displayName | Negado | HTTP 403; não testar no notebook 08 produtivo |
| A05 | Download do arquivo sintético de teste por OneLake/ADLS | Negado sem ReadAll adicional | HTTP 403; não confundir ReadData SQL com ReadAll |
| A06 | Upload de arquivo sintético no diretório de teste OneLake | Negado | HTTP 403 e arquivo não criado; limpar pelo autor se houver acesso indevido |

Cada caso deve registrar o esperado antes da execução e o observado depois. Uma identidade admin, uma falha de rede ou uma comparação de documentação não conta como teste de autorização. Se o comportamento divergir, investigar papéis herdados, compartilhamentos diretos e OneLake security antes de alterar a expectativa.

## RLS e mascaramento

O SQL preparado cria duas linhas sintéticas, uma RJ e uma SP. A policy deve permitir RJ ao leitor e manter ambas visíveis ao autor por uma condição explícita de permissão CONTROL; dbo também está sujeito ao predicado. A consulta real encontrou `CONTROL=1`, mas `IS_MEMBER('db_owner')=0` para o autor, portanto usar somente esse papel como bypass seria incorreto neste ambiente Fabric. A função não contém nome de conta. Confirmar CONTROL=0 e contexto real distinto no leitor antes de testar a restrição.

O leitor deve receber somente a linha RJ e um contato fictício mascarado. O autor confere as duas linhas e o valor fictício original. Nenhum CNPJ oficial é tratado como segredo e nenhum dado oficial recebe RLS/máscara para esse exercício. SQL RLS não protege automaticamente os arquivos OneLake; DDM não é autorização nem anonimização.

## Papéis e governança

Admin gerencia o workspace e seus acessos; Member pode compartilhar/adicionar papéis inferiores; Contributor escreve/executa itens; Viewer lê metadados e dados via SQL. Viewer não ganha ReadAll para OneLake/Spark pela associação ao workspace. Compartilhar somente um item é uma superfície diferente de conceder participação no workspace e pode acrescentar permissões específicas; registrar ambas no inventário.

Atribuir o Viewer ao leitor é a única concessão de workspace proposta para esse laboratório. Os fixtures e a policy ficam separados de Gold. Rótulos de sensibilidade e auditoria administrativa dependem de disponibilidade/licença/permissões; sua ausência deve ser documentada, sem reivindicar execução. Não há licença paga autorizada nem necessidade de nova capacidade para os testes.

## Login separado

Depois de confirmar que a conta leitora existe, fazer seu login interativo em um processo separado, com `AZURE_CONFIG_DIR=.local/azure-reader`. Para scripts Python, `FUELWATCH_IDENTITY=reader` seleciona esse cache; autor usa `author`/`.local/azure`. O shell operacional padrão restaura explicitamente a identidade autora. Não alternar identidades em um mesmo processo Python com tokens em memória. Se o login leitor retornar a conta autora, interromper antes dos testes; nunca interpretar o resultado como permissão do leitor.

Referências: [workspace roles](https://learn.microsoft.com/en-us/fabric/fundamentals/roles-workspaces), [lakehouse sharing](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-sharing), [RLS Warehouse](https://learn.microsoft.com/en-us/fabric/data-warehouse/row-level-security), [dynamic data masking](https://learn.microsoft.com/en-us/fabric/data-warehouse/dynamic-data-masking).
