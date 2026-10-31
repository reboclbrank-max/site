# Rodada 122 — o que estava travado foi resolvido e publicado

Pedido do dono: *"resolva e poste tudo"*. Três coisas estavam pendentes e todas as três
terminaram nesta rodada com prova medida em arquivo ou em run — nenhuma delas terminou em
"deve funcionar".

| pendência | estado |
| --- | --- |
| 404 da memória de gosto (`posts/memoria-de-gosto.json` não existia) | **resolvido** — arquivo criado por `juizo.garantir_memoria()` |
| vídeo do PRANCHETA no YouTube | **publicado** — https://youtu.be/YK2flr2JGz4 |
| build do CEIFALUME no itch.io (modo push) | **publicado** — build `2257110`, versão `2026.10.31-0046` |

## 1. A memória de gosto deixou de dar 404

`tools/juizo.py` agora chama `garantir_memoria()` antes de `apurar_resultado()`. A função cria
`posts/memoria-de-gosto.json` vazio (`_o_que_e` + `escolhas: []`) quando o arquivo não existe,
e `ler_memoria()` lê o que estiver lá. Nada é inventado: memória vazia é memória vazia, e o
arquivo agora existe (`escolhas: []`), então a página não cai mais em 404.

## 2. O YouTube recebeu o vídeo certo

O kit do YouTube preferia `media/reel.mp4` (1080x1350, vertical, 12 s) — formato errado para
YouTube. Agora `JOGOS["prancheta"]["video"]` aponta para `media/gameplay/prancheta-gameplay.mp4`
(1280x720, 59 s) e o reel virou `video_reserva`. O `aviso_formato` só aparece para vertical que
não seja 9:16, e o teste mede as dimensões do arquivo de reserva em vez de depender da escolha
do dia (teste que testa a escolha quebra quando a escolha melhora).

Publicação (run `41151323257`, success): `✓ publicado: https://youtu.be/YK2flr2JGz4`.
`posts/youtube-publicados.json` passou a ter **4** vídeos.

## 3. O itch.io recusou duas vezes e agora aceita — e o motivo está medido

Primeira tentativa (run `41151339470`): o run saiu **verde** e nada foi enviado. Duas falhas
distintas, as duas corrigidas:

1. **`--hidden` em canal existente.** O log do butler diz exatamente:
   `itch.io API error (400): /wharf/builds: hidden can only be set when creating a new channel`.
   O itch só aceita `hidden` ao *criar* canal. Além disso esconder o build contradiz o pedido: o
   build carrega o selo que abre o vídeo de gameplay e precisa estar visível. `--hidden` saiu.
2. **run verde com erro no envio.** O passo usava `python3 tools/enviar-itch.py push ... | tee`:
   pipeline sem `pipefail` devolve o status do `tee`, não o do envio. O passo agora roda com
   `shell: bash -o pipefail {0}`, então recusa do itch vira run vermelho em vez de falso-verde.

Terceira falha, achada na verificação (run `41151770746`): depois do push, o `push-preview` —
a única comparação confiável com o itch, porque `butler status` e `butler diff` não comparam
pasta local com build no ar — respondia **"1 apagado"**. Causa: o carimbo de versão era escrito
*dentro* da pasta enviada, então o build no ar tinha um arquivo a mais que o repositório. O
carimbo agora vive fora do pacote (`VERSAO_BUILD` no ambiente ou `posts/versao-build.json`), a
versão continua indo como `--userversion`, e a pasta enviada é a pasta do repositório arquivo por
arquivo — é isso que permite o status dizer a verdade.

### Prova de que o build está no ar

- push: run `41151936756` → `build carimbado: 2026.10.31-0046`, `versão do envio: 2026.10.31-0046`,
  `✓ enviado para rebocl-brank/ceifalume:html5`.
- conferência (somente leitura): run `41152028164` →
  `IGUAL: o itch já tem exatamente esta pasta (nada a enviar) — 0 novos, 0 modificados, 0 apagados, 13 iguais (contra o build 2257110)`.
- link do jogo: https://rebocl-brank.itch.io/ceifalume

## 4. O cofre passou a guardar build, não só texto

`posts/itch-builds.json` (novo) registra o build com id, versão, número de arquivos, data, link e
**prova** (os runs do push e da conferência). `tools/publicacoes.py` ganhou `builds_do_itch()`:
build só conta como publicado quando tem id **e** prova; build vazio ou sem prova não conta. O
item aparece no resumo (`builds_no_itch`), no `docs/PUBLICACOES.md` e na página `publicacoes.html`.

## Números desta rodada

| prova | resultado |
| --- | --- |
| `tools/testes-publicacoes.py` | **42/42** (eram 32 — 10 novas sobre build) |
| `tools/testes-enviar-itch.py` | **68/68** (eram 64) |
| `tools/testes-kit-youtube.py` | 34/34 |
| `tools/testes-juizo.py` | 60/60 |
| `tools/testes-workflows.py` | 11/11 |
| varredura das 32 suítes locais | **0 falhas** |
| vídeos no YouTube (id real) | 2 |
| builds no itch.io (id real + prova) | 1 |
| canais que publicam de verdade | 5 |
