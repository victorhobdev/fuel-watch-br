# Evidências do Fuel Watch BR

Resultados reais do Fabric, separados de testes locais e fixtures. Bindings, credenciais e respostas com identidade permanecem em `.local`, ignorado pelo Git.

- [Gold e SCD2](fabric/gold/README.md): publicação e sete cenários.
- [Versões oficiais](fabric/versioning/official/README.md): seleção por versão, repetição e correções.
- [Orquestração](fabric/orchestration/): M05 e sete tentativas; a execução de teste do M08 tem identificação própria.
- [Dataflow Gen2](fabric/dataflow/): baseline, replay, contrato inválido e recuperação.
- [Segurança](fabric/security/): setup de autor e limites de governança; testes com leitor pendentes.
- [Implantação](fabric/deployment/): promoção, execução em test, revisão, recuperação do mesmo lote e restauração; Git nativo pendente.
- [Desempenho](fabric/performance/): amostras individuais, planos e reconciliação; não representam economia medida de CU.
- [Streaming](fabric/streaming/): transporte finito, consultas, ação Activator e desligamento confirmado.
- [Consumo](fabric/consumption/): reconciliação DAX/SQL e PDF/PNG reais do relatório.

Uma operação aceita pela API não equivale a uma execução concluída. Falhas originais e recuperações são preservadas separadamente; contagens isoladas não substituem os fingerprints de negócio.

[Status consolidado de 13/11](project-status-2026-11-13.json) inclui critérios aceitos, dependências humanas e CI real.
