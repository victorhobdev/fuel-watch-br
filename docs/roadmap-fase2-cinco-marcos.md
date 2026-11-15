# Fase 2 — plano de execução em cinco marcos

Plano vigente aprovado pelo usuário: completar todos os marcos. O roteiro anterior de dez itens é detalhamento histórico; este agrupamento define o acompanhamento atual. A carga nacional já entregue integra F2-01, sem fechar sozinha o marco.

| Marco | Requisitos de aceite obrigatórios | Estado inicial |
|---|---|---|
| F2-01 Observatório nacional analítico | Base nacional; benchmarks/posição/persistência/bandeiras; seis respostas reconciliadas; relatório nacional funcional e renderizado; filtros e cobertura verificados | PARCIAL: somente base pronta |
| F2-02 Histórico e atualização | Dois anos completos adicionais mantendo 2026H1; contratos por versão; pipeline nacional parametrizado; novos/iguais/corrigidos/interrompidos/recuperados testados; publicação protegida; agenda finita desligada | NÃO FEITO |
| F2-03 Contexto socioambiental | População com referência temporal e join sem multiplicação; clima com geografia oficial, associação estação–município e completude; respostas exploratórias e página de contexto; cobertura/ausências/limites explícitos | NÃO FEITO |
| F2-04 Alertas e desempenho | Referência histórica versionada para eventos sintéticos; duplicatas/atrasos e ação real verificados; emissor/regra encerrados; gargalo real ampliado, baseline/intervenção medidos e reconciliados | NÃO FEITO |
| F2-05 Reprodução e entrega final | Artefatos necessários revisados/versionados; reconstrução em workspace vazio; dados comparados; promoção/restauração; CI e demo final; inventário final de recursos | NÃO FEITO |

Não alterar estes requisitos para se ajustar ao que já existe. Aceite exige evidência na abrangência do requisito. Não há prazo ou custo pago autorizado. Permanece dispensado o teste com segunda identidade, sem apresentá-lo como executado. Git seletivo já é experiência válida; reconstrução da solução ativa, e não quantidade de itens, é o objetivo adicional.

Sequência: F2-01 → F2-02 → F2-03 → F2-04 → F2-05, com coleta de métricas, contratos, qualidade e versionamento ao longo de todos. Falhas técnicas serão investigadas e corrigidas; dependências humanas reais não impedem trabalho independente autorizado.

Andamento detalhado e evidências: `evidence/phase2/progress.json`. Dados iniciais: `evidence/fabric/national/acceptance.json`. O plano técnico anterior descreve os contratos e os cuidados de cada componente: `fase-2-roadmap-observatorio-completo-2026-11-13.md`.

## Estado da revisão em 15/11/2026

F2-01 a F2-04 concluídos. F2-05 está parcial: o predecessor da publicação
histórica agora é verificado dentro da transação e foi exercitado em dev e no
workspace de rebuild; o pipeline integrado passou por uma repetição que pulou
a republicação. Falta reconstruir e validar esse pipeline no workspace limpo e
rodar CI para o commit corrigido. Evidências e pendências em
`evidence/phase2/progress.json`. Não foi criada capacidade paga; o consumo em
CU e a expiração da trial não foram verificados.
