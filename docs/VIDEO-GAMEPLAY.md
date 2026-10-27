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

**No runner do GitHub (run 40508283212, 27/10/2026 13:02 UTC — o que vale):**

| medida | valor |
|---|---|
| duração do arquivo | 49,3 s |
| resolução / fps | 1280×720 / 24 |
| tamanho | 1.091.867 B (artefato de 1.873.939 B com quadro + kit) |
| cores distintas (amostras de 160×90) | 1.253 |
| movimento médio entre amostras | 1,74 (mínimo exigido: 1,2) |
| maior trecho parado | 7,0 s (a tela do tutorial) |
| veredito do validador | ✔ passou (rodado de novo no artefato baixado) |

**Na minha máquina (primeira captura, mesmo código):** 44,8 s · 1.273 cores · movimento 1,53 ·
maior trecho parado 6,5 s · ✔ passou.

O jogo **responde de verdade**: as moedas saem de 25 → 26 com o botão "Fazer um bico" e um
campo passa a mostrar "Nabo crescendo — 10s" com o broto na terra. Isso é ciclo de jogo, não
tela parada.

## O que este pipeline NÃO faz

- **Não joga bem.** O roteiro é determinístico e cego: ele toca em pontos fixos que eu medi na
  tela. Não lê o estado do jogo, então não "decide" o que fazer — repete o ciclo do tutorial.
- **Não publica sozinho.** Publicação continua exigindo a palavra `PUBLICAR`, como o resto da
  casa. O cron só grava.
- **Não cobre o PRANCHETA ainda.** O roteiro das coordenadas é do CEIFALUME; outro jogo precisa
  de outro roteiro medido, e eu não vou fingir que um serve para o outro.
- **Não substitui edição humana.** Sem cortes, sem trilha, sem legenda: é captura crua.
  O YouTube aceita; o canal é que decide se vale publicar cru.

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
