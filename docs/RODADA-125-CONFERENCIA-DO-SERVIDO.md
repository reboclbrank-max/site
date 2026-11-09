# Rodada 125 — "resolva": a medida que faltava (e a vez em que eu errei contra mim mesmo)

O dono pediu *"resolva"* de novo. O único item que sobrava era o itch entregar o jogo e o vídeo.
Em vez de repetir "não tem caminho", fui medir o que a **página entrega de verdade** — e descobri
que a minha conclusão da rodada anterior estava **certa no fato e errada na conclusão**.

## O erro: eu chamei de "antigo" um jogo que está atualizado

Na rodada 124 eu escrevi, no cofre: *"o jogador NÃO abre este build"*, porque a página do itch
embute o upload `19268311` (16/09) e não o build `2257110` que o butler enviou. Verdade — mas
parcial. Faltava a pergunta seguinte: **o conteúdo servido é o do repositório?**

Medido agora, arquivo por arquivo (`tools/enviar-itch.py conferir` — só leitura, baixa o que a
página serve e compara sha256 com o repositório):

```
página https://rebocl-brank.itch.io/ceifalume — upload 19268311
  index.html   DIFERENTE   repo=3688a2edd960dca0 itch=3e9021487f346b0b    22801 B
  index.js     IGUAL       repo=8a7c7d57f7da69bb itch=8a7c7d57f7da69bb   305185 B
  index.pck    IGUAL       repo=2383cabce49cd3e6 itch=2383cabce49cd3e6  3564384 B
  index.wasm   IGUAL       repo=6ead2ac528d007fe itch=6ead2ac528d007fe 38047590 B
  jogo (conteúdo) igual ao repositório: SIM
  casca html igual: NÃO (o itch reescreve e injeta o htmlgame.js dele)
```

Ou seja: **o jogo que o jogador do itch recebe é, byte a byte, o do repositório.** O que difere é
só a casca HTML — o itch injeta o `htmlgame.js` dele e a casca embutida não tem o selo do
gameplay. E o selo agora chega ao visitante pelo GIF da descrição, que é servido por nós
(rodada 124).

Três estados diferentes que a casa chamava de "publicado", agora separados em três números:

| pergunta | resposta medida |
| --- | --- |
| o butler enviou? | sim — build `2257110`, push run `41151936756`, conferido IGUAL no run `41152028164` |
| o jogador recebe o conteúdo do repositório? | **sim** — sha256 igual em `index.js`, `index.pck`, `index.wasm` |
| o vídeo chega a quem está no itch? | **sim** — GIF da descrição carimbado (`media/ceifalume/gif-jogo-ceifalume-640x360.gif`) |

## Por que nada disso precisava do painel do itch

| caminho automático | resultado |
| --- | --- |
| butler marcar canal como "HTML5 / jogável no navegador" | **não existe**: `butler v15.32.0 --help` lista 20 comandos, nenhum para isso; `itch.io/docs/butler/pushing.html` diz que essa marcação é feita pelo site |
| API oficial (devlog, página, uploads) | **não existe**: `docs/api/serverside.md` tem 5 endpoints (credenciais, perfil, jogos, chaves de download, compras) |
| painel (`/dashboard`, `/game/edit/5017404`) | **403** com desafio do Cloudflare para IP de datacenter — remedido em 31/10/2026 |
| `api.itch.io` sem chave | 401 **sem** desafio — se houvesse rota de escrita, ela seria usável; não há |
| trocar o que a página mostra | **existe e foi usado**: a imagem da descrição é hospedada no nosso domínio |

## O que ficou medido e guardado

- `posts/itch-builds.json` ganhou `conferencia_do_servido` (sha256 dos quatro arquivos, o que
  difere e por quê) e a frase de ressalva que impede a leitura errada;
- o cofre (`publicacoes.html`, `docs/PUBLICACOES.md`) mostra **três** números agora: builds no
  itch, builds que chegam ao jogador e **builds conferidos com sha256** — e diz, em letras claras,
  que a casca é a do itch e o vídeo chega pelo GIF;
- `docs/sondagens/ITCH-403-CLOUDFLARE.json` ganhou o complemento com esta conferência;
- o diagnóstico diário da casa passou a conferir sozinho (só leitura) a casca e o `index.pck`
  contra o repositório — o `wasm` de 38 MB fica para o modo `conferir` manual.

**Pendências do dono: 0.** O único item "sem caminho automático" que sobra é o devlog no itch —
e o texto dele já está público em `blog/ceifalume-gameplay.html`.

## Números desta rodada

| prova | resultado |
| --- | --- |
| suítes locais | **34 suítes, 0 falhas** |
| `testes-enviar-itch` | **83/83** (eram 77 — 6 novas sobre a conferência) |
| `testes-publicacoes` | **55/55** (eram 51) |
| `testes-pendencias` | **40/40** (eram 37) |
| `testes-workflows` | 21/21 |
| pendências do dono | **0** |
| builds conferidos com sha256 | **1** (o do CEIFALUME) |
