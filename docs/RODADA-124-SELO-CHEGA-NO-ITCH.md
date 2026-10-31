# Rodada 124 — "resolva": o selo do gameplay agora chega a quem abre o jogo no itch

O dono pediu *"resolva"* sobre o único item que sobrava. Antes de responder "não tem como", medi
de novo — e achei duas coisas: uma **falha minha de medição** e um **caminho que ninguém tinha
usado**.

## 1. O "publicado" era falso-verde, e isso é meu

Na rodada 122 eu disse "build no ar (2257110)". Estava no ar **num canal do itch** — e isso não é
a mesma coisa que chegar ao jogador. Medido agora, com dois modos novos de leitura (nenhum
publica nada):

| medida | resultado |
| --- | --- |
| página do jogo (`https://rebocl-brank.itch.io/ceifalume`) | abre o upload **19268311** (`ceifalume-0.1-web.zip`, de **16/09**) |
| `index.html` desse upload | 21.639 bytes — **não tem** o selo do gameplay |
| uploads do jogo pela API oficial (run `41153867292`) | só dois: `19268311` (web, 13,0 MB) e `19268322` (APK, 83,6 MB), os dois de 16/09 |
| canal do build enviado | `html5` — existe no butler, **não é** o upload que a página abre |

Causa: um upload só vira "HTML5 / jogável no navegador" quando alguém marca isso **no painel**
(`docs/butler/pushing.html` diz isso em letras claras: *"Tagging a channel as 'HTML5 / Playable in
browser' needs to be done from the itch"*). O painel responde **403 com desafio do Cloudflare**
para IP de datacenter — remedido hoje, em `/dashboard` e em `/game/edit/5017404`.

Então: `posts/itch-builds.json` passou a separar **"está no canal"** de **"chega ao jogador"**.
O cofre (`publicacoes.html`, `docs/PUBLICACOES.md`) agora mostra, em letras claras, que o jogador
**não** abre o build enviado, e por quê. Um número que mentia virou dois números que não mentem.

## 2. O caminho que existe: a imagem da página é nossa

A descrição do jogo no itch — escrita meses atrás — começa com uma imagem **hospedada no nosso
domínio**:

```html
<img src="https://reboclbrank-max.github.io/site/media/ceifalume/gif-jogo-ceifalume-640x360.gif">
```

Quem visita a página do itch no navegador vê esse GIF. O conteúdo dele é servido por nós, então
trocá-lo **é** publicação nossa — e é o único caminho automático para o vídeo do gameplay chegar a
quem está no itch. `tools/gif-com-selo.py` carimba, em todos os 140 quadros, uma faixa discreta no
canto inferior direito:

```
▶ gameplay: youtu.be/GuE7af6dYo8
```

Três cuidados que o código cobra (e os testes provam):

- **o endereço não é digitado no código**: vem do selo de `ceifalume/index.html`. Se o vídeo mudar
  no build, a imagem muda junto;
- **idempotente**: sempre carimba a partir da fonte intocada (`…-fonte.gif`). Isso não é teórico —
  na primeira versão o script carimbava o carimbo e cada rodada perdia qualidade (2,91 MB → 2,29 →
  2,16 MB, medido hoje). Duas rodadas seguidas agora dão **o mesmo md5**;
- **não pesa a página**: com ffmpeg (paleta de 128 cores) o GIF novo ficou **menor** que o
  original — 2,29 MB contra 2,91 MB. Sem ffmpeg, a reserva (Pillow) geraria ~16 MB e o script
  **recusa** em vez de entregar isso a um visitante. O teto vale para os dois caminhos.

O GIF entra no cofre com sha256, porque passou a ser coisa publicada; a fonte intocada não entra.

## O que continua fora do alcance automático — com a prova

| pergunta | resposta |
| --- | --- |
| API oficial tem endpoint de devlog/post? | **não** — `docs/api/serverside.md` do próprio itch lista 5 endpoints (credenciais, perfil, jogos, chaves de download, compras); `api.itch.io` responde 401 **sem** desafio de Cloudflare |
| por que o itch não abre isso? | *"Generally we don't provide APIs for people to post things since it may contribute to spam"* (`itch.io/t/2097903`) |
| dá para marcar o canal como HTML5 por fora? | não: só pelo painel, que dá 403 para servidor |

Sondagem registrada em `docs/sondagens/ITCH-DEVLOG-SEM-CAMINHO-AUTOMATICO.json`.
**Pendências do dono: 0.** Nada aqui depende de clique; os dois itens sem caminho automático
aparecem no relatório com a medição, não com uma tarefa.

## Números desta rodada

| prova | resultado |
| --- | --- |
| suítes locais | **34 suítes, 0 falhas** (era 33 — entrou `testes-gif-com-selo`) |
| `testes-gif-com-selo` | 26/26 (novo) |
| `testes-publicacoes` | 51/51 (eram 48) |
| `testes-pendencias` | 37/37 (eram 31) |
| `testes-enviar-itch` | 77/77 (eram 68) |
| `testes-workflows` | 21/21 |
| GIF servido ao itch | 640x360, 140 quadros, **2,29 MB** (era 2,91 MB), selo em todos |
| pendências do dono | **0** |
| builds que chegam ao jogador | 0 (medido, com o motivo — antes era "1", inventado) |
