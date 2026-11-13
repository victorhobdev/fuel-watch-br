# M08 — implantação entre ambientes

Estado: **repositório privado criado após aprovação explícita em 13/11/2026**: https://github.com/victorhobdev/fuel-watch-br . Push, runner, integração Git do workspace e implantação ainda pendentes. O aceite exige sincronização Git, promoção, execução reconciliada e restauração reais.

## Destino proposto para aprovação

Repositório novo **privado** `victorhobdev/fuel-watch-br`, mantendo o histórico local do Fuel Watch. A integração do workspace usará o diretório `fabric/workspace` em branch própria, evitando misturar as definições geradas pelo Fabric com os exports/documentos do projeto. O diretório deve começar vazio e ser preenchido pela primeira sincronização do workspace.

A criação/push aguarda aprovação do destino. Antes do primeiro push, revisar tanto os arquivos atuais quanto o histórico alcançável, porque remover um segredo só do último commit não o retira dos anteriores. Não publicar `.local`, caches Azure, conexões com tokens, senhas ou screenshots de contas.

O GitHub autenticado na CLI serve para criar o repositório e fazer push. Sua credencial ampla não será copiada para uma conexão Fabric. Para a integração nativa, preferir PAT fine-grained limitado ao repositório aprovado, com Contents read/write, informado pelo usuário diretamente no fluxo seguro da plataforma. Nunca pedir token no chat. Se a conexão não puder ser criada por CLI sem expor o segredo, orientar somente esse passo pela interface.

## CI sem contratação de compute

O workflow `.github/workflows/checks.yml` está preparado somente para `workflow_dispatch` e runner **self-hosted Windows efêmero**, com label `fuelwatch-local`, exclusivo do repositório privado. Não instala Windows service, não recebe jobs públicos nem fica permanente. Registrar runner apenas após aprovação do destino; iniciar para uma execução e remover/verificar seu encerramento ao final.

O job tem `contents: read`, checkout por SHA imutável, sem credencial persistida e sem Fabric secrets. Não publica artifacts nem usa cache hospedado. A cobrança do GitHub distingue compute hospedado e armazenamento; self-hosted permanece gratuito segundo a documentação consultada em 13/11/2026. O computador local precisa estar ligado durante a execução. Nenhuma capacidade Azure paga está autorizada.

`tools/ci/check.ps1` executa testes portáteis de contrato, versões, orquestração, recuperação e isolamento de identidade. O ambiente é criado com `tools/ci/requirements.lock`. A suíte completa local usa também arquivos ANP/bundles ignorados pelo Git; por isso não se pode afirmar que ela passou em um checkout limpo usando somente estes checks. Uma execução local do mesmo script não conta como execução no provedor.

## Promoção e bindings

1. Inventariar tipos reais, conexões, permissões e suporte vigente. Conferir tenant switches para Git/GitHub; a autenticação Azure, sozinha, não os prova habilitados.
2. Conectar `fuelwatch-dev` ao destino aprovado e sincronizar uma alteração real. Registrar commit e definição relida.
3. Criar `fuelwatch-test` **na capacidade trial existente verificada**, sem comprar SKU. Separar IDs/conexões conforme `config/environments.example.json`; os bindings reais ficam em `.local`.
4. Criar deployment pipeline dev → test. Selecionar itens com suporte confirmado e registrar o resultado por tipo. Não presumir que arquivos Delta, arquivos de entrada, dados Warehouse ou segredos sejam copiados com metadados.
5. Preparar dados/entradas imutáveis no teste, remapear Lakehouse padrão, referências de notebooks/pipeline, endpoints SQL e parâmetros M. Confirmar que nenhum item no teste escreve em dev. A conexão OAuth do Dataflow precisa ser autorizada no destino.
6. Executar a fatia aprovada no destino; reconciliar 8.052 coletas, 502 postos, 27 municípios e a projeção completa de negócio, além de Gold/semanas. IDs de execução e datas de observação podem mudar; não mascarar diferenças de negócio com contagens.
7. Promover uma mudança pequena e verificável, restaurar a versão anterior por versão/implantação e executar novamente no teste. Não apagar dados ou ambientes como substituto de rollback.
8. Encerrar runner/agendas, exportar definições sem segredos e registrar versões, resultados e limitações. Só então marcar M08 aceito.

## Particularidades já observadas

- M06 é Dataflow Gen2 com definição nativa e suporte atual a CI/CD. Ainda não foi promovido entre ambientes. Seu Execute API preview usado no projeto requer identidade delegada; não afirmar suporte a service principal apenas porque outras APIs o aceitam.
- As referências GUID no M e os bindings de conexões não podem ser tratados como automaticamente remapeados sem leitura do destino.
- Dataflow criou staging Lakehouse/Warehouse na capacidade atual; dependências não devem ser apagadas como lixo do projeto.
- A policy/fixture de segurança M07 é laboratório separado; identidade leitora e permissões de dev não devem ser propagadas silenciosamente para test.
- Os checks CI propostos não executam Spark nem promovem recursos; a validação de implantação é uma etapa separada com autenticação própria.

Referências: [Git integration](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-get-started), [deployment process](https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/understand-the-deployment-process), [Dataflow CI/CD](https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-cicd-and-git-integration), [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
