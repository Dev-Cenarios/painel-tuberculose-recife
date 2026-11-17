"""Pacote de configuração da Tuberculose — Recife.

Segue o padrão de *disease pack* do projeto original: o core é único e cada
doença é só configuração. Cores, rótulos e ordem dos KPIs vêm daqui.

**A paleta é híbrida, por decisão de 28/ago/2026.** O cromo institucional é o
de Recife, para que quem usa o painel da equipe parceira reconheça o novo de
imediato. As cores de **métrica** seguem a família Cenários: incidência ocre,
óbito vermelho, cura verde — a decisão 6 do painel nacional, "cor é por
métrica, não por doença", que existe para o leitor não reaprender a legenda a
cada painel. As duas parecenças convivem porque atuam em camadas diferentes:
identidade no cromo, semântica no dado.
"""

from __future__ import annotations

from ..theme import cores

DOENCA = "TUBERCULOSE"
TITULO = "Monitoramento Tuberculose"

#: Só o nome da doença, para compor frase. `TITULO` já vem com "Monitoramento"
#: porque é o que o painel de origem usa na aba do navegador; encaixá-lo numa
#: frase daria "Painel de Monitoramento da Monitoramento Tuberculose".
TITULO_CURTO = "Tuberculose"

#: Cor por **métrica**, não por doença. As rampas do mapa saem daqui.
CORES = {
    # --- Cromo: identidade de Recife ---------------------------------------
    # Vindas do `disease_pack.R` da equipe parceira. Só vestem cabeçalho,
    # faixa e elementos de marca — nunca um dado.
    "primary": "#12346B",
    "secondary": "#1E73BE",
    "accent": "#4A8EFF",
    # --- Métricas: semântica da família ------------------------------------
    "casos": "#C1440A",
    "obitos": "#DC2626",
    "cura": "#16A34A",
    "cura_pct": "#16A34A",
    # Cinza médio e não quase-preto: `pop` em #111827 dava 2,4:1 de contraste
    # no tema escuro. Não é exibido como card hoje, mas a rampa do mapa usa a
    # cor da métrica.
    "pop": "#6B7280",
    "incid": "#92400E",
    # Herda o azul da família, e ele **colide com o cromo institucional**:
    # `#1D4ED8` e `#12346B` são ambos azuis, e no mapa a mortalidade fica
    # perto demais da cor de marca — o leitor pode ler identidade onde há
    # dado. Fica assim até a medição de contraste da semana 4, com o mapa de
    # pé; a correção sai de lá com número, não do olho. Se ceder, cede o
    # cromo: a semântica de métrica é compartilhada entre painéis, a
    # identidade não.
    "mortalidade": "#1D4ED8",
    "letalidade": "#6D28D9",
    "hiv_pos_pct": "#BE185D",
    "interrupcao_trat_pct": "#B45309",
    "testagem_hiv_pct": "#0E7490",
    "coinfeccao_pct": "#BE185D",
    "trm_pct": "#7C3AED",
    "nao_avaliados_pct": "#6B7280",
    "casos_0_14": "#B45309",
    "taxa_det_0_14": "#92400E",
}

ROTULOS = {
    "casos": "Casos novos",
    "obitos": "Óbitos",
    "cura": "Curas",
    "cura_pct": "Proporção de cura (%)",
    "pop": "População",
    "incid": "Incidência (por 100 mil hab.)",
    "mortalidade": "Taxa de mortalidade (por 100 mil hab.)",
    "letalidade": "Letalidade (%)",
    "casos_0_14": "Casos de 0 a 14 anos",
    "taxa_det_0_14": "Taxa de detecção 0–14 (por 100 mil hab.)",
    "hiv_pos_pct": "HIV positivo na testagem (%)",
    "interrupcao_trat_pct": "Interrupção de tratamento (%)",
    "testagem_hiv_pct": "Testagem para HIV entre os casos novos (%)",
    "coinfeccao_pct": "Coinfecção TB-HIV entre os casos novos (%)",
    "trm_pct": "TRM-TB nos casos novos pulmonares (%)",
    "nao_avaliados_pct": "Não avaliados: transferência e sem encerramento (%)",
}

#: Quais KPIs aparecem e em que ordem.
LAYOUT_KPI = (
    # carga
    "incid",
    "mortalidade",
    "cura_pct",
    "interrupcao_trat_pct",
    # cuidado
    "testagem_hiv_pct",
    "coinfeccao_pct",
    "trm_pct",
    "nao_avaliados_pct",
)

#: KPIs de proporção que mostram a fração de onde saem, sob o valor.
#:
#: "Curas: 49.114 ↓ 6.004 vs ano anterior" engana sem o denominador — os casos
#: também caíram. Com a fração à vista, o card diz a proporção e não esconde os
#: absolutos, que é o que o card antigo entregava.
#: Fração exibida sob o valor do card. Os dois campos precisam sair da mesma
#: fonte, ou a conta mostrada não dá a porcentagem mostrada — ver o comentário
#: de `cura_encerrada` em `kpis.py`.
FRACAO_KPI = {
    "cura_pct": ("curas", "desfecho_base"),
    "interrupcao_trat_pct": ("interrupcoes", "desfecho_base"),
    "nao_avaliados_pct": ("nao_avaliados", "desfecho_base"),
    "testagem_hiv_pct": ("hiv_testados", "casos"),
    "coinfeccao_pct": ("hiv_positivos", "casos"),
    "trm_pct": ("trm_realizados", "pulmonares"),
}

#: Métricas que o mapa e o ranking sabem desenhar.
#:
#: Ficam de fora `interrupcao_trat_pct` e `hiv_pos_pct`: as duas vêm do
#: `sinan_landing`, que o leitor consulta uma geografia por vez — serve para o
#: card, não para pintar 27 UFs de uma vez. Enquanto isso não mudar, elas não
#: entram no seletor, porque oferecer uma opção que leva a um painel vazio é
#: pior que não oferecer.
#: Métricas oferecidas no mapa.
#:
#: `cura_pct` e não `cura`: coroplético pinta **área**, e área não tem relação
#: com população. Com a contagem crua, São Paulo ficava no tom mais escuro por
#: ser São Paulo — o mapa de curas era, na prática, um mapa de população.
#: Proporção é comparável entre lugares de tamanhos diferentes, que é a razão
#: de existir de um coroplético. A contagem continua no card, com denominador.
# sem mortalidade: o SIM não tem bairro
METRICAS_MAPA = ("incid", "casos", "cura_pct")


#: Métricas em que uma queda é boa. `cura` fica de fora de propósito.
BOM_SE_CAI = frozenset(
    {"casos", "obitos", "incid", "mortalidade", "letalidade",
     "casos_0_14", "taxa_det_0_14", "hiv_pos_pct", "interrupcao_trat_pct",
     "coinfeccao_pct", "nao_avaliados_pct"}
)

#: Métricas exibidas com casas decimais.
TAXAS = frozenset(
    {"incid", "mortalidade", "letalidade", "taxa_det_0_14",
     "hiv_pos_pct", "interrupcao_trat_pct", "cura_pct",
     "testagem_hiv_pct", "coinfeccao_pct", "trm_pct", "nao_avaliados_pct"}
)

#: Paletas explícitas do mapa, herdadas do original. Quando existem, têm
#: precedência sobre a rampa gerada a partir da cor da métrica.
PALETA_MAPA = {
    "casos": (
        "#F5A878", "#EF8450", "#E56028", "#D04010",
        "#B82E08", "#921800", "#5E0C00",
    ),
    "incid": (
        "#E8B87A", "#D49040", "#BA7018", "#9A5210",
        "#7A3808", "#5C2404", "#3A1400",
    ),
}

def cor(metrica: str) -> str:
    return CORES.get(metrica, CORES["secondary"])


#: Cortes da **escala fixa** do mapa, por métrica.
#:
#: Só esta classificação torna dois anos comparáveis: as quebras naturais e os
#: quartis recalculam os limites a partir do próprio ano, então a régua muda
#: debaixo do mapa. Medido em Recife, a segunda quebra natural foi 93 em 2021,
#: 105 em 2022 e 101 em 2023 — um bairro escurece de um ano para o outro tendo
#: incidência menor.
#:
#: **Cada corte tem uma âncora, e ela está escrita aqui.** Escala fixa com
#: números escolhidos no olho é pior que quebra natural: fixa o arbítrio. O que
#: a âncora compra é a legenda poder ser lida em voz alta — "acima do dobro da
#: média da cidade" diz algo; "acima de 312" não.
#:
#: Âncoras de 2023 na definição do Boletim: Brasil ~40 por 100 mil (37,3 no
#: Boletim 2024, 39,7 em 2024); Recife 105,8, do SINAN nacional.
CORTES_FIXOS = {
    # Brasil (40) · 2× Brasil · Recife (106) · 2× Recife · 4× Recife
    "incid": (0, 40, 80, 106, 212, 424),
    # Contagem não tem âncora epidemiológica: são degraus redondos, escolhidos
    # para separar o bairro de dezenas do bairro de centenas.
    "casos": (0, 10, 25, 50, 100, 200),
    # **Aqui a âncora é oficial**: a meta de cura do Plano Nacional pelo Fim da
    # Tuberculose e da OMS é de 85%. Os degraus abaixo dela são os patamares
    # que o programa costuma reportar.
    "cura_pct": (0, 40, 60, 75, 85),
}

# nome de cada faixa na legenda, na ordem dos cortes; casos não tem âncora, fica sem
NOMES_FIXOS = {
    "incid": ("abaixo do Brasil", "até 2× Brasil", "abaixo do Recife",
              "até 2× Recife", "até 4× Recife", "mais de 4× Recife"),
    "cura_pct": ("crítica", "baixa", "intermediária", "perto da meta", "meta OMS"),
}

#: casas da régua na legenda: "40,0 a 79,9", a mesma precisão do número na tela
CASAS_REGUA = 1


def cortes_fixos(metrica: str) -> tuple[float, ...] | None:
    """Cortes declarados da métrica, ou ``None`` quando não há.

    Sem cortes, `mapa.escala` cai em quebras naturais em vez de estourar:
    mapa sem cor por falta de configuração é pior que mapa classificado de
    outro jeito.
    """
    return CORTES_FIXOS.get(metrica)


def nomes_fixos(metrica: str) -> tuple[str, ...] | None:
    return NOMES_FIXOS.get(metrica)


#: Rótulos curtos, para controles onde o nome inteiro não cabe.
#:
#: Só existem os que precisam: no seletor de métrica do mapa, "Taxa de
#: mortalidade (por 100 mil hab.)" empurrava os quatro botões para duas linhas.
#: A unidade não se perde — ela aparece na legenda do mapa e no título do
#: ranking, que é onde o número de fato é lido.
ROTULOS_CURTOS = {
    # Os seis da faixa de KPIs, para caberem em uma linha só.
    #
    # O painel de origem põe o rótulo inteiro e deixa o CSS cortar — vira
    # "Taxa de mort..." e "Interrupcao d...", que não identificam a métrica.
    # Aqui o nome é curto **de verdade**, e o completo continua acessível no
    # tooltip do card, junto com a descrição.
    #
    # A unidade fica no rótulo das taxas de propósito: um "156,06" sem "por
    # 100 mil" ao lado é um número sem grandeza.
    "incid": "Incidência /100 mil",
    "casos": "Casos novos",
    "mortalidade": "Mortalidade /100 mil",
    "interrupcao_trat_pct": "Interrupção",
    "hiv_pos_pct": "HIV positivo na testagem",
    "cura_pct": "Cura",
    "testagem_hiv_pct": "Testagem HIV",
    "coinfeccao_pct": "Coinfecção TB-HIV",
    "trm_pct": "TRM nos pulmonares",
    "nao_avaliados_pct": "Não avaliados",
}


#: Ícone de cada KPI, como no painel de origem — um glifo redondo à direita
#: do card. SVG inline (traço em `currentColor`) para herdar a cor da métrica
#: sem arquivo nem fonte de ícones; 24×24, viewBox do Lucide.
ICONES_KPI = {
    # velocímetro: taxa
    "incid": '<path d="M12 14l3.5-5"/><path d="M4 18a8 8 0 1 1 16 0"/>',
    # pulso: contagem de casos
    "casos": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    # linha em queda: mortalidade
    "mortalidade": '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    # círculo cortado: interrupção
    "interrupcao_trat_pct": '<circle cx="12" cy="12" r="9"/><path d="M5.5 5.5l13 13"/>',
    # porcentagem: positividade
    "hiv_pos_pct": '<path d="M19 5L5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    # check em círculo: cura
    "cura_pct": '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    # tubo de ensaio: testagem
    "testagem_hiv_pct": '<path d="M9 3h6"/><path d="M10 3v13a2 2 0 0 0 4 0V3"/><path d="M10 11h4"/>',
    # porcentagem: coinfecção
    "coinfeccao_pct": '<path d="M19 5L5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    # microscópio simplificado: TRM
    "trm_pct": '<path d="M6 18h8"/><path d="M3 22h18"/><path d="M14 22a7 7 0 1 0 0-14h-1"/><path d="M9 14h2"/><path d="M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2Z"/><path d="M12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3"/>',
    # interrogação: sem desfecho
    "nao_avaliados_pct": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6"/><path d="M12 17h.01"/>',
}


def icone(metrica: str) -> str:
    """Miolo do SVG do ícone da métrica, ou vazio quando não há."""
    return ICONES_KPI.get(metrica, "")


def rotulo(metrica: str) -> str:
    return ROTULOS.get(metrica, metrica)


def rotulo_curto(metrica: str) -> str:
    """Nome enxuto para botão; cai no completo quando não há versão curta."""
    return ROTULOS_CURTOS.get(metrica, rotulo(metrica))


def rampa_mapa(metrica: str) -> list[str]:
    """Rampa de 7 tons para o mapa.

    Usa a paleta explícita quando a métrica tem uma; senão deriva da cor base.
    """
    explicita = PALETA_MAPA.get(metrica)
    return list(explicita) if explicita else cores.rampa(cor(metrica))


#: Variáveis do SINAN oferecidas no painel de composição, agrupadas.
#:
#: O painel em R expõe nove; aqui são vinte e quatro, porque o dado já está
#: nos mesmos parquets e não custa nada a mais. Só entram as que dá para
#: rotular com segurança — errar o nome de uma variável de saúde é pior que
#: omiti-la.
#:
#: Ficam de fora, de propósito:
#: - ``NU_COMU_EX`` (contatos examinados) e ``EXTRAPUL_O``: numéricas, com 141
#:   e 1.587 valores distintos. O painel deles mostra a primeira; viraria uma
#:   parede de barras.
#: - ``BACILOSC_1``..``BACILOSC_6``: baciloscopia de acompanhamento mês a mês,
#:   redundante com ``BACILOSC_E``.
#: - ``MIGRADO_W``, ``NDUPLIC_N``, ``MUN_TRANSF``, ``AGRAVOUTDE``: controle do
#:   sistema, ou volume pequeno demais para significar algo.
#: - ``IN_VINCULA``: rótulos ambíguos ("vinculado"/"não vinculado") sem
#:   documentação que permita explicar ao usuário o que está sendo contado.
VARIAVEIS: dict[str, dict[str, str]] = {
    "Perfil": {
        "CS_RACA": "Raça/cor",
        "CS_ESCOL_N": "Escolaridade",
        "CS_GESTANT": "Gestante",
    },
    "Populações específicas": {
        "POP_RUA": "População em situação de rua",
        "POP_LIBER": "População privada de liberdade",
        "POP_IMIG": "População imigrante",
        "POP_SAUDE": "Profissional de saúde",
        "BENEF_GOV": "Beneficiário de programa do governo",
    },
    "Agravos associados": {
        "AGRAVAIDS": "Agravo: aids",
        "AGRAVALCOO": "Agravo: alcoolismo",
        "AGRAVDIABE": "Agravo: diabetes",
        "AGRAVDOENC": "Agravo: doença mental",
        # As duas que o painel de Recife expõe e o nacional não: existem no
        # microdado de Recife e entram na composição por bairro.
        "AGRAVDROGA": "Agravo: uso de drogas ilícitas",
        "AGRAVTABAC": "Agravo: tabagismo",
        "AGRAVOUTRA": "Agravo: outro",
    },
    "Clínica e diagnóstico": {
        "FORMA": "Forma clínica",
        "HIV": "Coinfecção HIV",
        "BACILOSC_E": "Baciloscopia de escarro",
        "CULTURA_ES": "Cultura de escarro",
        "RAIOX_TORA": "Raio-X de tórax",
        "HISTOPATOL": "Histopatologia",
    },
    "Tratamento e desfecho": {
        # No SINAN o campo é o tipo de *entrada* — as categorias são "Caso
        # novo", "Pós-óbito", "Não sabe". O painel em R chama de "Tipo de
        # tratamento", que descreve mal o que está ali.
        "TRATAMENTO": "Tipo de entrada",
        "TRATSUP_AT": "Tratamento diretamente observado",
        "SITUA_ENCE": "Situação de encerramento",
        # `DOENCA_TRA` saiu em 04/set/2026. Ela existe no SINAN e tem 9.654
        # registros no acumulado, o que a fez parecer viva — mas **todos** são
        # de 2010 a 2014. A partir de 2015 o campo deixou de ser preenchido em
        # Recife, e está zerado nos nove anos seguintes, 2023 inclusive.
        #
        # Oferecê-la é pior que omiti-la: quem seleciona vê um painel vazio e
        # atribui isso ao nosso painel, não à extração. Se a coleta voltar,
        # devolvê-la é esta linha mais o nome em `COLUNAS`.
        "TRANSF": "Transferência",
    },
}


#: As que abrem de saída: as dez do painel de origem e mais quatro sim/não que
#: entram de graça no pirulito dos agravos (privados de liberdade, diabetes,
#: doença mental e beneficiário). As 26 seguem no seletor.
#:
#: Ordem de leitura, não alfabética: desfecho e clínica primeiro, que é o que
#: a vigilância olha; perfil e populações específicas depois.
VARIAVEIS_DESTAQUE = (
    "SITUA_ENCE",
    "FORMA",
    "HIV",
    "TRATAMENTO",
    "CS_RACA",
    "AGRAVALCOO",
    "AGRAVDROGA",
    "AGRAVTABAC",
    "AGRAVDIABE",
    "AGRAVDOENC",
    "POP_RUA",
    "POP_LIBER",
    "POP_SAUDE",
    "BENEF_GOV",
)


def variaveis_planas() -> dict[str, str]:
    """``código -> rótulo``, na ordem dos grupos."""
    return {c: r for grupo in VARIAVEIS.values() for c, r in grupo.items()}


def grupo_da(codigo: str) -> str:
    """Grupo a que a variável pertence, para agrupar o seletor."""
    for grupo, itens in VARIAVEIS.items():
        if codigo in itens:
            return grupo
    return "Outras"


#: Explicação de cada KPI, mostrada ao passar o cursor.
#:
#: O que se explica aqui é sobretudo o **denominador**, que é onde mora a
#: ambiguidade: "Interrupção de tratamento (%)" não diz percentual sobre o
#: quê, e a resposta muda o número em quase quatro pontos. Os textos saem das
#: fórmulas em `src/data/indicadores.py` — mudou lá, muda aqui.
DESCRICOES = {
    "incid": (
        "Casos novos (caso novo, não sabe e pós-óbito) por 100 mil habitantes, "
        "do SINAN nacional — a base do Boletim Epidemiológico."
    ),
    "casos": "Casos novos notificados no ano: caso novo, não sabe e pós-óbito.",
    "obitos": "Óbitos com tuberculose (A15–A19) como causa básica, do SIM.",
    "pop": "População estimada do recorte.",
    "mortalidade": (
        "Óbitos por tuberculose (A15–A19, causa básica) por 100 mil habitantes, do SIM. "
        "O SIM não traz bairro, então no bairro fica vazio."
    ),
    "cura_pct": (
        "Curas sobre os casos novos do ano, sem falência, mudança de esquema e "
        "TB-DR (acompanhados no Site-TB), como no Boletim. A meta é 85%. "
        "Ano recente ainda tem caso em tratamento: a cura sobe com o tempo."
    ),
    "interrupcao_trat_pct": (
        "Abandono e abandono primário sobre o mesmo denominador da cura. "
        "A meta do programa é menos de 5%."
    ),
    "nao_avaliados_pct": (
        "Casos novos sem desfecho conhecido: encerrados como transferência ou "
        "sem encerramento. Quanto maior, menos se pode confiar na cura."
    ),
    "testagem_hiv_pct": (
        "Casos novos que fizeram o exame de HIV (positivo, negativo ou em "
        "andamento) sobre todos os casos novos. A meta é 100%."
    ),
    "coinfeccao_pct": "Casos novos com HIV positivo sobre todos os casos novos.",
    "trm_pct": (
        "Casos novos pulmonares que realizaram o teste rápido molecular "
        "(TRM-TB) sobre todos os casos novos pulmonares."
    ),
}


def descricao(metrica: str) -> str | None:
    return DESCRICOES.get(metrica)
