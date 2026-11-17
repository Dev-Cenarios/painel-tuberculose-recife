# Imagem do painel de tuberculose de Recife.
#
# Feita para ser **entregue**, não hospedada por nós: outra equipe recebe o
# tarball e roda. Isso decide duas coisas que divergem do painel nacional:
#
# 1. **Os dados entram na imagem.** Lá ficam fora, por volume, porque somos
#    nós que trocamos a extração por SSH. Aqui, dado fora significaria dois
#    artefatos e uma montagem de volume a acertar em máquina que não vemos —
#    toda falha vira "não funciona" a distância. São 7 MB; extração nova é
#    imagem nova.
#
# 2. **O caminho da URL é configurável, e a raiz é o padrão.** Lá é fixo em
#    `/cenarios/sinan` porque o nginx é nosso. Aqui quem decide a URL é quem
#    hospeda, por `BASE_URL_PATH`.
#
# O que NÃO entra: o CSV nominal de origem. Ver `.dockerignore`, e o teste
# que abre a imagem pronta para conferir.

FROM python:3.13-slim

WORKDIR /app

# Dependências de sistema:
#   curl     → healthcheck
#   libgomp1 → DuckDB usa OpenMP para paralelizar
# geopandas não precisa de GDAL do sistema: pyogrio, shapely e pyproj trazem
# GDAL, GEOS e PROJ nas próprias wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Do lock, não do requirements.txt: aquele declara faixas e dois builds do
# mesmo commit poderiam subir versões diferentes. O lock tem as versões exatas
# com que a suíte passa.
COPY requirements.lock.txt .
# O lock aponta para o wheel do cenarios-core em `vendor/`: vem antes do
# `pip install`, e o build não precisa de rede (nem do GitHub) para o core.
COPY vendor/ vendor/
RUN pip install --no-cache-dir -r requirements.lock.txt

# Código.
COPY app.py .
COPY src/ src/
COPY .streamlit/ .streamlit/
COPY assets/ assets/

# Dados — só o que a aplicação lê. `data/origem/` está barrado no
# `.dockerignore` e não existe neste contexto de build.
#
# `data/support/` não entra: só o `recortes.py` o lia, e ele é herança do
# painel nacional que a navegação de Recife nunca alcança. Os dois CSVs de
# população por bairro que estão lá são insumo do pipeline, não da tela.
COPY data/parquet/ data/parquet/
COPY data/geo/     data/geo/

# Onde os dados estão e qual doença o pack resolve. Fixos na imagem porque
# não há por que quem hospeda mexer neles.
ENV SINAN_DATA_DIR=/app/data \
    SINAN_DOENCA=tuberculose \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Caminho sob o qual o painel é servido. Vazio serve na raiz:
#   http://host:8501/
# Com `BASE_URL_PATH=cenarios/tbrecife` serve em
#   http://host:8501/cenarios/tbrecife/
# Sem barra inicial nem final — o Streamlit acrescenta.
ENV BASE_URL_PATH=""

EXPOSE 8501

# O healthcheck precisa do mesmo subcaminho do painel: sob `baseUrlPath`, o
# Streamlit responde em `/<caminho>/_stcore/health` e a raiz dá 404. O painel
# de Recife anterior ficou meses com healthcheck vermelho por causa disso.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail "http://localhost:8501/${BASE_URL_PATH:+$BASE_URL_PATH/}_stcore/health" || exit 1

# `sh -c` e não a forma exec: é o shell que expande `BASE_URL_PATH`. A forma
# exec passaria a string literal `${BASE_URL_PATH}` ao Streamlit.
ENTRYPOINT ["sh", "-c", "exec streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.baseUrlPath=\"$BASE_URL_PATH\" \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=true \
    --browser.gatherUsageStats=false"]
