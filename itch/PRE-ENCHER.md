# Modo navegador — controle da página do itch sem credencial nenhuma

O itch não tem API para escrever na página. A única superfície de escrita é o formulário
`/dashboard/game/<id>/edit`, que só aceita um navegador **logado**. Então existem só duas
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

1. Abra logado `https://itch.io/dashboard/game/5017404/edit`.
2. Clique no favorito **Ceifalume itch**.
3. Ele busca `posts/pagina-itch.json` (conteúdo desejado), mostra o antes/depois de cada campo
   e **só envia se você confirmar**. Campo `null` no JSON = não mexe.

Para **ler** o que está na página hoje (e me mandar), abra
`https://itch.io/dashboard/game/5017404/edit#ler` e clique no favorito: ele mostra o conteúdo
atual em uma caixa para copiar. Nada é gravado nesse modo.

## Travas

- Só age se a URL for `/dashboard/game/<números>/edit`. Em outra página, avisa e para.
- Só usa o formulário que tem `csrf_token` — se o itch mudar a página, ele aborta em vez de chutar.
- Nunca lê `document.cookie`; a sessão fica onde está.
- Só conversa com `raw.githubusercontent.com` (o JSON do repositório). Nenhum outro host.
- `11/11` contratos em `tools/testes-bookmarklet-itch.js`; a versão de instalar é derivada da
  fonte `tools/bookmarklet-itch.js` (`node tools/montar-bookmarklet.js --verificar`).
