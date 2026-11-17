"""Os oito KPIs da faixa, na definição do Boletim Epidemiológico do MS.

A cidade lê `indicadores_sinan`, extraído do SINAN nacional pelo
`scripts/extrair_indicadores_sinan.py` — é a base do Boletim. O bairro não
existe lá, então sai do microdado municipal pelas mesmas regras, traduzidas
para os códigos da ficha. Óbitos só do SIM, que não tem bairro: a mortalidade
do bairro fica vazia.

Definições (quadro de métodos do Boletim de TB 2024):

- casos novos: caso novo, não sabe, pós-óbito;
- testagem HIV: realizou o exame (positivo, negativo, em andamento) / casos novos;
- coinfecção: HIV positivo / casos novos;
- TRM: pulmonares com TRM-TB realizado / pulmonares;
- desfechos sobre casos novos sem falência, mudança de esquema e TB-DR;
  interrupção = abandono + abandono primário; não avaliados = transferência
  + sem encerramento.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from . import config, leitura
from .conexao import conectar
from .escopo import Escopo
from .microdado import CASO_NOVO, MESES, _fonte, _sem_zero_a_esquerda

POR_100K = 100_000

#: denominador menor que isto vira "sem dado", como no mapa
MINIMO_PARA_PROPORCAO = 5

#: (percentual, numerador, denominador) de cada KPI de proporção
PROPORCOES = {
    "cura_pct": ("curas", "desfecho_base"),
    "interrupcao_trat_pct": ("interrupcoes", "desfecho_base"),
    "nao_avaliados_pct": ("nao_avaliados", "desfecho_base"),
    "testagem_hiv_pct": ("hiv_testados", "casos"),
    "coinfeccao_pct": ("hiv_positivos", "casos"),
    "trm_pct": ("trm_realizados", "pulmonares"),
}

_CONTAGENS = (
    "casos", "hiv_testados", "hiv_positivos", "pulmonares", "trm_realizados",
    "desfecho_base", "curas", "interrupcoes", "nao_avaliados",
    "obitos_tb", "obitos_outras", "transferencias",
)


def _div(n, d, fator: float) -> float | None:
    if n is None or not d:
        return None
    return n / d * fator


def _compor(contagens: dict, pop: float | None, obitos: float | None, minimo: int = 0):
    k = {c: contagens.get(c) for c in _CONTAGENS}
    k["pop"], k["obitos"] = pop, obitos
    k["incid"] = _div(k["casos"], pop, POR_100K)
    k["mortalidade"] = _div(obitos, pop, POR_100K)
    for pct, (num, den) in PROPORCOES.items():
        base = k[den]
        k[pct] = _div(k[num], base, 100) if base and base >= minimo else None
    return SimpleNamespace(**k)


def _fonte_boletim(nome: str = "recife.parquet") -> str:
    fonte = config.dashboard_dir() / "indicadores_sinan" / nome
    if not fonte.is_file():
        raise FileNotFoundError(
            f"{fonte} não existe. Gere com: python -m scripts.extrair_indicadores_sinan"
        )
    return str(fonte)


def _do_boletim(ano: int) -> dict:
    df = conectar().execute(
        "SELECT * FROM read_parquet(?) WHERE ano = ?", [_fonte_boletim(), ano]
    ).fetchdf()
    if df.empty:
        return {}
    linha = df.iloc[0].to_dict()
    linha["casos"] = linha.pop("casos_novos")
    linha["obitos_tb"] = linha.pop("obitos_tb_sinan")
    return {c: float(linha[c]) for c in _CONTAGENS}


def da_cidade(esc: Escopo):
    """KPIs de Recife inteiro. ``esc`` no nível MUN."""
    pop = leitura.incidencia(esc).get("pop_total")
    return _compor(_do_boletim(esc.ano), pop, leitura.obitos_sim(esc))


def _populacao_por_ano(esc: Escopo) -> pd.DataFrame:
    pop = leitura.serie_anual(esc.no_municipio(), "pop")
    return pop.rename(columns={"valor": "pop"})


def serie_anual_cidade(esc: Escopo) -> pd.DataFrame:
    """Casos novos e incidência de Recife por ano: ``ano``, ``casos``, ``incid``.

    Só anos com população, que é o que dá a taxa.
    """
    casos = conectar().execute(
        "SELECT ano, casos_novos AS casos FROM read_parquet(?) ORDER BY ano",
        [_fonte_boletim()],
    ).fetchdf()
    df = casos.merge(_populacao_por_ano(esc), on="ano")
    df["incid"] = df["casos"] / df["pop"] * POR_100K
    return df[["ano", "casos", "incid"]]


def serie_mensal_cidade(esc: Escopo) -> pd.DataFrame:
    """Casos novos de Recife por mês do ano de ``esc``: ``mes``, ``mes_nome``,
    ``casos``, ``incid``. A taxa usa a população do ano, como o card."""
    casos = conectar().execute(
        """SELECT g.mes, coalesce(m.casos_novos, 0) AS casos
           FROM generate_series(1, 12) AS g(mes)
           LEFT JOIN (SELECT * FROM read_parquet(?) WHERE ano = ?) m ON m.mes = g.mes
           ORDER BY g.mes""",
        [_fonte_boletim("recife_mensal.parquet"), esc.ano],
    ).fetchdf()
    if not casos["casos"].sum():
        return pd.DataFrame(columns=["mes", "mes_nome", "casos", "incid"])
    pop = leitura.incidencia(esc.no_municipio()).get("pop_total")
    casos["mes_nome"] = [MESES[int(m) - 1] for m in casos["mes"]]
    casos["incid"] = casos["casos"] / pop * POR_100K if pop else float("nan")
    return casos[["mes", "mes_nome", "casos", "incid"]]


#: desfecho -> cor, na ordem do Sankey e da barra empilhada
DESFECHOS = {
    "Cura": "#16A34A",
    "Interrupção": "#C2410C",
    "Óbito por TB": "#7F1D1D",
    "Óbito por outras causas": "#9CA3AF",
    "Transferência": "#0E7490",
    "Sem encerramento": "#D5DADF",
}


def desfechos(k) -> pd.Series:
    """Os casos novos da coorte por desfecho (``DESFECHOS``), das contagens de ``k``."""
    partes = {
        "Cura": k.curas,
        "Interrupção": k.interrupcoes,
        "Óbito por TB": k.obitos_tb,
        "Óbito por outras causas": k.obitos_outras,
        "Transferência": k.transferencias,
    }
    # o que sobra da base é quem não foi encerrado
    partes["Sem encerramento"] = max((k.desfecho_base or 0) - sum(v or 0 for v in partes.values()), 0)
    return pd.Series(partes, dtype=float)


def serie_desfechos_cidade() -> pd.DataFrame:
    """Cura e interrupção de Recife por ano: ``ano``, ``cura_pct``, ``interrupcao_trat_pct``."""
    df = conectar().execute(
        "SELECT ano, curas, interrupcoes, desfecho_base FROM read_parquet(?) ORDER BY ano",
        [_fonte_boletim()],
    ).fetchdf()
    df["cura_pct"] = df["curas"] / df["desfecho_base"] * 100
    df["interrupcao_trat_pct"] = df["interrupcoes"] / df["desfecho_base"] * 100
    return df[["ano", "cura_pct", "interrupcao_trat_pct"]]


# códigos da ficha do SINAN no microdado
_ENCE = _sem_zero_a_esquerda("SITUA_ENCE")
_SQL_BAIRROS = f"""
    SELECT
        bairro_key,
        count(*) AS casos,
        count(*) FILTER (WHERE trim(HIV) IN ('1', '2', '3')) AS hiv_testados,
        count(*) FILTER (WHERE trim(HIV) = '1') AS hiv_positivos,
        count(*) FILTER (WHERE trim(FORMA) IN ('1', '3')) AS pulmonares,
        count(*) FILTER (WHERE trim(FORMA) IN ('1', '3')
                           AND trim(TEST_MOLEC) IN ('1', '2', '3', '4')) AS trm_realizados,
        count(*) FILTER (WHERE coalesce({_ENCE}, '') NOT IN ('7', '8', '9')) AS desfecho_base,
        count(*) FILTER (WHERE {_ENCE} = '1') AS curas,
        count(*) FILTER (WHERE {_ENCE} IN ('2', '10')) AS interrupcoes,
        count(*) FILTER (WHERE {_ENCE} = '3') AS obitos_tb,
        count(*) FILTER (WHERE {_ENCE} = '4') AS obitos_outras,
        count(*) FILTER (WHERE {_ENCE} = '5') AS transferencias,
        count(*) FILTER (WHERE {_ENCE} = '5' OR {_ENCE} NOT IN
            ('1', '2', '3', '4', '6', '7', '8', '9', '10') OR SITUA_ENCE IS NULL) AS nao_avaliados
    FROM read_parquet(?, hive_partitioning=true)
    WHERE ano = ? AND {CASO_NOVO}
    GROUP BY bairro_key
"""


def contagens_por_bairro(ano: int) -> pd.DataFrame:
    """Uma linha por bairro com casos novos, contagens das proporções e ``bairro_key``."""
    return conectar().execute(_SQL_BAIRROS, [_fonte(), ano]).fetchdf()


def do_bairro(esc: Escopo, pop: float | None):
    """KPIs de um bairro, do microdado. Sem SIM por bairro: mortalidade vazia."""
    tabela = contagens_por_bairro(esc.ano)
    linha = tabela[tabela["bairro_key"] == esc.bairro]
    contagens = {c: float(linha[c].iloc[0]) if len(linha) else 0.0 for c in _CONTAGENS}
    return _compor(contagens, pop, None, minimo=MINIMO_PARA_PROPORCAO)
