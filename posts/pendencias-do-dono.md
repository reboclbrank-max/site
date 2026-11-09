# Pendências do dono

Medido em 2026-11-09T22:27:33Z (o devlog do itch é público: dá para conferir de fora).

## Estado da casa

- Vídeos publicados: 14 · último: FNzW9c45E3M (Onde falar com quem fez CEIFALUME)
- Capas da casa: 55 aplicada(s) · canal com 169 vídeos, 51 com capa da casa, 11 citam jogo da casa no título · nenhum da casa sem capa (medido em 2026-11-07T04:43)
- PRANCHETA no itch: build 19604665 (a casa viu em 2026-11-07T05:38) · esse build não sobe por aqui: o dono publica no itch
- Fila: 5 pendente(s) (pesquisar 3, publicar 2) · a mais velha: pesquisar-20261107T064637Z há 63.7 h · 108 feita(s)
- Régua de metas: medida há 52.6 h · prazo 2026-11-12 · 5 dia(s) restante(s) · VENCIDA (medir de novo)
- Pulsos: 260 · última publicação 2026-11-09T22:00:16Z · última medição 2026-11-09T18:00:26Z

- Agenda: o cron pede **62** disparos/dia e o GitHub entregou **12.86/dia** (janela de 7 dia(s), medido em 2026-11-09).
- Corrente: em dia (último pulso 09/11 19:20, há 7 min) · próximo pulso 09/11 19:40 · 1 buraco(s) nas últimas 24h

- Originalidade: últimos 7 dias: 15 post(s), todos textos diferentes · média 4.62/dia · o último dia com repetição foi 2026-10-25

- Pauta: 16 par(es) assunto+ângulo livre(s) agora · o redator monta pauta: sim · a rotação volta a partir do 20º uso (medido: 40 escolhas seguidas sem ficar sem pauta)

| item | estado | como |
| --- | --- | --- |
| publicar o devlog do gameplay no itch | sem caminho automático | nada obrigatório: o conteúdo já chega ao jogador pelo build, pelo blog e pelo YouTube. Se quiser a cópia editorial no itch: abrir itch/devlog-gameplay-bookmarklet.txt como favorito em qualquer página do itch, logado — ele acha o formulário e posta posts/devlog-itch-gameplay.json |
| subir o build com o selo do gameplay (modo push + PUBLICAR) | feito | workflow enviar-itch, jogo=ceifalume, modo=push, confirmacao=PUBLICAR (o selo do vídeo já está em ceifalume/index.html) |
| o jogo no itch entregar o conteúdo do repositório (e o vídeo chegar lá) | feito | nada obrigatório: o jogo no itch já é o do repositório e o vídeo chega pelo GIF da descrição |
| vídeo de gameplay no YouTube | feito | nada: já publicado |

## Por que só o dono pode

Nada. Nenhuma pendência depende de clique do dono nesta medição.

## Sem caminho automático (medido, não pedido)

- **publicar o devlog do gameplay no itch** — a página pública de devlog respondeu 200 e não tem o post; o painel do itch responde 403 (Cloudflare) para IP de datacenter e a API oficial não tem endpoint de devlog — medido em 31/10/2026
  - sondagem: `docs/sondagens/ITCH-DEVLOG-SEM-CAMINHO-AUTOMATICO.json`
  - chega ao jogador por: blog/ceifalume-gameplay.html (site da casa, sem trava nenhuma)
  - chega ao jogador por: https://youtu.be/GuE7af6dYo8 (YouTube, público)
  - chega ao jogador por: vídeo dentro da pasta do jogo (media/) — vai junto de qualquer build futuro

## Canais desligados por decisão

Decidido em 2026-11-07. Ficam fora da cobrança diária; o motivo está escrito para não parecer esquecimento.
- **discord**: nunca publicou em 20 ciclos por falta de DISCORD_WEBHOOK; decisão de 07/11/2026: não ligar agora
- **mastodon**: nunca publicou em 20 ciclos por falta de MASTODON_URL + MASTODON_TOKEN; decisão de 07/11/2026: não ligar agora
- **telegram**: nunca publicou em 20 ciclos por falta de TELEGRAM_TOKEN + TELEGRAM_CHAT; decisão de 07/11/2026: não ligar agora

## Medições

- **publicar o devlog do gameplay no itch**: a página pública de devlog respondeu 200 e não tem o post; o painel do itch responde 403 (Cloudflare) para IP de datacenter e a API oficial não tem endpoint de devlog — medido em 31/10/2026
- **subir o build com o selo do gameplay (modo push + PUBLICAR)**: build 2257110 no ar (versão 2026.10.31-0046, https://rebocl-brank.itch.io/ceifalume) — push run 41151936756 ('✓ enviado'); status run 41152028164 → IGUAL, 0 novos, 0 modificados, 0 apagados, 13 iguais contra o build 2257110; MAS o run 41153867292 (modo uploads) lista só os uploads 19268311 e 19268322, ambos de 16/09, e a página abre 19268311 — cujo index.html NÃO tem o selo do gameplay (modo jogador). | conferência do servido (31/10/2026): index.js/index.pck/index.wasm IGUAIS ao repositório por sha256; index.html diferente (casca do itch).
- **o jogo no itch entregar o conteúdo do repositório (e o vídeo chegar lá)**: conferência do servido (sha256, arquivo por arquivo): index.html DIFERENTE, index.js IGUAL, index.pck IGUAL, index.wasm IGUAL — o jogo que o jogador recebe é o do repositório; o vídeo chega pelo GIF da descrição, que é servido por nós. o upload que a página abre é o 19268311 (16/09), NÃO o do canal html5; porém o conteúdo do jogo servido (index.js, index.pck, index.wasm) é byte a byte igual ao do repositório — medido em 31/10/2026 por sha256. A casca HTML é a do itch (injeta htmlgame.js e não tem o selo), e o vídeo chega ao visitante pelo GIF da descrição, que é servido por nós e agora leva o selo carimbado.
- **vídeo de gameplay no YouTube**: registro em posts/youtube-publicados.json

## Posts já no devlog público

- 1 semana de Ceifalume: o que vem na 0.2 (e eu quero sua opinião)
- 0.1 no ar: a fazenda não dorme
