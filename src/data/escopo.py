"""Recorte geográfico e temporal — o ``Escopo``.

Todo leitor e todo KPI recebe um ``Escopo``. Ele carrega o nível (BR, UF, MUN,
BAIRRO), a UF, o município e o bairro quando aplicáveis, a doença e o ano.

**BAIRRO é o nível deste painel, e nem todo dataset o tem.** Só ``incidence``
traz `nivel=BAIRRO`, e só o microdado tem a coluna por linha. Um leitor que
não sabe descer a bairro deve chamar `Escopo.no_municipio` e dizer na
docstring que agrega Recife inteiro — nunca filtrar por uma coluna que não
existe, porque o resultado disso é vazio silencioso, e não erro.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from . import config


@dataclass(frozen=True, slots=True)
class Escopo:
    """Recorte de análise.

    ``mun`` aceita o código IBGE com 6 ou 7 dígitos. Internamente tudo passa a
    usar o de **6**, que é a única chave presente em todos os datasets:
    ``incidence`` traz ``cod_mun6`` e ``cod_mun7``, mas os demais só têm
    ``geo_id``, de 6 dígitos. O 7º é dígito verificador e não é reconstruível
    por truncamento, então serve só para exibição.
    """

    doenca: str
    ano: int
    nivel: str = "BR"
    uf: str | None = None
    mun: str | None = None
    bairro: str | None = None

    def __post_init__(self) -> None:
        nivel = str(self.nivel or "BR").strip().upper()
        if nivel not in config.NIVEIS:
            raise ValueError(f"Nível inválido: {self.nivel!r}. Esperado {config.NIVEIS}.")
        object.__setattr__(self, "nivel", nivel)
        object.__setattr__(self, "doenca", config._canon(self.doenca))
        object.__setattr__(self, "ano", int(self.ano))

        if self.uf is not None:
            object.__setattr__(self, "uf", str(self.uf).strip().upper())
        if self.bairro is not None:
            object.__setattr__(self, "bairro", str(self.bairro).strip().upper())
        if self.mun is not None:
            object.__setattr__(self, "mun", mun6(self.mun))

        if nivel == "UF" and not self.uf:
            raise ValueError("Nível UF exige o parâmetro `uf`.")
        if nivel == "MUN" and not self.mun:
            raise ValueError("Nível MUN exige o parâmetro `mun`.")
        if nivel == "BAIRRO" and not self.bairro:
            raise ValueError("Nível BAIRRO exige o parâmetro `bairro`.")

    def filtro_geo(
        self, col_mun: str = "cod_mun6", col_bairro: str = "bairro_key"
    ) -> tuple[str, list]:
        """Cláusula WHERE do recorte geográfico, sem o nível nem a doença."""
        if self.nivel == "UF":
            return "uf = ?", [self.uf]
        if self.nivel == "MUN":
            return f"{col_mun} = ?", [self.mun]
        if self.nivel == "BAIRRO":
            return f"{col_bairro} = ?", [self.bairro]
        return "", []

    def no_municipio(self) -> "Escopo":
        """O mesmo recorte, um degrau acima: Recife inteiro.

        Para leitores cujo dataset não desce a bairro. Chamar isto é a forma
        **explícita** de agregar a cidade toda; o jeito implícito — filtrar por
        uma coluna que o dataset não tem — devolve vazio sem erro, que é a
        armadilha 3 do painel nacional.

        Em qualquer nível diferente de BAIRRO, devolve o próprio escopo.
        """
        if self.nivel != "BAIRRO":
            return self
        return Escopo(
            doenca=self.doenca,
            ano=self.ano,
            nivel="MUN",
            uf=self.uf or config.UF_RECIFE,
            mun=self.mun or config.MUN_RECIFE,
        )

    @property
    def ano_anterior(self) -> int:
        return self.ano - 1


def mun6(codigo) -> str:
    """Chave canônica de município: os 6 primeiros dígitos do código IBGE.

    Aceita 6 ou 7 dígitos e descarta o dígito verificador. É a única forma
    de município que existe em todos os datasets.
    """
    return "".join(ch for ch in str(codigo or "") if ch.isdigit())[:6]


def chave_bairro(nome: str) -> str:
    """Forma canônica do nome do bairro: sem acento, sem caixa, sem espaço duplo.

    O painel em R normaliza o mesmo jeito e ainda colapsa ``BAIRRO DO RECIFE``
    em ``RECIFE`` (`mod_charts.R:207`) — o CSV traz as duas grafias para o
    mesmo lugar. Reproduzir isso é obrigatório: sem o colapso, o bairro do
    Recife aparece duas vezes no ranking, com os casos divididos.
    """
    texto = unicodedata.normalize("NFKD", str(nome or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = " ".join(texto.upper().split())
    return "RECIFE" if texto == "BAIRRO DO RECIFE" else texto
