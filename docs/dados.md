# Dados — de onde vêm, como são preparados e as armadilhas

Este é o "contrato de dados" do painel. Ele explica:

- **o que chega** da equipe parceira;
- **o que o painel lê**;
- **como o dado com nome de paciente vira dado sem identificação**;
- **as armadilhas** que já fizeram a gente perder tempo investigando.

**Sobre a numeração das armadilhas:** ela segue a do painel nacional (`../sinan/docs/contrato-dados.md`), de onde o código herdou as referências. Por isso os números pulam: as que não valem para Recife não aparecem aqui, e as novas continuam a contagem de lá.

**Números conferidos em out/2026**, direto nos arquivos de dados que estão no servidor.

> **Desde 23/out/2026 a régua é o Boletim Epidemiológico.** Os números de Recife inteiro (cards, canal endêmico, série anual e epicurva) vêm do `indicadores_sinan`, extraído do SINAN nacional por `scripts/extrair_indicadores_sinan.py`. Bairro, mapa e ranking contam os casos novos do dado caso a caso (`sinan_recife`), pelas mesmas regras. As definições e os números em vigor estão em [`metodologia.md`](metodologia.md); a história da mudança, no §9 da [paridade](paridade-com-o-painel-r.md).

---

## O que chega

São duas entregas da equipe parceira, as duas guardadas em `data/`, que **não vai para o git**:

| Pasta | O que tem | Vai para a imagem Docker? |
|---|---|---|
| `data/origem/` | O CSV **com nome de paciente** do SINAN (`SINAN_RECIFE_TB.csv`, ~30 mil registros) e do SIM, e os contornos dos bairros e distritos em `malha/` | **Nunca** |
| `data/parquet/dashboard/` | Números já agregados pela equipe parceira, no mesmo formato do painel nacional, em pastas por partição (`doenca=…/nivel=…/ano=…`) | Só os conjuntos da tabela abaixo |
| `data/support/` | População por bairro (`pop_bairro_rc.csv`, `pop_bairro_estimado.csv`) | Não. Serve só para preparar os dados |
| `data/geo/` | Contornos para o mapa, gerados por nós | Sim |

## O que o painel lê

| Conjunto de dados | Pastas (partições) | Para que serve | Menor nível |
|---|---|---|---|
| `incidence` | `doenca/nivel/ano` | Números de destaque da cidade, mapa, ranking e números de destaque do bairro (`casos_total`, `casos_obitos`, `casos_cura`, `pop_total`, `encerramento_total`, `abandono`, `hiv_pos`, `hiv_tested`) | **Bairro** (94) |
| `sinan_landing` | `doenca/nivel/ano` | As variáveis do SINAN, uma linha por código (`variavel`, `valor`, `valor_lbl`, `sexo`, `n`). Usado para HIV e encerramento (`SITUA_ENCE`) da cidade | Município |
| `_cache_ts` | `nivel/doenca/ano` | Casos por mês: canal endêmico e curva epidêmica de Recife | Município |
| `cache_ts_sim_obitos` | `nivel/doenca/ano` | Óbitos do SIM, para a mortalidade | Município |
| `sinan_recife` | `ano` | **Os casos um a um, sem identificação**: as 37 colunas permitidas + `bairro_key` (o nome do bairro padronizado). Usado nos tópicos, na pirâmide, na curva epidêmica e no ranking por bairro | Bairro |
| `indicadores_sinan` | — | Indicadores e séries mensais de Recife inteiro, extraídos do SINAN nacional (`recife.parquet` e `recife_mensal.parquet`). É a base do Boletim | Município |
| `sinan_dict` | `doenca` | O "dicionário": de código para nome (ex.: `1` → "Cura") | — |
| `meta` | `doenca` | Até quando vai o dado (`dados_ate`) e quando foi processado (`processado_em`). É o que aparece na linha de "fonte" da tela | — |
| `geo/bairros.parquet` | — | Os 94 bairros, com `bairro_key`, o distrito (`ds`) e o nome do distrito (`ds_nome`) | — |
| `geo/distritos.parquet` | — | Os 8 distritos sanitários, montados juntando os bairros | — |
| `geo/recife.parquet` | — | O contorno da cidade | — |

**Lidos em papel menor:**
- `piramides` e `obitos_sim_faixa`: a pirâmide de Recife inteira (a de bairro sai do `sinan_recife`);
- `incidence_0_14`: calculado em `kpis.calcular`, mas sem cartão na tela;
- `cases_new`: só nos testes de paridade.

**Vêm na extração, mas ficam fora da imagem**, porque nada lê: `popsvs/` (54 MB de arquivos do IBGE) e `dim_geo/`. O `tests/test_imagem.py` confere isso.

### Cuidado com a ordem das pastas

**Cada conjunto organiza as pastas numa ordem diferente.** Por exemplo, o `incidence` é `doenca/nivel/ano`, e o `_cache_ts` é `nivel/doenca/ano`. A ordem de cada um está escrita em `src/data/conexao.py` → `PARTICOES`.

**O painel escolhe os arquivos pelo caminho da pasta, não pelo filtro da consulta (`WHERE`).** O motivo: se a consulta pegar a pasta inteira de uma vez, ela junta arquivos com colunas diferentes. O DuckDB usa as colunas do primeiro arquivo e **as outras colunas somem, sem nenhuma mensagem de erro**.

---

## Como os dados são preparados

São dois scripts. A gente roda os dois a cada extração nova. Eles podem ser rodados quantas vezes quiser, e o resultado é sempre o mesmo:

```bash
python -m scripts.preparar_microdado    # data/origem/SINAN_RECIFE_TB.csv → sinan_recife/
python -m scripts.preparar_geometria    # data/origem/malha/*.shp → data/geo/*.parquet
```

### `preparar_microdado`: tira a identificação

- Funciona com uma **lista de colunas permitidas** (`COLUNAS`, 37 colunas). **O que não está na lista não passa**, mesmo que exista no CSV.
- Guarda à parte a lista dos **27 identificadores jogados fora** (`IDENTIFICADORES_DESCARTADOS`): nome, nome da mãe, nascimento, cartão do SUS, prontuário, CEP, telefone, rua, número, complemento, ponto de referência, latitude, longitude, número da notificação, entre outros. Essa lista existe para ninguém colocar um deles de volta achando que foi esquecimento.
- **Tira notificações repetidas** usando o número da notificação, mas sem gravar esse número.
- **Padroniza o nome do bairro** com `chave_bairro()` (ex.: "BAIRRO DO RECIFE" → "RECIFE"), para casar com o mapa.
- **Dois testes vigiam:** o `tests/test_microdado.py` confere que nenhuma coluna proibida existe no arquivo gerado, e o `tests/test_imagem.py` confere o mesmo no arquivo **que está dentro da imagem Docker**.

### `preparar_geometria`: prepara o mapa

Lê os contornos dos bairros e o `Distrito_per.shp` e grava três arquivos:
- `bairros.parquet`: cada bairro com o seu distrito ("DS - I" a "DS - VIII");
- `distritos.parquet`: os distritos, juntando os bairros de cada um;
- `recife.parquet`: o contorno da cidade.

---

## Privacidade

- **Git:** o `.gitignore` barra `/data/` e `*.csv`. Nada de `data/` vai para o GitHub.
- **Docker:** o `.dockerignore` barra `data/origem/` e `**/*.csv`. O arquivo com nome de paciente nem chega perto da imagem.
- **O único dado caso a caso que vai para a imagem é o `sinan_recife`**, já sem identificação.
- **Senhas:** o `.env.exemplo` não tem senha nenhuma, e o `tests/test_segredos.py` falha se alguém preencher uma.

---

## Armadilhas

### 1. O SINAN não traz óbito; o óbito vem do SIM

**Na cidade:** no `incidence`, o campo `casos_obitos` da tuberculose é **zero em todos os anos**, porque o SINAN não preenche esse campo. Por isso, mortalidade e letalidade da cidade saem do **SIM** (`cache_ts_sim_obitos`). São duas fontes diferentes, e quem junta as duas é o painel (`leitura.obitos_sim`).

**No bairro:** não tem SIM por bairro. Então o mapa e o cartão do bairro usam o `casos_obitos` do `incidence` no nível de bairro, que ali **vem preenchido**. Só que esse número **não fecha com o da cidade**:

| | Óbitos em 2023 |
|---|---:|
| Soma dos 94 bairros | **377** |
| Recife, nível de município (bate com o SIM e com `SITUA_ENCE = 3` no dado caso a caso) | **141** |
| Óbito por TB + óbito por outra causa (`SITUA_ENCE` 3 + 4) | 233 |

Nenhuma conta óbvia chega no 377. **Enquanto a equipe parceira não explicar o que essa coluna conta no bairro, a mortalidade por bairro serve para comparar bairros entre si**, não para comparar com a taxa da cidade. Está registrado no §7 da paridade.

### 2. O código da doença muda de um conjunto para outro

Em Recife, é `TUBERCULOSE` tanto nos agregados quanto no `sinan_landing`. Mas no painel nacional tem casos em que muda (`HANS` × `HANSENIASE`). Por isso, **toda junção passa por `config.cod_agregado`, `cod_landing` ou `cod_sim`**, e nunca pelo texto direto.

### 3. Códigos podem vir "sujos" (espaço ou zero à esquerda)

No painel nacional, os códigos do `sinan_landing` vinham com espaço na frente (`" 1"`, `" 2"`). Sem limpar, **todo filtro por código devolve zero, sem dar erro**.

**Na extração atual de Recife** (conferida em out/2026):
- **nenhum código vem com espaço**;
- **zero à esquerda aparece** em algumas variáveis, como escolaridade (`CS_ESCOL_N`), transferência (`TRANSF`) e tratamento supervisionado (`TRATSUP_AT`). Não aparece em `SITUA_ENCE`.

O painel **limpa os dois casos antes de comparar**: o `microdado.composicao` faz `ltrim(valor, '0 ')`, que tira zeros e espaços do começo, antes de juntar com o dicionário. **Não tire essa limpeza** só porque a extração de hoje veio limpa: a próxima pode vir suja.

### 4. Três jeitos de calcular a interrupção do tratamento

| Regra | Conta como interrupção (`SITUA_ENCE`) | Divide por | Recife 2023 |
|---|---|---|---:|
| `paridade` (igual ao painel em R) | `2` (abandono) | todos os encerramentos | 22,5% |
| `ms` (indicador de monitoramento do MS) | `2` e `10` (abandono e abandono primário) | só os avaliados (tira `5`, `7` e `8`) | 28,1% |
| **`boletim`** (Tabela 9 do Boletim) | `2` e `10` | todos os encerramentos | **23,5%** |

**O painel usa a regra `boletim`** (`kpis.REGRA_INTERRUPCAO`). A cura usa o mesmo denominador, para as duas taxas poderem ser lidas lado a lado. Detalhes e medições em `paridade-com-o-painel-r.md`.

> "Todos os encerramentos" inclui os registros com código `NA`. Se alguém refizer a conta sem eles, os números saem um pouco diferentes (por exemplo, 23,7% em vez de 23,5%).

### 5. O nome do encerramento vem agrupado

No `valor_lbl`, os encerramentos vêm agrupados em só três nomes: Favorável, Desfavorável e Não avaliado. **Abandono, óbito e falência aparecem todos como "Desfavorável".** Para separar um do outro, **filtre sempre pelo código, nunca pelo nome**.

### 11. O `sinan_landing` tem uma linha `TOTAL`: somar tudo conta em dobro

A coluna `sexo` traz `M`, `F`, `I` (ignorado, em alguns anos) **e `TOTAL`**. O `TOTAL` já é a soma dos outros. Então, **somar a tabela inteira dá o dobro**.

- Nas **porcentagens** isso não aparece, porque o de cima e o de baixo dobram juntos.
- Nas **contagens mostradas** e no **limite de "base pequena"**, aparece.

**O painel em R tem esse dobro.** Nós lemos só `sexo = 'TOTAL'` (§1 da paridade).

### 18. O agregado e o dado caso a caso contam coisas diferentes

| Fonte | Recife 2023 | O que conta |
|---|---:|---|
| `indicadores_sinan` (SINAN nacional) | **1.685** | **Casos novos**, pela definição do Boletim |
| `sinan_recife`, filtrado | **1.920** | **Casos novos** do dado caso a caso, sem a deduplicação de transferências do SINAN nacional |
| `sinan_recife` (linhas) | **2.747** | **Todas as notificações** do ano |
| `incidence` → `casos_total` | **2.485** | Todas as notificações, na contagem do agregado |

Até 23/out/2026 os cards usavam o `casos_total` do agregado como se fosse "casos novos". Hoje:
- **números de destaque da cidade** usam o `indicadores_sinan`;
- **mapa, ranking e bairro** usam os casos novos do dado caso a caso;
- **tópicos e pirâmide** contam todas as notificações do dado caso a caso.

Por isso **a soma dos bairros não fecha com a cidade**. A diferença está explicada na metodologia e no §2 da paridade.

> Versões antigas deste documento falavam em 2.749 notificações. No arquivo atual são 2.747. Não deu para conferir de onde veio o 2.749, porque o CSV original não fica no servidor.

### 19. O HIV pode ser calculado de dois jeitos

| Nível | Divide por | Recife 2023 |
|---|---|---:|
| Bairro (`incidence`) | **todos os casos** (349 ÷ 2.480) | 14,1% |
| Cidade (`sinan_landing`) | **só os testados**, positivo + negativo (351 ÷ 2.018) | 17,4% |

**A decisão está pendente** (§3 da paridade). Até lá, **o cartão do bairro e o da cidade não podem ser comparados** nesse indicador.
