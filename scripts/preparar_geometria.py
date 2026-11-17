"""Pré-processa a geometria de Recife uma vez, em disco.

O dashboard em R simplificava a geometria **a cada redesenho do mapa**. Aqui
isso é feito uma vez e o resultado vai para GeoParquet, como no painel
nacional — o ganho de formato medido lá foi de 267 ms para 22 ms na leitura.

Três camadas saem daqui:

- ``bairros.parquet`` — os 94 bairros, que é a unidade do painel
- ``distritos.parquet`` — os 8 Distritos Sanitários
- ``recife.parquet`` — o contorno do município

**Os distritos são dissolvidos a partir dos bairros já simplificados**, e não
lidos do ``Distrito_per.shp``, que existe na origem. O motivo é o mesmo que
obriga a simplificação topológica: duas malhas simplificadas em separado não
coincidem na fronteira comum, e o mapa ganha fresta entre a borda do distrito
e a do bairro que deveria encostar nela. Dissolvendo, a divisa do distrito
**é** a divisa dos bairros, por construção.

A tolerância é relativa à largura do bounding box, como no painel nacional:
sem número mágico por camada.

Uso::

    python -m scripts.preparar_geometria
"""

from __future__ import annotations

import time
from pathlib import Path

import geopandas as gpd
import topojson as tp

from src.data import config
from src.data.escopo import chave_bairro

#: CRS métrico para medir área. SIRGAS 2000 / UTM 25S é o do próprio
#: shapefile de origem e cobre Recife inteiro sem distorção relevante.
CRS_AREA = "EPSG:31985"

#: CRS de saída. O deck.gl desenha em graus.
CRS_SAIDA = "EPSG:4326"

#: Divisor da tolerância. Recife inteiro tem ~20 km de largura; 1/2000 dá
#: cerca de 10 m, abaixo da largura de uma quadra — o bairro não muda de forma
#: perceptível e o arquivo encolhe uma ordem de grandeza.
DIVISOR = 2000


def simplificar(geo: gpd.GeoDataFrame, divisor: int) -> tuple[gpd.GeoDataFrame, float]:
    """Simplifica preservando as fronteiras compartilhadas.

    O ``simplify`` do shapely trata cada polígono isoladamente, então dois
    municípios vizinhos simplificam a divisa comum de formas diferentes e o
    mosaico se rompe. Medido no ES com a tolerância do R: 1,97% da área do
    estado virava fresta e 163 pares de polígonos passavam a se sobrepor — o
    coroplético ganha fiapos brancos e bordas dobradas. O dashboard em R tem
    esse defeito, porque usa ``st_simplify`` por feição.

    Aqui a simplificação é topológica: as arestas compartilhadas são
    simplificadas uma única vez. No mesmo ES, as sobreposições vão a zero e as
    frestas caem para 0,41%. Custa cerca de 1,5 s por UF, uma vez só.
    """
    xmin, _, xmax, _ = geo.total_bounds
    tolerancia = (xmax - xmin) / divisor
    if tolerancia <= 0:
        return geo, 0.0

    area_antes = geo.to_crs(CRS_AREA).area.sum()

    if len(geo) < 2:
        # Uma feição só (DF, contorno do país) não tem fronteira compartilhada
        # para romper — o simplify direto basta e evita o custo da topologia.
        saida = geo.copy()
        saida["geometry"] = saida.geometry.simplify(tolerancia, preserve_topology=True)
    else:
        topologia = tp.Topology(geo, prequantize=False, shared_coords=False)
        saida = topologia.toposimplify(tolerancia).to_gdf()
        saida = saida.set_crs(geo.crs, allow_override=True)
        # `to_gdf()` reordena as colunas; devolve na ordem de entrada.
        saida = saida[list(geo.columns)]

    # A simplificação topológica não garante validade; conserta o que quebrou.
    invalidas = ~saida.geometry.is_valid
    if invalidas.any():
        saida.loc[invalidas, "geometry"] = saida.loc[invalidas, "geometry"].buffer(0)

    area_depois = saida.to_crs(CRS_AREA).area.sum()
    erro = abs(area_depois - area_antes) / area_antes * 100 if area_antes else 0.0
    return saida, erro


def _tamanho(caminho: Path) -> float:
    return caminho.stat().st_size / 1e6


#: Algarismos romanos de 1 a 8, para o caso de a malha de distritos faltar.
_ROMANOS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")


def _rotulos_de_distrito(origem: Path) -> dict[str, str]:
    """Nome de exibição de cada Distrito Sanitário, por código.

    **Os oito não têm nome próprio.** São numerados, e a malha da prefeitura
    grafa "DS - I" a "DS - VIII" na coluna ``DS`` do ``Distrito_per.shp``. Ler
    de lá, e não gerar aqui, é o que garante que a tela use a grafia oficial —
    inclusive se um dia ela mudar.

    Sem o arquivo, cai no romano gerado: perder o mapa inteiro porque um
    rótulo faltou seria trocar dado por enfeite.
    """
    caminho = origem / "Distrito_per.shp"
    if caminho.is_file():
        tabela = gpd.read_file(caminho)
        if {"CRPAAACODI", "DS"} <= set(tabela.columns):
            return {
                str(cod).strip(): str(nome).strip()
                for cod, nome in zip(tabela["CRPAAACODI"], tabela["DS"], strict=True)
            }
    return {str(i + 1): f"DS - {r}" for i, r in enumerate(_ROMANOS)}


def _ler_bairros(origem: Path) -> gpd.GeoDataFrame:
    """Os 94 bairros, normalizados para as colunas que a aplicação usa.

    O arquivo se chama ``Distrito_Sanitário`` mas a camada é de **bairro** —
    94 feições com ``EBAIRRNOME``, o mesmo número que o ``incidence`` traz em
    ``nivel=BAIRRO``. O nome do arquivo engana; o conteúdo é que manda.

    ``CRPAAACODI`` é o código da RPA, que é o Distrito Sanitário. Ele vem
    **como atributo do bairro**, então agregar por distrito não exige cruzar
    geometria — é um ``group by``.

    O rótulo do distrito vem de `_rotulos_de_distrito`: os oito não têm nome
    próprio, são numerados em algarismo romano.
    """
    candidatos = sorted(origem.glob("*.shp"))
    for caminho in candidatos:
        geo = gpd.read_file(caminho)
        if "EBAIRRNOME" in geo.columns:
            break
    else:
        raise FileNotFoundError(
            f"Nenhum shapefile com EBAIRRNOME em {origem}. "
            f"Encontrados: {[c.name for c in candidatos]}"
        )

    geo = geo.to_crs(CRS_SAIDA)
    ds = geo["CRPAAACODI"].astype(str).str.strip()
    rotulos = _rotulos_de_distrito(origem)
    saida = gpd.GeoDataFrame(
        {
            "bairro_key": geo["EBAIRRNOME"].map(chave_bairro),
            "bairro_nome": geo["EBAIRRNOME"].astype(str).str.strip(),
            "cod_bairro": geo["CBAIRRCODI"].astype(str).str.strip(),
            "ds": ds,
            "ds_nome": ds.map(rotulos).fillna("DS " + ds),
        },
        geometry=geo.geometry,
        crs=CRS_SAIDA,
    )
    return saida


def main() -> None:
    origem = config.data_dir() / "origem" / "malha"
    destino = config.data_dir() / "geo"
    destino.mkdir(parents=True, exist_ok=True)

    inicio = time.perf_counter()
    bairros = _ler_bairros(origem)
    if bairros["bairro_key"].duplicated().any():
        repetidos = sorted(bairros.loc[bairros["bairro_key"].duplicated(), "bairro_key"])
        raise SystemExit(
            f"Chave de bairro repetida: {repetidos}. "
            f"Um join por bairro duplicaria linhas — conserte `chave_bairro`."
        )

    bairros, erro = simplificar(bairros, DIVISOR)
    caminho = destino / "bairros.parquet"
    bairros.to_parquet(caminho)
    print(f"bairros    {len(bairros):>3} feições  {_tamanho(caminho):.3f} MB  "
          f"erro de área {erro:.3f}%")

    distritos = bairros.dissolve(by="ds", as_index=False)[["ds", "ds_nome", "geometry"]]
    caminho = destino / "distritos.parquet"
    distritos.to_parquet(caminho)
    print(f"distritos  {len(distritos):>3} feições  {_tamanho(caminho):.3f} MB")

    contorno = bairros.dissolve()[["geometry"]]
    caminho = destino / "recife.parquet"
    contorno.to_parquet(caminho)
    print(f"recife     {len(contorno):>3} feição   {_tamanho(caminho):.3f} MB")

    print(f"em {time.perf_counter() - inicio:.1f}s")


if __name__ == "__main__":
    main()
