"""Linha de base de performance da camada de dados.

Mede o tempo de cada leitor sem o cache do Streamlit, para saber o custo real
por consulta. Serve de referência para a semana 6.

Uso::

    python -m scripts.medir_performance
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable

from src.data import kpis, leitura
from src.data.escopo import Escopo

REPETICOES = 5

#: Último ano fechado do dado de Recife.
ANO = 2023

ESCOPOS = {
    # Só Recife. O painel nacional media BR, UF e MUN porque navegava os três;
    # aqui o topo da navegação **é** o município, e medir BR mediria um escopo
    # que a aplicação nunca abre. Vale como aviso para quem copiar este script
    # de novo: o `piramides/nivel=BR` desta extração tem as 16 pastas de ano e
    # nenhum arquivo dentro, então medir BR falha por dado ausente, não por
    # lentidão.
    #
    # A linha de BAIRRO entra quando o nível existir no `Escopo` (semana 2).
    "MUN (Recife)": Escopo("TUBERCULOSE", ANO, "MUN", mun="261160"),
}

OPERACOES: dict[str, Callable[[Escopo], object]] = {
    "incidencia": leitura.incidencia,
    "incidencia_0_14": leitura.incidencia_0_14,
    "obitos_sim": leitura.obitos_sim,
    "serie_mensal": leitura.serie_mensal,
    "casos_novos": leitura.casos_novos,
    "piramide": leitura.piramide,
    "obitos_por_faixa": leitura.obitos_por_faixa,
    "variavel_sinan(HIV)": lambda e: leitura.variavel_sinan(e, "HIV"),
    "kpis.calcular (tudo)": kpis.calcular,
}


def cronometrar(fn: Callable[[Escopo], object], esc: Escopo) -> tuple[float, float]:
    """Devolve (mediana, pior) em milissegundos, descartando a primeira chamada."""
    fn(esc)  # aquece o cache de metadados do parquet
    tempos = []
    for _ in range(REPETICOES):
        inicio = time.perf_counter()
        fn(esc)
        tempos.append((time.perf_counter() - inicio) * 1000)
    return statistics.median(tempos), max(tempos)


def main() -> None:
    print(f"Mediana de {REPETICOES} execuções, em ms (primeira descartada)\n")
    largura = max(len(n) for n in OPERACOES)
    print(f"{'operação':<{largura}}" + "".join(f"{r:>22}" for r in ESCOPOS))

    totais = dict.fromkeys(ESCOPOS, 0.0)
    for nome, fn in OPERACOES.items():
        linha = f"{nome:<{largura}}"
        for rotulo, esc in ESCOPOS.items():
            mediana, pior = cronometrar(fn, esc)
            if nome != "kpis.calcular (tudo)":
                totais[rotulo] += mediana
            linha += f"{mediana:>14.1f}{pior:>8.1f}"
        print(linha)

    print(f"\n{'soma dos leitores':<{largura}}" + "".join(
        f"{totais[r]:>14.1f}{'':>8}" for r in ESCOPOS
    ))
    print("\n(cada célula: mediana / pior caso)")


if __name__ == "__main__":
    main()
