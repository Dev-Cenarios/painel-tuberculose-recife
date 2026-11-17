"""Localização dos dados e constantes de domínio.

Os parquets não são versionados. A raiz é resolvida nesta ordem:

1. variável de ambiente ``SINAN_DATA_DIR``
2. ``data/`` na raiz do projeto (padrão)
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Raiz dos dados. Ver docstring do módulo para a ordem de resolução."""
    env = os.environ.get("SINAN_DATA_DIR", "").strip()
    return Path(env).resolve() if env else PROJECT_ROOT / "data"


def dashboard_dir() -> Path:
    """Diretório com os datasets parquet particionados."""
    return data_dir() / "parquet" / "dashboard"


# ---------------------------------------------------------------------------
# Doenças
# ---------------------------------------------------------------------------
# O código da doença muda entre datasets — ver docs/dados.md,
# armadilha 2. Este é o mapa canônico: a aplicação usa sempre a chave
# canônica e traduz na fronteira da query.

TUBERCULOSE = "TUBERCULOSE"
HANSENIASE = "HANSENIASE"
DENGUE = "DENGUE"
ZIKA = "ZIKA"

#: Código usado nos datasets do SINAN agregado
#: (``incidence``, ``incidence_0_14``, ``_cache_ts``, ``piramides``, ``cases_new``).
_COD_AGREGADO = {
    TUBERCULOSE: "TUBERCULOSE",
    HANSENIASE: "HANSENIASE",
    DENGUE: "DENG",
    ZIKA: "ZIKA",
}

#: Código usado em ``sinan_landing`` e ``sinan_dict``. Hanseníase é ``HANS`` aqui.
_COD_LANDING = {
    TUBERCULOSE: "TUBERCULOSE",
    HANSENIASE: "HANS",
    DENGUE: "DENG",
    ZIKA: "ZIKA",
}

#: Código usado nos datasets do SIM (``cache_ts_sim_obitos``, ``obitos_sim_faixa``).
#: Dengue é ``DENGUE`` aqui, não ``DENG``.
_COD_SIM = {
    TUBERCULOSE: "TUBERCULOSE",
    HANSENIASE: "HANSENIASE",
    DENGUE: "DENGUE",
    ZIKA: "ZIKA",
}

def cod_agregado(doenca: str) -> str:
    """Código da doença nos datasets do SINAN agregado."""
    return _COD_AGREGADO[_canon(doenca)]


def cod_landing(doenca: str) -> str:
    """Código da doença em ``sinan_landing`` / ``sinan_dict``."""
    return _COD_LANDING[_canon(doenca)]


def cod_sim(doenca: str) -> str:
    """Código da doença nos datasets do SIM."""
    return _COD_SIM[_canon(doenca)]


#: Sinônimos aceitos na entrada, mapeados para a chave canônica.
_SINONIMOS = {
    "TB": TUBERCULOSE,
    "TUBERCULOSIS": TUBERCULOSE,
    "TUBERCULOSE": TUBERCULOSE,
    "HANS": HANSENIASE,
    "HANSENIASE": HANSENIASE,
    "DENG": DENGUE,
    "DENGUE": DENGUE,
    "ZIKA": ZIKA,
}


def _canon(doenca: str) -> str:
    chave = str(doenca or "").strip().upper()
    if chave not in _SINONIMOS:
        raise ValueError(
            f"Doença desconhecida: {doenca!r}. Esperado um de {sorted(set(_SINONIMOS))}."
        )
    return _SINONIMOS[chave]



#: Zika só tem registro a partir de 2016.


# ---------------------------------------------------------------------------
# Níveis geográficos
# ---------------------------------------------------------------------------
#: ``BAIRRO`` é o nível deste painel; ``MUN`` é Recife inteiro.
#:
#: ``BR`` e ``UF`` continuam aqui e **não são navegáveis**: a aplicação nunca
#: os abre. Existem porque vários leitores os consultam para compor
#: comparações, e porque o dado está particionado assim na origem. Tirá-los
#: quebraria a leitura sem tirar nada da tela.
#:
#: Só ``incidence`` e o microdado têm partição ou coluna de bairro. Quem
#: precisa de um leitor que não tem bairro usa `Escopo.no_municipio`, que
#: degrada explicitamente para Recife inteiro em vez de devolver vazio.
NIVEIS = ("BR", "UF", "MUN", "BAIRRO")

#: Recife. O painel inteiro vive dentro deste município.
MUN_RECIFE = "261160"
UF_RECIFE = "PE"

#: Último ano fechado do dado de Recife. O `sinan_landing` e o microdado param
#: em 2023; `incidence` vai até 2025, mas sem composição o ano não se sustenta.
ANO_MAX_RECIFE = 2023


# ---------------------------------------------------------------------------
# UF
# ---------------------------------------------------------------------------
#: Os dois primeiros dígitos do código IBGE do município identificam a UF.
#: Alguns datasets (``cases_new``, ``indicadores_tb_*``) só trazem o código do
#: município, então a UF precisa ser derivada daí.
UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}

CODIGO_POR_UF = {sigla: codigo for codigo, sigla in UF_POR_CODIGO.items()}

def codigo_uf(sigla: str) -> str:
    """Código IBGE de 2 dígitos a partir da sigla."""
    chave = str(sigla or "").strip().upper()
    if chave not in CODIGO_POR_UF:
        raise ValueError(f"UF desconhecida: {sigla!r}")
    return CODIGO_POR_UF[chave]
