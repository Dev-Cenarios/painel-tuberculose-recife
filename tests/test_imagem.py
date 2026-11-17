"""Abre a imagem Docker construída e confere o que foi parar dentro dela.

O `.dockerignore` diz o que **não** deve entrar. Este teste confere o que
**entrou** — são coisas diferentes, e a diferença é a razão de o teste
existir: um `.dockerignore` mal escrito não dá erro, dá uma imagem com o CSV
nominal dentro, e ninguém descobre até alguém abrir o tarball.

Roda só quando a imagem existe. Sem Docker, ou sem a imagem construída, é
pulado — não é falha de código, é ausência de artefato.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

IMAGEM = "recifetb:latest"


def _docker() -> str | None:
    return shutil.which("docker")


def _imagem_existe() -> bool:
    docker = _docker()
    if not docker:
        return False
    saida = subprocess.run(
        [docker, "image", "inspect", IMAGEM],
        capture_output=True, text=True, timeout=30,
    )
    return saida.returncode == 0


precisa_da_imagem = pytest.mark.skipif(
    not _imagem_existe(),
    reason=f"imagem {IMAGEM} não construída — `docker build -t {IMAGEM} .`",
)


def _listar(caminho: str) -> list[str]:
    """Arquivos sob ``caminho`` dentro da imagem, sem subir um container que
    fique: `--rm` e um `find` só."""
    saida = subprocess.run(
        [_docker(), "run", "--rm", "--entrypoint", "find", IMAGEM,
         caminho, "-type", "f"],
        capture_output=True, text=True, timeout=120,
    )
    if saida.returncode != 0:
        return []
    return [linha for linha in saida.stdout.splitlines() if linha]


@precisa_da_imagem
def test_nenhum_csv_dentro_da_imagem() -> None:
    """**O teste que não pode ficar vermelho.**

    O CSV de origem tem nome, nome da mãe, nascimento, cartão do SUS, telefone,
    endereço e coordenadas do domicílio de 29.948 pacientes. A imagem vai
    circular por rede de terceiros.
    """
    arquivos = _listar("/app")
    csvs = [a for a in arquivos if a.lower().endswith(".csv")]
    assert not csvs, f"CSV dentro da imagem: {csvs}"


@precisa_da_imagem
def test_pasta_de_origem_nao_existe_na_imagem() -> None:
    arquivos = _listar("/app/data")
    origem = [a for a in arquivos if "/origem/" in a]
    assert not origem, f"data/origem/ dentro da imagem: {origem[:5]}"


@precisa_da_imagem
def test_os_dados_que_a_aplicacao_le_estao_la() -> None:
    """O contrário do anterior: dado demais é vazamento, dado de menos é
    painel em branco na máquina deles."""
    arquivos = _listar("/app/data")
    assert any("/parquet/dashboard/incidence/" in a for a in arquivos)
    assert any("/parquet/dashboard/sinan_recife/" in a for a in arquivos)
    assert any("/parquet/dashboard/sinan_dict/" in a for a in arquivos)
    assert any("/parquet/dashboard/indicadores_sinan/" in a for a in arquivos)
    assert any(a.endswith("/geo/bairros.parquet") for a in arquivos)
    assert any(a.endswith("/geo/distritos.parquet") for a in arquivos)


@precisa_da_imagem
def test_o_que_ninguem_le_fica_de_fora() -> None:
    """`popsvs/` são 54 MB de zips do IBGE que vieram na extração e nenhum
    leitor abre. Oito vezes o resto dos dados, viajando à toa."""
    arquivos = _listar("/app/data")
    assert not any("/popsvs/" in a for a in arquivos)
    assert not any("/dim_geo/" in a for a in arquivos)


@precisa_da_imagem
def test_o_microdado_da_imagem_nao_tem_identificador() -> None:
    """Confere o parquet **de dentro da imagem**, não o do disco local.

    O de fora já é testado em `test_microdado.py`. Mas o que viaja é o de
    dentro, e um build a partir de um `data/` errado — outra pasta, outra
    máquina — passaria no teste local e falharia aqui.
    """
    script = (
        "import duckdb, glob;"
        "f = glob.glob('/app/data/parquet/dashboard/sinan_recife/**/*.parquet', recursive=True)[0];"
        "print(','.join(c[0] for c in duckdb.connect().execute("
        "f\"describe select * from read_parquet('{f}')\").fetchall()))"
    )
    saida = subprocess.run(
        [_docker(), "run", "--rm", "--entrypoint", "python", IMAGEM, "-c", script],
        capture_output=True, text=True, timeout=120,
    )
    assert saida.returncode == 0, saida.stderr
    colunas = {c.upper() for c in saida.stdout.strip().split(",")}
    proibidas = {
        "NM_PACIENT", "NM_MAE_PAC", "DT_NASC", "ID_CNS_SUS", "NU_PRONTUA",
        "NU_CEP", "NU_TELEFON", "NM_LOGRADO", "LATITUDE", "LONGITUDE",
        "NU_NOTIFIC",
    }
    vazadas = sorted(colunas & proibidas)
    assert not vazadas, f"identificador no parquet da imagem: {vazadas}"


@precisa_da_imagem
def test_o_codigo_de_preparo_nao_viaja() -> None:
    """`scripts/` lê o CSV nominal. Não tem o que fazer numa imagem que não
    o tem — e é uma pista a menos sobre onde ele mora."""
    arquivos = _listar("/app")
    assert not any("/scripts/" in a for a in arquivos)
    assert not any("/tests/" in a for a in arquivos)
