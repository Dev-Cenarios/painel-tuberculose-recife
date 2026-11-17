"""Painel de Monitoramento da Tuberculose — Recife.

Reconstrução do painel Shiny/R da equipe parceira, sobre o core do painel
nacional. Layout de página única, como o original: faixa de KPIs no topo,
mapa à esquerda, abas à direita, composição embaixo.

**Este arquivo é composição, não lógica.** Toda conta vive em `src/data/`, e o
que está aqui é arranjo de tela e fiação de estado. Quando uma linha daqui
começar a calcular alguma coisa, ela está no lugar errado.

Sobre a fonte de cada painel
----------------------------

Há duas fontes de dado, e a escolha entre elas é feita **aqui**, de propósito:

- os **KPIs, o mapa e o ranking** saem da camada agregada (`incidence`,
  `sinan_landing`), que é o que o painel de origem publica — conferido bairro
  a bairro no `tests/paridade/`;
- **composição, meses e pirâmide de bairro** saem do microdado, porque no
  nível de bairro não existem pré-agregados.

As duas discordam no total: 2.485 contra 2.749 em 2023. A pergunta está com a
equipe parceira e, enquanto não volta, a fiação é esta — que reproduz o que
eles publicam. Quando a resposta vier, muda aqui, e só aqui.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from cenarios_core import grafico_componente, mapa, mapa_componente, resiliencia

from src import doencas
from src.data import canal, config, geo, indicadores, leitura, microdado, retrato, valores
from src.estado import CLASSIFICACOES, RECORTES, Navegacao
from src.theme import componentes as ui

#: A doença vem do ambiente (``SINAN_DOENCA``), não de um import fixo.
pack = doencas.carregar()

st.set_page_config(
    page_title=f"{pack.TITULO} — Recife",
    layout="wide",
    initial_sidebar_state="collapsed",
)

#: KPIs por linha: oito em duas de quatro, carga em cima e cuidado embaixo.
#:
#: Um `st.columns` por linha, e não um único para todas: ao empilhar no mobile
#: o Streamlit renderiza coluna a coluna, e um grid único entregaria os cards
#: fora da ordem do `LAYOUT_KPI`. Com uma linha só isso é moot hoje, mas a
#: estrutura fica de pé se um KPI a mais aparecer.
#:
#: Quem faz caber é o CSS: `min-width: 150px` na coluna, com `flex-wrap` no
#: bloco. Em tela estreita eles quebram sozinhos, sem media query.
POR_LINHA = 4

ROTULO_RECORTE = {"BAIRRO": "Bairros", "DISTRITO": "Distritos Sanitários"}

#: O mapa vem do cenarios-core, que serve camadas municipais; o que é de
#: Recife entra por aqui. As feições são bairro (`bairro_key`) e distrito
#: sanitário (`ds`), nessa precedência.
CAMPOS_CLIQUE = ("bairro_key", "ds")

#: Rodapé do canal endêmico. Fala de Recife ("desta cidade"), então mora no
#: painel e não no core, de onde vêm os gráficos desde 14/out/2026.
AVISO_CANAL = (
    "A faixa azul é o intervalo interquartil dos {n} anos anteriores "
    "({anos}): metade dos meses históricos caiu dentro dela. Mês acima do "
    "topo da faixa está fora do padrão desta cidade para aquele mês."
)

#: Quartis, como no painel em R: um quarto dos bairros em cada cor. O padrão
#: do core são cinco classes (os quintis de PE). Vai ao mapa **e** ao ranking,
#: que pinta as barras com a mesma escala — com valores diferentes, a barra
#: e o bairro no mapa teriam cores de classes diferentes.
QUANTIS = 4

#: Nome da unidade no singular e no plural, para os textos que a mencionam.
#: O ranking segue o recorte do mapa desde sempre — o que não seguia era o
#: **rótulo**, e "Ranking de bairros" listando distritos é pior que rótulo
#: genérico: afirma algo falso sobre o que está na tela.
UNIDADE_RECORTE = {"BAIRRO": "bairros", "DISTRITO": "Distritos Sanitários"}

#: referências das linhas de tendência: Brasil 2023 no Boletim de 2024 e a
#: meta do Plano Nacional pelo Fim da TB
BRASIL_INCID = 37.3
META_INCID = 10.0

#: azul da marca e cinza das linhas de comparação
AZUL_RECIFE = "#12346B"
CINZA_REFERENCIA = "#7A8B95"

#: fim da faixa dos bairros; o Bairro do Recife (2.527) esmagaria os outros 93
TETO_FAIXA_INCID = 700

#: Rótulos e explicação de cada classificação de cor. A explicação vai para o
#: `help` do controle: a escolha muda o que o mapa **afirma**, e quem troca
#: precisa saber o que está trocando.
ROTULO_CLASSIFICACAO = {
    "FIXA": "Escala fixa",
    "NATURAL": "Quebras naturais",
    "QUARTIL": "Quartis",
}

AJUDA_CLASSIFICACAO = """Como as cores repartem os valores.

**Escala fixa** (padrão) usa cortes ancorados em referência — média do Brasil, média de Recife e múltiplos; na cura, a meta de 85% da OMS. Cada faixa tem nome e o número de bairros ao lado. É a única que deixa dois anos comparáveis: nas outras duas a régua é recalculada a cada ano.

**Quebras naturais** agrupam bairros parecidos e separam os diferentes — é a que melhor descreve esta base (GVF 0,88).

**Quartis** põem um quarto dos bairros em cada cor. Fácil de explicar, mas com a cauda longa de Recife a classe de cima junta 157 e 2.527 por 100 mil na mesma cor (GVF 0,24)."""


ALTURA_LINHA_1 = mapa.ALTURA

#: Altura do mapa; a legenda vai numa caixa embaixo, como no tbbrasil
ALTURA_MAPA = 600


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
#
# As funções cacheadas recebem **valores primitivos**, nunca o `Escopo` nem a
# `Navegacao`. Objeto mutável como chave de cache é como o painel nacional
# serviu dado de um ano no card de outro: o `st.cache_data` compara por hash
# do argumento, e uma dataclass mutável rehasheia sem invalidar o que já
# guardou.


@st.cache_resource
def _anos() -> list[int]:
    """Anos oferecidos no seletor.

    Teto em `ANO_MAX_RECIFE`, e não no último ano do `incidence`: ele vai até
    2025, mas o `sinan_landing` e o microdado param em 2023. Oferecer 2024
    entregaria mapa cheio com composição vazia — pior que não oferecer.
    """
    disponiveis = leitura.anos_disponiveis(pack.DOENCA)
    return [ano for ano in disponiveis if ano <= config.ANO_MAX_RECIFE]


def _rotulo_ds(codigo: str) -> str | None:
    """Nome de exibição de um Distrito Sanitário: "DS - VI", e não "6".

    Vem da malha da prefeitura, e não de rótulo nosso. Os oito distritos de
    Recife não têm nome próprio — são numerados em algarismo romano.
    """
    return dict(zip(geo.distritos()["ds"], geo.distritos()["ds_nome"])).get(codigo)


def _escopo(ano: int, nivel: str, bairro: str | None):
    from src.data.escopo import Escopo

    return Escopo(
        doenca=pack.DOENCA,
        ano=ano,
        nivel=nivel,
        uf=config.UF_RECIFE,
        mun=config.MUN_RECIFE,
        bairro=bairro,
    )


@st.cache_data(show_spinner=False)
def _kpis(ano: int, nivel: str, bairro: str | None):
    """Faixa de KPIs do recorte corrente.

    **Do bairro quando há bairro aberto.** A primeira versão degradava sempre
    para a cidade, e o resultado era pior que não descer: o card exibia o
    número de Recife com o subtítulo dizendo o nome do bairro. Card que mente
    sobre o próprio escopo é mais perigoso que card ausente, porque não parece
    defeito.

    Cidade pelo SINAN nacional (a base do Boletim), bairro pelo microdado com
    as mesmas definições — ver `src/data/indicadores.py`.
    """
    esc = _escopo(ano, nivel, bairro)
    if nivel == "BAIRRO":
        return indicadores.do_bairro(esc, valores.populacao_do_bairro(esc))
    return indicadores.da_cidade(esc.no_municipio())


@st.cache_data(show_spinner=False)
def _procedencia() -> tuple[str, str] | None:
    return valores.procedencia()


@st.cache_data(show_spinner=False)
def _notas_mapa(ano: int, metrica: str, recorte: str) -> pd.Series:
    return valores.notas_do_mapa(_escopo(ano, "MUN", None), metrica, recorte)


@st.cache_data(show_spinner=False)
def _valores_mapa(ano: int, metrica: str, recorte: str) -> pd.Series:
    return valores.para_o_mapa(_escopo(ano, "MUN", None), metrica, recorte)


@st.cache_data(show_spinner=False)
def _ranking(ano: int, metrica: str, recorte: str, top_n: int) -> pd.DataFrame:
    return valores.ranking(_escopo(ano, "MUN", None), metrica, recorte, top_n)


@st.cache_data(show_spinner=False)
def _canal(ano: int):
    """Canal endêmico de Recife inteiro.

    Sempre da cidade, mesmo com um bairro aberto: o `_cache_ts` não desce a
    bairro, e uma taxa mensal por 100 mil de um bairro com trinta casos no ano
    oscilaria tanto entre meses que a faixa não significaria nada.
    """
    return canal.montar(_escopo(ano, "MUN", None))


@st.cache_data(show_spinner=False)
def _serie_cidade() -> pd.DataFrame:
    """Casos novos e incidência de Recife por ano, até o último ano fechado."""
    serie = indicadores.serie_anual_cidade(_escopo(config.ANO_MAX_RECIFE, "MUN", None))
    return serie[serie["ano"] <= config.ANO_MAX_RECIFE]


@st.cache_data(show_spinner=False)
def _serie_desfechos() -> pd.DataFrame:
    serie = indicadores.serie_desfechos_cidade()
    return serie[serie["ano"] <= config.ANO_MAX_RECIFE]


@st.cache_data(show_spinner=False)
def _calor(ano: int) -> pd.DataFrame:
    """Incidência mensal de Recife de 2010 até ``ano``, para o mapa de calor."""
    partes = []
    for a in range(retrato.ANO_MIN, ano + 1):
        mensal = indicadores.serie_mensal_cidade(_escopo(a, "MUN", None))
        partes.append(mensal.assign(ano=a).rename(columns={"incid": "valor"}))
    return pd.concat(partes, ignore_index=True)[["ano", "mes", "valor"]]


@st.cache_data(show_spinner=False)
def _tabela_bairros(ano: int) -> pd.DataFrame:
    return retrato.tabela_dos_bairros(_escopo(ano, "MUN", None))


@st.cache_data(show_spinner=False)
def _serie_bairro(bairro: str) -> pd.DataFrame:
    return retrato.serie_do_bairro(_escopo(config.ANO_MAX_RECIFE, "BAIRRO", bairro))


@st.cache_data(show_spinner=False)
def _nomes_bairros() -> dict[str, str]:
    return dict(zip(geo.bairros()["bairro_key"], geo.bairros()["bairro_nome"], strict=True))


@st.cache_data(show_spinner=False)
def _piramide(ano: int, nivel: str, bairro: str | None) -> pd.DataFrame:
    esc = _escopo(ano, nivel, bairro)
    if nivel == "BAIRRO":
        return microdado.piramide(esc)
    return leitura.piramide_completa(esc.no_municipio())


@st.cache_data(show_spinner=False)
def _composicao(ano: int, nivel: str, bairro: str | None, variavel: str) -> pd.DataFrame:
    """Composição sempre pelo microdado, nos dois níveis.

    Não é indiferença à divergência de base: é o contrário. Ler bairro do
    microdado e cidade do agregado faria os dois **discordarem entre si** ao
    navegar, com o usuário vendo a proporção mudar por trocar de recorte.
    Uma fonte só para este painel mantém a leitura coerente; a diferença
    contra os KPIs está registrada em `docs/paridade-com-o-painel-r.md` §2.
    """
    return microdado.composicao(_escopo(ano, nivel, bairro), variavel)


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

if "nav" not in st.session_state:
    st.session_state.nav = Navegacao(ano=config.ANO_MAX_RECIFE)
nav: Navegacao = st.session_state.nav


def _ao_mudar_metrica() -> None:
    """Aplica a métrica **antes** do rerun, não durante.

    O seletor fica abaixo dos cards de KPI. Lendo o valor no ponto em que o
    widget é criado, os cards — já desenhados — realçavam a métrica antiga,
    e só o rerun seguinte (um segundo clique em qualquer coisa) os punha em
    dia. O callback roda antes do script, então todo mundo vê o valor novo
    na mesma passada. Desmarcar o botão (o `segmented_control` permite)
    devolve a métrica que estava.
    """
    escolhida = st.session_state.get("metrica_sel")
    if escolhida:
        nav.metrica = escolhida
    else:
        st.session_state["metrica_sel"] = nav.metrica


if st.session_state.get("metrica_sel") != nav.metrica:
    # Primeira passada, ou a métrica mudou por outro caminho: o widget
    # segue `nav`, nunca o contrário.
    st.session_state["metrica_sel"] = nav.metrica

st.markdown(ui.css_base(), unsafe_allow_html=True)
st.markdown(ui.css_layout(), unsafe_allow_html=True)
# O cromo institucional de Recife entra como variável de página: o CSS das
# pílulas o consome sem que `componentes.py` precise conhecer a doença.
st.markdown(
    f"<style>:root{{--intro-accent:{pack.CORES['primary']};}}</style>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cabeçalho e KPIs
# ---------------------------------------------------------------------------

st.markdown(
    ui.faixa_intro(
        f"Painel de Monitoramento da {pack.TITULO_CURTO} de Recife",
        escopo=nav.trilha(),
        cor=pack.CORES["primary"],
    ),
    unsafe_allow_html=True,
)

# Procedência, sob o cabeçalho: a imagem roda com os dados dentro, e esta é
# a única pista na tela de quão velhos eles estão.
if datas := _procedencia():
    st.markdown(
        ui.procedencia(
            *datas,
            ajuda="Data do último registro no SINAN incluído nesta versão e "
                  "data em que a extração foi processada.",
        ),
        unsafe_allow_html=True,
    )

with resiliencia.painel("Indicadores"):
    atual = _kpis(nav.ano, nav.nivel, nav.bairro)
    anterior = _kpis(nav.ano - 1, nav.nivel, nav.bairro) if nav.ano > min(_anos()) else None

    faixa = st.container(key="faixa-kpis")
    for inicio in range(0, len(pack.LAYOUT_KPI), POR_LINHA):
        linha = pack.LAYOUT_KPI[inicio : inicio + POR_LINHA]
        for coluna, metrica in zip(faixa.columns(len(linha)), linha, strict=True):
            valor = getattr(atual, metrica, None)
            antes = getattr(anterior, metrica, None) if anterior else None
            taxa = metrica in pack.TAXAS
            # Subtítulo no formato do painel de origem: o recorte e o ano,
            # mais o denominador quando a métrica é proporção. Dizer de que
            # lugar e de que ano o número fala é o que impede a leitura errada
            # depois de navegar para um bairro.
            sub = f"{nav.nome_bairro or nav.bairro or 'Recife'} • {nav.ano}"
            if metrica == "incid" and getattr(atual, "casos", None):
                sub += f" • {ui.formatar_inteiro(atual.casos)} casos"
            if fracao := pack.FRACAO_KPI.get(metrica):
                num, den = (getattr(atual, campo, None) for campo in fracao)
                if num is not None and den:
                    sub += f" • {ui.formatar_inteiro(num)} de {ui.formatar_inteiro(den)}"
            with coluna:
                st.markdown(
                    ui.kpi_card(
                        pack.rotulo_curto(metrica),
                        ui.formatar_decimal(valor) if taxa else ui.formatar_inteiro(valor),
                        cor=pack.cor(metrica),
                        subtitulo=sub,
                        # O card espelha a métrica ativa do mapa, como nos
                        # painéis irmãos — é leitura, não controle.
                        selecionado=metrica == nav.metrica,
                        badge_delta=ui.delta(
                            valor, antes,
                            taxa=taxa,
                            bom_se_cai=metrica in pack.BOM_SE_CAI,
                        ),
                        # O nome completo entra no tooltip junto com a
                        # descrição: o card mostra o curto, e quem quiser a
                        # definição passa o mouse. Nada se perde no encurtamento.
                        ajuda=" — ".join(
                            parte for parte in
                            (pack.rotulo(metrica), pack.descricao(metrica))
                            if parte
                        ),
                        icone=pack.icone(metrica),
                    ),
                    unsafe_allow_html=True,
                )
    # A mesma nota do tooltip, agora sob os cards: quem abriu o Bairro do
    # Recife vê 2.527 por 100 mil e precisa da explicação na mesma tela.
    if nav.nivel == "BAIRRO" and (nota := valores.nota_populacao(getattr(atual, "pop", None))):
        st.caption(f"ⓘ {nota}")


# ---------------------------------------------------------------------------
# Linha 1: mapa à esquerda, abas à direita
# ---------------------------------------------------------------------------

# Os controles do mapa numa faixa própria, **acima** das duas colunas.
#
# Estavam empilhados dentro da coluna esquerda e comiam cerca de um quinto da
# página: quatro linhas de controle antes de o mapa começar. O efeito colateral
# era o desalinhamento — o mapa nascia bem abaixo do canal endêmico, e as duas
# metades da tela não se liam como uma linha só.
#
# Numa faixa de largura inteira cabem os quatro lado a lado, e as duas colunas
# passam a começar na mesma altura.
#
# A ordem é a de uso, não a de implementação: **métrica** primeiro, porque é o
# que muda o que o mapa mostra; **cores**, que muda como mostra; e só então
# **ano** e **recorte**, que são o recorte do dado. Foi a ordem pedida.
#
# As larguras seguem o conteúdo: métrica tem quatro botões de rótulo longo,
# cores três, recorte dois, e o ano é um seletor estreito.
with resiliencia.painel("Controles"), st.container(
    border=True, key="cartao-controles"
):
    # `top` e não `bottom`: alinhado pelo rodapé, os widgets ficam retos e são
    # os **rótulos** que flutuam em quatro alturas — e o rótulo aqui é uma
    # pílula colorida, que desalinhada chama mais atenção que o controle.
    col_metrica, col_cores, col_ano, col_recorte = st.columns(
        [4, 3, 1.3, 2.4], vertical_alignment="top"
    )

    with col_metrica:
        st.segmented_control(
            "Métrica",
            pack.METRICAS_MAPA,
            format_func=pack.rotulo_curto,
            key="metrica_sel",
            on_change=_ao_mudar_metrica,
        )

    with col_cores:
        classificacao = st.segmented_control(
            "Cores",
            CLASSIFICACOES,
            format_func=lambda c: ROTULO_CLASSIFICACAO[c],
            default=nav.classificacao,
            help=AJUDA_CLASSIFICACAO,
        )
        if classificacao and classificacao != nav.classificacao:
            nav.definir_classificacao(classificacao)
            st.rerun()

    with col_ano:
        escolhido = st.selectbox(
            "Ano", _anos(), index=_anos().index(nav.ano), key="ano",
        )
        if escolhido != nav.ano:
            nav.ano = escolhido
            st.rerun()

    with col_recorte:
        # **Sem `key`.** Controle que o código também move não pode ser dono do
        # valor: o clique no mapa muda o estado, o widget restauraria o
        # anterior, e a navegação entra em laço. Foi o defeito que ficou dois
        # dias no ar no painel nacional.
        recorte = st.segmented_control(
            "Recorte",
            RECORTES,
            format_func=lambda r: ROTULO_RECORTE[r],
            default=nav.recorte,
            help="Pintar cada bairro, ou agregar nos oito Distritos Sanitários.",
        )
        if recorte and recorte != nav.recorte:
            nav.definir_recorte(recorte)
            st.rerun()


esquerda, direita = st.columns([5, 6], gap="medium")

with esquerda, resiliencia.painel("Mapa"):
    serie_mapa = _valores_mapa(nav.ano, nav.metrica, nav.recorte)
    camada = geo.distritos() if nav.recorte == "DISTRITO" else geo.bairros()
    chave = "ds" if nav.recorte == "DISTRITO" else "bairro_key"

    with st.container(border=True, key="cartao-mapa"):
        st.markdown(
            ui.titulo_painel(f"Mapa — {pack.rotulo(nav.metrica)}, {nav.ano}"),
            unsafe_allow_html=True,
        )
        if serie_mapa.dropna().empty:
            st.markdown(
                ui.painel_vazio("Mapa", "Sem dado para este recorte.", mapa=True),
                unsafe_allow_html=True,
            )
        else:
            desenho, escala = mapa.deck(
                camada,
                serie_mapa,
                chave=chave,
                rampa=pack.rampa_mapa(nav.metrica),
                rotulo_metrica=pack.rotulo(nav.metrica),
                coluna_nome="ds_nome" if nav.recorte == "DISTRITO" else "bairro_nome",
                decimais=1 if nav.metrica in pack.TAXAS else 0,
                altura=ALTURA_MAPA,
                destacado=nav.destacado,
                metodo=nav.classificacao,
                cortes_fixos=pack.cortes_fixos(nav.metrica),
                nomes_fixos=pack.nomes_fixos(nav.metrica),
                casas_regua=pack.CASAS_REGUA,
                quantis=QUANTIS,
                notas=_notas_mapa(nav.ano, nav.metrica, nav.recorte),
            )
            # Componente próprio, com `key` **estável**: é o que mantém o deck
            # vivo entre reruns e faz a câmera voar de um recorte ao outro em
            # vez de trocar de slide. O clique volta com um nonce; o último
            # tratado fica em `session_state` para o mesmo evento não navegar
            # duas vezes. Ver docs/mapa-clique.md, "Transição".
            evento = mapa_componente.desenhar(
                desenho, altura=ALTURA_MAPA, key="mapa",
                titulo=f"Mapa do Recife: {pack.rotulo(nav.metrica)}",
                # sem teto de altura: o do core é pra território largo, o Recife é alto
                proporcao_maxima=None,
            )
            # N de cada faixa na própria legenda; nome só na régua fixa
            st.markdown(
                mapa.legenda(
                    escala, pack.rotulo(nav.metrica),
                    contagem=mapa.classificar(serie_mapa, escala).value_counts(),
                    nomes=pack.nomes_fixos(nav.metrica) if nav.classificacao == "FIXA" else None,
                ),
                unsafe_allow_html=True,
            )

            # O clique volta com um nonce: só o evento novo navega, e o mesmo
            # valor persistindo entre reruns não dispara `st.rerun()` de novo.
            alvo, nonce = mapa_componente.alvo_do_clique(
                evento, st.session_state.get("clique_mapa"), CAMPOS_CLIQUE
            )
            if nonce:
                st.session_state["clique_mapa"] = nonce
            ja_estamos_la = alvo and alvo in (nav.bairro, nav.ds)
            if alvo and not ja_estamos_la:
                if nav.recorte == "DISTRITO":
                    nav.entrar_distrito(alvo, nome=_rotulo_ds(alvo))
                else:
                    nomes = dict(
                        zip(geo.bairros()["bairro_key"], geo.bairros()["bairro_nome"])
                    )
                    nav.entrar_bairro(alvo, nome=nomes.get(alvo))
                st.rerun()

        if nav.pode_voltar:
            # `key` e não `<div>` em volta: HTML solto no markdown não envolve o
            # widget seguinte — o Streamlit o renderiza no próprio contêiner. Com
            # `key`, ele carimba `st-key-voltar_recife` no contêiner, e o CSS
            # alcança só este botão em vez de todos os da página.
            if st.button("Ver Recife inteiro", key="voltar_recife"):
                nav.reset()
                st.rerun()
        else:
            st.caption(f"Clique num {'distrito' if nav.recorte == 'DISTRITO' else 'bairro'} para ver os números dele.")


with direita, st.container(border=True, key="cartao-graficos"):
    no_bairro = nav.nivel == "BAIRRO"
    nome_lugar = nav.nome_bairro or "Recife"
    abas = [
        *(["Bairro"] if no_bairro else []),
        "Evolução temporal",
        "Desfechos",
        f"Ranking de {UNIDADE_RECORTE[nav.recorte]}",
        "Pirâmide etária",
    ]
    # bairro novo abre direto na aba Bairro; sem bairro ela some
    if no_bairro and st.session_state.get("_retrato_de") != nav.bairro:
        st.session_state["abas_graficos"] = "Bairro"
        st.session_state["_retrato_de"] = nav.bairro
    if not no_bairro:
        st.session_state.pop("_retrato_de", None)
        if st.session_state.get("abas_graficos") not in abas:
            st.session_state["abas_graficos"] = abas[0]
    paineis = dict(zip(abas, st.tabs(abas, key="abas_graficos", on_change="rerun"), strict=True))
    cidade = _kpis(nav.ano, "MUN", None)

    if no_bairro:
        with paineis["Bairro"], resiliencia.painel("Bairro"):
            k = _kpis(nav.ano, nav.nivel, nav.bairro)
            casos = int(k.casos or 0)
            razao, apoio = 1.0, None
            if k.incid is not None and cidade.incid:
                razao = k.incid / cidade.incid
                incid_txt = ui.formatar_decimal(k.incid, 1)
                recife_txt = ui.formatar_decimal(cidade.incid, 1)
                if razao >= 1.05:
                    apoio = (f"Incidência de {incid_txt} por 100 mil — "
                             f"{ui.formatar_decimal(razao, 1)}× a do Recife ({recife_txt}).")
                elif razao <= 0.95:
                    apoio = (f"Incidência de {incid_txt} por 100 mil — "
                             f"{ui.formatar_inteiro((1 - razao) * 100)}% abaixo da do Recife ({recife_txt}).")
                else:
                    apoio = f"Incidência de {incid_txt} por 100 mil, igual à do Recife."
            rotulo_casos = "caso novo" if casos == 1 else "casos novos"
            st.markdown(ui.frase(
                ui.formatar_inteiro(casos),
                f"{rotulo_casos} de tuberculose em {nome_lugar} em {nav.ano}.",
                apoio, pack.cor("incid") if razao >= 1.05 else AZUL_RECIFE,
            ), unsafe_allow_html=True)

            tabela_b = _tabela_bairros(nav.ano)
            nomes = _nomes_bairros()
            incid_b = tabela_b["incid"].dropna()
            pos = retrato.posicao(incid_b, nav.bairro)
            faixa_valores = incid_b.clip(upper=TETO_FAIXA_INCID).rename(index=nomes)
            st.markdown(ui.titulo_painel(
                f"{pos}ª maior incidência entre {len(incid_b)} bairros",
                ajuda=f"Cada ponto é um bairro. Acima de {ui.formatar_inteiro(TETO_FAIXA_INCID)} por "
                      "100 mil o ponto fica no fim da faixa (o Bairro do Recife, com poucos "
                      "moradores, passa de 2.000).",
            ), unsafe_allow_html=True)
            evento_faixa = grafico_componente.desenhar(
                grafico_componente.faixa(
                    faixa_valores, destaque=nomes.get(nav.bairro), rotulo=pack.rotulo("incid"),
                    cor=pack.cor("incid"), casas=1, maximo=TETO_FAIXA_INCID,
                    texto_destaque=f"{pos}º de {len(incid_b)}",
                    referencia=("Recife", float(cidade.incid)),
                ),
                altura=170, key="faixa",
            )
            clicado, nonce = grafico_componente.alvo_do_clique(
                evento_faixa, st.session_state.get("clique_faixa"))
            if nonce:
                st.session_state["clique_faixa"] = nonce
            chaves = {v: c for c, v in nomes.items()}
            if clicado and chaves.get(clicado) and chaves[clicado] != nav.bairro:
                nav.entrar_bairro(chaves[clicado], nome=clicado)
                st.rerun()
            st.caption("Clique em outro ponto para trocar de bairro.")

            st.markdown(ui.titulo_painel(
                "Os indicadores contra o Recife",
                ajuda="Cada eixo vai até o valor que 95% dos bairros não passam. Leitura de "
                      "formato: o valor exato está nos cards. Interrupção, não avaliados e "
                      "coinfecção são melhores quanto menores.",
            ), unsafe_allow_html=True)
            eixos, do_bairro, da_cidade = [], [], []
            for m in retrato.EIXOS_TEIA:
                topo = float(np.ceil(tabela_b[m].quantile(0.95) / 10) * 10) or 1.0
                eixos.append((pack.rotulo_curto(m), topo))
                do_bairro.append(min(getattr(k, m) or 0.0, topo))
                da_cidade.append(min(getattr(cidade, m) or 0.0, topo))
            grafico_componente.desenhar(
                grafico_componente.teia(eixos, [(nome_lugar, do_bairro, pack.cor("incid")),
                                                ("Recife", da_cidade, CINZA_REFERENCIA)]),
                altura=330, key="teia",
            )

    with paineis["Evolução temporal"], resiliencia.painel("Evolução temporal"):
        if no_bairro:
            juntas = _serie_bairro(nav.bairro)[["ano", "incid"]].merge(
                _serie_cidade()[["ano", "incid"]].rename(columns={"incid": "recife"}),
                on="ano", how="left",
            )
            st.markdown(ui.titulo_painel(
                f"Incidência por ano: {nome_lugar} e Recife",
                ajuda="Casos novos por 100 mil habitantes. Num bairro pequeno um ou dois casos "
                      "mexem muito a linha: olhe a direção, não o ano solto.",
            ), unsafe_allow_html=True)
            grafico_componente.desenhar(
                grafico_componente.linhas_anuais(
                    juntas, series={"incid": (nome_lugar, pack.cor("incid")),
                                    "recife": ("Recife", CINZA_REFERENCIA)},
                    rotulo=pack.rotulo("incid"), ano=nav.ano,
                ),
                altura=ALTURA_LINHA_1 - 90, key="linha-bairro",
            )
        else:
            horizonte = st.radio(
                "Horizonte", ["Meses do ano", "Todos os anos"],
                horizontal=True, label_visibility="collapsed",
            )
            if horizonte == "Meses do ano":
                canal_atual = _canal(nav.ano)
                rodape = ""
                if canal_atual.anos:
                    fora = canal.meses_fora_da_faixa(canal_atual)
                    acima = int((fora["posicao"] == "acima").sum())
                    rodape = AVISO_CANAL.format(
                        n=len(canal_atual.anos),
                        anos=", ".join(str(a) for a in canal_atual.anos),
                    )
                    if acima:
                        rodape += f" Em {nav.ano}, **{acima} de 12 meses** ficaram acima do topo da faixa."
                st.markdown(ui.titulo_painel("Canal endêmico", ajuda=rodape), unsafe_allow_html=True)
                grafico_componente.desenhar(
                    grafico_componente.canal_endemico(
                        canal_atual, rotulo=pack.rotulo("incid"), cor=pack.cor("incid"),
                    ),
                    altura=ALTURA_LINHA_1 - 90, key="canal",
                )
            else:
                st.markdown(ui.titulo_painel(
                    "Incidência por ano",
                    ajuda="Casos novos por 100 mil habitantes, na definição do Boletim. O Brasil "
                          "é o de 2023 no Boletim de 2024; a meta é a do Plano Nacional pelo Fim "
                          "da Tuberculose: menos de 10 por 100 mil até 2035.",
                ), unsafe_allow_html=True)
                grafico_componente.desenhar(
                    grafico_componente.linhas_anuais(
                        _serie_cidade(), series={"incid": ("Recife", pack.cor("incid"))},
                        rotulo=pack.rotulo("incid"), ano=nav.ano,
                        referencias=[("Brasil 2023", BRASIL_INCID), ("Meta 2035", META_INCID)],
                    ),
                    altura=ALTURA_LINHA_1 - 90, key="anual",
                )
            st.markdown(ui.titulo_painel(
                "Incidência mês a mês",
                ajuda="Cada quadrado é um mês, cada linha um ano. Quanto mais escuro, mais casos "
                      "novos por 100 mil. A queda de 2020 e a alta de 2022 aparecem de relance.",
            ), unsafe_allow_html=True)
            grafico_componente.desenhar(
                grafico_componente.mapa_calor(
                    _calor(nav.ano), rotulo=pack.rotulo("incid"),
                    rampa=list(pack.rampa_mapa("incid")), casas=1, ano_em_foco=nav.ano,
                ),
                altura=360, key="calor",
            )

    with paineis["Desfechos"], resiliencia.painel("Desfechos"):
        cores_desf = indicadores.DESFECHOS
        if no_bairro:
            k = _kpis(nav.ano, nav.nivel, nav.bairro)
            linhas = []
            for nome_linha, contagens in ((nome_lugar, k), ("Recife", cidade)):
                partes = indicadores.desfechos(contagens)
                base = partes.sum() or 1.0
                linhas.append({"nome": nome_linha, **(partes / base * 100).to_dict()})
            st.markdown(ui.titulo_painel(
                f"Como terminou o tratamento: {nome_lugar} e Recife",
                ajuda="Casos novos do ano por desfecho, em % da coorte (sem falência, mudança de "
                      "esquema e TB-DR). A meta de cura é 85%.",
            ), unsafe_allow_html=True)
            grafico_componente.desenhar(
                grafico_componente.barras_por_grupo(
                    pd.DataFrame(linhas),
                    partes={c: (c, cor) for c, cor in cores_desf.items()},
                    rotulo="% dos casos novos", casas=1, sufixo="%", largura_rotulo=130,
                ),
                altura=230, key="desfecho-bairro",
            )
            desf = indicadores.desfechos(k)
        else:
            desf = indicadores.desfechos(cidade)
        st.markdown(ui.titulo_painel(
            f"Caminho dos casos novos de {nav.ano}",
            ajuda="Para onde foram os casos novos do ano: cada fita é um desfecho, com o N. "
                  "Cura abaixo de 85% e interrupção acima de 5% estão fora das metas.",
        ), unsafe_allow_html=True)
        # a coorte é a base do Boletim: casos novos sem TB-DR, falência e mudança de esquema
        coorte = f"Coorte de {nav.ano}"
        fluxos = pd.DataFrame({"origem": coorte, "destino": desf.index, "valor": desf.to_numpy()})
        grafico_componente.desenhar(
            grafico_componente.sankey(
                fluxos, cores={coorte: pack.cor("casos"), **cores_desf},
                lados=(nome_lugar, "desfecho"), rotulo="casos", margens=(110, 170),
            ),
            altura=340, key="sankey",
        )
        if not no_bairro:
            st.markdown(ui.titulo_painel(
                "Cura e interrupção por ano",
                ajuda="Em % dos casos novos de cada ano. Metas do Ministério da Saúde: cura de "
                      "85% ou mais, interrupção de 5% ou menos. O último ano ainda tem "
                      "tratamento em curso.",
            ), unsafe_allow_html=True)
            grafico_componente.desenhar(
                grafico_componente.linhas_anuais(
                    _serie_desfechos(),
                    series={"cura_pct": ("Cura", pack.cor("cura_pct")),
                            "interrupcao_trat_pct": ("Interrupção", pack.cor("interrupcao_trat_pct"))},
                    rotulo="% dos casos novos", ano=nav.ano, maximo=100,
                    referencias=[("Meta de cura 85%", 85.0), ("Meta de interrupção 5%", 5.0)],
                ),
                altura=280, key="linha-desfechos",
            )

    with paineis[abas[-2]], resiliencia.painel("Ranking"):
        maximo = 30 if nav.recorte == "BAIRRO" else 8
        top_n = (
            st.slider("Quantos exibir", 5, maximo, min(10, maximo), step=5,
                      key=f"top_n_{nav.recorte}")
            if maximo > 5
            else maximo
        )
        tabela = _ranking(nav.ano, nav.metrica, nav.recorte, top_n)
        # a mesma escala do mapa, da série inteira: a barra sai da cor do polígono
        escala_mapa = mapa.escala(
            _valores_mapa(nav.ano, nav.metrica, nav.recorte),
            pack.rampa_mapa(nav.metrica),
            metodo=nav.classificacao,
            cortes_fixos=pack.cortes_fixos(nav.metrica),
            nomes_fixos=pack.nomes_fixos(nav.metrica),
            casas_regua=pack.CASAS_REGUA,
            decimais=1 if nav.metrica in pack.TAXAS else 0,
            quantis=QUANTIS,
        )
        # formato do boletim: valor na ponta e a linha de comparação
        referencia = {
            "incid": ("Recife", float(cidade.incid)) if cidade.incid else None,
            "cura_pct": ("Meta 85%", 85.0),
        }.get(nav.metrica)
        evento_rank = grafico_componente.desenhar(
            grafico_componente.ranking(
                tabela,
                rotulo=pack.rotulo(nav.metrica),
                cor=pack.cor(nav.metrica),
                escala=escala_mapa,
                selecionado=nav.destacado if nav.recorte != "DISTRITO" else None,
                largura_rotulo=grafico_componente.LARGURA_ROTULO_RANKING,
                casas=0 if nav.metrica == "casos" else 1,
                rotulos_valor=True,
                sufixo="%" if nav.metrica.endswith("_pct") else "",
                referencia=referencia,
            ),
            altura=max(
                ALTURA_LINHA_1 - 120,
                grafico_componente.ALTURA_MIN_RANKING,
                grafico_componente.ALTURA_BARRA_RANKING * len(tabela) + grafico_componente.ALTURA_EIXO_RANKING,
            ),
            key="ranking",
        )
        clicado, nonce_rank = grafico_componente.alvo_do_clique(
            evento_rank, st.session_state.get("clique_ranking")
        )
        if nonce_rank:
            st.session_state["clique_ranking"] = nonce_rank
        if clicado:
            # a barra acende o bairro no mapa sem mudar o escopo
            if nav.recorte == "DISTRITO":
                nav.entrar_distrito(clicado, nome=_rotulo_ds(clicado))
            else:
                nav.destacar(clicado, nome=_nomes_bairros().get(clicado))
            st.rerun()

    with paineis["Pirâmide etária"], resiliencia.painel("Pirâmide etária"):
        dados_pir = _piramide(nav.ano, nav.nivel, nav.bairro)
        por_100mil = False
        if "pop" in dados_pir.columns:
            por_100mil = st.toggle(
                "Por 100 mil habitantes",
                help="Desconta o tamanho de cada faixa etária na população.",
            )
        elif not dados_pir.empty:
            st.caption(
                "Sem taxa por faixa: a população por bairro e faixa etária não "
                "existe na origem."
            )
        # onze faixas pedem 30px cada ou as barras encavalam
        grafico_componente.desenhar(
            grafico_componente.piramide(dados_pir, rotulo="Casos", por_100mil=por_100mil),
            altura=max(ALTURA_LINHA_1 - 120, 280, 30 * dados_pir["faixa_etaria"].nunique() + 80),
            key="piramide",
        )


# ---------------------------------------------------------------------------
# Linha 2: composição
# ---------------------------------------------------------------------------

#: roscas por linha; com a legenda ao lado, três cabem numa linha
TOPICOS_POR_LINHA = 3

#: altura de cada rosca
ALTURA_TOPICO = 210

#: categorias que não contam para decidir se a variável é sim/não
_SEM_RESPOSTA = {"Ignorado", "Em branco", "Não informado"}

#: até quantas categorias vira rosca; acima disso, barras
MAXIMO_ROSCA = 4

AJUDA_TOPICOS = (
    "Distribuição percentual de cada variável do SINAN no recorte corrente. "
    "As dez que abrem são as do painel de origem; as outras dezesseis estão no "
    "seletor. Abaixo de cinco registros o percentual não é publicável e só a "
    "contagem aparece."
)


def _binaria(dados: pd.DataFrame) -> bool:
    """Sim/não, tirando o ignorado: vai para o pirulito dos agravos."""
    respostas = set(dados["categoria"]) - _SEM_RESPOSTA
    return bool(respostas) and respostas <= {"Sim", "Não"}


def _pct_sim(dados: pd.DataFrame) -> float | None:
    if dados.empty:
        return None
    total = float(dados["n"].sum())
    sim = float(dados.loc[dados["categoria"] == "Sim", "n"].sum())
    return sim / total * 100 if total else None


def _desenhar_binarias(variaveis: list[str], planas: dict[str, str]) -> None:
    """As sim/não num pirulito só: % de "Sim" de cada uma, o Recife ao lado no bairro."""
    linhas = []
    for v in variaveis:
        dados = _composicao(nav.ano, nav.nivel, nav.bairro, v)
        ignorado = float(dados.loc[dados["categoria"].isin(_SEM_RESPOSTA), "n"].sum())
        total = float(dados["n"].sum()) or 1.0
        sim = float(dados.loc[dados["categoria"] == "Sim", "n"].sum())
        nome = planas[v].removeprefix("Agravo: ").capitalize()
        dica = (f"<b>{nome}</b><br/>Sim: <b>{ui.formatar_inteiro(sim)}</b> de "
                f"{ui.formatar_inteiro(total)} ({ui.formatar_decimal(sim / total * 100, 1)}%)"
                f"<br/>Ignorado: {ui.formatar_decimal(ignorado / total * 100, 1)}%")
        linha = {"nome": nome, "valor": _pct_sim(dados), "tooltip": dica}
        if nav.nivel == "BAIRRO":
            linha["ref"] = _pct_sim(_composicao(nav.ano, "MUN", None, v))
        linhas.append(linha)
    tabela = pd.DataFrame(linhas).sort_values("valor", ascending=False)
    st.markdown(ui.titulo_painel(
        "Agravos e condições associadas",
        ajuda="% das notificações com resposta \"Sim\" em cada variável sim/não da ficha. "
              "O ignorado conta no total (está no tooltip): quanto maior ele, mais o "
              "percentual subestima.",
    ), unsafe_allow_html=True)
    grafico_componente.desenhar(
        grafico_componente.pirulito(
            tabela, rotulo="% das notificações", cor=pack.cor("casos"),
            nome_valor=nav.nome_bairro or "Recife",
            referencia="Recife" if nav.nivel == "BAIRRO" else None,
            casas=1, largura_rotulo=230,
        ),
        altura=34 * len(tabela) + (90 if nav.nivel == "BAIRRO" else 70),
        key="topicos-binarias",
    )


def _desenhar_topico(variavel: str, rotulo: str, dados: pd.DataFrame, altura: int) -> None:
    """Rosca até quatro categorias; acima disso, barras com o valor na ponta."""
    st.markdown(ui.titulo_painel(rotulo), unsafe_allow_html=True)
    figura = (
        grafico_componente.rosca(dados, cor=pack.cor("casos"))
        if len(dados) <= MAXIMO_ROSCA
        else grafico_componente.composicao(
            dados, rotulo="", cor=pack.cor("casos"), largura_rotulo=150, rotulos_valor=True,
        )
    )
    grafico_componente.desenhar(figura, altura=altura, key=f"topico-{variavel}")
    if not dados.empty and dados["pct"].isna().all():
        st.caption(
            f"Base de {int(dados['total'].iloc[0])} registros — pequena demais "
            f"para percentual. Só a contagem aparece."
        )


with resiliencia.painel("Tópicos de interesse"), st.container(
    border=True, key="cartao-composicao"
):
    st.markdown(
        ui.titulo_painel("Tópicos de interesse", ajuda=AJUDA_TOPICOS),
        unsafe_allow_html=True,
    )
    planas = pack.variaveis_planas()
    escolhidas = st.multiselect(
        "Variáveis",
        sorted(planas, key=lambda v: planas[v]),
        default=list(pack.VARIAVEIS_DESTAQUE),
        format_func=lambda v: planas[v],
        label_visibility="collapsed",
        placeholder="Escolha as variáveis a exibir",
    )

    if not escolhidas:
        st.caption(
            "Nenhuma variável escolhida. Use o campo acima para trazer as que "
            "interessam — as dez do painel de origem são o padrão."
        )
    else:
        # cada variável no gráfico que serve a ela: sim/não juntas num pirulito,
        # até quatro categorias em rosca, mais que isso em barras
        dados_de = {v: _composicao(nav.ano, nav.nivel, nav.bairro, v) for v in escolhidas}
        binarias = [v for v in escolhidas if _binaria(dados_de[v])]
        outras = [v for v in escolhidas if v not in binarias]
        if binarias:
            _desenhar_binarias(binarias, planas)
        for inicio in range(0, len(outras), TOPICOS_POR_LINHA):
            linha = outras[inicio : inicio + TOPICOS_POR_LINHA]
            # a linha inteira com a altura do mais alto, para a grade não ficar em degraus
            altura = max(
                ALTURA_TOPICO if len(dados_de[v]) <= MAXIMO_ROSCA
                else grafico_componente.altura_composicao(len(dados_de[v]))
                for v in linha
            )
            colunas = st.columns(TOPICOS_POR_LINHA, gap="medium")
            for coluna, variavel in zip(colunas, linha, strict=False):
                with coluna:
                    _desenhar_topico(variavel, planas[variavel], dados_de[variavel], altura)
