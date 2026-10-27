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

## O que este pipeline NÃO faz

- **Não joga bem.** O agente lê o estado (tutorial, título e o verde de 5 células) e decide
  colher/semear/ganhar moeda — mas não entende estratégia: não escolhe a semente mais cara,
  não compra melhoria na hora certa, não joga o PRANCHETA.
- **O PRANCHETA ainda não tem roteiro.** O jogo só existe publicado no itch.io (o repositório
  tem as páginas de marketing, não o build), e a tela inicial dele ("Carregar carreira") não
  é a mesma do CEIFALUME. Faltam: baixar o build, medir as regiões dele e escrever o agente.
  `tools/gravar-gameplay.js --url <endereço>` já abre build externo — o que falta é a medição.
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

Barreira: `python3 tools/testes-gameplay.py` (27 provas, sem rede).
