# Rodada 120 — as melhorias agora têm endereço público

Até aqui, dez rodadas de melhoria estavam **só** em `docs/*.md` e no painel de marketing. Quem
abre o site não via nada disso — e melhoria invisível é quase promessa: não dá para discordar
dela, nem conferir.

## `melhorias.html` — gerada do próprio repositório

`tools/melhorias.py` monta a página a cada ciclo com números tirados dos artefatos que a casa
já produz sozinha:

| cartão | de onde vem |
| --- | --- |
| rodadas documentadas | `docs/RODADA-*.md` (título + link; o texto **não** é copiado) |
| suítes de teste / quantas na barreira | `tools/testes-*.py` + `postagem-diaria.yml` |
| ciclos registrados · canais publicando | `posts/log.md` |
| passos que adaptam · rituais · cegos | `posts/auditoria-inteligencia.json` |
| decisões com número · recusas · ignorâncias | `posts/decisoes.json` |
| repetição de texto desde o conserto | `posts/auditoria-inteligencia.json` |
| gosto medido no feed × declarado | `posts/perfil-de-gosto.json` |
| o que ainda depende do dono | `posts/percebido.json` |

Regra de honestidade embutida: valor ausente vira **"não medido"**, nunca `0`. O texto dos
documentos não é duplicado — copiar criaria duas versões, e a que envelhece é sempre a pública.

## Onde ela aparece

- link no rodapé do **painel do marketing** e no bloco "Acompanhar" de **canais.html**;
- no **sitemap.xml**;
- gerada e commitada pelo `postagem-diaria` a cada ciclo (junto com o painel).

## Provas

- `tools/testes-melhorias.py` — **30/30** (números batem com os artefatos, "não medido" no lugar
  de zero, rodadas em ordem decrescente, nenhuma cópia de texto, escrita atômica, links e
  encaixe no ciclo)
- **31 suítes locais, 31 verdes**
- barreira do `postagem-diaria` e `diagnostico-da-casa` cobram a suíte nova
