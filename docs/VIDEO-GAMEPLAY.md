# Vídeo de gameplay — o que agora é medido, não prometido

Até 27/10/2026 a casa tinha **um** vídeo do CEIFALUME: o trailer 0.1, feito à mão. Não existia
nada que repetisse aquilo, e por isso a resposta honesta sobre "vídeo" sempre foi ❌.

A partir de hoje existe um caminho que roda sozinho e entrega arquivo de vídeo de verdade:

```
ceifalume/ (build web Godot)
   │  servido em 127.0.0.1 com COOP+COEP (o build usa threads → SharedArrayBuffer)
   ▼
tools/gravar-gameplay.js  → Chromium sem tela, WebGL por software (SwiftShader)
   │  roteiro determinístico: atravessa título → splash → tutorial → ciclo de fazenda
   │  (semente → campo → bico → colher → vender), 1280x720 @ 24 fps
   ▼
media/gameplay/ceifalume-gameplay.mp4  (+ um quadro de prova .png)
   ▼
tools/validar-video.py  → MEDE: duração, resolução, fps, brilho, cores, movimento,
   │                      maior trecho congelado. Tela preta e imagem parada REPROVAM.
   ▼
tools/kit-gameplay.py   → pacote de envio (título/descrição/tags do kit oficial + linha
   │                      dizendo que o vídeo foi gravado do jogo, sem edição)
   ▼
.github/workflows/gravar-gameplay.yml
   • cron 4×/dia (01:25, 07:25, 13:25, 19:25 UTC) → só grava, guarda artefato
   • workflow_dispatch com `publicar=PUBLICAR` → aí sim chama tools/enviar-youtube.py
```

## Números medidos

**No runner do GitHub (run 40514754877, 27/10/2026 13:46 UTC — o que vale):**

| medida | valor |
|---|---|
| duração do vídeo final | 52,1 s (cru: 51,5 s + 3 s de cartão − sobreposição) |
| resolução / fps | 1280×720 / 24 |
| tamanho | 1,8 MB |
| legendas | 6 linhas, geradas das decisões do agente |
| trilha | sintetizada (média **-30,9 dB**, pico -21,5 dB) |
| cartão final | presente (brilho médio 52) |
| cores distintas / movimento | 1.297 cores · 1,67 |
| maior trecho parado | 10,0 s |
| validação de imagem | ✔ passou |
| validação de apresentação (som + legenda + cartão) | ✔ passou |
| decisões do agente na partida | plantou em 5 células, colheu 4 vezes, moedas mudando na tela |

**Na minha máquina (primeira captura, mesmo código):** 44,8 s · 1.273 cores · movimento 1,53 ·
maior trecho parado 6,5 s · ✔ passou.

O jogo **responde de verdade**: as moedas saem de 25 → 26 com o botão "Fazer um bico" e um
campo passa a mostrar "Nabo crescendo — 10s" com o broto na terra. Isso é ciclo de jogo, não
tela parada.

## O que estava errado no vídeo entregue em 27/10 (corrigido no mesmo dia)

O dono viu o vídeo e reprovou: *"as instruções de como jogar não saem da tela em momento algum"*.
Estava certo. Medições feitas no jogo rodando:

| o que o robô lia | com o tutorial aberto | jogando (sem tutorial) | veredito |
|---|---|---|---|
| "painel escuro" (r<40, g<45, b<60) | **0,255** | 0,748 | nunca passava do limiar 0,35 — o painel do tutorial é azul-escuro (rgb 44,52,65), não preto |
| painel azul (teste novo) | **0,878** | 0,080 | separa com folga |
| botão dourado dentro do painel | **0,582** | 0,000 | confirma que é o botão, não o brilho da colheita |

Ou seja: o detector de tutorial **nunca disparava**, o robô nunca tocou em "Entendi, jogar!" e o
modal ficou no quadro do começo ao fim. Agora ele fecha em ~2,8 s, o gravador confere por imagem
que o painel sumiu e o pipeline **falha** se o tutorial estiver na tela no fim da captura.

Outros dois erros de leitura, também medidos:

- **Colheita pelo sinal errado.** O código esperava "verde alto" para colher. No ponto de colheita o
  nabo fica **branco**: verde cai de 0,10 para 0,038 e aparece casca branca em 0,026-0,037. Era por
  isso que nenhuma das execuções colhia nada (0 colheitas em 4 tentativas de 45-75 s). Agora a
  colheita é decidida pela casca, e o botão "Colher" (rodapé da caixa) é o alvo do toque.
- **Semeadura dupla.** A barra dourada de progresso só aparece 1-3 s depois da semente; nesse vão a
  célula parecia vazia e o robô semeava de novo em cima, reiniciando o crescimento (8 sementes para
  4 campos e nenhuma colheita em 75 s). Agora a célula só é semeada quando duas leituras seguidas
  dizem que está livre.

## Espera longa: o que é corte e o que é jogo

Sob gravação o relógio do jogo anda ~3x mais devagar que o relógio da parede (24 s de crescimento
custam ~100 s de captura). Por isso o vídeo usa `--trechos`:

```bash
python3 tools/produzir-video.py cru.mp4 cru-decisoes.json final.mp4 --trechos "2-26,106-132"
```

Os trechos escolhidos são de ação (abertura + plantio, e colheita + venda). O que fica de fora é
espera parada — e isso está escrito aqui e no relatório do run. Nada é acelerado nem inventado: as
decisões que aparecem na legenda são as mesmas do relatório, com o tempo deslocado para a linha do
tempo do corte.


## O que este pipeline NÃO faz

- **Não joga bem.** O agente lê o estado (tutorial, título e o verde de 5 células) e decide
  colher/semear/ganhar moeda — mas não entende estratégia: não escolhe a semente mais cara,
  não compra melhoria na hora certa, não joga o PRANCHETA.
- ~~O PRANCHETA ainda não tem roteiro~~ — **resolvido em 27/10/2026.** `tools/gravar-prancheta.js`
  descobre o build atual na página do itch (`html-classic.itch.zone/html/<id>/index.html`, o id
  muda a cada versão), atravessa splash → menu → **Nova carreira** → aceitar convite de clube →
  sugestão do staff → microciclo → prancheta tática → partida (instrução no intervalo, velocidade,
  pular para o fim) e **confere cada passo por imagem**. Se menos de 4 passos essenciais mudarem a
  tela, ele falha em vez de entregar vídeo parado. Regiões medidas em 1280×720:
  nova carreira y≈87 · aceitar convite y≈179 · staff y≈232 · microciclo y≈612 · prancheta y≈259 ·
  jogar y≈289 · instrução (110,608) · seguir (636,573) · rápida (700,685) · pular (900,705).
  Workflow: `gravar-prancheta.yml` (3 gravações/dia, sem envio automático).
- **Não publica sozinho.** Publicação continua exigindo a palavra `PUBLICAR`, como o resto da
  casa. O cron só grava.
- **Trilha sintetizada, não música.** É um pad de três notas gerado pelo ffmpeg; a descrição
  do kit diz isso, para ninguém achar que é trilha composta.

## Como repetir à mão

```bash
npm install --no-save playwright-core@1
npx playwright install chromium-headless-shell
node tools/gravar-gameplay.js --saida media/gameplay/ceifalume-gameplay.mp4 --segundos 45
python3 tools/validar-video.py media/gameplay/ceifalume-gameplay.mp4
python3 tools/kit-gameplay.py
# publicar (só com a palavra):
KIT_YOUTUBE=posts/kit-gameplay.json CONFIRMACAO=PUBLICAR \
  YT_CLIENT_ID=... YT_CLIENT_SECRET=... YT_REFRESH_TOKEN=... \
  python3 tools/enviar-youtube.py ceifalume-gameplay
```

Barreira: `python3 tools/testes-gameplay.py` (65 provas, sem rede).

## Jogar melhor — o que foi medido antes e depois (27/10/2026)

O dono cobrou: *"o agente comprar melhoria e escolher a semente de maior valor… com medida de
moedas ganhas por minuto antes e depois, senão não conta como melhoria"*. Tudo abaixo foi
executado no jogo rodando, com o dinheiro lido no save (`ceifalume-save.cfg`), nada estimado.

**A régua (a mesma em todas as linhas):**
`ganho = (saldo final − saldo inicial) + gasto em melhorias + gasto em sementes`, dividido pela
janela. Saldo sozinho mente: comprar melhoria e semente derruba o saldo e não é prejuízo.

| robô | janela | execuções | ganho (moedas) | **moedas/min** |
|---|---|---|---|---|
| **original** (só imagem, 1 toque por decisão) | 150 s | 3 | 59 · 50 · 55 | **21,9** |
| hoje **sem** decisões de dinheiro (`--sem-economia`) | 150 s | 2 | 691 · 817 | **301,6** (média) |
| **completo** (bico + fazenda pelo save + compras + semente) | 150 s | 2 | 754 · 792 | **309,2** |
| **original** | 900 s | 1 | 720 | **48,0** |
| hoje **sem** decisões de dinheiro | 900 s | 1 | 5 707 | **380,5** |
| **completo** | 900 s | 1 | 6 913 | **460,9** |

**Veredito: agora conta como melhoria.** 48,0 → 460,9 moedas/min na janela longa (**9,6×**) e
21,9 → 309,2 na curta (**14×**). E a parte que o dono pediu nominalmente — comprar melhoria e
escolher a semente de maior valor — soma em cima do bico: **+21%** na janela de 900 s
(380,5 → 460,9) e +2,5% na de 150 s (dentro do ruído).

**Composição do ganho no vídeo de 900 s:** 5 202 moedas de bico (5 202 toques) + ~1 711 de fazenda
(20 colheitas de Trigo/Tomate, venda 110/380) − nada. O bico ainda é a maior fonte, e isso é
propriedade do jogo, não do robô.

### O que estava errado (três medições que mudaram o agente)

1. **O bico não tem espera.** Medido no jogo, 20 s por intervalo:
   60 ms → **525,0 moedas/min** · 120 ms → 306,0 · 250 ms → 195,0 · 500 ms → 111,0 · 1000 ms → 57,0.
   O robô antigo tocava uma vez a cada ~2,2 s (≈27/min). Agora ele faz **rajadas de 8 s** a cada
   45 ms e volta a olhar a fazenda no fim da rajada.
2. **Quem colhe é o clique no corpo da planta, não na barra do rodapé.** O clique em `y + h − 25`
   **planta** uma semente nova na célula — era por isso que o robô "colhia" e o save continuava
   com a planta madura no lugar (e o dinheiro caía, porque a semente era paga).
3. **A fazenda tem de ser decidida pelo save, não pela cor.** Com Milho/Trigo a planta madura não
   tem a casca branca do Nabo; e a célula D dava **casca 0,015 fixa** (limiar 0,012) e virava uma
   colheita fantasma a cada volta — 346 "colheitas" e só 96 bicos/min em 900 s. Agora, com save na
   mão, `campos[i].pronto` decide a colheita e `campos[i].planta === ""` decide o plantio; a
   leitura por pixel só vale como reserva (quando o save não abre).

### A 5ª célula (o campo comprado deixou de ser dinheiro jogado fora)

`Comprar campo` (50 moedas) grava **5 entradas** em `campos` — conferido no save. A célula nova
nasce embaixo, à direita da D: caixa em (640,372) 230×228, centro **(755,486)**. O robô agora
enxerga cinco células e planta/colhe na nova. O preço sobe a cada compra (a 5ª custou 73 na tela),
por isso a compra é uma vez por captura e a confirmação é sempre no save.

### Regras de dinheiro que ficaram (todas com número atrás)

- **Prioridade de compra por efeito medido:** Poço (crescimento +10%) → Lanterna (+1/colheita) →
  Composteira (8% dupla) → Campo (+1 célula) → Celeiro (capacidade, que o robô nunca enche porque
  vende na hora — catalogado, **não** comprado).
- **Semente com histerese:** sobe para a mais cara que o caixa cobre para **6 rodadas**
  (custo × 6 + 5 → 125 Milho, 365 Trigo, 1 205 Tomate) e só desce se não pagar **nenhuma** semente.
  Sem a faixa larga o robô pulava Nabo → Trigo → Nabo a cada compra.
- **Carência de 5 s** na célula recém-colhida e de 9 s na recém-plantada: o save atrasa 1–2 s e sem
  isso o robô repetia a ação em cima da leitura velha.

Prova automatizada: `tools/testes-gameplay.py` — **79/79**, incluindo o leitor do save, a prioridade
de compra, a histerese da semente, a fazenda pelo save (pronto → colhe no centro da célula; vazio →
planta; crescendo → bico), a carência da colheita, a 5ª célula em (755,486), o gasto de semente
entrando no ganho e `ganhoDeMoedas()` devolvendo 64 para saldo 25→19 com 70 gastos.

### Próximo passo (para não repetir o erro de comprar o que não rende)

1. As células 6ª em diante ainda não têm coordenada; comprar campo sem mapear a célula é dinheiro
   parado. Enquanto não houver mapa, a compra é uma só.
2. O bico satura perto de **340 toques/min** por causa do custo do toque sintético (~45-60 ms de
   ida e volta). Para subir mais é preciso mandar o toque em lote, sem esperar cada um.
3. Remedir sempre na **mesma régua** (900 s, mesmo `--sem-economia` como linha de base).
