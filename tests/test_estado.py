"""Testes da máquina de navegação.

O teste mais valioso aqui não é caso a caso: é percorrer o caminho de ida
inteiro e voltar passo a passo, conferindo que se chega exatamente ao ponto de
partida. Foi o que pegou estado inconsistente no painel nacional.

A hierarquia daqui é ``Recife -> (Distrito Sanitário) -> bairro``, sem nível
acima do município.
"""

from __future__ import annotations

import pytest

from src.data import config
from src.estado import RECORTES, Navegacao


def instantaneo(nav: Navegacao) -> tuple:
    """Só o que define o recorte — ignora doença, ano e métrica."""
    return (nav.nivel, nav.bairro, nav.detalhe, nav.recorte, nav.ds)


# ---------------------------------------------------------------------------
# Ida
# ---------------------------------------------------------------------------


def test_comeca_em_recife_inteiro() -> None:
    nav = Navegacao()
    assert nav.nivel == "MUN"
    assert nav.bairro is None
    assert nav.recorte == "BAIRRO"
    assert not nav.pode_voltar


def test_entrar_em_bairro() -> None:
    nav = Navegacao()
    nav.entrar_bairro("Boa Viagem", nome="Boa Viagem")
    assert nav.nivel == "BAIRRO"
    assert nav.bairro == "BOA VIAGEM"
    assert nav.pode_voltar


def test_entrar_em_bairro_normaliza_a_chave() -> None:
    """A chave vem do clique no mapa ou da barra do ranking, e as duas trazem
    o nome como está na malha — com acento e caixa mista."""
    nav = Navegacao()
    nav.entrar_bairro("Alto Santa Terezinha")
    assert nav.bairro == "ALTO SANTA TEREZINHA"

    nav.entrar_bairro("Bairro do Recife")
    assert nav.bairro == "RECIFE"


def test_distrito_filtra_sem_mudar_o_nivel() -> None:
    """O DS filtra o que o mapa mostra; os KPIs seguem falando de Recife."""
    nav = Navegacao()
    nav.entrar_distrito("3")
    assert nav.ds == "3"
    assert nav.nivel == "MUN"
    assert nav.escopo.nivel == "MUN"


def test_detalhe_so_existe_no_bairro() -> None:
    nav = Navegacao()
    with pytest.raises(ValueError, match="bairro"):
        nav.abrir_detalhe()

    nav.entrar_bairro("Ibura")
    nav.abrir_detalhe()
    assert nav.detalhe


# ---------------------------------------------------------------------------
# Volta — o caminho inteiro
# ---------------------------------------------------------------------------


def test_ida_e_volta_completas_fecham_no_ponto_de_partida() -> None:
    nav = Navegacao()
    nav.definir_recorte("DISTRITO")
    partida = instantaneo(nav)

    nav.entrar_distrito("5")
    nav.entrar_bairro("Curado", nome="Curado")
    nav.abrir_detalhe()

    nav.voltar()  # fecha o detalhe
    assert nav.nivel == "BAIRRO" and not nav.detalhe

    nav.voltar()  # bairro -> Recife, mantendo o DS
    assert instantaneo(nav) == ("MUN", None, False, "BAIRRO", "5")

    nav.voltar()  # limpa o DS, volta a ver os distritos
    assert instantaneo(nav) == partida
    assert not nav.pode_voltar


def test_voltar_no_topo_nao_faz_nada() -> None:
    nav = Navegacao()
    antes = instantaneo(nav)
    nav.voltar()
    nav.voltar()
    assert instantaneo(nav) == antes


def test_reset_volta_a_recife_inteiro() -> None:
    """É o "Ver Recife inteiro" do painel de origem."""
    nav = Navegacao()
    nav.entrar_distrito("2")
    nav.entrar_bairro("Afogados")
    nav.destacar("Ibura")

    nav.reset()
    assert instantaneo(nav) == ("MUN", None, False, "BAIRRO", None)
    assert nav.destacado is None


# ---------------------------------------------------------------------------
# Recorte
# ---------------------------------------------------------------------------


def test_recorte_invalido_recusado() -> None:
    nav = Navegacao()
    with pytest.raises(ValueError, match="Recorte inválido"):
        nav.definir_recorte("MACRO")  # existia no painel nacional, aqui não


def test_voltar_a_ver_distritos_descarta_o_distrito_escolhido() -> None:
    nav = Navegacao()
    nav.entrar_distrito("7")
    nav.definir_recorte("DISTRITO")
    assert nav.ds is None


@pytest.mark.parametrize("recorte", RECORTES)
def test_todo_recorte_declarado_e_aceito(recorte: str) -> None:
    Navegacao().definir_recorte(recorte)


# ---------------------------------------------------------------------------
# Destaque
# ---------------------------------------------------------------------------


def test_destacar_e_idempotente() -> None:
    """Não é interruptor: a seleção do gráfico persiste entre execuções, e um
    `destacar` que alternasse viraria laço infinito."""
    nav = Navegacao()
    nav.destacar("Ibura", nome="Ibura")
    nav.destacar("Ibura", nome="Ibura")
    assert nav.destacado == "IBURA"


def test_destacar_nao_muda_o_escopo() -> None:
    nav = Navegacao()
    nav.destacar("Cohab")
    assert nav.nivel == "MUN"
    assert nav.escopo.bairro is None


def test_entrar_num_bairro_apaga_o_destaque() -> None:
    nav = Navegacao()
    nav.destacar("Cohab")
    nav.entrar_bairro("Cohab")
    assert nav.destacado is None


# ---------------------------------------------------------------------------
# Escopo derivado
# ---------------------------------------------------------------------------


def test_escopo_sempre_carrega_recife() -> None:
    """Mesmo no nível BAIRRO: quem degrada com `no_municipio` precisa achar
    o município preenchido lá."""
    nav = Navegacao()
    nav.entrar_bairro("Torroes")
    esc = nav.escopo
    assert esc.nivel == "BAIRRO"
    assert esc.mun == config.MUN_RECIFE
    assert esc.uf == config.UF_RECIFE


def test_escopo_de_listagem_nunca_desce_a_bairro() -> None:
    """Dentro de um bairro o mapa continua listando os bairros de Recife."""
    nav = Navegacao()
    nav.entrar_bairro("Varzea")
    assert nav.escopo_listagem.nivel == "MUN"
    assert nav.escopo_listagem.bairro is None


# ---------------------------------------------------------------------------
# Trilha
# ---------------------------------------------------------------------------


def test_trilha_mostra_o_caminho_percorrido() -> None:
    nav = Navegacao()
    assert nav.trilha().startswith("Recife")

    nav.entrar_distrito("4")
    nav.entrar_bairro("Ibura", nome="Ibura")
    trilha = nav.trilha()
    assert "DS 4" in trilha
    assert "Ibura" in trilha
    assert f"Ano: {nav.ano}" in trilha
