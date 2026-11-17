"""Valores por geografia para o mapa e o ranking.

Vive fora de `leitura.py` porque responde a uma pergunta diferente. Lá cada
função entrega **um recorte**: os KPIs de Recife, a série de um bairro. Aqui
sempre se entrega **uma coluna inteira** — um valor para cada bairro, ou um
para cada Distrito Sanitário —, que é o que um coroplético consome.

Taxa não se soma
----------------

O ponto de existir deste módulo. ``incidence`` já traz ``incid_100k_total``
pronto por bairro, e é tentador somar ou tirar a média disso para chegar ao
Distrito Sanitário. **As duas contas dão errado**, e erram para lados
diferentes conforme o tamanho dos bairros: somar dá um número sem significado,
e a média simples pesa igual um bairro de 9 mil e um de 118 mil habitantes.

Então **toda métrica é recalculada a partir dos componentes**, nos dois níveis
— inclusive no de bairro, onde a coluna pronta existiria. Um caminho só: bairro
e distrito não podem divergir por construção, e a conta que aparece na tela é
a mesma que este arquivo declara.

Conferido contra a coluna pronta do ``incidence``: ``casos/pop*100000`` e
``óbitos/casos*100`` reproduzem ``incid_100k_total`` e ``letalidade_pct`` no
dígito, bairro a bairro.
"""

from __future__ import annotations

import pandas as pd

from . import config
from .conexao import caminho
from .conexao import conectar
from .escopo import Escopo

#: Como cada métrica se monta a partir das colunas do `incidence`.
#:
#: ``(numerador, denominador, fator)``. Denominador ``None`` é contagem crua —
#: aí o valor é a própria soma do numerador.
#:
#: Declarar em tabela, e não em ``if``, é o que garante que acrescentar uma
#: métrica seja uma linha aqui em vez de um ramo novo em duas funções.
#:
#: Contagens do microdado na definição do Boletim (`indicadores.contagens_por_bairro`);
#: só a população vem do ``incidence``. Óbito não entra: o SIM não tem bairro.
COMPOSICAO: dict[str, tuple[str, str | None, float]] = {
    "casos": ("casos", None, 1.0),
    "cura": ("curas", None, 1.0),
    "pop": ("pop_total", None, 1.0),
    "incid": ("casos", "pop_total", 100_000.0),
    "cura_pct": ("curas", "desfecho_base", 100.0),
    "interrupcao_trat_pct": ("interrupcoes", "desfecho_base", 100.0),
    "nao_avaliados_pct": ("nao_avaliados", "desfecho_base", 100.0),
    "testagem_hiv_pct": ("hiv_testados", "casos", 100.0),
    "coinfeccao_pct": ("hiv_positivos", "casos", 100.0),
    "trm_pct": ("trm_realizados", "pulmonares", 100.0),
}

#: Denominador abaixo disto vira "sem dado" nas métricas de proporção.
#:
#: Só nas proporções, e não nas taxas por população: um bairro com quatro
#: encerramentos e três curas exibiria 75% e pintaria como um dos melhores da
#: cidade, apoiado em quatro pessoas. Já `incid` tem população de denominador,
#: e população pequena não torna a incidência menos real — a de Curado é alta
#: de verdade.
MINIMO_PARA_PROPORCAO = 5

#: Abaixo desta população, a taxa por 100 mil ganha uma **nota**, não um corte.
#:
#: O Bairro do Recife tem 554 moradores e 20 casos em 2023 — 3.610 por 100
#: mil, a maior da cidade por larga margem. O número é verdadeiro e o mapa
#: tem de pintá-lo; o que ele não pode é ser lido como se fosse comparável a
#: Boa Viagem. Cada caso ali vale 180 por 100 mil. O centro antigo inteiro
#: está abaixo de 5 mil habitantes (Paissandu, Pau Ferro, Apipucos, Dois
#: Irmãos, Boa Vista, Santo Antônio, Ilha do Leite): pouca gente morando e
#: muita notificação, inclusive de quem não reside ali.
#:
#: Nota, e não supressão, porque a incidência alta do centro **é** achado de
#: vigilância — suprimir esconderia justamente o que o mapa existe para
#: mostrar. A nota diz quanto pesa um caso, e quem lê decide.
POPULACAO_PEQUENA = 5_000

#: Proporções sujeitas ao mínimo. As taxas por população ficam de fora.
_PROPORCOES = frozenset(m for m in COMPOSICAO if m.endswith("_pct"))


def metricas_disponiveis() -> tuple[str, ...]:
    return tuple(COMPOSICAO)


def _tabela(esc: Escopo) -> pd.DataFrame:
    """Uma linha por bairro, com as colunas cruas do ``incidence``.

    Sempre Recife inteiro, em qualquer nível do escopo: o mapa continua
    mostrando os 94 bairros de dentro de um deles.
    """
    fonte = caminho(
        "incidence",
        doenca=config.cod_agregado(esc.doenca),
        nivel="BAIRRO",
        ano=esc.ano,
    )
    from .indicadores import _CONTAGENS, contagens_por_bairro  # tardio: indicadores importa leitura

    pop = conectar().execute(
        f"SELECT bairro_key, pop_total FROM read_parquet('{fonte}', hive_partitioning=true)"
    ).fetchdf()
    # bairro sem caso novo no ano entra com zero, não some do mapa
    tabela = pop.merge(contagens_por_bairro(esc.ano), on="bairro_key", how="left")
    tabela[list(_CONTAGENS)] = tabela[list(_CONTAGENS)].fillna(0)
    return tabela


def _reduzir(tabela: pd.DataFrame, metrica: str, indice: str) -> pd.Series:
    """Agrega ``tabela`` por ``indice`` e aplica a composição da métrica."""
    if metrica not in COMPOSICAO:
        raise ValueError(
            f"Métrica desconhecida: {metrica!r}. "
            f"Disponíveis: {', '.join(metricas_disponiveis())}"
        )
    numerador, denominador, fator = COMPOSICAO[metrica]

    somas = tabela.groupby(indice, sort=False).sum(numeric_only=True)
    if denominador is None:
        return somas[numerador].astype(float)

    base = somas[denominador].astype(float)
    if metrica in _PROPORCOES:
        base = base.where(base >= MINIMO_PARA_PROPORCAO)
    return somas[numerador] / base.replace(0, pd.NA) * fator


def por_bairro(esc: Escopo, metrica: str) -> pd.Series:
    """Valor da métrica em cada bairro. Índice: ``bairro_key``."""
    return _reduzir(_tabela(esc), metrica, "bairro_key").rename(metrica)


def por_distrito(esc: Escopo, metrica: str) -> pd.Series:
    """Valor da métrica em cada Distrito Sanitário. Índice: ``ds``.

    O vínculo bairro → distrito vem da **malha**, não do dado: o `incidence`
    não tem coluna de DS. É a mesma coluna ``ds`` de que os polígonos do
    distrito foram dissolvidos, então o que o mapa pinta e o que ele soma
    coincidem por construção.
    """
    from . import geo  # tardio: puxa geopandas, e nem todo caminho precisa

    tabela = _tabela(esc)
    vinculo = geo.bairros()[["bairro_key", "ds"]]
    juncao = tabela.merge(vinculo, on="bairro_key", how="left")

    orfaos = juncao["ds"].isna().sum()
    if orfaos:
        raise ValueError(
            f"{orfaos} bairros do dado sem distrito na malha. "
            f"O join por `bairro_key` deveria cobrir 94 de 94 — "
            f"ver tests/test_geo.py."
        )
    return _reduzir(juncao, metrica, "ds").rename(metrica)


def nota_populacao(pop: float | None) -> str:
    """Texto da nota de população pequena, ou vazio quando não cabe."""
    if pop is None or pd.isna(pop) or pop <= 0 or pop >= POPULACAO_PEQUENA:
        return ""
    peso = 100_000 / float(pop)
    pop_txt = f"{int(pop):,}".replace(",", ".")
    peso_txt = f"{peso:.1f}".replace(".", ",")
    return (
        f"População pequena ({pop_txt} hab.): cada caso pesa {peso_txt} por "
        "100 mil. Taxa instável; leia junto com o número de casos."
    )


def notas_do_mapa(esc: Escopo, metrica: str, recorte: str) -> pd.Series:
    """Nota por geografia para o tooltip do mapa; vazia onde não há o que dizer.

    Só na incidência e só por bairro — os distritos somam dezenas de milhares
    de habitantes e a nota não se aplica.
    """
    if metrica != "incid" or str(recorte).upper() != "BAIRRO":
        return pd.Series(dtype=str)
    pop = por_bairro(esc, "pop")
    return pop.map(nota_populacao).rename("nota")


def para_o_mapa(esc: Escopo, metrica: str, recorte: str) -> pd.Series:
    """Valores no recorte que o mapa está desenhando.

    ``recorte`` vem de `estado.Navegacao.recorte` — ``BAIRRO`` ou ``DISTRITO``.
    """
    alvo = str(recorte or "BAIRRO").strip().upper()
    if alvo == "DISTRITO":
        return por_distrito(esc, metrica)
    if alvo == "BAIRRO":
        return por_bairro(esc, metrica)
    raise ValueError(f"Recorte desconhecido: {recorte!r}.")


def ranking(
    esc: Escopo, metrica: str, recorte: str = "BAIRRO", top_n: int = 15
) -> pd.DataFrame:
    """As ``top_n`` maiores geografias do recorte, para as barras.

    Colunas ``chave``, ``nome`` e ``valor`` — o contrato que
    `graficos.ranking` consome.

    **Sai de `para_o_mapa`, e não de uma consulta própria.** O ranking e o
    mapa mostram o mesmo recorte, e ler de lugares diferentes é como o card e
    a série do painel nacional passaram a divergir. Assim as cores das barras,
    que vêm da escala do mapa, casam com os polígonos por construção.

    Empate é desempatado pelo nome. Sem isso as barras trocam de lugar entre
    reexecuções do Streamlit, o que lê como defeito e não como empate.
    """
    serie = para_o_mapa(esc, metrica, recorte).dropna()
    if serie.empty:
        return pd.DataFrame(columns=["chave", "nome", "valor"])

    from . import geo

    if str(recorte).strip().upper() == "DISTRITO":
        # "DS - VI", da malha da prefeitura — não "Distrito 6", que era rótulo
        # nosso. Os oito distritos de Recife não têm nome próprio, são
        # numerados em romano, e essa é a grafia oficial.
        camada = geo.distritos()
        nomes = dict(zip(camada["ds"], camada["ds_nome"], strict=True))
    else:
        camada = geo.bairros()
        nomes = dict(zip(camada["bairro_key"], camada["bairro_nome"], strict=True))

    tabela = pd.DataFrame(
        {
            "chave": serie.index,
            "nome": [nomes.get(chave, chave) for chave in serie.index],
            "valor": serie.to_numpy(),
        }
    )
    return (
        tabela.sort_values(["valor", "nome"], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )


def populacao_do_bairro(esc: Escopo) -> float | None:
    """População do bairro aberto, denominador da incidência do card."""
    pop = por_bairro(esc, "pop")
    valor = pop.get(esc.bairro)
    return None if valor is None or pd.isna(valor) else float(valor)


def procedencia() -> tuple[str, str] | None:
    """(dados até, processado em) do dataset ``meta``, formatados dd/mm/aaaa.

    ``None`` quando o `meta` não existe — a linha some da tela em vez de
    inventar data.
    """
    raiz = config.data_dir() / "parquet" / "dashboard" / "meta"
    arquivos = sorted(raiz.glob("**/*.parquet"))
    if not arquivos:
        return None
    linha = conectar().execute(
        "SELECT max(dados_ate), max(processado_em) FROM read_parquet(?)",
        [[str(a) for a in arquivos]],
    ).fetchone()
    if not linha or linha[0] is None:
        return None
    dados_ate, processado = linha
    return dados_ate.strftime("%d/%m/%Y"), processado.strftime("%d/%m/%Y")
