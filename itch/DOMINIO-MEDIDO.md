# O que eu domino no itch.io — medido, não prometido

Última medição: 26/10/2026 · run `40411095611` (modo=auto) e sondas `40393236936`, `40393330688`, `40393413460`.

## Escreve de servidor (funciona)

| ação | como | prova |
|---|---|---|
| subir build (canal html5) | `butler push` com API key | `canal no itch: existe · versão d8f20fd4e6b2` — igual ao build local |
| conferir se o build publicado é o local | `butler status` | `✓ nada: build local e versão publicada são a mesma` |

## Lê de servidor (funciona)

| ação | prova |
|---|---|
| perfil, jogos, downloads, visitas | `api.itch.io/profile` e `/profile/games` → 200 |
| uploads do jogo | `games/5017404/uploads` → 200 |
| identidade pela chave antiga | `itch.io/api/1/<chave>/me` → 200 |

## Não escreve de servidor (porta fechada pelo itch, não por mim)

| ação | resposta medida |
|---|---|
| devlog / postagem | `api.itch.io/games/5017404/devlogs` → **404 invalid api endpoint** (não existe endpoint) |
| posts da conta | `api.itch.io/posts` e `/profile/posts` → **404** |
| editar página (título, resumo, descrição, gênero, capa) | `GET/POST itch.io/game/edit/5017404` → **403 desafio Cloudflare** |
| painel | `GET itch.io/dashboard` → **403 desafio** |
| login (mesmo com senha) | `GET/POST itch.io/login` → **403 desafio** |
| sessão por cookie | `dashboard/posts` → **403 "Please log in"** nas 3 combinações (cookie inteiro, só `itchio`, só `itchio_token`) |

## Conclusão

Domínio **parcial**: build sim, conteúdo não. Postagem, texto de página e devlog só
existem no navegador de quem tem a sessão — e o itch bloqueia o meu endereço de rede
antes de chegar em qualquer formulário.
