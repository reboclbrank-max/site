# Rodada 118 — o olho: saber o que precisa ser feito

A pergunta foi: *"por que ele precisa saber o que fazer, ser inteligente também, tipo você:
saber o que fazer e o que precisa ser feito?"*

Era a pergunta certa, e a resposta medida é desconfortável: **a casa sabia QUANDO, não sabia O
QUE.** O `orquestrador` decidia por relógio — "medição vencida (intervalo de 6 h)", "janela de
pesquisa (03h local)". Ele nunca olhava o estado para perguntar *o que está faltando agora?*

Prova do buraco: `posts/orquestrador.json` roda a cada pulso e escolheu **"medir"** nas últimas
execuções, enquanto três canais estavam cegos, um arquivo de aprendizado estava parado desde 27/10
e a repetição de texto estava em 37,5%. Nada disso virava tarefa, porque nada disso era lido.

## O que foi entregue: `tools/perceber.py`

O olho. Lê o estado medido e produz **necessidades** — cada uma com número, dono, como fazer e
como verificar. Não é relatório para o dono ler: as do robô são **enfileiradas em
`posts/fila-tarefas.json`**, e o pulso já dá prioridade à fila antes do relógio
(`orquestrador.usar_fila`). Perceber o problema já é o primeiro passo de resolvê-lo.

Sete sentidos, cada um com limite declarado no arquivo:

| sentido | o que detecta | dono |
| --- | --- | --- |
| `canais_cegos` | canal que nunca publicou em 20 ciclos e cuja linha nomeia o segredo | dono |
| `artefatos_velhos` | arquivo parado há mais de 26 h (ou ausente) | robô |
| `metas_em_risco` | meta cujo ritmo necessário passou de 1 por dia | robô |
| `repeticao_alta` | repetição acima de 10% desde o conserto de dedupe | robô |
| `fila_travada` | tarefa em `falhou` (desistiu após 3 tentativas) | robô |
| `kit_esperando` | vídeo pronto e sem id do YouTube | dono (PUBLICAR) |
| `pendencias_paradas` | pendência do dono parada há mais de 2 dias | dono |

## O que ele percebeu agora (medido, não exemplo)

Rodado no repositório real, nesta ordem de prioridade:

- **Robô, 2** — *empurrar a meta itch: downloads* (faltam 54, ritmo 4,15/dia) e *Instagram:
  seguidores* (faltam 50, ritmo 3,85/dia). **As duas já estão `pendente` na fila.**
- **Dono, 3** — *telegram*, *mastodon*, *discord*: "nunca publicou em 20 ciclos: falta o segredo
  `TELEGRAM_TOKEN + TELEGRAM_CHAT`" (e os outros dois), com o caminho exato para criar.

## O defeito que apareceu no caminho (e foi corrigido)

`marketing-continuo` estava **vermelho 5 vezes por dia** — não por defeito de código, mas porque
a barreira dele rodava `testes-gameplay.py`, que exige navegador instalado, num workflow que não
instala navegador. O teste "com o navegador instalado a escolha não é null" reprovava por falta
de ambiente. Agora ele **declara SKIP** quando não há navegador — e uma verificação nova garante
que o workflow que realmente grava (`gravar-gameplay.yml`) **instala** o navegador, para o SKIP
não esconder a ausência em todo lugar.

## Limites (o que continua não sendo "tipo eu")

1. **Eu vejo o que ainda não virou arquivo.** A casa só percebe o que já foi medido e gravado; se
   ninguém escreveu a métrica, o passo é cego — e agora isso aparece como cego, não como ✅.
2. **Eu decido o que *não* estava no plano.** A casa percebe desvios do que ela já sabe medir;
   inventar um indicador novo (ex.: "o público está entendendo o jogo?") continua exigindo alguém
   fora do loop.
3. **Nada disso autoriza publicação sem `PUBLICAR`.** A percepção enfileira; a regra do dono manda.

## Provas

- `tools/testes-perceber.py` — **40/40**
- `tools/testes-gameplay.py` — **98/98** (era 92/93, vermelho em CI 5×/dia)
- `tools/testes-painel-marketing.py` — **28/28**
- 29 suítes locais: **29 verdes** (todas)
- `marketing-24h.yml` roda `perceber.py` **antes** de `orquestrador.py` e commita
  `posts/percebido.{json,md}` + `posts/fila-tarefas.json`
- `marketing.html` abre com **"O que precisa ser feito agora"**, separando o que o robô assumiu
  do que só o dono destrava.
