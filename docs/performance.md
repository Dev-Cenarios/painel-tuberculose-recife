# Performance (velocidade)

## Ponto de partida — 28/ago/2026

Esta medição foi feita **antes de qualquer otimização**, e é justamente para isso que ela existe: ser o "antes".

No painel nacional, a gente só começou a medir na semana 6, quando já tinha coisa para otimizar. Resultado: metade dos números virou arqueologia, porque ninguém sabia mais como estava antes.

**Para medir de novo:**

```bash
python -m scripts.medir_performance
```

**Como foi medido:** cada operação rodou 5 vezes, a primeira foi descartada (é sempre mais lenta, porque abre os arquivos pela primeira vez) e ficou a mediana. Tudo para **Recife inteiro**, ano **2023**.

| Operação | Mediana (ms) | Pior vez (ms) |
|---|---:|---:|
| `incidencia` | 4,4 | 4,9 |
| `incidencia_0_14` | 3,2 | 4,3 |
| `obitos_sim` | 2,5 | 4,1 |
| `serie_mensal` | 4,6 | 5,8 |
| `casos_novos` | 1,8 | 2,0 |
| `piramide` | 3,7 | 6,9 |
| `obitos_por_faixa` | 8,4 | 10,8 |
| `variavel_sinan(HIV)` | 8,6 | 10,3 |
| **Soma das leituras** | **37,2** | |
| `kpis.calcular` (todos os números de destaque juntos) | 30,2 | 31,4 |

> ms = milissegundos. 1.000 ms = 1 segundo.

**Nada aqui é problema.** Todos os números de destaque saem em 30 ms, e o dado de Recife é pequeno perto do nacional: 94 bairros contra 5.571 municípios.

**O valor desta tabela é servir de "antes".** Quando o dado caso a caso e o mapa entrarem, dá para dizer **quanto cada um custou**, em vez de chutar.

## O que ainda não foi medido

- **O dado caso a caso** (`sinan_recife`, 29.607 linhas). É a parte que não existe no painel nacional, e a mais provável de pesar no tempo de resposta, porque ele **faz as contas na hora** em vez de ler um número pronto.
- **O mapa:** 94 contornos de bairro, contra até 5.571 municípios no nacional. O arquivo dos bairros tem só 0,07 MB, então a expectativa é que o mapa seja leve aqui.
- **A aplicação inteira, de ponta a ponta**, que só passou a existir a partir da semana 4.

## Diferenças em relação ao painel nacional

**O script mede só Recife.** No nacional ele media Brasil, estado e município, porque a navegação abria os três níveis. Aqui, o nível mais alto já é o próprio município.

**Duas armadilhas que apareceram ao trazer o script, anotadas para quem for repetir:**

1. **`piramides/nivel=BR` tem as pastas, mas nenhum arquivo dentro.** A pasta existe e a busca pelos arquivos não dá erro, mas a leitura falha por falta de dado, não por lentidão. Medir o nível Brasil nesta extração é medir o nada. (Conferido de novo em out/2026: continua sem nenhum arquivo.)
2. **O `obitos_sim_faixa` chama as colunas de `codmun` e `coduf`**, sem sublinhado. No painel nacional elas se chamam `cod_mun` e `cod_uf`. Cada extração dá nomes diferentes. Já corrigido em `leitura.obitos_por_faixa`.
