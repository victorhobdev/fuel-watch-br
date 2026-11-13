# M07 — revisão da implementação

Estado: **aceito no escopo revisado pelo usuário em 13/11/2026**. A exigência de criar uma conta leitora e executar os testes negativos foi substituída por revisão do código e leitura da configuração real no Fabric. Isso não reclassifica os casos de leitor como executados. [Revisão real](../evidence/fabric/security/implementation-review-2026-11-13.json).

O setup real criou duas linhas sintéticas, compilou a função/policy RLS e a máscara, criou o notebook de autorização e gravou/leu o arquivo sintético no OneLake. O autor viu RJ/SP e o contato original, conforme [evidência](../evidence/fabric/security/author-setup-2026-11-13.json). Nenhum papel foi concedido por esse setup. Isso não prova filtragem ou negação para o leitor.

## Identidades e escopo

Em 13/11 o usuário dispensou expressamente a segunda conta e solicitou validar a implementação existente. O aceite M07 passa a ser revisão de implementação/configuração; não há pendência de criar identidade. A01–A06 e o resultado de RLS/DDM sob identidade restrita ficam **NÃO EXECUTADOS — fora do aceite revisado**.

- `AUTOR`: administra somente os itens do projeto nesta execução e prepara os fixtures.
- `LEITOR_RJ`: segunda conta organizacional, sem papel administrativo, proposta como Viewer do workspace `fuelwatch-dev`, sem ReadAll adicional, Write, Reshare ou UNMASK.
- Objetos de teste: tabela `lab_m07.access_fixture`, notebook `lab_m07_permission_probe` e arquivos em `Files/lab_m07/`. As tentativas de escrita não apontam para dados oficiais.
- Contas/IDs/tokens ficam em `.local/`; a evidência versionada usa aliases. O login do leitor terá cache Azure separado do autor.

## Seis casos de acesso — referência opcional, não executados

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

Em 13/11 a API administrativa de tenant respondeu HTTP 403 à conta autora. A consulta Graph da própria conta retornou somente `POWER_BI_STANDARD`, identificado pela referência Microsoft como Fabric (Free); não foram observadas licenças Pro/PPU/AIP atribuídas. Aplicação de rótulos fica **NÃO APLICÁVEL nas condições atuais de licença/permissão**, sem alegar criação de política Purview. A auditoria de jobs/receipts do projeto foi consultada; auditoria administrativa do tenant não foi executada. Nenhuma configuração global foi alterada. [Limites observados](../evidence/fabric/security/governance-limitations-2026-11-13.json).

Responsabilidades: o proprietário do projeto autoriza custo/destinos e guarda credenciais; o autor mantém código, contratos, auditoria e recuperação; o futuro leitor valida menor privilégio; administração do tenant controla habilitação Git/exports/MIP e políticas globais. Conexões de origem usam anonimato para dados públicos ou OAuth delegado, sem segredo no Git. Endpoint SQL, IDs e caches operacionais ficam em `.local`; as definições de portfólio são redigidas antes do push.

Referências de licenciamento: [identificadores de produtos](https://learn.microsoft.com/en-us/entra/identity/users/licensing-service-plan-reference), [requisitos para rótulos](https://learn.microsoft.com/en-us/fabric/enterprise/powerbi/service-security-apply-data-sensitivity-labels).

## Login separado — somente se o laboratório opcional for retomado

Depois de confirmar que a conta leitora existe, fazer seu login interativo em um processo separado, com `AZURE_CONFIG_DIR=.local/azure-reader`. Para scripts Python, `FUELWATCH_IDENTITY=reader` seleciona esse cache; autor usa `author`/`.local/azure`. O shell operacional padrão restaura explicitamente a identidade autora. Não alternar identidades em um mesmo processo Python com tokens em memória. Se o login leitor retornar a conta autora, interromper antes dos testes; nunca interpretar o resultado como permissão do leitor.

Referências: [workspace roles](https://learn.microsoft.com/en-us/fabric/fundamentals/roles-workspaces), [lakehouse sharing](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-sharing), [RLS Warehouse](https://learn.microsoft.com/en-us/fabric/data-warehouse/row-level-security), [dynamic data masking](https://learn.microsoft.com/en-us/fabric/data-warehouse/dynamic-data-masking).

## Resultado da revisão, 13/11/2026

`tools/fabric/m07_review.py` usa somente SELECTs e GET de workspace roles, sem mudar dados, identidades ou concessões. A leitura do catálogo confirmou:

- A função `lab_m07.allow_uf` coincide com o código versionado e está schema-bound.
- A policy `lab_m07.uf_filter` está habilitada/schema-bound e aplica um FILTER à coluna `uf` da tabela `lab_m07.access_fixture`.
- A coluna `contato_ficticio` tem exatamente a máscara `email()`; os dois registros são sintéticos, RJ/SP.
- O autor tem CONTROL=1 e db_owner=0, compatível com o bypass explícito. Workspace: uma atribuição Admin; nenhum leitor foi criado ou recebeu acesso.
- Os GRANTs explícitos de `public` encontrados apontam somente para objetos de sistema; não há concessão explícita a public de CONTROL, UNMASK ou escrita no inventário consultado.

**Conclusão:** nenhum desvio encontrado entre fonte e objetos implantados no escopo do laboratório. A regra RJ é fixa para qualquer chamador SQL sem CONTROL, não um mapeamento de regiões por identidade. O FILTER não é um bloqueio de INSERT; não se afirma isolamento regional de escritores. RLS/máscara do Warehouse não protegem automaticamente arquivos OneLake ou outras tabelas. DDM reduz exposição visual e não é anonimização nem defesa contra inferência por consultas.

O inventário de workspace roles não é uma auditoria completa de compartilhamentos de itens/grupos. Não foram exercitados A01–A06, RLS ou DDM com identidade restrita. Uma divergência futura exige investigar implementação, acessos herdados e configuração antes de atribuir causa ao fornecedor. Esses limites ficam registrados, mas não exigem nova conta no escopo escolhido.

Referências da revisão: [RLS](https://learn.microsoft.com/en-us/fabric/data-warehouse/row-level-security), [DDM](https://learn.microsoft.com/en-us/fabric/data-warehouse/dynamic-data-masking), [workspace roles](https://learn.microsoft.com/en-us/fabric/fundamentals/roles-workspaces).
