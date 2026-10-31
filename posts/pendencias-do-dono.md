# Pendências do dono

Medido em 2026-10-31T00:56:53Z (o devlog do itch é público: dá para conferir de fora).

| item | estado | como |
| --- | --- | --- |
| publicar o devlog do gameplay no itch | esperando o dono | abrir itch/devlog-gameplay-bookmarklet.txt como favorito em qualquer página do itch, logado; ele descobre o formulário e posta o texto de posts/devlog-itch-gameplay.json |
| subir o build com o selo do gameplay (modo push + PUBLICAR) | feito | workflow enviar-itch, jogo=ceifalume, modo=push, confirmacao=PUBLICAR (o selo do vídeo já está em ceifalume/index.html) |
| vídeo de gameplay no YouTube | feito | nada: já publicado |

## Por que só o dono pode

- **publicar o devlog do gameplay no itch**: a Cloudflare do itch devolve 403 em /dashboard para IP de datacenter — medido em Ubuntu, macOS, Windows e com Chromium real (docs/sondagens/ITCH-403-CLOUDFLARE.json)

## Medições

- **publicar o devlog do gameplay no itch**: a página pública de devlog respondeu 200 e não tem o post do vídeo
- **subir o build com o selo do gameplay (modo push + PUBLICAR)**: build 2257110 no ar (versão 2026.10.31-0046, https://rebocl-brank.itch.io/ceifalume) — push run 41151936756 ('✓ enviado'); status run 41152028164 → IGUAL, 0 novos, 0 modificados, 0 apagados, 13 iguais contra o build 2257110
- **vídeo de gameplay no YouTube**: registro em posts/youtube-publicados.json

## Posts já no devlog público

- 1 semana de Ceifalume: o que vem na 0.2 (e eu quero sua opinião)
- 0.1 no ar: a fazenda não dorme
