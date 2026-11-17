"""Testes do mapa e da camada de valores que o alimenta.

O `src/mapa.py` veio inteiro do painel nacional e não foi reescrito — só dois
pontos encostavam na geografia: o nome da coluna de rótulo e o resolvedor de
clique. O que se testa aqui, então, é sobretudo **o que é novo**: a composição
das métricas e a agregação por Distrito Sanitário.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cenarios_core import mapa
from src.data import config, geo, valores
from src.data.escopo import Escopo
from src.doencas import tuberculose as pack

ANO = config.ANO_MAX_RECIFE


@pytest.fixture(scope="module")
def esc() -> Escopo:
    return Escopo("TUBERCULOSE", ANO, "MUN", uf=config.UF_RECIFE, mun=config.MUN_RECIFE)


# ---------------------------------------------------------------------------
# Composição das métricas
# ---------------------------------------------------------------------------


def test_casos_do_mapa_sao_os_casos_novos_do_microdado(esc: Escopo) -> None:
    """O mapa conta casos novos (Boletim), não notificações: 1.864 nos 94 bairros em 2023."""
    from src.data import indicadores

    casos = valores.por_bairro(esc, "casos")
    contagem = indicadores.contagens_por_bairro(esc.ano).set_index("bairro_key")["casos"]
    assert len(casos) == 94
    assert casos.sum() == contagem.reindex(casos.index).fillna(0).sum() == 1864


def test_mortalidade_fora_do_mapa() -> None:
    assert "mortalidade" not in pack.METRICAS_MAPA


@pytest.mark.parametrize("metrica", sorted(valores.metricas_disponiveis()))
def test_toda_metrica_declarada_calcula(esc: Escopo, metrica: str) -> None:
    serie = valores.por_bairro(esc, metrica)
    assert len(serie) == 94
    assert serie.notna().any(), f"{metrica} veio inteira vazia"


def test_metrica_desconhecida_recusada(esc: Escopo) -> None:
    with pytest.raises(ValueError, match="Métrica desconhecida"):
        valores.por_bairro(esc, "inventada")


# ---------------------------------------------------------------------------
# Agregação por distrito — taxa não se soma
# ---------------------------------------------------------------------------


def test_incidencia_do_distrito_nao_e_media_dos_bairros(esc: Escopo) -> None:
    """**A razão de existir deste módulo.**

    A média simples pesa igual um bairro de 9 mil e um de 118 mil habitantes.
    A conta certa é ``soma(casos) / soma(pop)``, e as duas dão números
    diferentes — se um dia coincidirem, é porque a agregação virou média sem
    ninguém decidir isso.
    """
    correto = valores.por_distrito(esc, "incid")
    media = (
        valores.por_bairro(esc, "incid")
        .to_frame("incid")
        .join(geo.bairros().set_index("bairro_key")["ds"])
        .groupby("ds")["incid"]
        .mean()
    )
    assert not np.allclose(correto.sort_index(), media.sort_index())


def test_casos_do_distrito_somam_os_bairros(esc: Escopo) -> None:
    """Contagem, ao contrário de taxa, **se** soma — e tem de fechar."""
    por_ds = valores.por_distrito(esc, "casos").sum()
    por_bairro = valores.por_bairro(esc, "casos").sum()
    assert por_ds == por_bairro


def test_distrito_cobre_os_oito(esc: Escopo) -> None:
    assert len(valores.por_distrito(esc, "incid")) == 8


# ---------------------------------------------------------------------------
# Base pequena
# ---------------------------------------------------------------------------


def test_proporcao_suprimida_em_base_pequena(esc: Escopo) -> None:
    """Um bairro com quatro encerramentos e três curas exibiria 75% e pintaria
    como um dos melhores da cidade, apoiado em quatro pessoas."""
    assert valores.por_bairro(esc, "cura_pct").isna().any()


def test_incidencia_nao_e_suprimida(esc: Escopo) -> None:
    """População pequena não torna a incidência menos real — a de Curado é
    alta de verdade. A supressão vale para proporção, não para taxa."""
    assert valores.por_bairro(esc, "incid").notna().all()


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------


def test_quebras_naturais_batem_os_quantis(esc: Escopo) -> None:
    """Herdado do painel nacional, e vale aqui igual: a incidência por bairro
    tem cauda longa — o bairro do Recife dá 3.610 por 100 mil — e o quantil
    comprime tudo numa faixa só de cor.

    Medido: GVF 0,84 contra 0,32.
    """
    v = valores.por_bairro(esc, "incid").dropna().to_numpy(float)

    def gvf(cortes) -> float:
        sdam = ((v - v.mean()) ** 2).sum()
        idx = np.clip(np.searchsorted(cortes[1:-1], v, side="right"), 0, len(cortes) - 2)
        scdm = sum(
            ((g - g.mean()) ** 2).sum()
            for g in (v[idx == k] for k in range(len(cortes) - 1))
            if len(g)
        )
        return 1 - scdm / sdam

    natural = mapa.escala_natural(
        pd.Series(v), pack.PALETA_MAPA["incid"], decimais=1
    ).cortes
    quantis = list(np.quantile(v, np.linspace(0, 1, len(natural))))
    assert gvf(natural) > gvf(quantis) + 0.3


def test_cortes_sao_crescentes(esc: Escopo) -> None:
    cortes = mapa.escala_natural(
        valores.por_bairro(esc, "incid"), pack.PALETA_MAPA["incid"], decimais=1
    ).cortes
    assert cortes == sorted(cortes)


# ---------------------------------------------------------------------------
# Montagem do deck
# ---------------------------------------------------------------------------


def test_deck_de_bairros_monta(esc: Escopo) -> None:
    deck, escala = mapa.deck(
        geo.bairros(),
        valores.para_o_mapa(esc, "incid", "BAIRRO"),
        chave="bairro_key",
        rampa=list(pack.PALETA_MAPA["incid"]),
        rotulo_metrica=pack.rotulo("incid"),
        coluna_nome="bairro_nome",
    )
    assert deck.layers
    assert len(escala.cortes) >= 2


def test_deck_de_distritos_monta(esc: Escopo) -> None:
    deck, _ = mapa.deck(
        geo.distritos(),
        valores.para_o_mapa(esc, "incid", "DISTRITO"),
        chave="ds",
        rampa=list(pack.PALETA_MAPA["incid"]),
        rotulo_metrica=pack.rotulo("incid"),
        coluna_nome="ds",
    )
    assert deck.layers


@pytest.mark.parametrize("metrica", sorted(pack.METRICAS_MAPA))
def test_toda_metrica_do_seletor_desenha(esc: Escopo, metrica: str) -> None:
    """Oferecer no seletor uma métrica que leva a painel vazio é pior que não
    oferecer — a regra que o pack do painel nacional já registrava."""
    serie = valores.para_o_mapa(esc, metrica, "BAIRRO")
    assert serie.notna().sum() > 10, metrica
    deck, _ = mapa.deck(
        geo.bairros(), serie, chave="bairro_key",
        rampa=list(pack.PALETA_MAPA.get(metrica, (pack.cor(metrica),))),
        rotulo_metrica=pack.rotulo(metrica), coluna_nome="bairro_nome",
    )
    assert deck.layers


def test_recorte_desconhecido_recusado(esc: Escopo) -> None:
    with pytest.raises(ValueError, match="Recorte desconhecido"):
        valores.para_o_mapa(esc, "incid", "QUARTEIRAO")


# ---------------------------------------------------------------------------
# Clique
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# As três classificações
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metodo", mapa.CLASSIFICACOES)
def test_toda_classificacao_produz_escala_usavel(esc: Escopo, metodo: str) -> None:
    v = valores.por_bairro(esc, "incid")
    e = mapa.escala(
        v, pack.rampa_mapa("incid"), metodo=metodo,
        cortes_fixos=pack.cortes_fixos("incid"),
    )
    assert e.cortes == sorted(e.cortes)
    assert len(e.rotulos) >= 2
    # Toda classe da legenda tem cor, e toda cor tem classe.
    assert set(e.rotulos) | {mapa.ROTULO_SEM_DADO} == set(e.cores)


def test_quartil_reparte_em_quatro_partes_iguais(esc: Escopo) -> None:
    """É a propriedade que define o método, e o motivo de pedirem por ele: um
    quarto dos bairros em cada cor."""
    v = valores.por_bairro(esc, "incid").dropna()
    # Quatro, e não o padrão do core (cinco, os quintis de PE): é o
    # `QUANTIS` do `app.py`, que o mapa e o ranking recebem.
    e = mapa.escala_quartis(v, pack.rampa_mapa("incid"), quantis=4)
    contagem = mapa.classificar(v, e).value_counts()
    assert len(e.rotulos) == 4
    assert contagem.max() - contagem.min() <= 2  # 94 não divide por 4


def test_escala_fixa_nao_muda_entre_anos(esc: Escopo) -> None:
    """**A razão de a escala fixa existir.**

    Nos outros dois métodos a régua é recalculada a cada ano: a segunda quebra
    natural foi 93 em 2021, 105 em 2022 e 101 em 2023. Um bairro escurece de um
    ano para o outro tendo incidência menor, e dois mapas lado a lado não se
    comparam. Aqui os cortes internos são os declarados no pack, sempre.
    """
    declarados = list(pack.cortes_fixos("incid"))
    internos = []
    for ano in (ANO - 2, ANO - 1, ANO):
        e = mapa.escala(
            valores.por_bairro(Escopo("TUBERCULOSE", ano, "MUN",
                                      uf=config.UF_RECIFE, mun=config.MUN_RECIFE),
                               "incid"),
            pack.rampa_mapa("incid"),
            metodo="FIXA",
            cortes_fixos=declarados,
        )
        # O último corte é o máximo da série, e esse muda de ano para ano —
        # os declarados, não.
        internos.append(e.cortes[1:-1])
    assert internos[0] == internos[1] == internos[2]
    assert internos[0] == [float(c) for c in declarados[1:]]


def test_naturais_ajustam_melhor_que_quartis(esc: Escopo) -> None:
    """Registro executável do número que sustenta o padrão: 0,84 contra 0,24."""
    v = valores.por_bairro(esc, "incid").dropna().to_numpy(float)

    def gvf(cortes) -> float:
        sdam = ((v - v.mean()) ** 2).sum()
        idx = np.clip(np.searchsorted(np.asarray(cortes)[1:-1], v, side="right"),
                      0, len(cortes) - 2)
        scdm = sum(((g - g.mean()) ** 2).sum()
                   for g in (v[idx == k] for k in range(len(cortes) - 1)) if len(g))
        return 1 - scdm / sdam

    serie = valores.por_bairro(esc, "incid")
    nat = mapa.escala(serie, pack.rampa_mapa("incid"), metodo="NATURAL").cortes
    qua = mapa.escala(serie, pack.rampa_mapa("incid"), metodo="QUARTIL").cortes
    assert gvf(nat) > 0.8
    assert gvf(qua) < 0.4


def test_classificacao_desconhecida_recusada(esc: Escopo) -> None:
    with pytest.raises(ValueError, match="Classificação desconhecida"):
        mapa.escala(valores.por_bairro(esc, "incid"), pack.rampa_mapa("incid"),
                    metodo="JENKS")


def test_fixa_sem_cortes_cai_em_naturais(esc: Escopo) -> None:
    """Mapa sem cor por falta de configuração é pior que mapa classificado de
    outro jeito — por isso a ausência degrada em vez de estourar."""
    v = valores.por_bairro(esc, "incid")
    sem = mapa.escala(v, pack.rampa_mapa("incid"), metodo="FIXA", cortes_fixos=None)
    natural = mapa.escala(v, pack.rampa_mapa("incid"), metodo="NATURAL")
    assert sem.cortes == natural.cortes


def test_toda_metrica_do_mapa_tem_corte_fixo_declarado() -> None:
    """Sem isto, trocar para escala fixa devolveria quebras naturais em
    silêncio numa métrica e escala fixa noutra — a mesma tela com duas réguas
    diferentes conforme o botão apertado."""
    faltando = [m for m in pack.METRICAS_MAPA if not pack.cortes_fixos(m)]
    assert not faltando, f"métricas sem corte fixo: {faltando}"


def test_escala_fixa_preserva_a_ancora_de_cima(esc: Escopo) -> None:
    """O máximo da série entra como corte **a mais**, não no lugar do último.

    Substituir apagava a âncora de cima: com cortes até 624 e máximo em 3.610,
    a legenda exibia "312 a 3.610" e o 4× Recife sumia da tela.
    """
    declarados = list(pack.cortes_fixos("incid"))
    e = mapa.escala(
        valores.por_bairro(esc, "incid"),
        pack.rampa_mapa("incid"),
        metodo="FIXA",
        cortes_fixos=declarados,
    )
    for corte in declarados[1:]:
        assert float(corte) in e.cortes, f"corte declarado {corte} sumiu da escala"
    assert e.cortes[-1] > declarados[-1]


@pytest.mark.parametrize("metrica", sorted(pack.NOMES_FIXOS))
def test_cada_faixa_da_regua_tem_nome(metrica: str) -> None:
    """Um nome por faixa: N cortes viram N faixas, a última aberta."""
    assert len(pack.nomes_fixos(metrica)) == len(pack.cortes_fixos(metrica))
    e = mapa.escala(pd.Series([1.0]), pack.rampa_mapa(metrica), metodo="FIXA",
                    cortes_fixos=pack.cortes_fixos(metrica),
                    nomes_fixos=pack.nomes_fixos(metrica), casas_regua=pack.CASAS_REGUA)
    assert e.rotulos[0].startswith("< ") and e.rotulos[-1].startswith("≥ ")


def test_regua_de_incidencia_na_legenda(esc: Escopo) -> None:
    """Nome e N de cada faixa na legenda, e os N somam os 94 bairros."""
    serie = valores.por_bairro(esc, "incid")
    e = mapa.escala(serie, pack.rampa_mapa("incid"), metodo="FIXA",
                    cortes_fixos=pack.cortes_fixos("incid"),
                    nomes_fixos=pack.nomes_fixos("incid"), casas_regua=pack.CASAS_REGUA)
    assert e.rotulos == ["< 40,0", "40,0 a 79,9", "80,0 a 105,9",
                         "106,0 a 211,9", "212,0 a 423,9", "≥ 424,0"]
    contagem = mapa.classificar(serie, e).value_counts()
    assert int(contagem[e.rotulos].sum()) == serie.notna().sum()
    html = mapa.legenda(e, "Incidência", contagem=contagem, nomes=pack.nomes_fixos("incid"))
    assert "abaixo do Brasil" in html and "mais de 4× Recife" in html


def test_mapa_abre_na_escala_fixa() -> None:
    from src.estado import CLASSIFICACOES, Navegacao

    assert Navegacao().classificacao == "FIXA" == CLASSIFICACOES[0]


def test_nenhuma_geografia_com_valor_sai_sem_cor(esc: Escopo) -> None:
    """**Regressão de um defeito que pintava de branco quem tinha dado.**

    No `escala_quartis` os cortes eram arredondados para dez casas ao
    deduplicar. Parecia inofensivo e excluía o mínimo: com o Distrito
    Sanitário III em 72,2660471147612, o corte inferior virava
    72,2660471148 — maior que o próprio valor —, o `pd.cut` devolvia nulo e o
    distrito saía de "sem dado", branco, que num mapa é justamente o que mais
    chama atenção.

    Vale para as três classificações e os dois recortes: quem tem número tem
    cor.
    """
    for recorte in ("BAIRRO", "DISTRITO"):
        serie = valores.para_o_mapa(esc, "incid", recorte)
        for metodo in mapa.CLASSIFICACOES:
            e = mapa.escala(
                serie, pack.rampa_mapa("incid"), metodo=metodo,
                cortes_fixos=pack.cortes_fixos("incid"),
            )
            classes = mapa.classificar(serie, e)
            orfas = serie.notna() & (classes == mapa.ROTULO_SEM_DADO)
            assert not orfas.any(), (
                f"{recorte}/{metodo}: {sorted(serie.index[orfas])} têm valor e "
                f"saíram sem cor"
            )


def test_o_menor_valor_entra_na_primeira_classe(esc: Escopo) -> None:
    """O extremo de baixo é o que a fronteira da primeira classe mais ameaça —
    qualquer deslocamento do corte o expulsa."""
    serie = valores.para_o_mapa(esc, "incid", "DISTRITO").dropna()
    for metodo in mapa.CLASSIFICACOES:
        e = mapa.escala(
            serie, pack.rampa_mapa("incid"), metodo=metodo,
            cortes_fixos=pack.cortes_fixos("incid"),
        )
        assert e.cortes[0] <= serie.min(), f"{metodo}: corte acima do mínimo"


# ---------------------------------------------------------------------------
# Nota de população pequena
# ---------------------------------------------------------------------------


def test_nota_de_populacao_pequena_diz_quanto_pesa_um_caso() -> None:
    """O Bairro do Recife tem 554 moradores: cada caso vale 180,5 por 100 mil.
    A nota tem de dizer isso com o número, e ficar vazia acima do limiar."""
    nota = valores.nota_populacao(554)
    assert "554" in nota and "180,5" in nota
    assert valores.nota_populacao(valores.POPULACAO_PEQUENA) == ""
    assert valores.nota_populacao(None) == ""


def test_notas_do_mapa_so_nas_taxas_e_so_por_bairro(esc: Escopo) -> None:
    notas = valores.notas_do_mapa(esc, "incid", "BAIRRO")
    com_nota = notas[notas != ""]
    assert "RECIFE" in com_nota.index
    assert "BOA VIAGEM" not in com_nota.index
    assert valores.notas_do_mapa(esc, "casos", "BAIRRO").empty
    assert valores.notas_do_mapa(esc, "incid", "DISTRITO").empty


# ---------------------------------------------------------------------------
# O mapa não entra debaixo da legenda
# ---------------------------------------------------------------------------


def test_legenda_fica_embaixo_do_mapa() -> None:
    """Como no tbbrasil: caixa abaixo do mapa, sem margem negativa por cima dele."""
    from pathlib import Path

    from src.theme import componentes

    fonte = Path(componentes.__file__).read_text(encoding="utf-8")
    bloco = fonte[fonte.index(".mapa-legenda {{"):]
    bloco = bloco[: bloco.index("}}")]
    assert "margin: -" not in bloco and "width: 100%" in bloco


def test_nomes_de_bairro_em_caixa_normal() -> None:
    nomes = set(geo.bairros()["bairro_nome"])
    assert {"Guabiraba", "Alto José do Pinho", "Bairro do Recife", "Caxangá"} <= nomes
    assert not any(n.isupper() and len(n) > 4 for n in nomes)
