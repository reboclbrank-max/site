# O que dá para automatizar de verdade — itch.io e YouTube

Medido em 26/10, não deduzido. Onde não dá, está dito por quê e qual é a saída.

## itch.io

**Estado medido em 26/10, com o robô trabalhando sozinho:**

```
rodada 1 (modo auto): decisão enviar → butler: Pushing 40.26 MiB (13 files) ✓ Build is now processing
rodada 2 (modo auto): canal no itch: existe · versão d8f20fd4e6b2 → ✓ nada
```

O canal `html5` do CEIFALUME foi criado pelo robô, sem clique, com a versão igual ao hash do
build. A rodada seguinte não chamou o butler nenhuma vez — é assim que se prova automação: a
segunda passada não faz nada. O canal está **oculto** de propósito (não aparece como download
antes de você ver); tirar do oculto é um clique na página de edição, e não tem API para isso.

| operação | automático? | como |
|---|---|---|
| subir / atualizar build | **sim, feito** | `tools/administrar-itch.py auto`, cron diário |
| saber se o build mudou | **sim** | hash dos 13 arquivos contra `size` do upload no itch |
| ler downloads, visitas, publicado | **sim** | `api.itch.io/profile/games` |
| criar página de jogo | **não** | o itch não tem endpoint; nunca teve |
| editar texto, capa, tags, preço | **não** | idem |
| publicar rascunho | **não** | é botão de interface |
| escrever devlog | **não** | idem |

Não é falta de chave nem de esforço: a API do itch é **só de leitura** — o único caminho de
escrita que existe no serviço é o `butler push`. E o itch já respondeu publicamente a pedido de
API de postagem: *"we don't provide APIs for people to post things since it may contribute to
spam that we have to moderate"* (itch.io, resposta a pedido de devlog API).

**O que o robô faz sozinho a cada dia:** lê o estado, compara com o build local e, se mudou,
sobe — em canal **oculto**, com `--if-changed`, com a versão no hash da build. Build igual não
gera nenhum comando. Jogo vetado (`posts/nunca-publicar.json`) nunca é tocado: o Toque Rápido
está lá, e a falha é fechada — sem lista, nada sobe.

**A parte que sobra para o navegador** tem texto pronto em `posts/kit-itch.md` (devlog escrito,
o clique do SharedArrayBuffer, o publish do rascunho). Se um dia isso virar automático, o único
caminho seria robô de navegador com a sua sessão logada — isso exige a sua senha/sessão e vai
contra o que o itch espera de automação. Não faço sem você pedir sabendo disso.

## YouTube

| operação | automático? | observação |
|---|---|---|
| ler inscritos, views, vídeos | **sim** | API key, já funciona |
| editar título, descrição, tags | **sim** | `tools/administrar-youtube.py auto`, cron diário |
| playlist, miniatura, comentários | **sim** | mesmo consentimento |
| **postar vídeo** | **sim, com duas travas reais** | ver abaixo |

As duas travas, e nenhuma delas é nossa:

1. **Vídeo enviado por API de projeto não auditado fica travado como privado.** Política do
   Google desde 28/07/2020: *"All videos uploaded via the videos.insert endpoint from unverified
   API projects created after 28 July 2020 will be restricted to private viewing mode."* Não há
   recurso; o vídeo tem de ser reenviado por serviço auditado ou pelo navegador.
   → Saída A: pedir a auditoria de conformidade (grátis, demora ~1 semana).
   → Saída B: enviar pelo navegador (mesma conta) e usar a API para administrar o resto.
2. **Consentimento em "Testing" mata o token em 7 dias.** Enquanto a tela de consentimento
   estiver em Testing, todo refresh token expira em 7 dias — automação morre toda semana.
   → Saída: publicar o app ("In production", grátis) **antes** de autorizar. Aí o token dura
   (só cai por revogação ou 6 meses sem uso).

O escopo pedido agora é `https://www.googleapis.com/auth/youtube` — **um consentimento só** que
cobre enviar e administrar. Antes era só `youtube.upload`, o que obrigaria um segundo
consentimento depois. Cota (desde 01/06/2026): `videos.insert` e `search.list` têm balde próprio de **100 chamadas
por dia cada**, e o resto divide 10.000 unidades. Volume não é limite — a trava do vídeo
privado é. Passo a passo com links: `GUIA-YOUTUBE.md`.

## O que continua fora do alcance de qualquer robô

- Publicar em rede social sozinho sem pedido explícito (regra da casa) — os robôs produzem e
  enfileiram.
- Criar conta, chave ou serviço pago.
- Adivinhar texto de post: sai do kit, nunca de improviso.

## O que só você pode fazer (e é uma vez)

1. **YouTube:** criar o cliente OAuth (TVs e dispositivos), publicar o app em "In production" e
   rodar `autorizar-youtube` → digitar o código. Depois disso, o resto é automático para sempre.
2. **itch:** nada obrigatório. O build sobe sozinho. Texto de página e devlog, quando quiser,
   com o texto já escrito no kit.
