# Metodologia — o que o painel mostra e como calcula

Referência para quem lê o painel. Cada número da tela vem de uma das regras
abaixo; onde há mais de uma definição possível, a escolhida e o motivo estão
escritos. As divergências com o painel em R que este substitui estão em
[`paridade-com-o-painel-r.md`](paridade-com-o-painel-r.md).

## Fonte e cobertura

- **SINAN nacional** (banco `cenarios_ai`, a base do Boletim) para os
  indicadores e as séries de Recife inteiro (canal endêmico, série anual,
  epicurva), e **SINAN municipal** (notificações de residentes em Recife,
  extração da Secretaria de Saúde) para bairro, mapa e os demais gráficos. Anos completos 2010–2023; 2024–2025 existem
  na extração mas incompletos, e o painel abre em **2023**.
- **SIM** para óbitos (o campo de óbito do SINAN é subnotificado — ver
  `dados.md`, armadilha 1).
- **População** por bairro: estimativas da prefeitura (`data/support/`), fixa
  por bairro; a de Recife inteiro é a soma.
- **Geografia**: 94 bairros e 8 Distritos Sanitários (DS I a VIII), da malha
  oficial da prefeitura.

A linha "Dados até / Processado em" sob o cabeçalho diz a data do último
registro incluído e a data da extração.

## Os oito indicadores

Todos são do **ano selecionado** e do **território selecionado** (Recife ou um
bairro). A seta compara com o ano anterior no mesmo território. A régua é o
**Boletim Epidemiológico de Tuberculose do Ministério da Saúde**, e as
definições são as do quadro de métodos dele.

**Recife inteiro** sai do SINAN nacional (`silver.tuberculose` no banco
`cenarios_ai`), que é a base do Boletim — `scripts/extrair_indicadores_sinan.py`
agrega no banco e só contagens por ano saem de lá. **O bairro** não existe no
SINAN nacional: sai do microdado da Secretaria, pelas mesmas regras.

*Casos novos* = caso novo + não sabe + pós-óbito.

| Indicador | Fórmula | Fonte | Recife 2023 | Boletim 2024 |
|---|---|---|---:|---:|
| Incidência /100 mil | casos novos ÷ população × 100.000 | SINAN + população | 105,8 (1.685 casos) | 99,0 (1.637) |
| Mortalidade /100 mil | óbitos por TB (A15–A19, causa básica) ÷ população × 100.000 | SIM | 8,85 (141) | 6,0 em 2022 (99; SIM 2022 = 99) |
| Cura | curas ÷ casos novos sem falência, mudança de esquema e TB-DR | SINAN | 59,9% | 51,5% (coorte 2022) |
| Interrupção | (abandono + abandono primário) ÷ o mesmo denominador | SINAN | 17,5% | 10,1% (coorte 2022) |
| Testagem HIV | casos novos com exame (positivo, negativo, em andamento) ÷ casos novos | SINAN | 81,5% | 67,7% |
| Coinfecção TB-HIV | HIV positivo ÷ casos novos | SINAN | 12,0% | 11,9% |
| TRM nos pulmonares | pulmonares com TRM-TB realizado ÷ casos novos pulmonares | SINAN | 40,9% | 38,7% |
| Não avaliados | (transferência + sem encerramento) ÷ o denominador da cura | SINAN | 13,4% | 17,2% (coorte 2022) |

Por que não bate no dígito com o Boletim:

- **Data do banco.** O Boletim de 2024 usou o banco de fevereiro/2024, com dado
  preliminar. Desde então entraram notificações, resultados de HIV e
  encerramentos — por isso testagem e cura sobem e não avaliados caem.
- **Coorte.** O Boletim publica cura e interrupção da coorte do ano anterior
  (2022 na edição de 2024). O painel mostra o ano de notificação selecionado;
  o ano mais recente tem casos ainda em tratamento.
- **População.** O Boletim divide por uma estimativa do IBGE (~1,65 milhão em
  2023); o painel usa a população do dataset (1,59 milhão).

Antes de out/2026 os cards vinham da tabela agregada da extração, que dava 2.485
"casos novos" e incidência de 156 para Recife em 2023: contava todas as
notificações, não só casos novos. O microdado municipal tem 1.920 casos novos
— a base municipal não passa pela deduplicação de transferências do SINAN
nacional —, e por isso **a soma dos bairros não fecha com a cidade**.

- **Mapa e ranking** contam os casos novos do microdado por bairro, pelas
  mesmas regras (1.864 nos 94 bairros em 2023), sobre a população de cada
  bairro. A cura e as demais proporções também.
- **Mortalidade no bairro**: o SIM não traz bairro de residência preenchido.
  O card do bairro fica vazio e a mortalidade saiu do mapa e do ranking —
  a coluna da extração somava 377 óbitos contra 141 da cidade (§7 da paridade).
- **População pequena** (abaixo de 5.000 hab.): a taxa é verdadeira e o mapa
  a pinta, mas o painel avisa — no tooltip do bairro e sob os cards quando
  ele está aberto — quanto **um caso pesa** na taxa. O Bairro do Recife tem
  554 moradores e 14 casos novos em 2023: 2.527 por 100 mil, com cada caso valendo
  180,5. É o centro antigo inteiro (Recife, Paissandu, Pau Ferro, Apipucos,
  Dois Irmãos, Boa Vista, Santo Antônio, Ilha do Leite): pouca gente morando
  e muita notificação. Nota, e não supressão, porque a incidência alta do
  centro é achado de vigilância.
- **Proporções em base pequena**: abaixo de **5** encerramentos (ou testados)
  o percentual não é calculado e o bairro aparece como "sem dado". Um bairro
  com 3 curas em 4 encerramentos não é "75% de cura". Taxas por população
  (incidência) não sofrem esse corte: população pequena não torna
  a taxa menos real.
- A fração sob os cards de proporção ("999 de 1.668") é exatamente a conta que
  produziu o percentual.

## Mapa

Coroplético por **bairro** ou por **Distrito Sanitário** (seletor "Recorte"),
sem mapa-base — só os polígonos de Recife, como no painel em R —, para as
três métricas que existem no nível de bairro: incidência, casos novos e cura.
Mortalidade não: o SIM não tem bairro. Clicar num polígono abre o território; "Ver Recife inteiro"
volta.

Três formas de colorir (seletor "Cores"):

| Método | Como corta | Quando usar |
|---|---|---|
| **Escala fixa** (padrão) | Cortes declarados, iguais em todo ano, com nome em cada faixa | **Comparar anos** — é a única em que a cor de 2021 e a de 2023 significam a mesma coisa |
| **Quebras naturais** | Jenks, seis classes: minimiza a variância dentro de cada classe, a partir dos dados do ano | Ver a estrutura dos dados daquele ano |
| **Quartis** | Percentis 25/50/75 da série do ano — 25% dos territórios em cada classe | "Este bairro está no quarto superior" |

Em todas, a legenda mostra ao lado de cada faixa quantos territórios caem
nela.

A escala fixa é uma régua: as faixas são sempre as mesmas, abertas nas pontas
("< 40,0", "≥ 424,0"), e aparecem mesmo quando nenhum bairro cai nelas. Os
cortes e o nome de cada faixa:

| Métrica | Faixas | Âncora |
|---|---|---|
| Incidência /100 mil | < 40 abaixo do Brasil · 40 a 79,9 até 2× Brasil · 80 a 105,9 abaixo do Recife · 106 a 211,9 até 2× Recife · 212 a 423,9 até 4× Recife · ≥ 424 mais de 4× Recife | 40 ≈ Brasil (37,3 no Boletim 2024); 106 = Recife 2023 (105,8) |
| Cura (%) | < 40 crítica · 40 a 59,9 baixa · 60 a 74,9 intermediária · 75 a 84,9 perto da meta · ≥ 85 meta OMS | **85% é a meta** do Plano Nacional / OMS |
| Casos novos | 0 · 10 · 25 · 50 · 100 · 200, sem nome | contagem não tem âncora; degraus redondos |

A âncora é a de Recife, e não a régua nacional: com a mediana dos bairros em
90,6 por 100 mil, os cortes do Brasil (10 · 20 · 40 · 80) poriam 53 dos 94
bairros na última faixa em 2023.

## Evolução temporal

Canal, série anual e epicurva contam **casos novos**, na mesma definição dos
KPIs: os doze meses do canal somam a incidência do card (105,8 em 2023), e a
série anual dá 1.685 casos em 2023.

**Canal endêmico** (aba padrão): a linha grossa é a incidência mensal do ano
selecionado; a faixa é o **intervalo interquartil (Q1–Q3) dos cinco anos
anteriores**, mês a mês; as linhas finas são esses anos. Mês acima da faixa
está acima do esperado para a época; abaixo, abaixo. O painel em R usa três
anos; escolhemos cinco porque com três, um único ano atípico (2020, pandemia)
desloca a faixa inteira. A incidência de cada ano usa a população daquele ano.
Em 2023, **8 dos 12 meses** ficaram acima da faixa: a incidência subiu de 82,3
em 2020 a 109,3 em 2022, e sob tendência de alta a faixa fica atrás — a leitura
é "a doença cresceu", não "houve surto".

Só existe para **Recife inteiro**: o SINAN nacional não tem bairro,
e uma taxa mensal por bairro (dezenas de casos ÷ dezenas de milhares de
habitantes) seria ruído.

**Incidência por ano** ("Todos os anos"): linha de Recife de 2010 a 2023, com
duas referências tracejadas — o Brasil de 2023 no Boletim de 2024 (37,3) e a
meta do Plano Nacional pelo Fim da Tuberculose (menos de 10 por 100 mil até
2035).

**Incidência mês a mês**: mapa de calor com um quadrado por mês, uma linha por
ano, de 2010 ao ano selecionado; quanto mais escuro, mais casos novos por 100
mil. É a epicurva dobrada em linhas: a queda de 2020 e a alta de 2022 aparecem
de relance.

Com um bairro aberto, a aba mostra a incidência anual do bairro (microdado,
2010–2023) junto com a do Recife. Num bairro pequeno um ou dois casos mexem
muito a linha: a leitura é a direção.

## Bairro

Ao clicar num bairro, a aba **Bairro** abre na frente:

- **a frase**: casos novos do ano e a incidência comparada à do Recife
  ("Guabiraba: 17 casos novos, 228,0 por 100 mil — 2,2× a do Recife");
- **a faixa dos 94 bairros**: cada ponto é um bairro, o aberto aceso com a
  posição ("10º de 94"), e a linha do Recife. Acima de 700 por 100 mil o ponto
  fica no fim da faixa — o Bairro do Recife (2.527, com 554 moradores)
  esmagaria os outros 93. Clicar num ponto troca de bairro;
- **a teia**: os sete indicadores do bairro (sem mortalidade, que não tem
  bairro) contra os do Recife. Cada eixo vai até o valor que 95% dos bairros
  não passam; é leitura de formato, e o valor exato está nos cards.

## Desfechos

**Caminho dos casos novos** (Sankey): a coorte do ano — casos novos sem
falência, mudança de esquema e TB-DR, a base do Boletim (1.668 em 2023) — e
para onde ela foi: cura (999), interrupção (292), óbito por TB (89), óbito por
outras causas (64), transferência (213) e sem encerramento (11).

**Cura e interrupção por ano**: as duas proporções de 2001 a 2023 com as metas
do Ministério da Saúde (cura ≥ 85%, interrupção ≤ 5%). O último ano ainda tem
tratamento em curso.

Com um bairro aberto, uma barra empilhada compara os desfechos do bairro aos
do Recife, em % da coorte, e o Sankey passa a ser o do bairro.

## Ranking

Os territórios do recorte atual (bairros ou DS) ordenados pela métrica do
mapa, com desempate pelo nome, no formato do boletim: valor escrito na ponta
da barra e a linha tracejada do Recife (incidência) ou da meta de 85% (cura).
Mesma fonte e mesmas regras do mapa, então a posição no ranking e a cor no
mapa nunca discordam.

## Pirâmide etária

Notificações por sexo e faixa etária (11 faixas, de "0 a 4" a "80 ou mais"),
do ano e território selecionados, calculadas do microdado a partir de
`NU_IDADE_N`. Registros sem idade ou sem sexo M/F ficam de fora.

## Tópicos de interesse

Cada variável vai no gráfico que serve a ela, escolhido pelo próprio dado:

- **sim/não** (agravos, populações especiais, beneficiário, tratamento
  observado): todas juntas num **pirulito**, o % de "Sim" de cada uma
  ordenado do maior para o menor — em 2023, alcoolismo 24,3%, tabagismo 23,3%,
  drogas 23,1%. Com um bairro aberto, o Recife vem como bolinha vazada na
  mesma linha. O ignorado conta no total e está no tooltip;
- **até quatro categorias** (forma clínica, HIV, encerramento): **rosca**, a
  maior escrita no centro ("83% Pulmonar");
- **cinco ou mais** (raça/cor, tipo de entrada, escolaridade): **barras** com o
  valor na ponta, onde as categorias pequenas (indígena 0,3%) continuam
  visíveis.

Abrem catorze: as dez do painel de origem e mais quatro sim/não que cabem de
graça no pirulito (privados de liberdade, diabetes, doença mental,
beneficiário). Distribuição
percentual das variáveis do SINAN entre as notificações do ano e
território: situação de encerramento, forma clínica, HIV, tipo de entrada,
raça/cor, agravos (alcoolismo, drogas, tabagismo), população em situação de
rua, profissional de saúde, e as demais disponíveis no seletor. "Ignorado" e
"não informado" ficam visíveis como categorias — omiti-los faria os
percentuais parecerem mais completos do que são. Mesmo corte de base pequena
dos KPIs.

Os tópicos e a pirâmide saem do **microdado** (registro a registro, sem
identificação) e contam **todas as notificações** do ano — por isso o tipo
de entrada mostra reingresso e recidiva. Os KPIs contam só **casos novos**,
do SINAN nacional: em 2023, 2.749 registros nos tópicos contra 1.685 casos
novos no card.
