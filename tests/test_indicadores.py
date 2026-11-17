"""Os oito KPIs na definição do Boletim, conferidos no banco do SINAN em 23/out/2026."""

from __future__ import annotations

import pytest

from src.data import config, indicadores
from src.data.escopo import Escopo

FONTE = config.dashboard_dir() / "indicadores_sinan" / "recife.parquet"
pytestmark = pytest.mark.skipif(not FONTE.is_file(), reason="sem indicadores_sinan")


@pytest.fixture(scope="module")
def recife_2023():
    return indicadores.da_cidade(
        Escopo("TUBERCULOSE", 2023, "MUN", uf=config.UF_RECIFE, mun=config.MUN_RECIFE)
    )


def test_contagens_do_banco(recife_2023) -> None:
    k = recife_2023
    assert (k.casos, k.hiv_testados, k.hiv_positivos) == (1685, 1373, 202)
    assert (k.pulmonares, k.trm_realizados) == (1467, 600)
    assert (k.desfecho_base, k.curas, k.interrupcoes, k.nao_avaliados) == (1668, 999, 292, 224)


def test_perto_do_boletim_2024(recife_2023) -> None:
    """Boletim 2024 (banco de fev/2024): coinfecção 11,9%, TRM 38,7%."""
    assert recife_2023.coinfeccao_pct == pytest.approx(11.9, abs=0.5)
    assert recife_2023.trm_pct == pytest.approx(38.7, abs=3)


def test_mortalidade_vem_do_sim(recife_2023) -> None:
    assert recife_2023.obitos == 141


def test_bairro_sem_sim_fica_sem_mortalidade() -> None:
    b = Escopo("TUBERCULOSE", 2023, "BAIRRO", uf=config.UF_RECIFE,
               mun=config.MUN_RECIFE, bairro="BOA VIAGEM")
    k = indicadores.do_bairro(b, 120_000.0)
    assert k.mortalidade is None and k.casos > 0


def test_series_da_cidade_casam_com_o_card() -> None:
    from src.data import canal

    esc = Escopo("TUBERCULOSE", 2023, "MUN", uf=config.UF_RECIFE, mun=config.MUN_RECIFE)
    anual = indicadores.serie_anual_cidade(esc).set_index("ano")
    assert anual.loc[2023, "casos"] == 1685
    assert anual.loc[2020, "incid"] == pytest.approx(82.3, abs=0.05)
    epi = canal.epicurva(esc)
    assert epi.query("ano == 2023")["casos"].sum() == 1685


def test_desfechos_somam_a_coorte(recife_2023) -> None:
    d = indicadores.desfechos(recife_2023)
    assert d.sum() == recife_2023.desfecho_base == 1668
    assert (d["Cura"], d["Transferência"], d["Sem encerramento"]) == (999, 213, 11)


def test_retrato_de_guabiraba() -> None:
    from src.data import retrato

    b = Escopo("TUBERCULOSE", 2023, "BAIRRO", uf=config.UF_RECIFE,
               mun=config.MUN_RECIFE, bairro="GUABIRABA")
    tabela = retrato.tabela_dos_bairros(b)
    assert retrato.posicao(tabela["incid"], "GUABIRABA") == 10
    serie = retrato.serie_do_bairro(b).set_index("ano")
    assert serie.loc[2023, "casos"] == 17 and serie.index.min() == 2010
