"""Testes da camada de microdado.

É a camada que o painel nacional não tinha, então não há código herdado que a
proteja. O que se confere aqui, em ordem de importância:

1. que os identificadores não voltaram para o parquet;
2. que a idade do SINAN é decodificada, e não lida como número;
3. que os totais reconciliam entre os leitores;
4. que a rotulagem sai do mesmo dicionário da camada agregada.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data import config, indicadores, microdado
from src.data.escopo import Escopo

ANO = config.ANO_MAX_RECIFE


@pytest.fixture(scope="module")
def cidade() -> Escopo:
    return Escopo(
        "TUBERCULOSE", ANO, "MUN", uf=config.UF_RECIFE, mun=config.MUN_RECIFE
    )


@pytest.fixture(scope="module")
def bairro() -> Escopo:
    """Um bairro grande, para que os testes de proporção tenham base."""
    return Escopo(
        "TUBERCULOSE", ANO, "BAIRRO",
        uf=config.UF_RECIFE, mun=config.MUN_RECIFE, bairro="BOA VIAGEM",
    )


# ---------------------------------------------------------------------------
# Privacidade — o teste que não pode ficar vermelho
# ---------------------------------------------------------------------------

#: Identificadores que a conversão descarta. Se um deles reaparecer no parquet,
#: dado nominal de paciente com tuberculose voltou a circular no projeto.
IDENTIFICADORES = (
    "NM_PACIENT", "NM_MAE_PAC", "DT_NASC", "ID_CNS_SUS", "NU_PRONTUA",
    "NU_CEP", "NU_TELEFON", "NM_LOGRADO", "NU_NUMERO",
    "LATITUDE", "LONGITUDE", "COD_SETOR", "NU_NOTIFIC", "address",
)


def test_nenhum_identificador_no_parquet() -> None:
    presentes = {c.upper() for c in microdado._colunas()}
    vazados = sorted(i for i in IDENTIFICADORES if i.upper() in presentes)
    assert not vazados, (
        f"identificador de paciente no parquet: {vazados}. "
        f"Ver a lista de permissão em scripts/preparar_microdado.py."
    )


def test_a_lista_de_identificadores_cobre_a_do_script() -> None:
    """O script é a fonte; este teste cobra que as duas não se separem."""
    from scripts.preparar_microdado import IDENTIFICADORES_DESCARTADOS

    faltando = {i.upper() for i in IDENTIFICADORES} - {
        i.upper() for i in IDENTIFICADORES_DESCARTADOS
    }
    assert not faltando, f"testado mas não descartado pelo script: {faltando}"


# ---------------------------------------------------------------------------
# Idade — o campo composto do SINAN
# ---------------------------------------------------------------------------


def test_piramide_nao_le_a_idade_como_numero(cidade: Escopo) -> None:
    """``NU_IDADE_N`` é unidade + valor: ``3011`` é 11 meses, não 3.011 anos.

    Lido cru, todo menor de um ano some da primeira faixa e a pirâmide perde
    justamente a faixa que o KPI de 0 a 14 anos observa.
    """
    p = microdado.piramide(cidade)
    assert not p.empty
    assert p["faixa_ord"].max() <= 80
    assert (p["valor"] > 0).all()
    # Os menores de um ano têm de estar na primeira faixa, não fora dela.
    assert 0 in set(p["faixa_ord"])


def test_piramide_so_tem_as_faixas_declaradas(cidade: Escopo) -> None:
    esperadas = {ini for ini, _, _ in microdado.FAIXAS}
    assert set(microdado.piramide(cidade)["faixa_ord"]) <= esperadas


def test_piramide_so_traz_M_e_F(cidade: Escopo) -> None:
    """``I`` existe — três registros em catorze anos — e um terceiro lado de
    três casos não é pirâmide, é ruído com eixo."""
    assert set(microdado.piramide(cidade)["sexo"]) <= {"M", "F"}


# ---------------------------------------------------------------------------
# Reconciliação entre leitores
# ---------------------------------------------------------------------------


def test_serie_mensal_soma_os_casos_novos(cidade: Escopo) -> None:
    """Casos novos, como o mapa: menos que o total de notificações."""
    mensal = int(microdado.serie_mensal(cidade)["casos"].sum())
    assert mensal == int(indicadores.contagens_por_bairro(cidade.ano)["casos"].sum())
    assert mensal < microdado.total(cidade)


def test_serie_mensal_traz_os_doze_meses(bairro: Escopo) -> None:
    """Inclusive os zerados: num bairro pequeno há mês sem caso, e a linha que
    pula o mês liga novembro a janeiro como se dezembro não existisse."""
    s = microdado.serie_mensal(bairro)
    assert list(s["mes"]) == list(range(1, 13))


def test_ranking_soma_menos_que_o_total(cidade: Escopo) -> None:
    """Menos, e não igual: as chaves órfãs — sem polígono — ficam de fora."""
    r = microdado.ranking_bairros(cidade)
    assert 0 < int(r["casos"].sum()) <= microdado.total(cidade)


def test_ranking_vem_ordenado(cidade: Escopo) -> None:
    casos = microdado.ranking_bairros(cidade)["casos"].tolist()
    assert casos == sorted(casos, reverse=True)


def test_ranking_desempata_de_forma_estavel(cidade: Escopo) -> None:
    """Ibura e Iputinga empatam em 85 casos em 2023. Sem segundo critério o
    DuckDB os devolve em ordem arbitrária, e como o Streamlit reexecuta o
    script a cada interação, as barras trocariam de lugar sozinhas."""
    r = microdado.ranking_bairros(cidade)
    empatados = r[r["casos"].duplicated(keep=False)]
    assert not empatados.empty, "sem empate no ano — teste perdeu o objeto"
    for _, grupo in empatados.groupby("casos"):
        nomes = grupo["bairro_key"].tolist()
        assert nomes == sorted(nomes)


def test_ranking_nao_muda_dentro_de_um_bairro(cidade: Escopo, bairro: Escopo) -> None:
    """O ranking existe para situar um bairro entre os outros."""
    pd.testing.assert_frame_equal(
        microdado.ranking_bairros(cidade), microdado.ranking_bairros(bairro)
    )


# ---------------------------------------------------------------------------
# Recorte
# ---------------------------------------------------------------------------


def test_bairro_e_subconjunto_da_cidade(cidade: Escopo, bairro: Escopo) -> None:
    assert 0 < microdado.total(bairro) < microdado.total(cidade)


def test_composicao_de_bairro_soma_menos_que_a_da_cidade(
    cidade: Escopo, bairro: Escopo
) -> None:
    assert (
        microdado.composicao(bairro, "HIV")["n"].sum()
        < microdado.composicao(cidade, "HIV")["n"].sum()
    )


# ---------------------------------------------------------------------------
# Rotulagem
# ---------------------------------------------------------------------------


def test_situacao_de_encerramento_vem_reagrupada(cidade: Escopo) -> None:
    """O dicionário colapsa os códigos 2, 3, 4, 9 e 10 em "Desfavorável", que é
    o que o painel de origem mostra. Reproduzir o reagrupamento aqui, à mão,
    seria a forma de os dois gráficos da mesma tela discordarem."""
    categorias = set(microdado.composicao(cidade, "SITUA_ENCE")["categoria"])
    assert categorias == {"Favorável", "Desfavorável", "Não avaliado"}


def test_nenhuma_categoria_fica_sem_rotulo(cidade: Escopo) -> None:
    for variavel in ("HIV", "FORMA", "TRATAMENTO", "CS_RACA"):
        categorias = set(microdado.composicao(cidade, variavel)["categoria"])
        assert "(sem rótulo)" not in categorias, variavel


def test_percentual_fecha_em_cem(cidade: Escopo) -> None:
    pct = microdado.composicao(cidade, "HIV")["pct"].sum()
    assert pct == pytest.approx(100.0, abs=0.01)


def test_variavel_inexistente_devolve_vazio_e_nao_estoura(cidade: Escopo) -> None:
    """A conversão descarta colunas; pedir uma delas tem de ser resposta vazia,
    não erro de binder vindo do meio de um painel."""
    vazio = microdado.composicao(cidade, "NM_PACIENT")
    assert vazio.empty
    assert list(vazio.columns) == ["categoria", "n", "pct", "total"]


def test_forma_da_saida_e_o_limiar_batem_com_a_camada_de_valores(cidade: Escopo) -> None:
    """Um limiar só para "proporção não interpretável" na tela inteira: se o
    mapa suprime abaixo de 5, a composição não pode mostrar percentual de 4."""
    from src.data import valores

    assert list(microdado.composicao(cidade, "HIV").columns) == [
        "categoria", "n", "pct", "total"
    ]
    assert microdado.MINIMO_PARA_PERCENTUAL == valores.MINIMO_PARA_PROPORCAO


# ---------------------------------------------------------------------------
# A divergência em aberto, medida
# ---------------------------------------------------------------------------


def test_microdado_e_agregado_ainda_divergem(cidade: Escopo) -> None:
    """**Não é teste de defeito — é medida de uma pergunta em aberto.**

    O microdado tem mais notificações que o agregado, e qual extração vale
    está perguntado à equipe parceira. Este teste prende a diferença: se ela
    mudar, alguém trocou o dado, e a decisão pendente tem de ser revisitada
    antes que a tela misture as duas fontes.

    Quando a resposta chegar, este teste sai ou vira igualdade.
    """
    from src.data import leitura

    agregado = leitura.casos_novos(cidade)
    assert agregado is not None
    assert microdado.total(cidade) > agregado
    assert microdado.total(cidade) - agregado == 262


# ---------------------------------------------------------------------------
# O que o pack oferece, a conversão precisa carregar
# ---------------------------------------------------------------------------


def test_toda_variavel_oferecida_existe_no_microdado() -> None:
    """**Regressão de doze painéis vazios.**

    O pack herdou 26 variáveis de composição do painel nacional; a primeira
    versão da conversão carregou 27 colunas ao todo, e doze das variáveis
    oferecidas no seletor não tinham coluna nenhuma por trás. A tela mostrava
    "sem registro" para metade das opções — exatamente o que o pack proíbe ao
    dizer que oferecer opção que leva a painel vazio é pior que não oferecer.

    O desencontro não dá erro: `composicao` devolve vazio quando a coluna não
    existe, de propósito, para o painel não cair. Por isso ele precisa de um
    teste, e não de uma exceção.
    """
    from src.doencas import tuberculose as pack
    from scripts.preparar_microdado import COLUNAS

    presentes = {c.upper() for c in COLUNAS}
    faltando = sorted(v for v in pack.variaveis_planas() if v.upper() not in presentes)
    assert not faltando, (
        f"variáveis oferecidas sem coluna no parquet: {faltando}. "
        f"Acrescente-as a COLUNAS em scripts/preparar_microdado.py e regere."
    )


def test_variaveis_oferecidas_tem_dado_no_ultimo_ano(cidade: Escopo) -> None:
    """Coluna existir não basta, e ter dado "em algum ano" também não.

    Esta asserção começou frouxa — cobrava registro em qualquer ano — e deixou
    passar `DOENCA_TRA`, que tem 9.654 registros **todos entre 2010 e 2014** e
    está zerada desde 2015. No painel, que abre em 2023, ela era uma opção que
    só entregava vazio.

    A régua certa é o ano corrente: quem é oferecido tem de responder no ano
    que o painel mostra por padrão.
    """
    import duckdb

    from src.doencas import tuberculose as pack

    fonte = microdado._fonte()
    con = duckdb.connect()
    mudas = []
    for variavel in sorted(pack.variaveis_planas()):
        preenchidas = con.execute(
            f"SELECT count(*) FROM read_parquet('{fonte}') "
            f"WHERE ano = ? AND trim(\"{variavel}\") NOT IN ('NA', '')",
            [ANO],
        ).fetchone()[0]
        if not preenchidas:
            mudas.append(variavel)
    assert not mudas, (
        f"oferecidas e sem nenhum registro em {ANO}: {mudas}. "
        f"Ou a extração parou de preencher, ou a variável não serve a este "
        f"painel — nos dois casos, oferecer é pior que omitir."
    )


def test_altura_do_grafico_cresce_com_as_categorias() -> None:
    """**Regressão de rótulos encavalados em "Tipo de entrada".**

    A primeira versão da grade usava `max(altura, 30 * n)`, e com cinco
    categorias isso dava exatamente os 150px pedidos pelo painel — os mesmos
    150 de um gráfico de três. Como título, eixo e rótulo do eixo comem os
    primeiros 85, sobravam 65px para cinco barras, treze cada.

    O cromo entra na conta separado das barras, e por isso cada categoria a
    mais soma altura de verdade.
    """
    from cenarios_core import grafico_componente as graficos

    alturas = [graficos.altura_composicao(n) for n in (3, 4, 5, 11)]
    assert alturas == sorted(alturas)
    for anterior, seguinte in zip(alturas, alturas[1:], strict=False):
        assert seguinte > anterior

    # Cada barra fica com o espaço declarado, independentemente de quantas são.
    for n in (3, 5, 11):
        barras = graficos.altura_composicao(n) - graficos.CROMO_COMPOSICAO
        assert barras // n == graficos.ALTURA_BARRA_COMPOSICAO
