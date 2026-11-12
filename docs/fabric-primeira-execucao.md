# Próximo bloco — acesso e primeira execução no Fabric

## Progresso informado após a configuração

O usuário informou criação da identidade de laboratório, entrou no portal Fabric (captura da experiência Power BI), informou avaliação gratuita de 60 dias e confirmou a criação do Lakehouse após o roteiro de `lh_fuelwatch`. Nome efetivo do workspace, identificador/região/SKU da capacidade e execução de dados ainda não foram inspecionados. O próximo passo é a primeira Copy activity. Credenciais ficam no Gerenciador de Credenciais do Windows; não registrar senhas no projeto.

Atualização: usuário informou **Status do pipeline: Bem-sucedido** na primeira Copy. Isso registra o resultado relatado da ingestão, sem inferir tamanho/hash do arquivo ou sucesso de Spark. Próxima verificação: confirmar o ZIP em Files/landing, importar o notebook Bronze, anexar o Lakehouse como padrão e substituir EXECUTION_ID pelo nome real da pasta criada pela Copy. Na execução interativa, deixar `p_run_id` vazio para cada tentativa gerar UUID próprio; o caminho de landing fica na auditoria para relacioná-la à Copy. A versão inicial de referência deve reconciliar 8.488.624 bytes e 422.418 registros, além do SHA-256 esperado. Divergência exige investigação.

As notas de reconhecimento abaixo descrevem as condições observadas antes dessa configuração; não significam que o login do Fabric continue pendente.

Situação confirmada: acesso ao portal Azure com conta Microsoft pessoal. A tela enviada pelo usuário e o portal observado exibem uma assinatura chamada **Azure for Students**, papel **Owner** na assinatura e um diretório Microsoft Entra associado. Crédito de US$ 100 foi informado pelo usuário; saldo e validade não foram verificados. O nome exibido da assinatura não substitui a verificação da oferta. Acesso ao Fabric ainda não configurado; usuário Entra compatível, permissões do diretório, capacidade e região continuam sem confirmação.

O portal autenticado e a sessão da CLI são independentes. A primeira consulta CLI foi bloqueada pelo sandbox ao escrever no cache; uma consulta posterior autorizada leu o cache com uma assinatura padrão em estado `Enabled`. A consulta online ao Azure Resource Manager falhou com `AADSTS700082` (refresh token expirado por inatividade). A consulta de capacidades não chegou a executar. O login no portal não comprova renovação do token da CLI. Evidência sanitizada em `evidence/environment.json`.

## Acesso antes de capacidade paga

O usuário confirmou que usa **conta Microsoft pessoal**. A Microsoft documenta uma rota específica: usar a conta Azure existente, verificar o tenant próprio e criar/reutilizar um usuário Microsoft Entra para entrar no Fabric. O guia não exige atribuir funções administrativas ao novo usuário. A senha inicial e os desafios de autenticação devem ser configurados pelo usuário no portal. Referência: [trial Fabric com e-mail pessoal](https://learn.microsoft.com/en-us/fabric/fundamentals/free-trial-account-personal-email). Ainda não verificamos se esse usuário já existe.

1. No portal Azure já autenticado, buscar **Microsoft Entra ID**, abrir **Users** e verificar se já existe um usuário com **User principal name (UPN)** no domínio `.onmicrosoft.com` do diretório. Confirmar que o tenant é próprio para laboratório. O papel Owner da assinatura não comprova papel administrativo no diretório. Renovar a CLI separadamente somente quando retomarmos as consultas por ela. Não enviar senhas, tokens ou IDs ao repositório.
2. Confirmar se há uma identidade de estudante ou de tenant próprio aceita em [app.fabric.microsoft.com](https://app.fabric.microsoft.com). Conta Microsoft pessoal, assinatura Azure e acesso ao serviço Fabric são condições diferentes. Se faltar uma identidade compatível, orientar a configuração conforme a conta disponível, sem iniciar outro trial pago por suposição.
3. Após entrar, verificar **Account manager → Start trial** e a opção de capacidade no workspace. Uma licença de avaliação Power BI não comprova capacidade Fabric para Lakehouse/Spark. A documentação descreve trial Fabric de 60 dias; elegibilidade, opções e região devem ser verificadas na conta.
4. Se o trial Fabric não estiver disponível, parar antes da criação paga. Comparar região, SKU, preço por hora, horas previstas, armazenamento, elegibilidade do crédito e prazo da oferta. Apresentar essa estimativa ao usuário e obter autorização. US$ 100 informados não autorizam consumir créditos ou criar capacidade.

Referências: [trial Fabric](https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial), [requisitos de inscrição](https://learn.microsoft.com/en-us/power-bi/fundamentals/service-self-service-signup-purchase-for-power-bi), [preços Fabric](https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/).

## Execução inicial, depois de validar acesso e capacidade

Os nomes abaixo são sugestões. Confirmar região e capacidade antes de criar itens. Evitar fixar IDs de workspace ou conexão em código compartilhado.

1. Criar workspace `fuelwatch-dev` usando capacidade trial confirmada e Lakehouse `lh_fuelwatch`. Registrar o estado real sem publicar dados de conta.
2. Criar **Data pipeline** `pl_anp_landing`. Adicionar **Copy data** com conexão **HTTP**, autenticação anônima para o arquivo público, método **GET**, formato **Binary**, sem descompressão. Manter validação TLS. URL exata em `config/sources.json`.
3. Destino **Lakehouse → Files**, caminho `landing/anp/2026-1/<identificador-da-execucao>/ca-2026-01.zip`. No campo da pasta, usar **Add dynamic content** com `@concat('landing/anp/2026-1/', pipeline().RunId)`; nome do arquivo `ca-2026-01.zip`, formato Binary, sem compressão/descompressão configurada. Cada execução manual terá sua pasta; retries da mesma execução podem regravar seu landing. A preservação por hash ocorre depois, no notebook. O download local de referência teve 8.488.624 bytes; conferir tamanho e hash da versão efetivamente recebida, sem presumir que a origem nunca será republicada. O ZIP evita interpretar a origem prematuramente como texto delimitado.
4. Importar `notebooks/01_landing_to_bronze.ipynb` como Notebook **PySpark (Python)**, anexar o Lakehouse como padrão e preencher a célula de parâmetros. O notebook usa `/lakehouse/default/Files`; a disponibilidade desse caminho deve ser confirmada no runtime anexado.
5. Executar com run_id novo. O notebook preserva o ZIP por hash, valida layout/linhas, extrai CSV e prepara strings + metadados para `bronze_anp`. Não deduplica a Bronze. A sobrescrita seletiva da mesma source_sha256 usa `replaceWhere`, cujo comportamento deve ser exercitado no runtime real; não houve execução Spark local.
6. Guardar resultado da Copy, run_id, versão do runtime e JSON de `Files/audit/anp/`. Verificar 422.418 linhas da versão inicial, incluindo seis repetições exatas. Reexecutar com novo run_id: mesma versão deve continuar com 422.418 linhas. Outras versões não devem ser removidas.

O suporte HTTP/Binary está descrito na [documentação da Copy activity](https://learn.microsoft.com/en-us/fabric/data-factory/connector-http-copy-activity). O Fabric aceita importação de `.ipynb`, conforme [documentação de notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook). O comportamento pretendido de substituição seletiva está descrito na [documentação do Delta Lake](https://docs.delta.io/delta-batch/). Essas referências validam o desenho; não comprovam a execução nesta conta.

## Critério de avanço e etapas posteriores

A etapa só muda de preparada para validada depois de execução no Fabric e reconciliação observada. Não há pipeline exportado com IDs inventados. A configuração da Copy activity e sua ligação ao notebook serão versionadas a partir dos itens reais, junto com integração Git.

Depois da Bronze, portar as regras locais para Silver PySpark e testar equivalência de dados, tipos e categorias. A Silver deve consumir uma versão escolhida e validada por escopo, e não todas as versões da Bronze em conjunto. Gold no Warehouse terá fato de coleta e dimensões de data, produto, município e posto com histórico observado. A agregação semanal será derivada.

O ensaio local não valida atomicidade do Delta/Warehouse, falha entre camadas, autorização OneLake/SQL, Git do workspace, implantação ou desempenho da capacidade. Esses são exercícios reais futuros. Não executar `OPTIMIZE`, `VACUUM`, RLS ou mascaramento apenas para constar no README.
