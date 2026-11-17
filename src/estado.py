"""Estado de navegação do painel.

Deliberadamente sem dependência do Streamlit: a máquina de estados é testada
sozinha, e a aplicação só guarda uma instância em ``st.session_state``.

**A hierarquia é mais rasa que a do painel nacional.** Lá o caminho era
``BR -> UF -> município``, com desvio por macrorregião e região de saúde. Aqui
o topo **é** o município — Recife — e o caminho de ida é

    Recife -> (Distrito Sanitário) -> bairro

O distrito é opcional: ele filtra quais bairros o mapa mostra, do mesmo jeito
que a macrorregião filtrava as regiões de saúde no nacional, e pode ser
pulado. O ``voltar`` desfaz esse caminho um passo por vez.

Não existe nível acima de Recife. O botão ``Ver Recife inteiro`` do painel de
origem é o ``reset`` daqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .data import config
from .data.escopo import Escopo, chave_bairro

#: Como o mapa subdivide Recife. ``BAIRRO`` é o padrão e a unidade do dado;
#: ``DISTRITO`` agrega os bairros pela coluna ``ds`` da malha.
RECORTES = ("BAIRRO", "DISTRITO")

#: Como o mapa reparte os valores em cores. Ver `mapa.CLASSIFICACOES` para o
#: que cada uma custa; o padrão é a fixa, a única que compara anos.
CLASSIFICACOES = ("FIXA", "NATURAL", "QUARTIL")


@dataclass
class Navegacao:
    """Recorte corrente. Mutável — a aplicação guarda uma instância viva."""

    doenca: str = config.TUBERCULOSE
    ano: int = config.ANO_MAX_RECIFE
    metrica: str = "incid"

    #: ``MUN`` é Recife inteiro; ``BAIRRO`` é um bairro aberto.
    nivel: str = "MUN"
    bairro: str | None = None
    detalhe: bool = False

    recorte: str = "BAIRRO"

    #: Classificação de cor do mapa. Não muda o dado, só como ele é repartido —
    #: por isso vive aqui e não no `Escopo`, que é recorte de dado.
    classificacao: str = "FIXA"

    #: Distrito Sanitário selecionado. Filtra os bairros do mapa e do ranking;
    #: **não** muda o escopo dos KPIs, que seguem falando de Recife.
    ds: str | None = None

    #: Rótulos correntes, só para exibição. As chaves são `bairro` e `ds`.
    nome_bairro: str | None = None
    nome_ds: str | None = None

    #: Bairro apontado no mapa sem entrar nele, vindo do clique na barra do
    #: ranking. É só localização: o escopo continua em Recife.
    #:
    #: Existe porque as duas perguntas são diferentes. "Onde fica esse bairro?"
    #: se responde olhando o mapa com ele aceso; "como está esse bairro?" se
    #: responde entrando nele, o que o clique no próprio mapa já faz.
    destacado: str | None = None
    nome_destacado: str | None = None

    _historico: list[str] = field(default_factory=list, repr=False)

    # -- consultas ----------------------------------------------------------

    @property
    def escopo(self) -> Escopo:
        """Recorte no formato que a camada de dados consome.

        ``uf`` e ``mun`` vão sempre preenchidos, mesmo no nível BAIRRO: os
        leitores que não descem a bairro chamam `Escopo.no_municipio` e
        precisam encontrar Recife lá.
        """
        return Escopo(
            doenca=self.doenca,
            ano=self.ano,
            nivel=self.nivel,
            uf=config.UF_RECIFE,
            mun=config.MUN_RECIFE,
            bairro=self.bairro,
        )

    @property
    def escopo_listagem(self) -> Escopo:
        """Escopo do que o mapa e o ranking **listam**, que é sempre Recife.

        Substitui o `nivel_agregado` do painel nacional. Lá a função existia
        porque a lista mudava com a profundidade — no Brasil listavam-se UFs,
        dentro de uma UF os municípios dela. Aqui a lista nunca muda: dentro de
        um bairro o mapa continua mostrando os bairros de Recife, para o
        usuário ver onde ele se situa.

        Montar um escopo de nível BAIRRO para listar estouraria pelo mesmo
        motivo que estourava lá — foi assim que o ranking derrubou a página no
        painel nacional.
        """
        return self.escopo.no_municipio()

    @property
    def pode_voltar(self) -> bool:
        return self.nivel == "BAIRRO" or self.detalhe or self.ds is not None

    # -- ida ----------------------------------------------------------------

    def entrar_distrito(self, ds: str, nome: str | None = None) -> None:
        """Clicar num Distrito Sanitário filtra os bairros dentro dele."""
        self.ds = str(ds).strip()
        self.nome_ds = nome
        self.recorte = "BAIRRO"

    def entrar_bairro(self, bairro: str, nome: str | None = None) -> None:
        self.bairro = chave_bairro(bairro)
        self.nome_bairro = nome
        self.nivel = "BAIRRO"
        self.detalhe = False
        self.limpar_destaque()

    def destacar(self, bairro: str, nome: str | None = None) -> None:
        """Acende um bairro no mapa sem mudar o escopo.

        **Idempotente de propósito, e não um interruptor.** A seleção do
        gráfico persiste entre execuções: o clique não chega como evento, mas
        como estado que continua lá na próxima passada. Um `destacar` que
        alternasse acendia, reiniciava a página, apagava, reiniciava — laço
        infinito, e foi o que aconteceu na primeira versão do painel nacional.

        Quem apaga é `limpar_destaque`, pelo botão ao lado do mapa.
        """
        self.destacado = chave_bairro(bairro)
        self.nome_destacado = nome

    def limpar_destaque(self) -> None:
        self.destacado = None
        self.nome_destacado = None

    def abrir_detalhe(self) -> None:
        if self.nivel != "BAIRRO":
            raise ValueError("Detalhe só existe no nível de bairro.")
        self.detalhe = True

    def definir_classificacao(self, metodo: str) -> None:
        """Troca o método de classificação de cor do mapa."""
        valor = str(metodo or "FIXA").strip().upper()
        if valor not in CLASSIFICACOES:
            raise ValueError(
                f"Classificação inválida: {metodo!r}. Esperado {CLASSIFICACOES}."
            )
        self.classificacao = valor

    def definir_recorte(self, recorte: str) -> None:
        """Troca entre ver bairros e ver Distritos Sanitários."""
        valor = str(recorte or "BAIRRO").strip().upper()
        if valor not in RECORTES:
            raise ValueError(f"Recorte inválido: {recorte!r}. Esperado {RECORTES}.")
        self.recorte = valor
        # Voltar a ver distritos descarta o distrito selecionado: ele só faz
        # sentido enquanto se olha os bairros de dentro dele.
        if valor == "DISTRITO":
            self.ds = self.nome_ds = None

    # -- volta --------------------------------------------------------------

    def voltar(self) -> None:
        """Desfaz um passo do caminho de ida.

        A ordem das regras importa:

        1. bairro em detalhe -> fecha o detalhe
        2. bairro -> Recife, mantendo o distrito por onde se entrou
        3. Recife com distrito escolhido -> volta a ver os distritos
        4. Recife -> não faz nada, é o topo
        """
        if self.nivel == "BAIRRO" and self.detalhe:
            self.detalhe = False
            return

        if self.nivel == "BAIRRO":
            self.nivel = "MUN"
            self.bairro = None
            self.nome_bairro = None
            self.detalhe = False
            return

        if self.ds is not None:
            self.ds = self.nome_ds = None
            self.recorte = "DISTRITO"
            return

    def reset(self, manter_ano: bool = True) -> None:
        """Volta a Recife inteiro — o ``Ver Recife inteiro`` do painel de origem."""
        self.nivel = "MUN"
        self.bairro = None
        self.nome_bairro = None
        self.detalhe = False
        self.limpar_destaque()
        self.recorte = "BAIRRO"
        self.ds = self.nome_ds = None
        if not manter_ano:
            self.ano = config.ANO_MAX_RECIFE

    # -- exibição -----------------------------------------------------------

    def trilha(self) -> str:
        """Breadcrumb do recorte."""
        partes: list[str] = ["Recife"]

        if self.nivel == "BAIRRO":
            if self.ds:
                partes.append(self.nome_ds or f"DS {self.ds}")
            partes.append(f"Bairro: {self.nome_bairro or self.bairro or '—'}")
            if self.detalhe:
                partes.append("detalhe")
        elif self.recorte == "DISTRITO":
            partes.append("Distritos Sanitários")
        elif self.ds:
            partes.append(self.nome_ds or f"DS {self.ds}")
            partes.append("Bairros")

        partes.append(f"Ano: {self.ano}")
        return " • ".join(partes)
