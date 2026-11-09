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
gosto. Antes de o feed existir: 0 medido, 10 declarados. **Depois da primeira medição real (run
`41144446261`, 300 posts, commit `f144b24`), dois traços viraram peso medido:**

| traço | com o traço | sem o traço | ganho | desvio |
| --- | --- | --- | --- | --- |
| emoji no início | 2,21 (n=78) | 0,82 (n=222) | **1,38** | 1,09 |
| tem número concreto | 2,05 (n=78) | 0,88 (n=222) | **1,17** | 1,09 |

Os outros oito seguem **declarados**: a amostra de cada lado não passou ou a diferença ficou
dentro do desvio. É a primeira vez que a casa tem de onde aprender gosto — e ela já recusou oito
de dez palpites.

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

## Dois defeitos medidos em CI (e consertados)

O primeiro run de verdade mostrou o juízo funcionando **e** dois erros silenciosos que
engoliam o resultado:

```
cerebro | ✅ post novo validado — motor=g4f auto + motor=g4f auto · juízo: escolhi o 1º de 2
(1 válidos): cita jogo, chamada, hashtag 1 ou 2 · 220 caracteres · abre diferente do último post
```

Mas `posts/memoria-de-gosto.json` não chegava ao repositório. Causas, medidas:

1. **`git stash push -u`** no passo do painel levava embora o arquivo **novo** (untracked) — a
   memória existia no runner e sumia antes do commit. Agora o stash não usa `-u` (untracked não
   bloqueia rebase).
2. **`git add a b c`** com um caminho ausente aborta o add **inteiro**
   (`fatal: pathspec … did not match any files`): a medição com feed e perfil ficava fora do
   commit sem avisar. Agora é um `git add` por arquivo, tolerando ausência.

Prova do conserto: o run seguinte commitou `posts/feed-medido.json` (**create mode 100644**) e o
perfil com os dois traços medidos. A memória de escolhas aparece no próximo ciclo que
**publicar** — o run em que ela seria escrita caiu na trava de cadência (`cadencia=PULADO`), que
é comportamento correto, não falha.

## Provas

- `tools/testes-juizo.py` — **56/56** (escolha, empate, dedupe de candidatos, validador,
  revisão idempotente e sem invenção, memória, apuração de resultado, CLI, integração e o
  caminho de **juízo indisponível** que mantém o comportamento antigo)
- `tools/testes-autonomia-marketing.py` — **83/83** (era 82)
- `tools/testes-painel-marketing.py` — **30/30**
- **30 suítes locais, 30 verdes** (zero falhas)
- CI `postagem-diaria` **success** em `41144446261`, com `testes-juizo.py` 56/56 na barreira
- `postagem-diaria`, `marketing-24h` e `diagnostico-da-casa` cobram `testes-juizo.py` a cada ciclo
- o `postagem-diaria` regenera `perfil-de-gosto.json` e apura os resultados a cada medição

## O limite que continua de pé

Gosto sobre **conteúdo de terceiros**, humor, o que é "bonito" e o que vale publicar no YouTube
seguem fora: isso exige alguém que possa se envergonhar do resultado. O juízo decide dentro do
que a casa mede; fora disso, ele para — e diz que parou.
