# Modo navegador — controle da página do itch sem credencial nenhuma

O itch não tem API para escrever na página. A única superfície de escrita é o formulário
`/game/edit/<id>`, que só aceita um navegador **logado**. Então existem só duas
formas de escrever:

| caminho | precisa de | expira? | quem aperta o botão |
|---|---|---|---|
| segredo `ITCH_COOKIE` + workflow | cookie de sessão copiado | **sim**, um dia (sem prazo publicado) | eu, sozinho |
| **modo navegador** (este documento) | você estar logado | **não**, não há credencial para expirar | você, um clique |

O modo navegador não guarda nada: ele usa a sessão viva da sua aba, preenche o formulário e
pede confirmação. Não há token para copiar, para vazar ou para vencer.

## Instalar (uma vez, 30 segundos)

1. Abra `itch/preencher-bookmarklet.txt` neste repositório e copie **a linha inteira**
   (começa com `javascript:`).
2. No navegador, crie um favorito (Ctrl+D) com:
   - **Nome:** `Ceifalume itch`
   - **URL:** cole a linha copiada
3. Deixe esse favorito na barra de favoritos.

## Usar

1. Abra logado `https://itch.io/game/edit/5017404`.
2. Clique no favorito **Ceifalume itch**.
3. Ele busca `posts/pagina-itch.json` (conteúdo desejado), mostra o antes/depois de cada campo
   e **só envia se você confirmar**. Campo `null` no JSON = não mexe.

Para **ler** o que está na página hoje (e me mandar), abra
`https://itch.io/game/edit/5017404#ler` e clique no favorito: ele mostra o conteúdo
atual em uma caixa para copiar. Nada é gravado nesse modo.

## Travas

- Só age se a URL for `/dashboard/game/<números>/edit`. Em outra página, avisa e para.
- Só usa o formulário que tem `csrf_token` — se o itch mudar a página, ele aborta em vez de chutar.
- Nunca lê `document.cookie`; a sessão fica onde está.
- Só conversa com `raw.githubusercontent.com` (o JSON do repositório). Nenhum outro host.
- `11/11` contratos em `tools/testes-bookmarklet-itch.js`; a versão de instalar é derivada da
  fonte `tools/bookmarklet-itch.js` (`node tools/montar-bookmarklet.js --verificar`).

## Entrar com um clique (quando a sessão cair)

A partir de datacenter o itch **não** deixa logar: medido em 26/10, `POST /login` → 403 e um
`fetch` de dentro da própria origem do itch → 403 `Just a moment…`. O desafio do Cloudflare
fecha antes de existir formulário. Por isso a senha só serve em um lugar: o seu navegador.

- Favorito **"Ceifalume entrar"** (`itch/entrar-bookmarklet.txt`): abra `https://itch.io/login`,
  clique e ele preenche usuário e senha e envia. Na primeira vez ele pergunta; se você autorizar,
  guarda no `localStorage` do próprio itch.io para entrar com um clique nas próximas.
- Para apagar o que foi guardado: abra `https://itch.io/login#esquecer` e clique no favorito.
- **Nenhuma senha entra no repositório**: um dos 17 contratos falha se aparecer senha literal
  em qualquer uma das fontes ou linhas derivadas.

Depois de entrar, o `ITCH_COOKIE` do Actions pode ser renovado (copiando `itchio_token`) **ou**
você simplesmente usa o favorito de preencher, que não precisa de segredo nenhum.
