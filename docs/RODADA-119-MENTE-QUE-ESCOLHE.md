# Rodada 119 — a mente que escolhe (juízo, gosto aprendido e revisão)

O pedido: *"coloque ele pra ter uma mente humana e deixe ele fazer decisões e escolhas"*.

O que é honesto entregar disso, e o que eu **não** vou fingir:

- **não** vou dizer que ele sente, tem opinião ou acha algo bonito — isso seria mentira com
  aparência de código;
- **vou** entregar o que "mente" significa em decisão: **critério explícito, escolha entre
  opções com justificativa registrada, gosto que se corrige com resultado medido, e revisão do
  próprio texto.**

Até esta rodada o robô não escolhia nada: `cerebro_com_motivo()` devolvia um texto e o
`texto_gerado_seguro()` dizia sim/não. Aprovar o primeiro que chega não é escolher — é ordem de
chegada com carimbo.

## `tools/juizo.py` — as quatro peças

### 1. Critério declarado (auditável)

Dez traços, cada um com peso **e origem**:

| traço | peso | origem |
| --- | --- | --- |
| cita o jogo/casa | +2 | declarado |
| tem pergunta / pergunta no fim | +1 | declarado |
| chamada ("grátis", "no navegador", "conta pra mim") | +1 | declarado |
| tamanho 120–200 caracteres | +1 | declarado |
| 1 ou 2 hashtags | +1 | declarado |
| tem número concreto | +1 | declarado |
| link no corpo | **−1** | declarado (o destino entra depois) |

Origem "declarado" é dita em voz alta: é escolha da casa, não fato medido.

### 2. Gosto aprendido **só com prova**

`posts/feed-medido.json` (novo, gravado pelo `metricas.py`) guarda engajamento **por post**.
O juízo compara cada traço com/sem e **só troca o peso** quando há ≥ 15 posts de cada lado **e**
a diferença supera o desvio padrão — a mesma lei do aprendizado de horário. Ruído não vira
gosto. Hoje: **0 medido, 10 declarados, amostra 0** — porque o feed medido ainda não tinha sido
persistido. É a primeira vez que a casa tem onde aprender; a próxima medição enche.

### 3. Escolha com justificativa (e variedade)

O postador agora pede **duas versões** (`JUIZO_CANDIDATOS`, padrão 2 — a segunda com a instrução
"não comece com o mesmo recurso"), valida as duas no crivo, deduplica e escolhe pela pontuação.
Empate: preferência por quem **abre diferente do último post** — variedade é critério, não sorte.

O log do ciclo passa a carregar a razão:

```
cerebro | ✅ post novo validado — motor=g4f auto + g4f lightning · juízo: escolhi o 2º de 2
(2 válidos): cita jogo, chamada, hashtag 1 ou 2 · 123 caracteres
```

### 4. Revisão de si mesmo (que só corta)

`revisar()` normaliza espaços, remove hashtag além da segunda, corta no limite de 220 e avisa
quando há link no corpo. **Nunca cria conteúdo**: se a revisão inventasse uma frase, seria outro
post com o nome de revisão. Há teste garantindo que o conjunto de palavras só encolhe.

### Memória do gosto, com resultado

`posts/memoria-de-gosto.json` guarda cada escolha (texto, justificativa, candidatos, revisão) e,
quando o post aparece no feed medido, **liga o resultado**: `apurar_resultado()` preenche o
engajamento daquela escolha. É o laço fechado — a casa vê se a escolha dela funcionou.

## Melhorias do pacote (o "tudo")

| antes | agora |
| --- | --- |
| aprovava o primeiro texto válido | escolhe entre 2 com justificativa no log |
| "gosto" não existia | 10 critérios com origem e 1 via de aprendizado por resultado |
| medição tinha engajamento por post e jogava fora | `posts/feed-medido.json` persistido |
| revisão do texto: nenhuma | revisão automática, só cortando, com registro |
| painel não dizia como escolhe | seção **"Como a casa escolhe (o gosto, com origem)"** |
| `marketing-continuo` vermelho 5×/dia | barreira verde (rodada 118) |
| dedupe deixava passar 1 em 72 repetições | pega 72 de 72 (rodada 117) |
| pulso priorizava a rotina sobre o problema | necessidade percebida vale 95 (rodada 118) |

## Provas

- `tools/testes-juizo.py` — **52/52** (escolha, empate, dedupe de candidatos, validador,
  revisão idempotente e sem invenção, memória, apuração de resultado, CLI, integração e o
  caminho de **juízo indisponível** que mantém o comportamento antigo)
- `tools/testes-autonomia-marketing.py` — **83/83** (era 82)
- `tools/testes-painel-marketing.py` — **30/30**
- **30 suítes locais, 30 verdes** (zero falhas)
- `postagem-diaria`, `marketing-24h` e `diagnostico-da-casa` cobram `testes-juizo.py` a cada ciclo
- o `postagem-diaria` regenera `perfil-de-gosto.json` e apura os resultados a cada medição

## O limite que continua de pé

Gosto sobre **conteúdo de terceiros**, humor, o que é "bonito" e o que vale publicar no YouTube
seguem fora: isso exige alguém que possa se envergonhar do resultado. O juízo decide dentro do
que a casa mede; fora disso, ele para — e diz que parou.
