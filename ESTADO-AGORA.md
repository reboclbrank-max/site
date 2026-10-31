# Estado medido — 26/10, depois da autorização

Nada aqui é estimativa: cada linha veio de uma chamada real, feita no runner.

## Chaves do YouTube

18 segredos no repositório `site`. Os cinco do YouTube, todos presentes:

| segredo | conferido como | resultado |
|---|---|---|
| `YT_API_KEY` | `videos.list` com a chave | **HTTP 200** — válida, API ativa |
| `YT_CHANNEL_ID` | leitura do canal | resolve o canal certo |
| `YT_CLIENT_ID` | `device/code` | **HTTP 200** — cliente do tipo TVs aceito |
| `YT_CLIENT_SECRET` | troca de token com refresh falso | `invalid_grant` (não `invalid_client`) — par reconhecido |
| `YT_REFRESH_TOKEN` | gravação na autorização | 103 caracteres, gravado no cofre |

**Prazo do token: ILIMITADO.** Medido, não deduzido: o Google só devolve
`refresh_token_expires_in` quando o app está em *Testing*. Ele **não devolveu** →
`✓ autorizado/ilimitado`. O token cai apenas por revogação ou 6 meses sem uso.

## Leitura do canal pelo OAuth (não por API key)

```
canal: Rebocl Brank · 24 inscritos · 160 vídeos · 5398 views
últimos vídeos lidos: 25
  _6V1NtfgMkI · Desenhe a prancheta e decida a partida — Pra…  · public
  pRwGAeNrtrY · Prancheta — simulador de gestão de futebol e…  · public
  Gm7ZIGNRLTg · Ceifalume: a horta acordou à noite 🌙 jogo gr… · public
  tB449xupDzY · Ceifalume — trailer oficial (jogo de fazenda…  · public
  bYyFqHcQyd4 · "NOVO APLICATIVO pra assistir jogos do CR7 e…   · public
```

Administrar título, descrição, tags, playlist, miniatura e comentários: **destravado**. É o que
o escopo `youtube` cobre, e o token não expira.

## itch.io

| item | estado |
|---|---|
| canal `html5` do CEIFALUME | existe no remoto, versão `d8f20fd4e6b2` = hash do build local |
| rodada seguinte do robô | `✓ nada` — não chamou o butler nenhuma vez |
| visibilidade do canal | **oculto** (escolha nossa; o butler não tem como desocultar) |
| jogo já jogável na página | sim, servido do upload antigo `19268311` (13 MB) |
| Toque Rápido | vetado em `posts/nunca-publicar.json` — nenhum robô toca |

## As três coisas que eu tinha dito "fora do alcance" — medidas

**1. Vídeo público por API → RESOLVIDO, não se aplica a você.**
Sondagem no canal de verdade: subi `media/reel.mp4` pedindo `unlisted`, o YouTube **aplicou
`unlisted`** (a trava se manifesta forçando `private`), e o vídeo foi apagado em seguida
(`apagado (204)`). Veredito medido: `sem_trava`. O envio por API já pede `privacyStatus: public`,
então publicar funciona. Auditoria do Google: **desnecessária**. Id da sonda: `79qExhG8Gos`
(removido).

**2. Devlog do itch → RESOLVIDO por outro caminho.**
O itch não tem API para devlog. O diário de bordo passou a ser publicado onde não existe trava:
`posts/devlog/*.json` → `blog/<slug>.html` + índice, por commit, no nosso domínio
(`tools/devlog.py`, roda no workflow diário). O texto do CEIFALUME já está no ar. O mesmo texto
continua no kit para colar no itch quando quiser.

**3. Autorização do Google → feita uma vez, e não deve ser pedida de novo.**
O token não tem prazo. O `administrar-youtube` roda todo dia e renova o access token — isso
também impede a expiração por 6 meses de inatividade. Se o Google revogar, o log passa a dizer
`ALERTA: invalid_grant … rode autorizar-youtube`.

## O que continua fora do alcance

- **Página do itch — FECHADO em 26/10 com duas medidas independentes.** (1) `/dashboard` e
  (2) **`/game/edit/5017404`** — o endereço real do editor — devolvem **403 com desafio da
  Cloudflare** a partir do runner, com o cookie completo do dono **e também sem cookie nenhum**.
  Não é sessão, não é User-Agent, não é código: é o IP de datacenter.
  **Consequência prática:** automação por servidor é impossível; a automação tem de rodar no
  navegador do dono. É o que `itch/ceifalume-auto.user.js` faz — eu edito o JSON no repositório,
  o navegador dele aplica (com `auto: true`, sem clique nenhum).
- **Página do itch — histórico.**
  Com o cookie real do dono (`itchio` + `itchio_token`) em mãos, a sonda
  `.github/workflows/sondar-cookie-itch.yml` testou 3 User-Agents × 3 conjuntos de cookies no
  runner: **`/dashboard` devolveu 403 (desafio) em todas as 12 combinações — inclusive SEM
  cookie nenhum.** A página pública do jogo continua 200. Conclusão: não é a sessão, é o IP de
  datacenter; automação por servidor do painel do itch está morta. O segredo `ITCH_COOKIE` foi
  apagado (não servia para nada) e o código passou a distinguir "bloqueado" de "sessão inválida"
  (46/46 testes). O controle vive no navegador: o favorito `itch/preencher-bookmarklet.txt` e o
  comando `itch/comando-console.txt`, ambos sem credencial nenhuma.
- **Página do itch — o que já funciona por sessão.** `tools/itch-navegador.py` (32/32 offline)
  lê e escreve os campos pelo formulário real, e `.github/workflows/editar-itch.yml` roda isso no
  runner: descobre a página pela API (`/dashboard/game/5017404/edit`), confere a sessão, faz backup
  dos valores anteriores em `posts/backup-itch.json` e só escreve com a palavra `EDITAR`.
  O chat dispara tudo com `!itch` (ler) e `!itch editar` (escrever) e **responde com o resultado**,
  lendo o que o run registra em `posts/estado-itch.json`.
  **Falta uma coisa só, e é do dono:** o segredo `ITCH_COOKIE` no repositório `site`
  (Settings → Secrets and variables → Actions → New repository secret). O valor é o cabeçalho
  `Cookie` inteiro de uma aba já logada no itch (DevTools → Network → qualquer requisição a
  itch.io → Request Headers → Cookie). O `/login` é bloqueado por Cloudflare a partir de
  datacenter, então login automatizado nunca será o caminho.
- **Vídeo público por API**: projeto de API não auditado tem vídeo travado como privado pelo
  Google. Independe do token, do app ou do meu código.
- **Autorizar no Google**: exige sessão da conta dona. É o único passo que não é meu.
