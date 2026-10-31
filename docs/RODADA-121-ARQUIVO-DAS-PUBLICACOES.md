# Rodada 121 — o cofre: toda publicação fica salva, com prova

Pedido do dono: *"deixar toda publicação que fez, salva"*. O que a casa publica estava espalhado
em seis lugares, cada um envelhecendo do seu jeito, sem um inventário único e sem prova de
integridade. "Salvo" sem impressão digital é só uma lista de nomes.

## `tools/publicacoes.py` → três arquivos

| artefato | para quem |
| --- | --- |
| `posts/publicacoes.json` | máquina: resumo + canais + vídeos + páginas + documentos + mídia |
| `docs/PUBLICACOES.md` | leitura em texto, versionada |
| `publicacoes.html` | página pública no site |

Cada item carrega **data, tamanho e sha256** (16 caracteres). O hash é o que permite provar
depois que o arquivo publicado não mudou — por isso há teste que recalcula o hash do disco e
compara com o inventário.

## O que ele inventariou agora

| o quê | quantos |
| --- | --- |
| ciclos de marketing | 103 |
| textos de post registrados | 96 |
| canais que publicaram de verdade | 5 (ntfy 103 · nostr 101 · bluesky 100 · threads 100 · instagram 33) |
| vídeos no YouTube com id real | 2 |
| páginas públicas | 20 |
| documentos | 10 |
| arquivos de mídia | 11 |

## Duas honestidades que o inventário força

1. **`VIDEO123` não é vídeo publicado.** O registro tem uma entrada de teste com id falso; ela
   aparece como *"sem id real"* e não entra na contagem de vídeos.
2. **`✅ commit falhou` não é publicação.** A contagem de "publicou" passou a exigir que o texto
   do resultado não contenha erro — antes, um ✅ com erro atrás inflava o número. Passos internos
   do ciclo (medir, aprender, vigia) aparecem na tabela **marcados como passo**, para não inflar
   "quantos canais publicam".

## Onde ele fica

- link no rodapé do **painel de marketing**, em **melhorias.html**, no bloco "Acompanhar" de
  **canais.html** e no **sitemap.xml**;
- gerado e commitado pelo `postagem-diaria` a cada ciclo.

## Provas

- `tools/testes-publicacoes.py` — **32/32**
- **32 suítes locais, 32 verdes**
- barreira do `postagem-diaria` e `diagnostico-da-casa` cobram a suíte nova
