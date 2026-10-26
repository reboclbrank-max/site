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

## O que continua fora do alcance

- **Página do itch** (texto, capa, devlog, botão publicar): sem API no itch, por decisão deles.
- **Vídeo público por API**: projeto de API não auditado tem vídeo travado como privado pelo
  Google. Independe do token, do app ou do meu código.
- **Autorizar no Google**: exige sessão da conta dona. É o único passo que não é meu.
