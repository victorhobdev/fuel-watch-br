# Fuel Watch Atlas

React + TypeScript + MapLibre. Página de demonstração do snapshot histórico de resultados do projeto Fabric, com navegação Brasil → UF → município, seis combustíveis e 131 semanas.

## Rodar

```powershell
npm ci
npm run dev
npm run build
```

Node 22.12+; fonte Manrope auto-hospedada. Não há chaves de API, tiles externos, login no Fabric ou consultas cloud no navegador. O mapa usa malhas oficiais IBGE empacotadas. A publicação pública usa GitHub Pages no subdiretório `/fuelwatch/` de `victorhob.me`. O build define esse caminho base; em desenvolvimento, o Vite usa a raiz local.

## Dados e semântica

`public/data/manifest.json` registra origem, período, snapshot, hashes e critérios. Os seis produtos são carregados sob demanda. A semana inicial é a última completa (22–28/06/2026); 29–30/06 permanece selecionável e marcada como parcial.

- Cada posto tem um peso na mediana regional/nacional, a partir de sua mediana semanal.
- UF comparável: pelo menos 10 postos. Município comparável: pelo menos 3 e referência da UF elegível.
- `lo`/`hi` são extremos das coletas brutas aceitas. Não foram removidos preços positivos incomuns.
- Ausência de coleta não é zero. Cobertura varia por produto e semana.
- Geometria IBGE simplificada é o snapshot atual da API, sem reconstruir limites históricos. Rótulos municipais usam as sedes oficiais, nunca localizações de postos.
- Preços por posto são medianas semanais individuais. Seus arquivos ficam separados por produto e UF; o navegador só pede o arquivo depois que uma UF é escolhida. No zoom estadual os marcadores ficam agrupados; a partir do zoom 9 cada ponto abre nome, preço da semana, coletas e endereço.
- Localizações vêm da API de revendedores da ANP, consultada em 15/11/2026. O recorte inclui 8.933 dos 13.030 postos históricos: coordenadas no Brasil, estimativa de acurácia reportada e município compatível com o último registro de preço. A acurácia informada varia de 1 a 13 m (mediana 4 m), mas a própria ANP marca as posições como não validadas. Preço e endereço podem pertencer a datas diferentes; postos sem localização elegível não aparecem como pontos.
- Comparação cromática usa escala fixa de ±15%; valores além desse intervalo saturam a cor, mas o valor exato permanece no painel/tooltip.

`public/data/validation.json` contém a evidência de reconciliação dos três fingerprints Fabric, agregações, cobertura geográfica e 786 medianas nacionais recomputadas com Decimal. O exportador repetível é `scripts/export_snapshot.py`; execução a partir do ambiente Python analítico do repositório. Usa os artefatos locais reconciliados com o Fabric.

`scripts/data/anp-station-geography-2026-11-15.json` guarda o recorte público da API ANP usado para os marcadores. Para reconstruir os arquivos por posto, execute `python web/fuelwatch-atlas/scripts/export_station_map.py` a partir da raiz do repositório; o exportador valida compatibilidade de município/UF e a cobertura contra `posto_semana.parquet`.

## Referências de interface

A curadoria completa dos sete sites está em `../../docs/frontend-inspirations-2026-11-15.md`. As interações MapLibre seguem a documentação do mapcn e do MapLibre; o número animado é implementação própria inspirada em Number Ticker (Magic UI). Não foram copiados templates pagos, screenshots de produtos nem componentes de licença não conferida. Motion, Lucide, Manrope e MapLibre são dependências registradas no lockfile; suas licenças acompanham os pacotes.

## Validação

Build TypeScript/Vite, navegação em navegador, conferência de dados estáticos e auditoria npm. Esta página é uma camada de consumo do laboratório; não altera a aceitação do roadmap Fabric e não substitui prática de engenharia para DP-700.
