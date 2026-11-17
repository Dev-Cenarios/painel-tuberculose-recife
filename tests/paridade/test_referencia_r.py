"""Comparação com o painel em R que está no ar.

**Paridade mede concordância, não correção.** No painel nacional houve o caso
em que os dois painéis exibiam o mesmo número errado, e nenhuma comparação
entre eles teria como perceber — quem fechou foi o Boletim Epidemiológico do
MS. Aqui vale igual: onde divergimos de propósito, a justificativa está em
`docs/paridade-com-o-painel-r.md`, e a fonte que decide é externa.

O que este harness protege é o outro lado: **regressão nossa**. Onde hoje
batemos, tem de continuar batendo; onde divergimos, a divergência tem de
continuar registrada.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data import config, leitura, microdado
from src.data.escopo import Escopo

REFERENCIA = json.loads(
    (Path(__file__).parent / "referencia_r.json").read_text(encoding="utf-8")
)

ANO = REFERENCIA["_sobre"]["ano"]


@pytest.fixture(scope="module")
def cidade() -> Escopo:
    return Escopo(
        "TUBERCULOSE", ANO, "MUN", uf=config.UF_RECIFE, mun=config.MUN_RECIFE
    )


# ---------------------------------------------------------------------------
# Onde batemos — e tem de continuar batendo
# ---------------------------------------------------------------------------


def test_ranking_de_bairros_bate_exatamente() -> None:
    """Quinze de quinze, sem diferença nenhuma.

    Foi este teste que revelou de onde vem o número deles: o ranking do painel
    em R sai do `incidence` agregado, e não do microdado que veio junto no
    pacote. O microdado tem de 5 a 15% mais casos por bairro.

    Se este teste ficar vermelho, ou a extração mudou, ou trocamos a fonte do
    ranking sem decidir trocar.
    """
    import duckdb

    fonte = (
        config.dashboard_dir() / "incidence" / "doenca=TUBERCULOSE"
        / "nivel=BAIRRO" / f"ano={ANO}" / "*.parquet"
    ).as_posix()
    nosso = dict(
        duckdb.connect().execute(
            f"SELECT bairro_key, casos_total FROM read_parquet('{fonte}')"
        ).fetchall()
    )

    esperado = {
        chave: valor
        for chave, valor in REFERENCIA["ranking_bairros_casos"].items()
        if not chave.startswith("_")
    }
    divergentes = {
        chave: (nosso.get(chave), valor)
        for chave, valor in esperado.items()
        if nosso.get(chave) != valor
    }
    assert not divergentes, f"(nosso, deles): {divergentes}"


def test_casos_novos_bate_com_o_card() -> None:
    """2.485, o mesmo número do card "Casos novos" deles."""
    esc = Escopo("TUBERCULOSE", ANO, "MUN", uf=config.UF_RECIFE, mun=config.MUN_RECIFE)
    assert leitura.casos_novos(esc) == REFERENCIA["kpis"]["casos"]["valor"]


# ---------------------------------------------------------------------------
# Onde divergimos — e a divergência tem de estar escrita
# ---------------------------------------------------------------------------


def test_denominador_deles_e_o_dobro_do_nosso(cidade: Escopo) -> None:
    """Registro executável da divergência §1 do `docs/paridade-com-o-painel-r.md`.

    O `sinan_landing` soma a linha `TOTAL` junto com M e F, e o painel deles
    exibe 4.970 onde o correto é 2.485. A proporção não sente, porque
    numerador e denominador dobram juntos — foi por isso que o defeito
    sobreviveu à inspeção casual, lá e aqui.
    """
    import duckdb

    fonte = (
        config.dashboard_dir() / "sinan_landing" / "doenca=TUBERCULOSE"
        / "nivel=MUN" / f"ano={ANO}" / "*.parquet"
    ).as_posix()
    por_sexo = dict(
        duckdb.connect().execute(
            f"""SELECT sexo, sum(n) FROM read_parquet('{fonte}', hive_partitioning=true)
                WHERE variavel = 'SITUA_ENCE' AND cast(geo_id AS varchar) LIKE '261160%'
                GROUP BY sexo"""
        ).fetchall()
    )
    total = por_sexo["TOTAL"]
    assert por_sexo["M"] + por_sexo["F"] == total, (
        "a linha TOTAL deixou de ser a soma — a premissa da §1 caiu"
    )
    exibido = REFERENCIA["kpis"]["interrupcao_trat_pct"]["denominador_exibido"]
    assert exibido == 2 * total


def test_composicao_concorda_em_forma_e_diverge_em_base(cidade: Escopo) -> None:
    """A distribuição reproduz a deles; a contagem não, e isso é esperado.

    Duas causas somadas, e nenhuma é defeito nosso: eles dobram a base, e o
    microdado que lemos é uma extração mais larga que o agregado. Ver §1 e §2.
    """
    nossa = microdado.composicao(cidade, "HIV").set_index("categoria")
    deles = REFERENCIA["composicao"]["HIV"]["categorias"]

    for categoria, esperado in deles.items():
        assert categoria in nossa.index, categoria
        # Mesma ordem de grandeza na proporção: tolerância de 1 ponto.
        assert nossa.loc[categoria, "pct"] == pytest.approx(esperado["pct"], abs=1.0)

    # E a base diverge — se um dia parar de divergir, a §2 fechou e sai daqui.
    assert nossa["total"].iloc[0] != REFERENCIA["composicao"]["HIV"]["base_exibida"]


# ---------------------------------------------------------------------------
# O registro tem de acompanhar o código
# ---------------------------------------------------------------------------


def test_toda_divergencia_esta_registrada() -> None:
    """`docs/paridade-com-o-painel-r.md` existe e nomeia as divergências que os testes acima
    exercitam. Sem isso o registro envelhece calado, que é como a primeira
    reunião vira discussão de número em vez de discussão de decisão."""
    texto = (Path(__file__).parents[2] / "docs" / "paridade-com-o-painel-r.md").read_text(encoding="utf-8")
    for marca in ("sinan_landing", "TOTAL", "microdado", "2.485", "2.749"):
        assert marca in texto, f"não registrado em docs/paridade-com-o-painel-r.md: {marca}"
