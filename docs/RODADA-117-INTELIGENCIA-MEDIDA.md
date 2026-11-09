# Rodada 117 — a inteligência medida (não a prometida)

A pergunta foi: *"mas ele fará tudo de forma inteligente e sábio?"*

A casa não responde isso com adjetivo. Esta rodada construiu o instrumento que mede a única
coisa que "inteligente" pode significar em automação: **comportamento que muda quando o
resultado muda.** Onde não há leitura, não há inteligência — há ritual, e o ritual estava
escondido atrás de ✅.

## O instrumento: `tools/auditar-inteligencia.py`

Lê o próprio `posts/log.md` (últimos 40 ciclos), passo por passo, e classifica:

| classe | critério | o que significa |
| --- | --- | --- |
| **adaptativo** | 3+ resultados distintos | há leitura alimentando decisão |
| **binário** | 2 resultados | liga/desliga — varia pouco, mas varia |
| **ritual** | 1 resultado sempre igual | nada entra, nada se aprende |
| **fachada** | ✅ todo ciclo com "já registrado"/"cadência" no texto | parece trabalho, não fez nada de novo |
| **cego** | sempre indisponível | falta olho (segredo/API), não falta vontade |

Medido agora (janela de 40 ciclos):

- **11 adaptativos** — entre eles `cerebro` (texto novo validado ou não), `instagram`
  (trava de 6 h), `threads`, `nostr`, `cáçador de oportunidades`, `régua de metas`;
- **2 rituais** — `ntfy` (push sai igual todo ciclo: está funcionando) e `aula do cérebro`;
- **3 cegos** — `telegram`, `mastodon`, `discord`, todos por segredo ausente, com o nome do
  segredo escrito na linha;
- **0 fachadas** hoje — mas a classe existe porque já houve: `descobridor de redes` e
  `censo mundial` confessam "já registrado hoje" em **29 de 40** ciclos.

> Ritual não é xingamento. Push que sai igual todo ciclo é serviço, não falha. O problema é o
> passo que **diz** que fez algo novo e não fez — e era exatamente esse que ninguém media.

## O defeito que a auditoria achou (e que foi consertado)

Repetição de texto publicado: **13 vezes o mesmo post** na janela de 40 ciclos (37,5%).

Investigando a causa, o número honesto aparece separado por época:

| período | ciclos | repetidos |
| --- | --- | --- |
| 24–25/10 (antes do conserto de dedupe) | 10 | 10 (100%) |
| **depois de 26/10** | **16** | **1 (6,2%)** |

O conserto de 26/10 funcionou. Mas sobrou **um** furo: o dedupe comparava o texto **como foi
escrito**, então bastava o motor trocar um emoji, um `·` ou uma quebra de linha para a repetição
passar com ✅. Simulação sobre os 102 ciclos do diário: a chave antiga pegava **71 de 72**
repetições; a nova pega **72 de 72**.

### Conserto

`postador.py` ganhou `assinatura()`: NFC, sem acento, **só letras e números**, espaços
colapsados. O dedupe passou a comparar conteúdo, não embalagem. Provas em
`testes-autonomia-marketing.py` (**82/82**, +7 verificações): emoji trocado, separador trocado,
`⏎` vs `·` vs quebra de linha, e o caso que tem de continuar passando (texto genuinamente novo).

## Onde isso aparece

- `posts/auditoria-inteligencia.{json,md}` — gerado a cada ciclo, commitado pelo runner.
- `marketing.html` — seção **"Onde a casa pensa e onde ela só repete"**, com a repetição desde
  o conserto e a explicação de que ritual ≠ falha.
- Barreira offline do `postagem-diaria` e do `diagnostico-da-casa` cobram as duas suítes novas.

## Provas desta rodada

- `tools/testes-auditar-inteligencia.py` — **18/18**
- `tools/testes-autonomia-marketing.py` — **82/82** (era 75)
- `tools/testes-painel-marketing.py` — **25/25** (era 22)
- `tools/testes-decisoes.py` 28/28 · `testes-aprender-horario.py` 16/16
- 28 suítes locais: **27 verdes**; a única falha (`testes-gameplay.py`) é de ambiente (o sandbox
  não tem navegador instalado), não do código — no CI ela passa.
