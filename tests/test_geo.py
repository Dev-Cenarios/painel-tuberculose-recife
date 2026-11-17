"""Testes da geometria de Recife.

O que se protege aqui é o **cruzamento**. Chave que não bate não levanta erro:
devolve vazio, o mapa fica cinza, e ninguém descobre por semanas. Foi a
armadilha 3 do painel nacional e é a mais cara de todas.
"""

from __future__ import annotations

import duckdb
import pytest

from src.data import config, geo
from src.data.escopo import chave_bairro

#: Quantos bairros Recife tem. O número aparece na malha e no `incidence`, e
#: se um dos dois mudar o teste tem de falhar — é sinal de extração nova.
N_BAIRROS = 94

#: Distritos Sanitários (RPAs).
N_DISTRITOS = 8


@pytest.fixture(scope="module")
def bairros():
    return geo.bairros()


@pytest.fixture(scope="module")
def dado_do_incidence() -> list[tuple[str, str]]:
    """Pares ``(bairro_key, bairro_nome)`` do `incidence` no último ano."""
    fonte = (
        config.dashboard_dir()
        / "incidence"
        / "doenca=TUBERCULOSE"
        / "nivel=BAIRRO"
        / f"ano={config.ANO_MAX_RECIFE}"
        / "*.parquet"
    )
    return duckdb.connect().execute(
        f"SELECT DISTINCT bairro_key, bairro_nome "
        f"FROM read_parquet('{fonte.as_posix()}')"
    ).fetchall()


@pytest.fixture(scope="module")
def chaves_do_dado(dado_do_incidence) -> set[str]:
    return {chave for chave, _ in dado_do_incidence}


# ---------------------------------------------------------------------------
# Forma das camadas
# ---------------------------------------------------------------------------


def test_bairros_tem_as_colunas_da_aplicacao(bairros) -> None:
    assert set(bairros.columns) == {
        "bairro_key", "bairro_nome", "cod_bairro", "ds", "ds_nome", "geometry"
    }
    assert len(bairros) == N_BAIRROS


def test_distritos_saem_dos_bairros() -> None:
    distritos = geo.distritos()
    assert len(distritos) == N_DISTRITOS
    assert set(distritos.columns) == {"ds", "ds_nome", "geometry"}


def test_recife_e_uma_feicao_so() -> None:
    assert len(geo.recife()) == 1


def test_geometria_em_graus() -> None:
    """O deck.gl desenha em WGS84; entregar UTM põe o mapa no oceano."""
    for camada in (geo.bairros(), geo.distritos(), geo.recife()):
        assert camada.crs is not None
        assert camada.crs.to_epsg() == 4326


def test_bounds_caem_sobre_recife() -> None:
    minx, miny, maxx, maxy = geo.recife().total_bounds
    assert -35.1 < minx < -34.8
    assert -8.2 < miny < -7.9
    assert maxx <= -34.8
    assert maxy <= -7.9


def test_geometria_valida(bairros) -> None:
    """A simplificação topológica não garante validade — o pipeline conserta
    com `buffer(0)`, e aqui se confere que consertou."""
    assert bairros.geometry.is_valid.all()


# ---------------------------------------------------------------------------
# Cruzamento — o que de fato importa
# ---------------------------------------------------------------------------


def test_chave_de_bairro_e_unica(bairros) -> None:
    """Chave repetida duplica linha no join, e o bairro aparece duas vezes no
    ranking com os casos divididos."""
    assert not bairros["bairro_key"].duplicated().any()


def test_toda_chave_da_malha_esta_normalizada(bairros) -> None:
    for chave in bairros["bairro_key"]:
        assert chave == chave_bairro(chave)


def test_malha_e_dado_cruzam_inteiros(bairros, chaves_do_dado) -> None:
    """94 de 94. Se este teste ficar vermelho, o mapa vai ficar cinza."""
    da_malha = set(bairros["bairro_key"])
    assert da_malha == chaves_do_dado, (
        f"só na malha: {sorted(da_malha - chaves_do_dado)}; "
        f"só no dado: {sorted(chaves_do_dado - da_malha)}"
    )


def test_nome_de_exibicao_do_dado_nao_serve_de_chave(dado_do_incidence) -> None:
    """Registro executável de uma divergência real, e não um teste de defeito.

    Dentro do próprio `incidence`, ``bairro_nome`` nem sempre normaliza para o
    ``bairro_key`` da mesma linha: a extração grafa "Alto Sta. Terezinha" onde
    a chave diz "ALTO SANTA TEREZINHA". Quem cruzar pelo nome exibido perde
    esse bairro em silêncio — e é por isso que a chave existe.

    A abreviação é do dado, não da malha: o shapefile grafa por extenso. Só
    este bairro diverge, em 94.

    Se um dia a extração normalizar as duas, este teste falha e manda apagar o
    aviso da docstring de `geo.bairros`.
    """
    divergentes = [
        (chave, nome)
        for chave, nome in dado_do_incidence
        if chave_bairro(nome) != chave
    ]
    assert divergentes == [("ALTO SANTA TEREZINHA", "Alto Sta. Terezinha")]


# ---------------------------------------------------------------------------
# Distrito Sanitário
# ---------------------------------------------------------------------------


def test_todo_bairro_pertence_a_um_distrito(bairros) -> None:
    assert bairros["ds"].notna().all()
    assert (bairros["ds"].str.strip() != "").all()


def test_distrito_tem_rotulo_oficial() -> None:
    """"DS - I" a "DS - VIII", da malha da prefeitura — não "Distrito 6", que
    seria rótulo nosso. Os oito não têm nome próprio, são numerados em romano,
    e o mapa mostrava só o número antes disso existir."""
    nomes = set(geo.distritos()["ds_nome"])
    assert nomes == {f"DS - {r}" for r in
                     ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")}


def test_os_distritos_dos_bairros_sao_os_da_camada(bairros) -> None:
    """Dissolvidos a partir da mesma coluna, então não podem divergir — e é
    justamente por isso que a camada não vem de shapefile separado."""
    assert set(bairros["ds"]) == set(geo.distritos()["ds"])
