# Próximo bloco — acesso e primeira execução no Fabric

Situação confirmada: há conta Azure e crédito de US$ 100 informado pelo usuário. Acesso ao Fabric ainda não configurado. Não foram confirmados tipo/validade da oferta Azure, tenant, usuário compatível, permissão, capacidade ou região. A tela de entrada do Fabric foi observada. A primeira consulta CLI foi bloqueada pelo sandbox ao escrever no cache; uma consulta posterior autorizada leu o cache com uma assinatura padrão em estado `Enabled`. A consulta online ao Azure Resource Manager falhou com `AADSTS700082` (refresh token expirado por inatividade). O cache não confirma o estado atual nem saldo; a consulta de capacidades não chegou a executar. Evidência sanitizada em `evidence/environment.json`.

## Acesso antes de capacidade paga

O usuário confirmou que usa **conta Microsoft pessoal**. A Microsoft documenta uma rota específica: usar a conta Azure existente, verificar o tenant próprio e criar/reutilizar um usuário Microsoft Entra para entrar no Fabric. O guia não exige atribuir funções administrativas ao novo usuário. A senha inicial e os desafios de autenticação devem ser configurados pelo usuário no portal. Referência: [trial Fabric com e-mail pessoal](https://learn.microsoft.com/en-us/fabric/fundamentals/free-trial-account-personal-email). Ainda não verificamos se esse usuário já existe.

1. Renovar o login interativamente no portal Azure (ou na CLI, quando formos retomar as consultas). Identificar o tipo de assinatura e se existe um tenant Microsoft Entra próprio para laboratório. Não usar tenant do empregador. Não enviar senhas, tokens ou IDs ao repositório.
2. Confirmar se há uma identidade de estudante ou de tenant próprio aceita em [app.fabric.microsoft.com](https://app.fabric.microsoft.com). Conta Microsoft pessoal, assinatura Azure e acesso ao serviço Fabric são condições diferentes. Se faltar uma identidade compatível, orientar a configuração conforme a conta disponível, sem iniciar outro trial pago por suposição.
3. Após entrar, verificar **Account manager → Start trial** e a opção de capacidade no workspace. Uma licença de avaliação Power BI não comprova capacidade Fabric para Lakehouse/Spark. A documentação descreve trial Fabric de 60 dias; elegibilidade, opções e região devem ser verificadas na conta.
4. Se o trial Fabric não estiver disponível, parar antes da criação paga. Comparar região, SKU, preço por hora, horas previstas, armazenamento, elegibilidade do crédito e prazo da oferta. Apresentar essa estimativa ao usuário e obter autorização. US$ 100 informados não autorizam consumir créditos ou criar capacidade.

Referências: [trial Fabric](https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial), [requisitos de inscrição](https://learn.microsoft.com/en-us/power-bi/fundamentals/service-self-service-signup-purchase-for-power-bi), [preços Fabric](https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/).

## Execução inicial, depois de validar acesso e capacidade

Os nomes abaixo são sugestões. Confirmar região e capacidade antes de criar itens. Evitar fixar IDs de workspace ou conexão em código compartilhado.

1. Criar workspace `fuelwatch-dev` usando capacidade trial confirmada e Lakehouse `lh_fuelwatch`. Registrar o estado real sem publicar dados de conta.
2. Criar **Data pipeline** `pl_anp_landing`. Adicionar **Copy data** com conexão **HTTP**, autenticação anônima para o arquivo público, método **GET**, formato **Binary**, sem descompressão. Manter validação TLS. URL exata em `config/sources.json`.
3. Destino **Lakehouse → Files**, caminho `landing/anp/2026-1/<identificador-da-tentativa>/ca-2026-01.zip`. Usar caminho novo por tentativa; não sobrescrever o arquivo já recebido. Conferir o tamanho inicial de 8.488.624 bytes e o hash no notebook. O ZIP evita interpretar a origem prematuramente como texto delimitado.
4. Importar `notebooks/01_landing_to_bronze.ipynb` como Notebook **PySpark (Python)**, anexar o Lakehouse como padrão e preencher a célula de parâmetros. O notebook usa `/lakehouse/default/Files`; a disponibilidade desse caminho deve ser confirmada no runtime anexado.
5. Executar com run_id novo. O notebook preserva o ZIP por hash, valida layout/linhas, extrai CSV e prepara strings + metadados para `bronze_anp`. Não deduplica a Bronze. A sobrescrita seletiva da mesma source_sha256 usa `replaceWhere`, cujo comportamento deve ser exercitado no runtime real; não houve execução Spark local.
6. Guardar resultado da Copy, run_id, versão do runtime e JSON de `Files/audit/anp/`. Verificar 422.418 linhas da versão inicial, incluindo seis repetições exatas. Reexecutar com novo run_id: mesma versão deve continuar com 422.418 linhas. Outras versões não devem ser removidas.

O suporte HTTP/Binary está descrito na [documentação da Copy activity](https://learn.microsoft.com/en-us/fabric/data-factory/connector-http-copy-activity). O Fabric aceita importação de `.ipynb`, conforme [documentação de notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook). O comportamento pretendido de substituição seletiva está descrito na [documentação do Delta Lake](https://docs.delta.io/delta-batch/). Essas referências validam o desenho; não comprovam a execução nesta conta.

## Critério de avanço e etapas posteriores

A etapa só muda de preparada para validada depois de execução no Fabric e reconciliação observada. Não há pipeline exportado com IDs inventados. A configuração da Copy activity e sua ligação ao notebook serão versionadas a partir dos itens reais, junto com integração Git.

Depois da Bronze, portar as regras locais para Silver PySpark e testar equivalência de dados, tipos e categorias. A Silver deve consumir uma versão escolhida e validada por escopo, e não todas as versões da Bronze em conjunto. Gold no Warehouse terá fato de coleta e dimensões de data, produto, município e posto com histórico observado. A agregação semanal será derivada.

O ensaio local não valida atomicidade do Delta/Warehouse, falha entre camadas, autorização OneLake/SQL, Git do workspace, implantação ou desempenho da capacidade. Esses são exercícios reais futuros. Não executar `OPTIMIZE`, `VACUUM`, RLS ou mascaramento apenas para constar no README.
