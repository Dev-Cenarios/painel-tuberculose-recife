# Divergências com o painel em R

Toda diferença numérica entre este painel e o de origem deve estar registrada
aqui, com justificativa. **O que não estiver listado e divergir é bug.**

`tests/paridade/test_referencia_r.py` compara a cada execução contra os valores lidos da tela
deles, congelados em `tests/paridade/referencia_r.json` em 28/ago/2026 — **antes** de qualquer
fórmula ser escrita, para que a comparação seja contra o que eles publicam e
não contra o que lembramos que publicavam.

**Estado em 17/set/2026:** o ranking de bairros bate exatamente, quinze de
quinze, e quatro dos seis KPIs saem no dígito. Seis divergências registradas:
**três fechadas** por medição direta (§1, §5 e o método dos quartis), **uma
decidida** por nós (§6, cinco anos no canal), **duas em aberto** com a equipe
parceira (§2 e §4) e **uma decisão pendente** do lado de cá (§3, denominador
do HIV). Nenhuma é defeito nosso.

> **Paridade mede concordância, não correção.** No painel nacional houve o caso
> em que os dois painéis exibiam o mesmo número errado, e a comparação entre
> eles não tinha como perceber; quem fechou foi o Boletim Epidemiológico do MS.
> Vale igual aqui: onde divergirmos, a fonte que decide é externa, e é por isso
> que `referencia_ms.json` vai existir ao lado de `referencia_r.json`.

---

## 0. Onde já batemos

| Item | Nosso | Deles | Observação |
|---|---:|---:|---|
| Ranking de bairros, top 15 | igual | igual | Quinze de quinze, diferença zero |
| Casos novos (Recife, 2023) | 2.485 | 2.485 | Fonte comum: `cases_new` |

O ranking bater exatamente é mais informativo do que parece: foi assim que se
descobriu que **o painel deles exibe o `incidence` agregado**, e não o
microdado que veio junto no mesmo pacote.

---

## 1. Contagem dobrada no `sinan_landing` — estamos certos, eles não

| | No R | Aqui |
|---|---|---|
| Base de composição e de encerramentos | soma o dataset inteiro | soma só `sexo='TOTAL'` |
| Denominador exibido (Recife, 2023) | 4.970 | **2.485** |
| Testados para HIV | 4.036 | 2.018 |

A linha `TOTAL` do `sinan_landing` **já é** a soma de M e F. Conferido em
Recife/2023, na variável `SITUA_ENCE`:

```
F      813
M    1.672
TOTAL  2.485      <- 813 + 1.672
```

Somar as três dá 4.970, que é exatamente a base que o painel deles exibe.
É a mesma armadilha fechada no painel nacional em ago/2026, onde inflava a
contagem em 31,8%.

**A proporção não sente**, e é por isso que o defeito sobrevive à inspeção
casual: abandono deles 1.118/4.970 = 22,49%; o nosso 557/2.455 = 22,69%.
Numerador e denominador dobram juntos.

**Consequência na tela:** nossos denominadores vão aparecer como metade dos
deles. Alguém vai reportar isso como bug do painel novo — esta seção existe
para que essa conversa seja sobre a decisão, e não sobre o número.

Fechado por: conferência direta no dataset. Não depende de resposta de
ninguém.

---

## 2. Microdado e agregado são extrações diferentes — **resolvido pelo Boletim (23/out/2026)**

> Nenhum dos dois é a régua. Os cards de Recife passaram ao SINAN nacional,
> base do Boletim: 1.685 casos novos em 2023 (Boletim 2024: 1.637, com o banco
> de fev/2024). O agregado contava todas as notificações (2.485); o microdado
> municipal tem 1.920 casos novos, sem a deduplicação nacional. Ver §9.

| Fonte | Notificações, Recife 2023 |
|---|---:|
| `cases_new` | 2.485 |
| `sinan_landing`, base de todas as 42 variáveis | 2.485 |
| `incidence`, somando os 94 bairros | 2.480 |
| **Microdado `SINAN_RECIFE_TB.csv`, notificações distintas** | **2.749** |

São 264 de diferença, e **não** é filtro nosso. Conferido:

- residência: todas as 2.766 linhas são de residentes de Recife;
- notificação: todas notificadas em Recife;
- bairro: nenhuma linha sem bairro preenchido;
- retratamento: casos novos (`TRATAMENTO=1`) são 1.881, que não bate com
  nenhum dos outros números.

Por bairro a diferença é consistente e vai de 5% a 15% — Cohab tem 126 no
agregado e 144 no microdado, Iputinga 71 contra 85. Só Curado quase coincide,
157 contra 156.

**Perguntado à equipe parceira em 28/ago/2026. Sem resposta até o fechamento
da semana 3.**

Enquanto não volta, `src/data/microdado.py` lê o microdado e **não decide**
qual fonte alimenta a tela. `microdado.total()` existe para que a diferença
seja mensurável a qualquer momento, e `test_microdado.py` prende o valor em
262 — se mudar, alguém trocou o dado e esta decisão precisa ser revisitada.

Quando a resposta chegar, ela vira fiação no `app.py`, não reescrita da camada.

---

## 3. Denominador do KPI de HIV — definição, não contagem — **resolvido (23/out/2026)**

> O card "HIV positivo na testagem" saiu. No lugar, os dois indicadores do
> Boletim: testagem para HIV (exame realizado ÷ casos novos) e coinfecção
> TB-HIV (positivos ÷ casos novos). Ver §9.

| | Numerador | Denominador | Recife/2023 |
|---|---|---|---:|
| Painel em R | HIV positivo | quem foi **testado** (exclui "não realizado" e "em andamento") | 17,4% |
| `incidence` | HIV positivo | **todos** os casos | 14,07% |

O rótulo deles — "HIV positivo na testagem" — descreve a primeira. As duas são
defensáveis e medem coisas diferentes: positividade entre testados contra
prevalência de coinfecção detectada entre casos.

Não é divergência de contagem, é definição, e muda um KPI de capa. **Decisão
pendente**, e ela entra no contrato de dados antes de a fórmula ser
escrita.

---

## 4. Gráfico histórico para em 2019 — **fechado (23/out/2026)**

> O R deixou de ser referência: o histórico vai até o último ano com dado.

O gráfico "Todos os anos" do painel deles tem 120 pontos, de `2010-01` a
`2019-12`, com dado disponível até 2023. Janela fixa de dez anos por decisão,
ou truncamento?

Perguntado junto com a §2. Não reproduzir por imitação até saber: copiar um
comportamento sem entender é como se herda defeito.

---

## 5. Canal endêmico: denominador fixo contra denominador de cada ano

| | No R | Aqui |
|---|---|---|
| População usada nas séries de anos anteriores | a do **ano selecionado** | a **de cada ano** |
| Efeito | as linhas de 2020–2022 sobem cerca de 0,37% | taxa real de cada ano |

Medido, não suposto. Dividindo a contagem de janeiro pela taxa que eles
publicam, a população implicada é a mesma nos quatro anos:

| Ano | Casos em janeiro | População implicada no painel deles |
|---|---:|---:|
| 2020 | 172 | 1.592.362 |
| 2021 | 147 | 1.592.362 |
| 2022 | 187 | 1.592.362 |
| 2023 | 279 | 1.592.362 |

1.592.362 é a população de 2023. As nossas são 1.598.198, 1.597.208 e
1.594.897 para os três anos anteriores.

**Estamos certos, e a diferença importa pouco no número mas muito no
significado.** Com denominador fixo, a linha de 2020 não é a incidência de
2020 — é a contagem de 2020 medida contra a população de hoje, um número que
não é a taxa de ano nenhum. Como o canal existe justamente para dizer se o mês
corrente saiu do padrão **histórico**, o padrão precisa ser o que de fato
aconteceu.

A **regra** dos quartis é a mesma nos dois: três anos anteriores, interpolação
linear. Confirmado no sexto decimal antes de a divergência de população
aparecer — `tests/test_canal.py` prende as duas coisas separadamente.

Fechado por: medição direta. Não depende de resposta de ninguém.

---

## 6. Anos de referência do canal: cinco, contra três deles — **decidido**

| | No R | Aqui |
|---|---:|---:|
| Anos na faixa | 3 | **5** |
| Faixa para 2023 | 2020–2022 | 2018–2022 |
| Largura média da faixa | 2,05 | 1,70 |
| Meses de 2023 acima do Q3 | 10 de 12 | **11 de 12** |

Desde 23/out/2026 o canal conta casos novos do Boletim (§9), e os números
mudaram: largura média 1,37 com três anos e 1,16 com cinco; acima do Q3, 5 e
**8** de 12. A regra dos quartis segue conferida contra o R em
`tests/test_canal.py`, rodando sobre a base antiga.

Decidido em 28/ago/2026. Com três pontos por mês cada quartil cai
entre dois valores, e 2020 — o mínimo da série — pesa um terço da faixa.

**A justificativa inicial estava parcialmente errada e vale registrar.**
Escrevi que 2020 e 2021 eram anos de notificação deprimida pela pandemia. A
série desmente metade disso:

| Ano | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Incidência | 123,8 | 123,5 | 111,2 | 113,7 | **103,9** | 127,2 | 150,9 | 156,1 |

Só **2020** foi deprimido. 2021 já supera 2018 e 2019.

### O limite que nenhum número de anos resolve

A tuberculose em Recife está em **alta sustentada**: 50% acima do piso de 2020
em três anos. O canal endêmico pressupõe padrão estacionário — a faixa
histórica é o "esperado", e o ano corrente se compara a ela. Sob tendência de
alta a faixa fica sempre atrás, e o ano corrente aparece acima quase todo mês.

Foi o que aconteceu, e piorou com cinco anos: passou de dez para **onze** dos
doze meses acima do Q3, porque 2018 e 2019 são mais baixos que 2021 e 2022 e
puxam o Q3 para baixo.

**A leitura é verdadeira, mas diz "a doença cresceu", e não "houve um surto em
março".** Quem usar o gráfico para detectar anomalia sazonal precisa saber
disso. Aumentar o número de anos melhora a estabilidade da faixa; não resolve
a tendência.

Se detectar anomalia sazonal virar requisito, o instrumento tem de mudar — uma
faixa ajustada por tendência, ou comparação contra o esperado de um modelo, e
não contra o quartil bruto. Fica anotado, sem virar tarefa.

---

## 7. Óbitos por bairro não fecham com a cidade — **fechado (23/out/2026)**

> A régua da mortalidade é o SIM (99 óbitos em 2022, igual ao Boletim; 140 em
> 2023). O SIM do banco não tem bairro de residência preenchido: o card do
> bairro ficou vazio e a mortalidade saiu do mapa e do ranking. Fechado.

Em `incidence`, `casos_obitos` no nível de município é 141 em 2023 — bate com
o SIM (8,85/100 mil) e com `SITUA_ENCE = 3` no microdado. No nível de
**bairro** a soma dos 94 é **377**. Não é 3 + 4 (óbito por TB + outras
causas: 233), nem todas as notificações em vez de casos novos. A série
inteira tem o mesmo desnível (2022: 343 contra 100).

O painel em R não mostra mortalidade por bairro, então não há referência.
Enquanto a coluna não for explicada, a mortalidade por bairro no mapa e no
ranking é **ordenação**, não taxa comparável à do card de Recife — e a
metodologia diz isso. Pergunta enviada junto com a §2.

Fica em aberto até: resposta da equipe parceira sobre o que `casos_obitos`
conta em `nivel=BAIRRO`.

---

## 8. O mapa abre na escala fixa, não em quartis — **decidido**

O painel em R abre o mapa em quartis. Aqui, desde 23/out/2026, abre na escala
fixa com nome e N em cada faixa ("< 40,0 abaixo do Brasil 13"), o padrão dos
painéis da família. Quartis continua no seletor, com a mesma regra do R.

A âncora é a de Recife (Brasil 40, Recife 106 e múltiplos desde a régua do
Boletim; antes, 156), e não a régua nacional do tbbrasil: com ela 53 dos 94
bairros cairiam na última faixa em 2023. Não muda número nenhum, só a cor de saída — ver `metodologia.md`.

---

## 9. A régua passa a ser o Boletim — **decidido (23/out/2026)**

Decidido em 23/out/2026: os números se conferem contra o **Boletim Epidemiológico
de Tuberculose do MS** e, na mortalidade, contra o **SIM**. O painel em R deixa
de ser referência, e as perguntas abertas à equipe parceira (§2, §4, §7) não
esperam mais resposta.

A faixa de KPIs passou de seis para oito, nas definições do quadro de métodos
do Boletim 2024: incidência, mortalidade (SIM), cura, interrupção, testagem
HIV, coinfecção TB-HIV, TRM nos pulmonares e não avaliados. "Casos novos" foi
para o subtítulo da incidência, e "HIV positivo na testagem" saiu. Recife
inteiro vem do SINAN nacional (`scripts/extrair_indicadores_sinan.py`); o
bairro, do microdado pelas mesmas regras. Números e comparação com o Boletim em
`metodologia.md`.

Mapa e ranking passaram a contar casos novos do microdado por bairro, com a
régua reancorada no Recife de 105,8 (§8). Canal endêmico, série anual e
epicurva de Recife inteiro passaram a casos novos do SINAN nacional
(`indicadores_sinan/recife_mensal.parquet`, do mesmo script); o gráfico de
meses do bairro, a casos novos do microdado. Nada de série conta mais todas as
notificações.
