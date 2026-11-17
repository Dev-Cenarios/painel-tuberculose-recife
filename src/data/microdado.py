"""Leitura do microdado do SINAN de Recife — uma linha por notificação.

**Esta camada não existe no painel nacional**, e é a diferença de arquitetura
que define este projeto.

Lá tudo vinha pré-agregado: composição, meses e pirâmide saíam de datasets já
somados por geografia. Aqui só ``incidence`` desce a bairro. Composição, meses
e pirâmide **por bairro** não existem prontas em lugar nenhum — o painel de
origem as calcula relendo o CSV cru a cada interação (`mod_charts.R:307`), e
aqui elas saem daqui, de parquet particionado por ano.

Rotulagem
---------

Os rótulos de categoria **não** são escritos aqui: vêm do ``sinan_dict``, o
mesmo dicionário que a camada agregada usa. Isso não é economia, é garantia —
se as duas fontes rotulassem por conta própria, "Desfavorável" poderia
significar coisas diferentes em dois gráficos da mesma tela.

O dicionário já entrega ``SITUA_ENCE`` reagrupado em Favorável, Desfavorável e
Não avaliado, que é exatamente o que o painel de origem mostra. E o join
normaliza o **zero à esquerda**: o dado traz ``03`` convivendo com ``3`` em
2018 e 2019, e ``trim`` não resolve isso — sem normalizar, esses registros
cairiam calados fora de qualquer categoria.

A questão em aberto
-------------------

Para Recife/2023 o microdado tem **2.749** notificações distintas e a camada
agregada declara **2.485** — em ``cases_new`` e em todas as 42 variáveis do
``sinan_landing``. Não é residência, bairro nem retratamento: os três foram
conferidos. São extrações diferentes, e qual delas vale está perguntado à
equipe parceira.

**Esta camada não decide isso, e de propósito.** Ela lê o microdado e diz
quanto ele tem, via :func:`total`. Quem escolhe qual fonte alimenta cada
elemento da tela é o ``app.py``, e a resposta que vier vira fiação lá — não
reescrita aqui. Enquanto isso, `total` existe justamente para que a diferença
seja mensurável a qualquer momento, em vez de descoberta na revisão.
"""

from __future__ import annotations

import pandas as pd

from . import config
from .conexao import conectar
from .escopo import Escopo

#: Abaixo disto o percentual não é publicável — proporção sobre dois registros
#: não é achado, é ruído. Mesmo limiar da camada agregada.
MINIMO_PARA_PERCENTUAL = 5

#: Faixas da pirâmide, iguais às do dataset `piramides`: quinquênios até 19
#: anos e décadas daí em diante. Reproduzidas para que microdado e agregado
#: sejam comparáveis linha a linha — banda diferente inviabiliza a conferência.
FAIXAS = (
    (0, 4, "0 a 4 anos"),
    (5, 9, "5 a 9 anos"),
    (10, 14, "10 a 14 anos"),
    (15, 19, "15 a 19 anos"),
    (20, 29, "20 a 29 anos"),
    (30, 39, "30 a 39 anos"),
    (40, 49, "40 a 49 anos"),
    (50, 59, "50 a 59 anos"),
    (60, 69, "60 a 69 anos"),
    (70, 79, "70 a 79 anos"),
    (80, 200, "80 anos ou mais"),
)

#: Idade em anos completos a partir de ``NU_IDADE_N``.
#:
#: O campo do SINAN é composto: o primeiro dígito é a **unidade** — 2 dias,
#: 3 meses, 4 anos — e os três últimos o valor. ``4032`` é 32 anos; ``3011``
#: é 11 meses, que em anos completos é zero.
#:
#: Ler os quatro dígitos como número põe uma criança de 11 meses na faixa de
#: 3.011 anos. Em Recife são 222 registros com unidade diferente de ano, todos
#: menores de um ano — 0,75% do total, e todos na primeira faixa da pirâmide,
#: que é justamente a que o KPI de 0 a 14 anos observa.
_IDADE_EM_ANOS = """
    CASE
        WHEN substr(trim(NU_IDADE_N), 1, 1) = '4'
            THEN TRY_CAST(substr(trim(NU_IDADE_N), 2) AS INTEGER)
        WHEN substr(trim(NU_IDADE_N), 1, 1) IN ('1', '2', '3')
            THEN 0
        ELSE NULL
    END
"""


def _sem_zero_a_esquerda(coluna: str) -> str:
    """SQL que tira o zero à esquerda preservando o próprio ``'0'``.

    ``ltrim(x, '0')`` sozinho transforma ``'0'`` em string vazia, o que
    silenciaria a categoria zero em vez de normalizá-la. O ``regexp_replace``
    com lookahead resolveria em outros bancos, mas o DuckDB não aceita ``(?=``.
    """
    limpo = f"ltrim(trim({coluna}), '0')"
    return f"CASE WHEN {limpo} = '' THEN '0' ELSE {limpo} END"


#: caso novo do Boletim: caso novo, não sabe, pós-óbito; sem mudança de diagnóstico
CASO_NOVO = (
    "trim(TRATAMENTO) IN ('1', '4', '6') "
    f"AND coalesce({_sem_zero_a_esquerda('SITUA_ENCE')}, '') <> '6'"
)


def _fonte() -> str:
    """Glob do microdado. Não usa `conexao.caminho`: o dataset é local deste
    painel e tem partição só de ano, sem doença nem nível."""
    base = config.dashboard_dir() / "sinan_recife"
    if not base.is_dir():
        raise FileNotFoundError(
            f"Microdado não encontrado em {base}.\n"
            f"Gere com: python -m scripts.preparar_microdado"
        )
    return (base / "**" / "*.parquet").as_posix()


def _onde(esc: Escopo) -> tuple[str, list]:
    """Filtro de ano e, quando o escopo for de bairro, de bairro.

    Em qualquer nível acima de BAIRRO o recorte é Recife inteiro — que é todo
    o conteúdo do dataset. Não há o que filtrar, e filtrar por município aqui
    seria filtrar por uma coluna que a conversão descartou.
    """
    sql = "ano = ?"
    params: list = [esc.ano]
    if esc.nivel == "BAIRRO":
        sql += " AND bairro_key = ?"
        params.append(esc.bairro)
    return sql, params


def total(esc: Escopo) -> int:
    """Notificações no recorte.

    É por aqui que se mede a diferença entre esta fonte e a agregada — ver a
    seção "A questão em aberto" na docstring do módulo.
    """
    onde, params = _onde(esc)
    linha = conectar().execute(
        f"SELECT count(*) FROM read_parquet('{_fonte()}') WHERE {onde}", params
    ).fetchone()
    return int(linha[0]) if linha else 0


def composicao(esc: Escopo, variavel: str) -> pd.DataFrame:
    """Distribuição de uma variável do SINAN, com percentual quando cabe.

    Devolve ``categoria``, ``n``, ``pct`` e ``total``. É a única fonte dos
    tópicos de interesse: a versão agregada (`leitura.composicao`, herdada do
    painel nacional) saiu em set/2026 porque o `sinan_landing` de Recife não
    desce a bairro, e o microdado desce.

    ``pct`` vem nulo inteiro quando ``total`` não alcança
    :data:`MINIMO_PARA_PERCENTUAL` — o mesmo limiar de
    `valores.MINIMO_PARA_PROPORCAO`, pelo mesmo motivo. Num bairro pequeno
    isso acontece de verdade.
    """
    colunas = {c.upper() for c in _colunas()}
    if variavel.upper() not in colunas:
        return pd.DataFrame(columns=["categoria", "n", "pct", "total"])

    onde, params = _onde(esc)
    dicionario = (
        config.dashboard_dir() / "sinan_dict" / f"doenca={config.TUBERCULOSE}"
        / "*.parquet"
    ).as_posix()

    # `lstrip` do zero à esquerda dos dois lados do join: o dado traz `03` e o
    # dicionário só `3`. Sem isso, 2018 e 2019 perdem registros em silêncio.
    sql = f"""
        WITH bruto AS (
            SELECT {_sem_zero_a_esquerda(f'"{variavel}"')} AS valor
            FROM read_parquet('{_fonte()}')
            WHERE {onde}
        )
        SELECT coalesce(d.valor_lbl, '(sem rótulo)') AS categoria,
               count(*) AS n
        FROM bruto
        LEFT JOIN (
            SELECT {_sem_zero_a_esquerda('valor')} AS valor, valor_lbl
            FROM read_parquet('{dicionario}')
            WHERE variavel = ?
        ) AS d USING (valor)
        WHERE bruto.valor IS NOT NULL
          AND bruto.valor <> ''
          AND d.valor_lbl IS NOT NULL
        GROUP BY 1
        ORDER BY n DESC
    """
    dados = conectar().execute(sql, [*params, variavel.upper()]).fetchdf()
    if dados.empty:
        return pd.DataFrame(columns=["categoria", "n", "pct", "total"])

    soma = float(dados["n"].sum())
    dados["pct"] = (dados["n"] / soma * 100) if soma >= MINIMO_PARA_PERCENTUAL else pd.NA
    dados["total"] = soma
    return dados[["categoria", "n", "pct", "total"]].reset_index(drop=True)


#: Nomes de mês em minúscula, como o `leitura.serie_dupla` devolve. O gráfico
#: fatia os três primeiros caracteres e capitaliza, então a grafia daqui é a
#: que aparece no eixo.
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def serie_mensal(esc: Escopo) -> pd.DataFrame:
    """Casos novos por mês, na definição do Boletim (`CASO_NOVO`). Colunas ``mes``, ``mes_nome`` e ``casos``.

    ``mes_nome`` existe porque `graficos.evolucao_mensal` o consome — é o
    contrato de `leitura.serie_dupla`, e as duas fontes alimentam o mesmo
    gráfico conforme o nível. Sem ele o painel de meses caía ao entrar num
    bairro, contido pela resiliência e portanto **em silêncio**: a página
    subia inteira com um aviso no lugar do gráfico.

    Os doze meses vêm sempre, inclusive os zerados: num bairro pequeno há mês
    sem caso, e uma série que pula o mês desenha a linha ligando novembro a
    janeiro como se dezembro não tivesse existido.

    O mês sai de ``DT_NOTIFIC``, que aparece nas duas grafias — ISO e
    brasileira — dentro do mesmo arquivo.
    """
    onde, params = _onde(esc)
    sql = f"""
        WITH m AS (
            SELECT CASE
                WHEN regexp_matches(trim(DT_NOTIFIC), '^\\d{{4}}-\\d{{2}}')
                    THEN TRY_CAST(substr(trim(DT_NOTIFIC), 6, 2) AS INTEGER)
                WHEN regexp_matches(trim(DT_NOTIFIC), '^\\d{{2}}/\\d{{2}}/\\d{{4}}$')
                    THEN TRY_CAST(substr(trim(DT_NOTIFIC), 4, 2) AS INTEGER)
            END AS mes
            FROM read_parquet('{_fonte()}')
            WHERE {onde} AND {CASO_NOVO}
        )
        SELECT g.mes, count(m.mes) AS casos
        FROM generate_series(1, 12) AS g(mes)
        LEFT JOIN m ON m.mes = g.mes
        GROUP BY g.mes
        ORDER BY g.mes
    """
    dados = conectar().execute(sql, params).fetchdf()
    dados["mes_nome"] = [MESES[int(m) - 1] for m in dados["mes"]]
    return dados[["mes", "mes_nome", "casos"]]


def piramide(esc: Escopo) -> pd.DataFrame:
    """Casos por sexo e faixa etária. Colunas ``sexo``, ``faixa_ord``,
    ``faixa_etaria`` e ``valor``.

    Só M e F: ``CS_SEXO`` traz três registros com ``I`` em catorze anos, e uma
    pirâmide com um terceiro lado de três casos não é legível. Eles continuam
    contados em tudo que não separa por sexo.

    Diferente de `leitura.piramide`, esta **não** traz população nem razão: o
    denominador por faixa existe só para Recife inteiro, no `popsvs`, e não
    por bairro. Taxa por faixa etária de bairro exigiria população por bairro e
    faixa, que a origem não tem.
    """
    onde, params = _onde(esc)
    casos = " ".join(
        f"WHEN idade BETWEEN {ini} AND {fim} THEN {ini}" for ini, fim, _ in FAIXAS
    )
    rotulos = " ".join(
        f"WHEN {ini} THEN '{rotulo}'" for ini, _, rotulo in FAIXAS
    )
    sql = f"""
        WITH base AS (
            SELECT trim(CS_SEXO) AS sexo, {_IDADE_EM_ANOS} AS idade
            FROM read_parquet('{_fonte()}')
            WHERE {onde}
        ), faixas AS (
            SELECT sexo, CASE {casos} END AS faixa_ord
            FROM base
            WHERE idade IS NOT NULL AND sexo IN ('M', 'F')
        )
        SELECT sexo, faixa_ord,
               CASE faixa_ord {rotulos} END AS faixa_etaria,
               count(*) AS valor
        FROM faixas
        WHERE faixa_ord IS NOT NULL
        GROUP BY 1, 2
        ORDER BY faixa_ord, sexo
    """
    return conectar().execute(sql, params).fetchdf()


def ranking_bairros(esc: Escopo, limite: int | None = None) -> pd.DataFrame:
    """Notificações por bairro no ano do escopo. Colunas ``bairro_key`` e
    ``casos``, da maior para a menor.

    Ignora o bairro do escopo de propósito: o ranking existe para situar um
    bairro entre os outros, então dentro de um ele continua listando todos.

    As chaves órfãs — ``NA``, ``IGN``, ``ZONA RURAL`` e dois erros de digitação,
    43 linhas em 29.607 — ficam de fora: não têm polígono, então não têm onde
    ser desenhadas nem com o que ser comparadas.

    **O desempate é pelo nome, e não é detalhe.** Ibura e Iputinga empatam em
    85 casos em 2023, e sem segundo critério o DuckDB devolve os dois em ordem
    arbitrária a cada execução. Como o Streamlit reexecuta o script a cada
    interação, as barras trocariam de lugar sozinhas enquanto o usuário
    apenas muda de aba — que lê como defeito, não como empate.
    """
    sql = f"""
        SELECT bairro_key, count(*) AS casos
        FROM read_parquet('{_fonte()}')
        WHERE ano = ? AND bairro_key IN (SELECT bairro_key FROM malha)
        GROUP BY 1
        ORDER BY casos DESC, bairro_key
    """
    if limite:
        sql += f" LIMIT {int(limite)}"

    from . import geo  # tardio: `geo` puxa geopandas, e nem todo caminho precisa

    con = conectar()
    con.register("malha", geo.bairros()[["bairro_key"]])
    try:
        return con.execute(sql, [esc.ano]).fetchdf()
    finally:
        con.unregister("malha")


def _colunas() -> list[str]:
    """Colunas presentes no parquet — a conversão descarta identificadores, e
    pedir uma delas devolveria erro de binder em vez de resposta vazia."""
    return [
        linha[0]
        for linha in conectar().execute(
            f"DESCRIBE SELECT * FROM read_parquet('{_fonte()}')"
        ).fetchall()
    ]
