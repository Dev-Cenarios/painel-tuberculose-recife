# Guia de desenvolvimento

Para quem vai mexer no código: comandos, arquitetura e as armadilhas que já
custaram uma investigação. O que o painel mostra e como calcula está no
README e nas outras docs.

Painel de monitoramento da tuberculose do Recife, em Streamlit. Reconstrução
do painel Shiny/R da equipe parceira (`Projetos em R/dash monitoramento
recife`), construída sobre o núcleo de `../sinan` seguindo
`../sinan/docs/como-fazer.md`. **Os números seguem o Boletim Epidemiológico;
a cara segue o painel em R** — ver `docs/paridade-com-o-painel-r.md` para cada
divergência decidida.

**O mapa não mora aqui** desde 14/out/2026: `mapa`, `mapa_componente` e
`resiliencia` — e, desde o 0.6.0, os gráficos (`grafico_componente`) — vêm do
**`cenarios-core`** (`../cenarios-core`) 0.18.0, instalado
do wheel em `vendor/` em versão fixa. O que é de Recife entra pelo `app.py`:
`CAMPOS_CLIQUE = ("bairro_key", "ds")`, `QUANTIS = 4` (o core usa cinco),
`proporcao_maxima=None` (o teto de altura do core é para território largo).
Desde 26/out/2026 o mapa segue o tbbrasil: título em cima, legenda numa caixa
embaixo (não flutua mais) e dica de clique. Nomes de bairro em caixa normal
por `geo.nome_proprio` (a malha vem em caixa alta, com acentos errados).
Correção no mapa se faz lá, solta versão e o wheel é trocado aqui.

Documentação, código, commits e comentários em português.

**Entrega é um container** (e a mesma imagem roda na nossa VM — `docs/publicacao.md`). A imagem carrega os dados dentro
(7 MB) e vai por `docker save` para outra equipe rodar. Ver `README.md`.

## Comandos

Ambiente: o `.venv` do painel vizinho, `../sinan/.venv` (Python 3.13).

```bash
streamlit run app.py                       # aplicação (porta 8501)
pytest                                     # suíte (186 testes, ~20 s)
pytest tests/test_aplicacao.py -q          # ponta a ponta com AppTest
pytest tests/paridade -q                   # harness de paridade com o R
pytest -rs                                 # motivo de cada skip

python -m scripts.preparar_microdado       # CSV nominal → parquet sem identificador
python -m scripts.preparar_geometria       # shapefiles → data/geo/*.parquet

docker build -t recifetb:latest .
pytest tests/test_imagem.py                # abre a imagem: nada nominal dentro
docker run --rm -p 8512:8501 recifetb:latest
docker save recifetb:latest | gzip > entrega/recifetb.tar.gz
```

Sem formatter. `ruff check --select F` (do `.venv` do sinan) é o que se roda
para achar código morto — foi assim que 850 linhas herdadas saíram em set/2026.
Em desenvolvimento o painel roda na porta 8512.

## Dado nominal — regra absoluta

`data/origem/` tem o CSV cru do SINAN com nome, mãe, nascimento, CNS,
telefone, endereço e coordenadas de ~30 mil pacientes. **Nunca** entra no git
(`.gitignore`: `/data/`, `*.csv`), **nunca** entra na imagem (`.dockerignore`),
e `scripts/preparar_microdado.py` descarta 27 identificadores antes de gravar
o parquet — só o parquet viaja. `tests/test_imagem.py` abre a imagem pronta e
falha se achar `.csv`, `origem/` ou coluna identificadora. `.env.exemplo` não
tem segredo, e `tests/test_segredos.py` vigia.

## Arquitetura

**Fluxo:** `app.py` (página única) → `src/estado.py` (`Navegacao`: Recife →
distrito sanitário → bairro) → `src/data/*` → `cenarios_core.mapa` e
`cenarios_core.grafico_componente`. O aviso do canal endêmico
(`AVISO_CANAL`, "padrão desta cidade") é do painel e mora no `app.py`.

- **`src/data/escopo.py`** — `Escopo` com níveis BR/UF/MUN/BAIRRO.
  `no_municipio()` é a degradação explícita para leitores que não sabem de
  bairro. `chave_bairro()` normaliza nomes ("BAIRRO DO RECIFE" → "RECIFE").
- **`src/data/valores.py`** — `por_bairro`, `por_distrito` (join pela `ds` da
  geometria), `para_o_mapa`, `ranking`, `populacao_do_bairro`. `COMPOSICAO` é a
  tabela das variáveis de tópico. Proporção só com `MINIMO_PARA_PROPORCAO=5`;
  `POPULACAO_PEQUENA=5_000` põe nota (não corte) na taxa — `nota_populacao`.
- **`src/data/indicadores.py`** — os 8 KPIs na definição do Boletim do MS:
  cidade de `indicadores_sinan` (SINAN nacional, gerado por
  `python -m scripts.extrair_indicadores_sinan`, exige VPN e `.env`), bairro
  do microdado pelas mesmas regras. Mortalidade só do SIM (sem bairro).
  `desfechos` (Sankey e barra empilhada, cores em `DESFECHOS`) e as séries da
  cidade (`serie_anual_cidade`, `serie_mensal_cidade`, `serie_desfechos_cidade`).
- **`src/data/retrato.py`** — a aba Bairro (26/out/2026): tabela dos 94
  bairros para a faixa e a teia, posição e incidência anual do bairro.
  Coluna da direita: Bairro (só com bairro aberto, abre na frente) ·
  Evolução (canal + mapa de calor; no bairro, linha bairro × Recife) ·
  Desfechos (Sankey + cura por ano com metas) · Ranking (boletim) · Pirâmide.
- **`src/data/microdado.py`** — lê `sinan_recife` (37 colunas, sem
  identificador): `composicao` (join com `sinan_dict`), `serie_mensal`,
  `piramide`, `ranking_bairros`.
- **`src/data/canal.py`** — canal endêmico: quartis dos **5 anos anteriores**
  (`ANOS_REFERENCIA`; o R usa 3 — decidido em `docs/paridade-com-o-painel-r.md` §6).
- **`src/doencas/tuberculose.py`** — *disease pack*: `CORES` (híbrida: cromo
  azul institucional `#12346B` + cores de métrica da família), `ROTULOS_CURTOS`
  dos 6 KPIs, `CORTES_FIXOS` da escala fixa com a âncora de cada corte em
  comentário, `VARIAVEIS_DESTAQUE`. `carregar()` resolve por `SINAN_DOENCA`.
- **`cenarios_core.mapa`** — pydeck (Plotly não dá clique). Três
  classificações em `CLASSIFICACOES`: `FIXA` (padrão), `NATURAL` (quebras naturais),
  `QUARTIL` (com `quantis=QUANTIS`, quatro). O clique lê
  `bairro_key` e depois `ds` (`CAMPOS_CLIQUE`). **Sem mapa-base**: o core
  põe `ESTILO_SEM_FUNDO`, um `data:` URL com estilo vazio. O mapa abre na
  escala fixa, que é régua: `NOMES_FIXOS` do pack dá nome a cada faixa e a
  legenda leva nome e N ("< 40,0 abaixo do Brasil 13").
- **`src/theme/componentes.py`** — CSS dos cartões (`[class*="st-key-cartao-"]`),
  pills, legenda flutuante, `titulo_painel(texto, ajuda)`.

**Dados** (`data/`): `parquet/dashboard/incidence` (tem `nivel=BAIRRO`, 94
bairros), `sinan_landing` (linha TOTAL = M+F; não somar tudo), `_cache_ts`,
`sinan_recife`, `sinan_dict`; `geo/bairros.parquet` (com `ds`, `ds_nome`),
`geo/distritos.parquet`, `geo/recife.parquet`. `data/support/` é insumo do
pipeline, não da tela.

## Armadilhas que já morderam

- **Mapa e gráficos são componentes próprios**, portados do tbpe em
  21/set/2026: o do mapa hoje vem do cenarios-core
  (`cenarios_core.mapa_componente`; deck.gl vivo, voo da câmera e cor
  interpolada) e os gráficos também (`cenarios_core.grafico_componente` +
  `componente_grafico/` no pacote; ECharts vivo: ranking, tópicos, canal, série
  anual, casos por mês do bairro, epicurva, pirâmide). `key` estável,
  clique com nonce em `session_state`. O `graficos.py` Altair saiu em
  21/set/2026. Receita e medição: `../tbpe/docs/mapa-clique.md`.
- **Animação não se mede com a janela do navegador oculta**: o navegador
  cai para 1 quadro por segundo e dá falso negativo.
- **Módulos importados não recarregam** no Streamlit: editou `src/`, reinicie
  o servidor.
- `st.markdown` **remove `<script>`**: JS (trava de zoom do mapa) vai por
  `st.components.v1.html(..., height=0)`.
- `st.pydeck_chart` tem altura padrão 500 e **sobrescreve** a do deck: passar
  `height=`.
- Seletores de CSS do Streamlit: `[data-testid="stTab"]`,
  `.react-aria-SelectionIndicator`, `.st-key-<key>`. Inspecione o DOM antes de
  chutar.
- `use_container_width` está depreciado: `width="stretch"`.
- Quartis: **não arredondar** os cortes — arredondar excluía o mínimo e deixava
  um distrito branco. Escala fixa: o máximo entra como corte **a mais**, não no
  lugar do último, senão a âncora de cima some da legenda.
- `docker build` pelo wrapper do Bash pode reportar rc=0 com o daemon fora do
  ar — confira `docker image ls`. O Docker Desktop cai entre sessões; `docker
  desktop start` e esperar ~60 s.
- A rede do trabalho bloqueia github.com sem VPN. Como o painel está no ar
  na VM: `docs/publicacao.md`.

## Estado e decisões abertas

**A régua é o Boletim Epidemiológico do MS e, na mortalidade, o SIM** — o
painel em R deixou de ser referência em 23/out/2026 (§9 da paridade).
`docs/paridade-com-o-painel-r.md` é o diário: §2, §3, §4 e §7 fechados pela
régua nova. Mapa, ranking e séries contam casos novos (cidade do SINAN
nacional, bairro do microdado); mortalidade não entra no mapa (SIM sem bairro).
`docs/metodologia.md` é o que o cliente lê;
`docs/dados.md` é o contrato de dados.
