"""Indicadores dos casos novos do Recife, do SINAN nacional (`silver.tuberculose`).

É a base do Boletim Epidemiológico do MS, e por isso é a régua dos KPIs da
cidade. As definições são as do quadro de métodos do Boletim de TB 2024:

- casos novos: caso novo, não sabe e pós-óbito;
- testagem HIV: realizou o exame (positivo, negativo ou em andamento);
- coinfecção: HIV positivo sobre os casos novos;
- TRM: pulmonares que realizaram TRM-TB sobre os pulmonares;
- desfechos: sem falência, mudança de esquema e TB-DR no denominador
  (vão pro Site-TB); interrupção = abandono + abandono primário; não avaliados
  = transferência + sem encerramento.

Só contagens por ano (e casos novos por mês) saem do banco — a agregação é
no SQL. Exige VPN e o
`.env` com `CENARIOS_USER` e `CENARIOS_PASSWORD`.

Uso::

    python -m scripts.extrair_indicadores_sinan
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "data" / "parquet" / "dashboard" / "indicadores_sinan" / "recife.parquet"
#: casos novos por mês, pro canal endêmico e a epicurva
DESTINO_MENSAL = DESTINO.with_name("recife_mensal.parquet")

# Recife em 6 e 7 dígitos
RECIFE = ("261160", "2611606")

_CASOS_NOVOS = """
WITH t AS (
    SELECT * FROM (
        SELECT *, row_number() OVER (PARTITION BY sk_sinan_tube ORDER BY dt_notificacao) AS _o
        FROM silver.tuberculose
        WHERE municipio_residencia_id IN %(recife)s
    ) x
    WHERE _o = 1 AND tipo_entrada IN ('Caso novo', 'Nao sabe', 'Pos-obito')
)
"""

SQL = _CASOS_NOVOS + """
SELECT
    ano_notificacao::int AS ano,
    count(*) AS casos_novos,
    count(*) FILTER (WHERE resultado_hiv IN ('Positivo', 'Negativo', 'Em andamento')) AS hiv_testados,
    count(*) FILTER (WHERE resultado_hiv = 'Positivo') AS hiv_positivos,
    count(*) FILTER (WHERE forma_clinica IN ('Pulmonar', 'Pulmonar + Extrapulmonar')) AS pulmonares,
    count(*) FILTER (
        WHERE forma_clinica IN ('Pulmonar', 'Pulmonar + Extrapulmonar')
          AND teste_molecular_rapido IN ('Detectavel sensivel a Rifampicina',
              'Detectavel resistente a Rifampicina', 'Nao detectavel', 'Inconclusivo')
    ) AS trm_realizados,
    count(*) FILTER (
        WHERE situacao_encerramento IS NULL
           OR situacao_encerramento NOT IN ('Falencia', 'Mudanca de esquema', 'TB-DR')
    ) AS desfecho_base,
    count(*) FILTER (WHERE situacao_encerramento = 'Cura') AS curas,
    count(*) FILTER (WHERE situacao_encerramento IN ('Abandono', 'Abandono primario')) AS interrupcoes,
    count(*) FILTER (WHERE situacao_encerramento = 'Obito por TB') AS obitos_tb_sinan,
    count(*) FILTER (WHERE situacao_encerramento = 'Obito por outras causas') AS obitos_outras,
    count(*) FILTER (WHERE situacao_encerramento = 'Transferencia') AS transferencias,
    count(*) FILTER (
        WHERE situacao_encerramento IS NULL
           OR situacao_encerramento IN ('Transferencia', 'Nao informado')
    ) AS nao_avaliados
FROM t
GROUP BY 1
ORDER BY 1
"""

SQL_MENSAL = _CASOS_NOVOS + """
SELECT ano_notificacao::int AS ano, extract(month FROM dt_notificacao)::int AS mes,
       count(*) AS casos_novos
FROM t
GROUP BY 1, 2
ORDER BY 1, 2
"""


def _carregar_env() -> None:
    caminho = RAIZ / ".env"
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip())


def extrair(sql: str = SQL) -> pd.DataFrame:
    import psycopg2

    _carregar_env()
    if not (os.environ.get("CENARIOS_HOST") and os.environ.get("CENARIOS_USER") and os.environ.get("CENARIOS_PASSWORD")):
        raise RuntimeError("Credenciais ausentes: preencha CENARIOS_HOST, CENARIOS_USER e CENARIOS_PASSWORD no .env.")
    conexao = psycopg2.connect(
        host=os.environ["CENARIOS_HOST"],
        port=int(os.environ.get("CENARIOS_PORT", "5432")),
        dbname=os.environ.get("CENARIOS_DB", "cenarios_ai"),
        user=os.environ["CENARIOS_USER"],
        password=os.environ["CENARIOS_PASSWORD"],
        connect_timeout=10,
        options="-c default_transaction_read_only=on",
    )
    try:
        conexao.set_session(readonly=True, autocommit=True)
        with conexao.cursor() as cur:
            cur.execute(sql, {"recife": RECIFE})
            colunas = [c.name for c in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=colunas)
    finally:
        conexao.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destino", type=Path, default=DESTINO)
    a = p.parse_args()
    a.destino.parent.mkdir(parents=True, exist_ok=True)
    df = extrair()
    df.to_parquet(a.destino, index=False)
    print(f"{len(df)} anos em {a.destino}")
    print(df.tail(4).to_string(index=False))
    mensal = extrair(SQL_MENSAL)
    destino_mensal = a.destino.with_name(DESTINO_MENSAL.name)
    mensal.to_parquet(destino_mensal, index=False)
    print(f"{len(mensal)} meses em {destino_mensal}")


if __name__ == "__main__":
    main()
