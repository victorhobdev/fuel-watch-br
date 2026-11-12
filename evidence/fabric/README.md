# Evidências Fabric fornecidas pelo usuário

`bronze/528c6d6e-2483-4024-bb31-925ccf1b1dee.json` reproduz o JSON de saída enviado pelo usuário após executar o notebook 01 no Fabric. O escape Markdown da URL foi removido; os demais valores foram preservados. Não houve consulta remota independente à tabela pelo agente.

A execução ocorreu em **11/11/2026, 21:17:15–21:17:42, America/Sao_Paulo**; o JSON conserva os timestamps originais em UTC. Hash do ZIP e hash do CSV coincidem com a entrega local perfilada. Os 8.488.624 bytes e 422.418 registros de origem/Bronze reconciliam com o perfil.

O resultado comprova a primeira carga conforme a auditoria apresentada. Não comprova repetição, Silver, Gold, segurança ou recuperação entre camadas. Run_id, caminho relativo e hashes são mantidos para rastreabilidade. Senhas e identificadores de conta não fazem parte desta evidência.

Próximo teste preparado: `notebooks/02_verify_bronze_replay.ipynb`. Capturar baseline com modo before, reexecutar o notebook 01 na mesma entrada e comparar no modo after. A aprovação exige mesma contagem e mesmo multiconjunto das 16 colunas originais, sem tratar as seis duplicatas exatas como erro da Bronze.
