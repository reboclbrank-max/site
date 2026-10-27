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

Barreira: `python3 tools/testes-gameplay.py` (37 provas, sem rede).
