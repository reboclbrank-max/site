# Pendências do dono

Medido em 2026-10-31T01:07:33Z (o devlog do itch é público: dá para conferir de fora).

| item | estado | como |
| --- | --- | --- |
| publicar o devlog do gameplay no itch | sem caminho automático | nada obrigatório: o conteúdo já chega ao jogador pelo build, pelo blog e pelo YouTube. Se quiser a cópia editorial no itch: abrir itch/devlog-gameplay-bookmarklet.txt como favorito em qualquer página do itch, logado — ele acha o formulário e posta posts/devlog-itch-gameplay.json |
| subir o build com o selo do gameplay (modo push + PUBLICAR) | feito | workflow enviar-itch, jogo=ceifalume, modo=push, confirmacao=PUBLICAR (o selo do vídeo já está em ceifalume/index.html) |
| vídeo de gameplay no YouTube | feito | nada: já publicado |

## Por que só o dono pode

Nada. Nenhuma pendência depende de clique do dono nesta medição.

## Sem caminho automático (medido, não pedido)

- **publicar o devlog do gameplay no itch** — a página pública de devlog respondeu 200 e não tem o post; o painel do itch responde 403 (Cloudflare) para IP de datacenter e a API oficial não tem endpoint de devlog — medido em 31/10/2026
  - sondagem: `docs/sondagens/ITCH-DEVLOG-SEM-CAMINHO-AUTOMATICO.json`
  - chega ao jogador por: build no ar (2257110): ceifalume/index.html leva o selo ▶ gameplay com instruções
  - chega ao jogador por: blog/ceifalume-gameplay.html (site da casa)
  - chega ao jogador por: https://youtu.be/GuE7af6dYo8 (YouTube)

## Medições

- **publicar o devlog do gameplay no itch**: a página pública de devlog respondeu 200 e não tem o post; o painel do itch responde 403 (Cloudflare) para IP de datacenter e a API oficial não tem endpoint de devlog — medido em 31/10/2026
- **subir o build com o selo do gameplay (modo push + PUBLICAR)**: build 2257110 no ar (versão 2026.10.31-0046, https://rebocl-brank.itch.io/ceifalume) — push run 41151936756 ('✓ enviado'); status run 41152028164 → IGUAL, 0 novos, 0 modificados, 0 apagados, 13 iguais contra o build 2257110
- **vídeo de gameplay no YouTube**: registro em posts/youtube-publicados.json

## Posts já no devlog público

- 1 semana de Ceifalume: o que vem na 0.2 (e eu quero sua opinião)
- 0.1 no ar: a fazenda não dorme
