"""O componente próprio do mapa: o que o Python promete ao JavaScript."""

from __future__ import annotations

import json




# ---------------------------------------------------------------------------
# Valor ausente: o `NaN` que deixava o mapa parado
# ---------------------------------------------------------------------------
#
# Achado no DFTB em 08/out/2026 (`a4a2101` de lá) e trazido para cá em 14/out.
# Aqui estava latente: o app não passa a geometria memoizada, e o geopandas já escrevia null.


def _json_estrito(texto: str) -> dict:
    """Parse que recusa `NaN`/`Infinity` como o `JSON.parse` do navegador."""

    def recusa(constante: str):
        raise ValueError(f"não é JSON válido: {constante}")

    return json.loads(texto, parse_constant=recusa)


def _tres_geografias():
    import geopandas as gpd
    from shapely.geometry import box

    return gpd.GeoDataFrame(
        {"chave": ["1", "2", "3"], "nome": ["A", "B", "C"]},
        geometry=[box(-36, -9, -35, -8), box(-35, -9, -34, -8), box(-34, -9, -33, -8)],
        crs="EPSG:4326",
    )


def _deck_com(camada, valores, **extra):
    import pandas as pd

    from cenarios_core import mapa

    return mapa.deck(
        camada, pd.Series(valores, index=["1", "2", "3"]), chave="chave",
        rampa=["#FFFFFF", "#DDDDDD", "#BBBBBB", "#999999", "#777777", "#555555", "#333333"],
        rotulo_metrica="x", coluna_nome="nome", **extra,
    )


def test_todas_sem_valor_tambem_nao_quebra() -> None:
    from cenarios_core import mapa

    camada = _tres_geografias()
    desenho, escala = _deck_com(
        camada, [float("nan")] * 3, geometrias=mapa.geometrias_geojson(camada)
    )
    _json_estrito(desenho.to_json())
    assert not escala.rotulos


