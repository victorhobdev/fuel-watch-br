# M11 — consumo Power BI verificado

O modelo `sm_fuelwatch` consulta `gold.powerbi_coletas` por DirectQuery. A view preserva as 8.052 coletas e acrescenta o início da semana ISO pelo calendário Gold. Não há cópia importada dos preços nem agregação antecipada que elimine o CNPJ/data.

O relatório `Fuel Watch BR` tem uma página com quatro indicadores, evolução semanal, comparação municipal e tabela de cobertura. O cabeçalho explicita ANP, GASOLINA/RJ, janeiro–junho de 2026 e BRL/litro. Seleções nos visuais aplicam filtros às demais medidas; a quantidade de observações acompanha o preço.

As cinco medidas foram comparadas com SQL em total, 27 semanas, 27 municípios e filtro de janeiro. Contagens são exatas; soma/média usam tolerância numérica de 1e-8 na comparação. A média é calculada por soma dos preços dividida pelo número de coletas, sem média de médias. Como `decimal` no modelo tem semântica de moeda fixa, a medida converte a soma para DOUBLE antes de DIVIDE para evitar arredondamento intermediário de quatro casas; o formato exibido tem três casas.

Totais de referência: 8.052 coletas, 502 postos, 27 municípios, soma 52.777,200 e média aritmética das coletas. Postos são CNPJs distintos dentro do filtro, não soma de contagens semanais. A pesquisa é amostral e não mede volume vendido ou todos os postos existentes.

A [conferência DAX/SQL](../evidence/fabric/consumption/measure-verification-2026-11-13.json) e a [renderização real em português](../evidence/fabric/consumption/powerbi-render-ptbr-2026-11-13.png) foram obtidas do Fabric/Power BI. A exportação PNG foi negada por configuração do tenant; usamos a exportação PDF permitida e renderizamos com Poppler para inspeção, sem mudar o tenant. Não houve controle de mouse nem publicação pública.

As definições nativas relidas estão em `fabric/m11/`, com identificadores de ambiente substituídos por placeholders. Elas documentam o resultado; os comandos `m11_model.py` e `m11_report.py` usam bindings privados para materializar um ambiente autorizado. `--update` atualiza somente os itens identificados e guarda a definição anterior. `check_m11.py` consulta medidas reais; um arquivo PBIR aceito, sozinho, não prova que os visuais funcionam.

O aceite global de M11 ainda depende da identidade leitora de M07 e da sincronização Git nativa de M08. O índice, a documentação e o inventário final já foram conferidos. Não confundir o consumo já validado com todos os marcos concluídos.
