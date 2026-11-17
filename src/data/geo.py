"""Leitura da geometria pré-processada.

As camadas vêm de ``data/geo/``, geradas por ``scripts.preparar_geometria``.
Nunca leia o ``_geo_cache`` do pipeline direto na aplicação: ele é GeoJSON
gzipado e custa mais de dez vezes o tempo de um GeoParquet.

Regenerar após qualquer mudança nos dados de origem::

    python -m scripts.preparar_geometria
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import geopandas as gpd

from . import config


def geo_dir() -> Path:
    return config.data_dir() / "geo"


def _ler(caminho: Path) -> gpd.GeoDataFrame:
    if not caminho.exists():
        raise FileNotFoundError(
            f"Camada não encontrada: {caminho}\n"
            f"Gere com: python -m scripts.preparar_geometria"
        )
    return gpd.read_parquet(caminho)


#: palavras que ficam minúsculas no meio do nome
_MINUSCULAS = {"de", "da", "do", "das", "dos", "e"}

#: grafia da malha com acento errado ou faltando
_GRAFIA = {
    "Caxangà": "Caxangá",
    "Cidade Universitària": "Cidade Universitária",
    "Morro da Conceicão": "Morro da Conceição",
    "Brasilia Teimosa": "Brasília Teimosa",
    "Hipodromo": "Hipódromo",
    "Recife": "Bairro do Recife",
}


def nome_proprio(texto: str) -> str:
    """'ALTO JOSE DO PINHO' -> 'Alto Jose do Pinho'; a malha vem em caixa alta."""
    palavras = str(texto).lower().split()
    nome = " ".join(
        p if i and p in _MINUSCULAS else p[:1].upper() + p[1:]
        for i, p in enumerate(palavras)
    )
    return _GRAFIA.get(nome, nome)


@lru_cache(maxsize=1)
def bairros() -> gpd.GeoDataFrame:
    """Os 94 bairros de Recife. Colunas: ``bairro_key``, ``bairro_nome``,
    ``cod_bairro``, ``ds``.

    ``bairro_key`` é a chave canônica — sem acento, sem caixa — e é por ela que
    se cruza com o dado. **Nunca cruze por ``bairro_nome``:** a extração grafa
    "ALTO STA. TEREZINHA" onde a malha grafa "ALTO SANTA TEREZINHA", e o join
    por nome perde esse bairro sem erro nenhum.
    """
    camada = _ler(geo_dir() / "bairros.parquet")
    camada["bairro_nome"] = camada["bairro_nome"].map(nome_proprio)
    return camada


@lru_cache(maxsize=1)
def distritos() -> gpd.GeoDataFrame:
    """Os 8 Distritos Sanitários. Coluna ``ds``.

    Dissolvidos a partir dos bairros já simplificados, então a fronteira do
    distrito coincide com a dos bairros por construção — ver
    `scripts/preparar_geometria.py`.
    """
    return _ler(geo_dir() / "distritos.parquet")


@lru_cache(maxsize=1)
def recife() -> gpd.GeoDataFrame:
    """Contorno do município, para moldura e enquadramento inicial."""
    return _ler(geo_dir() / "recife.parquet")


# Houve aqui um `centroides()`, que lia
# `_geo_cache/municipios_centroids.parquet` e nunca foi chamado por nenhum
# caminho de produção — só pelo próprio teste. Saiu em 14/ago/2026, junto com o
# arquivo no pacote de publicação, pelo mesmo motivo que o dataset `obitos`
# saiu de `preparar_publicacao.DATASETS`: dado morto que ia para o servidor.
#
# Quem precisar de um ponto por polígono use `representative_point()` da própria
# geometria, como faz `mapa._camada_rotulos`. Além de dispensar o arquivo, ele
# funciona em qualquer nível — UF, macro, região de saúde — e garante um ponto
# **dentro** do polígono, coisa que o centroide não garante: em forma côncava
# ele cai fora, e o rótulo vai parar no vizinho.


# Havia aqui `limpar_cache()`, para descartar a geometria em memória depois de
# regerar as camadas. Nunca foi chamado — nem pela aplicação, nem pelos
# scripts. Regerar geometria exige reiniciar o serviço de qualquer forma, e o
# reinício limpa o cache sozinho.
