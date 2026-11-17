"""O retrato de um bairro: onde ele fica entre os 94 e como anda no tempo.

Tudo em casos novos do microdado, pelas regras do Boletim (`indicadores`).
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from . import config, valores
from .escopo import Escopo
from .indicadores import POR_100K, contagens_por_bairro

#: indicadores da teia, na ordem dos eixos (a mortalidade fica fora: SIM sem bairro)
EIXOS_TEIA = (
    "incid", "cura_pct", "interrupcao_trat_pct", "nao_avaliados_pct",
    "testagem_hiv_pct", "coinfeccao_pct", "trm_pct",
)

#: primeiro ano do microdado
ANO_MIN = 2010


def tabela_dos_bairros(esc: Escopo) -> pd.DataFrame:
    """Uma linha por ``bairro_key`` com os indicadores da teia e os casos novos."""
    cidade = esc.no_municipio()
    colunas = {m: valores.por_bairro(cidade, m) for m in (*EIXOS_TEIA, "casos")}
    return pd.DataFrame(colunas)


def posicao(serie: pd.Series, chave: str) -> int | None:
    """Posição do bairro do maior para o menor (1 = maior)."""
    limpa = serie.dropna()
    if chave not in limpa.index:
        return None
    return int((limpa > limpa[chave]).sum()) + 1


def serie_do_bairro(esc: Escopo) -> pd.DataFrame:
    """Casos novos e incidência do bairro por ano: ``ano``, ``casos``, ``incid``."""
    linhas = []
    for ano in range(ANO_MIN, config.ANO_MAX_RECIFE + 1):
        do_ano = replace(esc, ano=ano)
        contagens = contagens_por_bairro(ano)
        casos = float(contagens.loc[contagens["bairro_key"] == esc.bairro, "casos"].sum())
        pop = valores.populacao_do_bairro(do_ano)
        linhas.append({"ano": ano, "casos": casos,
                       "incid": casos / pop * POR_100K if pop else None})
    return pd.DataFrame(linhas)
