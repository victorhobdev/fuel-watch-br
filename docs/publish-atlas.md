# Publicação do atlas no domínio

Destino: https://victorhob.me/fuelwatch/. Usa o mesmo GitHub Pages de `victorhobdev/victorhob1981.github.io`, que já publica o mapa da Rural. Fonte Pages: branch `main`, raiz `/`, domínio `victorhob.me`, arquivo `.nojekyll` existente. Não exige novo DNS nem recursos Fabric ativos.

## Fonte e atualização

O código do atlas está em `web/fuelwatch-atlas`. A cópia do Git interno da hospedagem anterior foi preservada em `.local/atlas-sites-git-backup-20261116` antes de incorporar os arquivos ao repositório principal. A publicação anterior no Sites permanece separada; o endereço de portfólio é o domínio acima.

1. Em `web/fuelwatch-atlas`, executar `npm ci` e `npm run build`. O comando inclui `--base=/fuelwatch/`; os dados usam `import.meta.env.BASE_URL`.
2. Em uma cópia atualizada de `victorhobdev/victorhob1981.github.io`, criar/atualizar somente `fuelwatch/` com o conteúdo de `dist/`. Preservar `CNAME`, `.nojekyll`, raiz, `mapa-rural/` e demais diretórios.
3. Conferir `git diff --stat`, fazer commit e push para `main`. Aguardar `repos/victorhobdev/victorhob1981.github.io/pages/builds/latest` indicar `built` para o commit enviado.
4. Conferir HTTP 200 para o HTML, manifesto, JS, worker e dados de uma UF; abrir o mapa e verificar seleção de UF, município e produto. Os arquivos de postos só devem carregar após selecionar uma UF.

## Retorno

Reverter apenas o commit que adiciona/atualiza `fuelwatch/` e aguardar novo build Pages. Não sobrescrever a configuração DNS ou restaurar o repositório inteiro. O atlas contém preços históricos e dados cadastrais ANP com data de snapshot explícita.
