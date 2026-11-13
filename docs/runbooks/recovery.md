# Recuperação do pipeline mestre — M05

**Preparado; exercício no Fabric pendente.** Não interpretar este runbook como prova de execução.

1. No `Monitoring hub`, identificar a execução raiz e a primeira atividade com falha. Guardar a saída/erro real e os tempos; não repetir todos os itens por hábito.
2. Relacionar o `Pipeline RunId` com `Files/audit/m05/<root_run_id>` e os caminhos dos recibos filhos. Recibo `started` não significa publicação válida; `failed` deve conservar a causa. O lote exportado precisa vir da execução atual, nunca do último arquivo encontrado indiscriminadamente.
3. Para a falha injetada Silver, confirmar que exportação, importação e publicação Gold não executaram. Rodar `90_assert_unchanged.sql` com a execução que capturou o baseline; fatos, dimensões e marcador anterior devem ser iguais, inclusive timestamps da publicação.
4. Para falha injetada Gold, confirmar erro 51999 após escritas e antes do commit. Conferir o mesmo guard: a transação Warehouse deve ter revertido fatos, histórico e marcador. Stage/arquivos de transferência não equivalem a publicação aceita.
5. Desativar a falha e iniciar uma nova execução raiz. Não reutilizar o identificador da tentativa e não sobrescrever seu baseline/auditoria. O caminho de recebimento, o hash aprovado e o escopo devem permanecer explícitos.
6. Após recuperação, conferir `m04_gold_snapshot_validated` e `m05_gold_attempt_validated`, com correspondência entre lote da tentativa e `gold.publication`. Esses retornos validam a carga Gold; a execução de ponta a ponta depende também do sucesso das atividades anteriores no pipeline. Repetir o fluxo completo e comparar negócio, cobertura, histórico e agregado; novos IDs/timestamps de tentativa são esperados.
7. Se a importação disser que o manifesto ainda não está visível no SQL endpoint, aguardar a sincronização e repetir somente a importação com o **mesmo lote aprovado**, antes de publicar. Não escolher outro lote para esconder atraso ou inconsistência. O retry finito precisa ser configurado e demonstrado no pipeline.
8. Em HTTP 430, conferir jobs/sessões ativos antes de tentar novamente. Encerrar somente a sessão identificada do laboratório, após verificar que não há trabalho necessário em andamento. Não ampliar capacidade paga. Aguardar liberação e registrar tentativa bem-sucedida separada da falha.

Não existe uma transação única entre Copy, Delta e Warehouse. Os guards protegem a verificação da publicação anterior, não garantem concorrência; este laboratório executa um publicador por vez. A referência municipal e o calendário permanecem fixos nesta primeira integração revisada.

Ao testar agendamento, usar uma janela delimitada e desabilitar após a execução comprovada. Registrar o estado final desabilitado e verificar que nenhum job ficou ativo. Nenhum agendamento foi criado nesta preparação.
