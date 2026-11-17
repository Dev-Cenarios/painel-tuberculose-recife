"""Executa a aplicação inteira com o ``AppTest`` do Streamlit.

**Entra agora, e não na última semana.** No painel nacional o `app.py` ficou
quase todo o projeto com zero cobertura de execução: os testes cobriam
leitores, gráficos e mapa, e ninguém rodava a aplicação. Um defeito de
navegação ficou dois dias no ar sem nenhum teste vermelho.

A armadilha do teste ingênuo
----------------------------

`resiliencia.painel` contém a falha de um painel no próprio painel — de
propósito, porque no Streamlit exceção no corpo do script troca a página
inteira pelo traceback. O efeito colateral é que a aplicação "sobe" com metade
dos gráficos quebrados e um teste que só confere ausência de exceção passa
feliz.

Por isso :func:`test_nenhum_painel_caiu` existe, e é o teste mais importante
deste arquivo: ele confere o **aviso** que a resiliência desenha no lugar do
painel que caiu.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

from src.data import config

ANO = config.ANO_MAX_RECIFE

#: Generoso de propósito: a primeira execução lê parquet frio e monta a
#: geometria. Passar disso é sintoma, não lentidão de máquina.
TEMPO_LIMITE = 120

#: Absoluto: o `AppTest.from_file` resolve caminho relativo contra o arquivo
#: que o chama, e não contra a raiz do projeto — daqui, "app.py" viraria
#: `tests/app.py`.
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(scope="module")
def app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()


# ---------------------------------------------------------------------------
# A aplicação sobe — e sobe inteira
# ---------------------------------------------------------------------------


def _mapas(at):
    """Só o componente do mapa: o spec do pydeck vai no argumento `spec`."""
    return [c for c in at.get("component_instance") if '"spec"' in c.proto.json_args]


def test_sobe_sem_excecao(app: AppTest) -> None:
    assert not app.exception, [e.value for e in app.exception]


def test_nenhum_painel_caiu(app: AppTest) -> None:
    """O teste que a ausência de exceção não substitui.

    `resiliencia.painel` engole a falha e desenha um aviso. Sem conferir o
    aviso, um painel quebrado passa despercebido.
    """
    assert not app.warning, [w.value for w in app.warning]
    assert not app.error, [e.value for e in app.error]


def test_desenha_o_mapa_e_todos_os_graficos(app: AppTest) -> None:
    """Mapa, mais os seis fixos de Recife, mais os tópicos.

    Os seis: canal endêmico e mapa de calor (Evolução), Sankey e cura por ano
    (Desfechos), ranking e pirâmide. Nos tópicos as sim/não dividem um
    pirulito só; as outras têm um gráfico cada.
    """
    from src.doencas import tuberculose as pack

    fixos = 6
    assert len(_mapas(app)) == 1
    sim_nao = {"AGRAVALCOO", "AGRAVDROGA", "AGRAVTABAC", "AGRAVDIABE", "AGRAVDOENC",
               "POP_RUA", "POP_LIBER", "POP_SAUDE", "BENEF_GOV"}
    outras = [v for v in pack.VARIAVEIS_DESTAQUE if v not in sim_nao]
    assert len(app.get("component_instance")) == 1 + fixos + 1 + len(outras)
    assert len(app.get("vega_lite_chart")) == 0


def test_abas_de_recife(app: AppTest) -> None:
    assert [t.label for t in app.tabs] == [
        "Evolução temporal", "Desfechos", "Ranking de bairros", "Pirâmide etária"]


def test_bairro_abre_no_retrato() -> None:
    """Clicar num bairro traz a aba Bairro na frente, com a frase e o 10º de 94."""
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.entrar_bairro("Guabiraba", nome="Guabiraba")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert [t.label for t in at.tabs][0] == "Bairro"
    texto = " ".join(m.value for m in at.markdown)
    assert "casos novos de tuberculose em Guabiraba em 2023" in texto
    assert "10ª maior incidência entre 94 bairros" in texto
    assert "2,2× a do Recife" in texto


# ---------------------------------------------------------------------------
# Os números da tela
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rotulo", "valor"),
    [
        # 1.685 casos novos no SINAN nacional; o Boletim de 2024 publicou 1.637
        # com o banco de fev/2024
        ("Incidência", "105,82"),
        ("Incidência", "1.685 casos"),
        ("Proporção de cura", "999 de 1.668"),
        ("Coinfecção TB-HIV", "202 de 1.685"),
        ("TRM-TB", "600 de 1.467"),
        # SIM: 141 óbitos
        ("Taxa de mortalidade", "8,85"),
    ],
)
def test_kpi_aparece_com_o_valor(app: AppTest, rotulo: str, valor: str) -> None:
    """Recife 2023 na definição do Boletim, conferido no banco do SINAN."""
    texto = " ".join(m.value for m in app.markdown)
    assert rotulo in texto
    assert valor in texto


def test_trilha_comeca_em_recife(app: AppTest) -> None:
    texto = " ".join(m.value for m in app.markdown)
    assert "Recife" in texto
    assert f"Ano: {ANO}" in texto


# ---------------------------------------------------------------------------
# Controles
# ---------------------------------------------------------------------------


def test_seletor_de_ano_nao_oferece_ano_sem_composicao(app: AppTest) -> None:
    """`incidence` vai até 2025, mas `sinan_landing` e o microdado param em
    2023. Oferecer 2024 entregaria mapa cheio com composição vazia."""
    # O `AppTest` devolve as opções já formatadas para a tela, como texto.
    anos = [int(a) for a in app.selectbox[0].options]
    assert max(anos) == ANO
    assert 2024 not in anos


def test_trocar_o_ano_muda_os_numeros() -> None:
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    antes = " ".join(m.value for m in at.markdown)

    at.selectbox[0].select(ANO - 1).run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]
    assert " ".join(m.value for m in at.markdown) != antes


def test_trocar_o_recorte_para_distrito_nao_derruba_nada() -> None:
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.definir_recorte("DISTRITO")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]
    assert len(_mapas(at)) == 1


def test_variaveis_de_composicao_do_painel_de_origem_estao_no_seletor(
    app: AppTest,
) -> None:
    """As dez que a equipe parceira expõe têm de estar oferecidas."""
    from src.doencas import tuberculose as pack

    planas = pack.variaveis_planas()
    esperadas = {
        "TRATAMENTO", "HIV", "FORMA", "CS_RACA", "AGRAVALCOO",
        "SITUA_ENCE", "POP_RUA", "POP_SAUDE", "AGRAVDROGA", "AGRAVTABAC",
    }
    assert esperadas <= set(planas)


# ---------------------------------------------------------------------------
# Navegação — o drill-down até o bairro
# ---------------------------------------------------------------------------


def test_entrar_num_bairro_mantem_a_aplicacao_de_pe() -> None:
    """O clique no mapa não é simulável — deck.gl faz *picking* por GPU. O que
    dá para exercitar é o **efeito** dele: o estado muda e a página reexecuta.
    """
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.entrar_bairro("Boa Viagem", nome="Boa Viagem")
    at.run()

    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]
    texto = " ".join(m.value for m in at.markdown)
    assert "Boa Viagem" in texto


def test_dentro_de_um_bairro_o_mapa_continua_mostrando_a_cidade() -> None:
    """O mapa lista sempre os 94 bairros, para o usuário ver onde ele está."""
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.entrar_bairro("Ibura")
    at.run()
    assert len(_mapas(at)) == 1
    assert at.session_state.nav.escopo_listagem.nivel == "MUN"


def test_bairro_pequeno_nao_derruba_a_composicao() -> None:
    """Bairro com poucos casos leva a proporção abaixo do mínimo publicável.
    O painel tem de mostrar a contagem, não cair."""
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.entrar_bairro("Soledade")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]


def test_ver_recife_inteiro_volta_ao_topo() -> None:
    """É o botão que o painel de origem chama de "Ver Recife inteiro"."""
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.entrar_bairro("Curado")
    at.run()

    botoes = [b for b in at.button if "Recife inteiro" in b.label]
    assert botoes, "o botão de voltar sumiu ao entrar num bairro"
    botoes[0].click().run()

    assert at.session_state.nav.nivel == "MUN"
    assert at.session_state.nav.bairro is None
    assert not at.exception


# ---------------------------------------------------------------------------
# O card não pode mentir sobre o próprio escopo
# ---------------------------------------------------------------------------


def test_kpi_de_bairro_e_do_bairro_e_nao_da_cidade() -> None:
    """Regressão de um defeito real, e do tipo que não parece defeito.

    A primeira versão degradava o KPI para a cidade em qualquer nível, mas o
    subtítulo do card exibia o nome do bairro aberto. A tela mostrava
    "GUABIRABA • 2023" ao lado de 2.485 casos, que são de Recife inteiro.
    """
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    cidade = " ".join(m.value for m in at.markdown)
    assert "1.685 casos" in cidade

    at.session_state.nav.entrar_bairro("Guabiraba", nome="Guabiraba")
    at.run()
    bairro = " ".join(m.value for m in at.markdown)

    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]
    assert "Guabiraba" in bairro
    assert "1.685 casos" not in bairro, "o card continuou exibindo o número da cidade"


def test_clique_repetido_no_mesmo_bairro_nao_reexecuta_sem_fim() -> None:
    """A seleção do deck persiste entre execuções: ela não chega como evento,
    e sim como estado. Sem o guarda, reagir a ela dispara `st.rerun()` a cada
    passada — o laço infinito que já aconteceu no painel nacional."""
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.entrar_bairro("Ibura", nome="Ibura")
    at.run()
    at.run()  # segunda passada com o mesmo estado
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state.nav.bairro == "IBURA"


# ---------------------------------------------------------------------------
# O recorte precisa atravessar a tela inteira
# ---------------------------------------------------------------------------


def test_ranking_muda_de_nome_com_o_recorte() -> None:
    """"Ranking de bairros" listando Distritos Sanitários é pior que um rótulo
    genérico: afirma algo falso sobre o que está na tela.

    O ranking já seguia o recorte desde que `valores.ranking` passou a receber
    o método; o que não seguia era o **rótulo da aba**.
    """
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    assert any("bairros" in aba.label for aba in at.tabs), [a.label for a in at.tabs]

    at.session_state.nav.definir_recorte("DISTRITO")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]

    rotulos = [aba.label for aba in at.tabs]
    assert any("Distritos Sanitários" in r for r in rotulos), rotulos
    assert not any("bairros" in r for r in rotulos), rotulos


def test_mapa_de_distritos_pinta_todos_os_oito() -> None:
    """Regressão do distrito branco: com quartis, o de menor incidência saía
    sem cor por um corte arredondado acima do próprio valor."""
    import json

    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.definir_recorte("DISTRITO")
    at.session_state.nav.definir_classificacao("QUARTIL")
    at.run()

    assert not at.exception, [e.value for e in at.exception]
    from cenarios_core import mapa

    # O mapa é componente próprio (`cenarios_core.mapa_componente`): o spec do
    # pydeck vai como argumento `spec`, texto JSON dentro dos `json_args`.
    args = json.loads(_mapas(at)[0].proto.json_args)
    spec = json.loads(args["spec"])
    feicoes = spec["layers"][0]["data"]["features"]
    assert len(feicoes) == 8
    sem_cor = [
        f["properties"]["ds"]
        for f in feicoes
        if f["properties"]["cor"][:3] == list(mapa._rgb(mapa.SEM_DADO))[:3]
    ]
    assert not sem_cor, f"distritos pintados de sem dado: {sem_cor}"


def test_topicos_abrem_com_o_conjunto_do_painel_de_origem(app: AppTest) -> None:
    """Dez de saída, as mesmas que eles mostram — continuidade para quem vem
    do painel deles. As outras dezesseis ficam no seletor."""
    from src.doencas import tuberculose as pack

    escolhidas = app.multiselect[0].value
    assert list(escolhidas) == list(pack.VARIAVEIS_DESTAQUE)
    assert len(pack.variaveis_planas()) > len(pack.VARIAVEIS_DESTAQUE)


def test_sem_topico_escolhido_a_pagina_continua_de_pe() -> None:
    """Esvaziar o seletor é uma ação legítima, e não pode derrubar o painel
    nem deixar um vão mudo no fim da página."""
    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.multiselect[0].set_value([]).run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]
    texto = " ".join(c.value for c in at.caption)
    assert "Nenhuma variável escolhida" in texto


def test_um_clique_na_metrica_realca_o_card_na_mesma_passada() -> None:
    """Os cards ficam acima do seletor de métrica. Lendo o valor onde o widget
    é criado, os cards realçavam a métrica antiga e só o rerun seguinte — um
    segundo clique em qualquer coisa — os punha em dia (21/set/2026). A
    métrica muda num callback, antes do script, e o card acompanha no
    primeiro clique."""
    import re

    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    from src import doencas

    pack = doencas.carregar()
    seletor = next(w for w in at.segmented_control if w.label == "Métrica")
    # `options` do AppTest são os rótulos formatados; o valor é a chave.
    alvo = next(m for m in pack.METRICAS_MAPA if m != seletor.value and m in pack.LAYOUT_KPI)
    seletor.set_value(alvo).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state.nav.metrica == alvo
    html = " ".join(m.value for m in at.markdown)
    cards = re.findall(r'class="kpi-card is-selected[^"]*"(.{0,400})', html)
    assert len(cards) == 1
    assert pack.rotulo_curto(alvo) in cards[0]


def test_quartis_no_mapa_sao_quatro() -> None:
    """O core usa cinco classes por padrão (os quintis de PE). Recife usa
    quartis, como o painel em R — e é o `app.py` quem diz isso ao mapa
    (`QUANTIS`). Sem ele, migrar para o cenarios-core trocava a régua."""
    import json

    at = AppTest.from_file(APP, default_timeout=TEMPO_LIMITE).run()
    at.session_state.nav.definir_classificacao("QUARTIL")
    at.run()

    assert not at.exception, [e.value for e in at.exception]
    from cenarios_core import mapa

    spec = json.loads(json.loads(_mapas(at)[0].proto.json_args)["spec"])
    classes = {f["properties"]["classe"] for f in spec["layers"][0]["data"]["features"]}
    assert len(classes - {mapa.ROTULO_SEM_DADO}) == 4, sorted(classes)


def test_o_quadro_do_mapa_tem_nome_para_leitor_de_tela(app: AppTest) -> None:
    """O core põe no quadro do mapa o `titulo` que o painel manda; sem ele o
    leitor de tela anunciaria o nome interno do componente."""
    import json

    args = json.loads(_mapas(app)[0].proto.json_args)
    assert args["titulo"].startswith("Mapa do Recife: "), args.get("titulo")
    # Sem teto de altura: o padrão do core (1,15 × largura) cortava a caixa
    # de 720 para 642, e o teste da legenda mede contra os 720.
    assert args["proporcao_maxima"] is None
