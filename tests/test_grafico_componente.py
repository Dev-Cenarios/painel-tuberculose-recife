"""Os gráficos vêm do cenarios-core desde 14/out/2026, que os testa.

Fica aqui o que depende do painel: o canal endêmico montado com o `Canal`
de `src/data/canal.py`, no padrão de legenda do RecifeTB (cada ano nomeado).
"""

from __future__ import annotations


import pandas as pd

from cenarios_core import grafico_componente as gc


def test_canal_tem_faixa_muda_referencias_e_ano_por_cima() -> None:
    from src.data import canal as mod_canal

    faixa = pd.DataFrame({"mes": [1, 2], "mes_nome": ["janeiro", "fevereiro"], "q1": [1.0, 1.5], "q3": [2.0, 2.5]})
    ref = pd.DataFrame({"mes": [1, 2, 1, 2], "mes_nome": ["janeiro", "fevereiro"] * 2, "ano": [2022, 2022, 2023, 2023], "valor": [1.2, 1.8, 1.9, 2.2]})
    atual = pd.DataFrame({"mes": [1, 2], "mes_nome": ["janeiro", "fevereiro"], "valor": [2.4, 1.1]})
    c = mod_canal.Canal(faixa=faixa, referencia=ref, atual=atual, anos=(2022, 2023))
    opt = gc.canal_endemico(c, rotulo="Incidência", cor="#92400E")
    ids = [s["id"] for s in opt["series"]]
    assert ids == ["faixa-base", "faixa", "q1", "q3", "ref-2022", "ref-2023", "atual"]
    # A faixa é empilhada: base no Q1 e altura Q3 − Q1.
    assert opt["series"][0]["data"] == [1.0, 1.5]
    assert opt["series"][1]["data"] == [1.0, 1.0]
    # As duas séries mudas ficam fora da legenda e do tooltip.
    assert opt["legend"]["data"] == ["Ano selecionado", "2022", "2023", "Q1", "Q3"]
    assert set(opt["tooltip"]["ocultas"]) == {s["name"] for s in opt["series"][:2]}
    assert opt["series"][-1]["data"] == [2.4, 1.1]
    assert opt["xAxis"]["data"] == ["Jan", "Fev"]


