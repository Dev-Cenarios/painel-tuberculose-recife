"""Testes do ``Escopo`` — com atenção ao nível BAIRRO, que é novo aqui.

O painel nacional ia até MUN. BAIRRO é o nível deste painel, e a armadilha que
ele traz é a de sempre: **só `incidence` e o microdado têm bairro.** Filtrar um
dataset que não tem a coluna não dá erro, dá vazio. `no_municipio` existe para
que a degradação seja escrita, e não acidental.
"""

from __future__ import annotations

import pytest

from src.data import config
from src.data.escopo import Escopo, chave_bairro, mun6

RECIFE = {"uf": "PE", "mun": config.MUN_RECIFE}


# ---------------------------------------------------------------------------
# Construção e validação
# ---------------------------------------------------------------------------


def test_bairro_exige_o_parametro() -> None:
    with pytest.raises(ValueError, match="BAIRRO"):
        Escopo("TUBERCULOSE", 2023, "BAIRRO", **RECIFE)


def test_bairro_e_normalizado_para_a_chave_canonica() -> None:
    esc = Escopo("TUBERCULOSE", 2023, "BAIRRO", bairro="  boa viagem ", **RECIFE)
    assert esc.bairro == "BOA VIAGEM"


def test_nivel_desconhecido_recusado() -> None:
    with pytest.raises(ValueError, match="Nível inválido"):
        Escopo("TUBERCULOSE", 2023, "DISTRITO", **RECIFE)


def test_niveis_declarados_incluem_bairro() -> None:
    assert "BAIRRO" in config.NIVEIS
    # BR e UF continuam: não são navegáveis, mas os leitores os consultam.
    assert {"BR", "UF", "MUN"} <= set(config.NIVEIS)


# ---------------------------------------------------------------------------
# Filtro geográfico
# ---------------------------------------------------------------------------


def test_filtro_de_bairro_usa_a_chave() -> None:
    esc = Escopo("TUBERCULOSE", 2023, "BAIRRO", bairro="Ibura", **RECIFE)
    onde, params = esc.filtro_geo()
    assert onde == "bairro_key = ?"
    assert params == ["IBURA"]


def test_filtro_de_bairro_aceita_outra_coluna() -> None:
    """O microdado e o `incidence` podem nomear a coluna diferente."""
    esc = Escopo("TUBERCULOSE", 2023, "BAIRRO", bairro="Ibura", **RECIFE)
    onde, _ = esc.filtro_geo(col_bairro="bairro")
    assert onde == "bairro = ?"


def test_filtro_de_municipio_continua_valendo() -> None:
    esc = Escopo("TUBERCULOSE", 2023, "MUN", **RECIFE)
    onde, params = esc.filtro_geo()
    assert onde == "cod_mun6 = ?"
    assert params == [config.MUN_RECIFE]


# ---------------------------------------------------------------------------
# Degradação explícita
# ---------------------------------------------------------------------------


def test_no_municipio_sobe_um_degrau() -> None:
    esc = Escopo("TUBERCULOSE", 2023, "BAIRRO", bairro="Curado", **RECIFE)
    cidade = esc.no_municipio()
    assert cidade.nivel == "MUN"
    assert cidade.bairro is None
    assert cidade.mun == config.MUN_RECIFE
    assert (cidade.doenca, cidade.ano) == (esc.doenca, esc.ano)


@pytest.mark.parametrize("nivel", ["BR", "UF", "MUN"])
def test_no_municipio_e_identidade_fora_de_bairro(nivel: str) -> None:
    esc = Escopo("TUBERCULOSE", 2023, nivel, **RECIFE)
    assert esc.no_municipio() is esc


# ---------------------------------------------------------------------------
# Chaves canônicas
# ---------------------------------------------------------------------------


def test_chave_bairro_tira_acento_e_caixa() -> None:
    assert chave_bairro("Alto Santa Terezinha") == "ALTO SANTA TEREZINHA"
    assert chave_bairro("Torrões") == "TORROES"
    assert chave_bairro("  Boa   Viagem  ") == "BOA VIAGEM"


def test_chave_bairro_colapsa_bairro_do_recife() -> None:
    """O CSV traz as duas grafias para o mesmo lugar; sem o colapso ele
    aparece duas vezes no ranking, com os casos divididos."""
    assert chave_bairro("Bairro do Recife") == "RECIFE"
    assert chave_bairro("RECIFE") == "RECIFE"


def test_chave_bairro_aceita_vazio() -> None:
    assert chave_bairro(None) == ""
    assert chave_bairro("") == ""


def test_mun6_continua_truncando() -> None:
    assert mun6("2611606") == "261160"
    assert mun6(config.MUN_RECIFE) == config.MUN_RECIFE
