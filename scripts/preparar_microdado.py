"""Converte o microdado do SINAN de Recife em parquet particionado por ano.

O painel em R calcula composição, meses e pirâmide **por bairro** relendo o
CSV cru a cada interação (`mod_charts.R:307`). Os parquets agregados só têm
`nivel=BAIRRO` no `incidence`, então a granularidade fina não existe
pré-calculada — e é por isso que esta camada precisa existir aqui.

**Este script descarta identificadores, e essa é a razão principal de ele
existir separado da leitura.**

O CSV de origem é dado **nominal**: 147 colunas, entre elas nome do paciente,
nome da mãe, data de nascimento, cartão do SUS, prontuário, telefone, CEP,
logradouro com número e complemento, e latitude/longitude do endereço
geocodificado. São 29.948 pessoas com tuberculose, identificáveis e
localizáveis.

Nada disso é necessário para um painel que agrega por bairro e ano. Manter o
identificador "porque um dia pode ser útil" é como o dado sensível vaza: ele
sobrevive num arquivo intermediário, entra num backup, e acompanha o projeto
para sempre. Aqui a lista de colunas é uma **permissão explícita** — coluna que
não está em COLUNAS não atravessa. Acrescentar uma é uma decisão consciente,
com o nome dela escrita neste arquivo.

A deduplicação usa `NU_NOTIFIC`, que também **não** é gravado: ele serve para
contar uma notificação uma vez, e depois sai.

Uso::

    python -m scripts.preparar_microdado
    python -m scripts.preparar_microdado --origem <csv> --destino <dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from src.data import config
from src.data.escopo import chave_bairro

#: Colunas que atravessam para o parquet. Lista de permissão, não de bloqueio:
#: o que não estiver aqui é descartado, mesmo que exista na origem.
#:
#: Agrupadas pelo que sustentam no painel, para que remover um gráfico deixe
#: claro qual coluna pode sair junto.
COLUNAS = (
    # tempo
    "NU_ANO",
    "DT_NOTIFIC",
    "DT_DIAG",
    "DT_ENCERRA",
    # geografia — bairro e distrito sanitário, sem endereço
    "ID_BAIRRO",
    "NM_BAIRRO",
    "ID_DISTRIT",
    "CS_ZONA",
    # pirâmide etária
    "CS_SEXO",
    "NU_IDADE_N",
    # composição (as dez variáveis do painel de origem)
    "TRATAMENTO",
    "FORMA",
    "HIV",
    "CS_RACA",
    "AGRAVALCOO",
    "AGRAVDROGA",
    "AGRAVTABAC",
    "POP_RUA",
    "POP_SAUDE",
    "SITUA_ENCE",
    # clínicas e diagnóstico
    "AGRAVAIDS",
    "AGRAVDIABE",
    "AGRAVDOENC",
    "AGRAVOUTRA",
    "BACILOSC_E",
    "CULTURA_ES",
    "HISTOPATOL",
    "RAIOX_TORA",
    "TEST_MOLEC",
    # perfil e populações específicas
    "CS_ESCOL_N",
    "CS_GESTANT",
    "POP_LIBER",
    "POP_IMIG",
    "BENEF_GOV",
    # tratamento e desfecho
    "TRAT_SUPER",
    "TRATSUP_AT",
    "TRANSF",
)

#: Fora de propósito: `DOENCA_TRA` deixou de ser preenchida em Recife a partir
#: de 2015 — 9.654 registros, todos entre 2010 e 2014, e zero nos nove anos
#: seguintes. Carregar coluna que ninguém lê é o "dado morto que vai para o
#: servidor" que o guia do painel nacional lista como custo.

#: Variáveis de composição que o pack oferece e a conversão precisa carregar.
#:
#: **A lista acima não pode ficar aquém desta.** O pack herdou 26 variáveis do
#: painel nacional; a primeira versão desta conversão carregou 27 colunas ao
#: todo, e doze das variáveis oferecidas vinham vazias na tela — exatamente o
#: que o próprio pack proíbe ao dizer que oferecer opção que leva a painel
#: vazio é pior que não oferecer.
#:
#: `tests/test_microdado.py` confere as duas listas uma contra a outra, para o
#: desencontro não voltar em silêncio na próxima variável nova.

#: Descartadas de propósito. Não é a lista inteira do que fica de fora — é o
#: registro do que fica de fora **por ser identificador**, para que ninguém
#: reintroduza uma delas achando que foi esquecimento.
IDENTIFICADORES_DESCARTADOS = (
    "NM_PACIENT", "NM_MAE_PAC", "DT_NASC", "ID_CNS_SUS", "NU_PRONTUA",
    "NU_CEP", "NU_CEP2", "NU_TELEFON", "NU_DDD_TEL",
    "NM_LOGRADO", "NU_NUMERO", "NM_COMPLEM", "NM_REFEREN", "ID_LOGRADO",
    "address", "address2", "address3", "ADDRESS_CORE", "ENDERECO_CNEFE",
    "LATITUDE", "LONGITUDE", "COD_SETOR", "ID_GEO1", "ID_GEO2",
    "FONETICA_N", "SOUNDEX", "NU_NOTIFIC",
)


def converter(origem: Path, destino: Path) -> int:
    """Grava ``destino/ano=YYYY/part-0.parquet`` e devolve o total de linhas."""
    con = duckdb.connect()
    con.create_function("chave_bairro", chave_bairro, ["VARCHAR"], "VARCHAR")

    colunas = ", ".join(f'"{c}"' for c in COLUNAS)
    destino.mkdir(parents=True, exist_ok=True)

    # `row_number` sobre NU_NOTIFIC deduplica a notificação repetida sem
    # gravar o identificador: ele existe só dentro desta consulta.
    con.execute(
        f"""
        COPY (
            SELECT {colunas},
                   chave_bairro("NM_BAIRRO") AS bairro_key,
                   CAST("NU_ANO" AS INTEGER) AS ano
            FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY "NU_NOTIFIC" ORDER BY "DT_NOTIFIC"
                ) AS _ordem
                FROM read_csv_auto(?, ignore_errors=true, all_varchar=true)
            )
            WHERE _ordem = 1
              AND TRY_CAST("NU_ANO" AS INTEGER) IS NOT NULL
        ) TO '{destino.as_posix()}'
        (FORMAT PARQUET, PARTITION_BY (ano), OVERWRITE_OR_IGNORE, COMPRESSION ZSTD)
        """,
        [origem.as_posix()],
    )
    return con.execute(
        f"SELECT count(*) FROM read_parquet('{destino.as_posix()}/**/*.parquet')"
    ).fetchone()[0]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--origem", type=Path,
                   default=config.data_dir() / "origem" / "SINAN_RECIFE_TB.csv")
    p.add_argument("--destino", type=Path,
                   default=config.dashboard_dir() / "sinan_recife")
    a = p.parse_args()

    if not a.origem.is_file():
        raise SystemExit(f"Origem não encontrada: {a.origem}")

    linhas = converter(a.origem, a.destino)
    print(f"{linhas} linhas em {a.destino}")
    print(f"{len(COLUNAS)} colunas mantidas; "
          f"{len(IDENTIFICADORES_DESCARTADOS)} identificadores descartados.")


if __name__ == "__main__":
    main()
