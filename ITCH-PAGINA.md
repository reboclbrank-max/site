# Página do itch.io — o que eu controlo e o que não

## O que a "conexão com o GitHub" é, medido

Não existe integração GitHub↔itch que edite página. O que existe, conferido agora:

| verificação | resultado |
|---|---|
| GitHub Apps instalados / integração no repo | **nenhuma** (`0` hooks, API sem instalação) |
| credencial do itch no GitHub | `ITCH_API_KEYS` nos repos `site` e `motor` |
| o que essa credencial faz | lê jogos/uploads **e sobe build** (butler) — provado |
| o que ela **não** faz | editar texto, capa, tags, preço; publicar rascunho; escrever devlog |

`/credentials/info` responde só `{"type":"api_key"}` — escopo nesse endpoint existe para token
JWT, não para API key. Ou seja: a credencial não declara poder de escrita porque **não há** esse
poder a declarar. O butler autentica por outro caminho e é o único canal de escrita do serviço.

## O que eu controlo dentro da página, sem login

A descrição do CEIFALUME no itch carrega uma imagem **do nosso domínio**:

```
<img src="https://reboclbrank-max.github.io/site/media/ceifalume/gif-jogo-ceifalume-640x360.gif">
```

Conferido: **HTTP 200, 3.054.658 bytes, image/gif**. Ou seja, essa mídia é minha: se eu trocar o
arquivo no repositório, a página do itch muda sem ninguém tocar no itch. Junto com o build
(o iframe do jogo) e os downloads, é a parte viva da página que já é automática.

O que sobra na interface deles: título, texto, tags, capa, screenshots, botão publicar, devlog.

## Kit de colar — os arquivos já estão prontos no repositório

**Capa** (o itch pede 630×500 ou maior):

```
itch/capa-630x500.png        → 630×500 · 436 KB
```

**Screenshots** (ordem sugerida, 1280×720, arraste nesta sequência):

```
1. itch/shots/titulo.png     → 1280×720 · 1.163 KB   (tela de título, abre bem)
2. itch/shots/inicial.png    → 1280×720 ·   817 KB   (primeira horta)
3. itch/shots/meio.png       → 1280×720 ·   741 KB   (meio do jogo)
4. itch/shots/cheio.png      → 1280×720 ·   838 KB   (plantação cheia)
```

**Campos de texto:**

| campo | valor |
|---|---|
| Title | `Ceifalume` |
| Short description / tagline | `Fazenda noturna e aconchegante: plante, colha e negocie à luz da lanterna — o preço muda a cada dia.` |
| Classification | `Game` |
| Kind of project | `HTML` (roda no navegador) + mantenha o upload Android |
| Pricing | `No payments` (grátis) |
| Tags | `godot`, `farming`, `idle`, `portuguese`, `singleplayer`, `2d`, `cozy` |
| Genre | `Simulation` |
| Release status | `Released` |
| Plataformas | marcar **HTML5** e **Android** |

**Descrição** — mantém a imagem do nosso domínio no topo e o texto que já está lá. Se quiser
trocar o gif, é só me dizer: eu substituo o arquivo e a página muda sozinha.

## Por que isto continua sendo um clique seu

O itch não tem endpoint de edição de página — não é falta de chave, é decisão deles ("we don't
provide APIs for people to post things"). A única alternativa técnica seria robô de navegador com
a sua sessão logada, e isso exige a sua senha. Não é bloqueio do meu lado: é a fronteira do
serviço.

Nada disso bloqueia nada: o build sobe sozinho, o devlog sai no nosso domínio, e a página
funciona como está.
