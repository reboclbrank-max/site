# Postar devlog no itch (1 clique)

O texto da postagem mora em `posts/devlog-itch.json` (título + corpo). Eu escrevo e
publico ali; o envio acontece no seu navegador, onde a sessão do itch está viva.

## Instalar (uma vez)
1. Abra e copie tudo: https://raw.githubusercontent.com/reboclbrank-max/site/main/itch/devlog-bookmarklet.txt
2. **Ctrl+D** → nome `Postar devlog` → **URL:** apague e cole a linha → salvar.

## Usar (sempre)
1. Abra `https://itch.io/game/edit/5017404` (qualquer aba do jogo serve).
2. Clique no favorito **Postar devlog**.
   Ele procura a aba *Devlog*, acha o formulário de criar postagem, preenche título e
   corpo e envia. No fim aparece "Devlog postado no itch ✅".

## Travas
- Só age em `itch.io` e só depois de você ter aberto a página de edição uma vez (guarda o id do jogo).
- Não chuta nome de campo: lê os campos do formulário real e reenvia todos (csrf incluído), trocando só título e corpo.
- Se não achar campo de texto, **não envia nada** e diz o motivo.
- Guarda a versão aplicada no navegador: a mesma versão não é postada duas vezes.
- Nunca lê cookie; o texto vem de `raw.githubusercontent.com` do repositório.

## Por que não é automático de servidor
Medido em 26/10/2026: `https://itch.io/game/edit/5017404` responde **403 com desafio da
Cloudflare** para datacenter, com cookie e sem cookie; e a API **não tem** endpoint de
devlog (`api.itch.io/games/5017404/devlogs` → 404 `invalid api endpoint`). O formulário
só abre no navegador do dono — por isso o clique mora aí.

## Medição
`python3 tools/testes-devlog-navegador.py` → **11/11** (Chromium; itch simulado).
