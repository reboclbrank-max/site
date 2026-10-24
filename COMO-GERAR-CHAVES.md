# Como gerar as chaves que faltam — itch.io e YouTube

> **STATUS 24/10/2026: RESOLVIDO.** As duas leituras estão ligadas e rodando em
> produção. A chave do itch já existia em `base/ferramentas/chaves.md` e foi para o
> secret `ITCH_API_KEYS`; a chave do YouTube foi recebida do dono e está em
> `YT_API_KEY`. Ver "Resultado medido" no fim deste arquivo. O passo a passo abaixo
> continua válido para quando for preciso gerar ou trocar uma chave.

> O código já está pronto e testado. Falta **só** você gerar as chaves e colar nos
> cofres do GitHub. Enquanto elas não existirem, o medidor escreve
> `NAO_OBSERVAVEL` (não escreve zero, não inventa número).

## Antes de tudo: onde as chaves são coladas

Todas vão em **um lugar só**:

`https://github.com/reboclbrank-max/site/settings/secrets/actions`

Clique em **New repository secret** → cole o **nome exato** da tabela → cole o valor →
**Add secret**. Nunca cole chave em arquivo do repositório, em issue, em chat ou em
commit. Depois de salva, o GitHub não mostra mais o valor — se perder, gera de novo.

| Nome do secret | De onde vem | Obrigatório? |
|---|---|---|
| `ITCH_API_KEYS` | itch.io (uma chave por conta) | sim, para medir download |
| `YT_API_KEY` | Google Cloud Console | sim, para medir inscritos |
| `YT_CHANNEL_ID` | já sei qual é: `UCQdxKtfRnqNLd1ZOs9B6eaQ` | opcional (tem padrão no código) |

---

# 1. itch.io — 1 minuto, a mais fácil

Você tem **duas contas** publicando (`reboclbrank-max` e `rebocl-brank`). A API do itch
só devolve os jogos da conta dona da chave, então precisa de **uma chave por conta**.

### Passo a passo (repita para cada conta)

1. Entre na conta no itch.io.
2. Abra direto: **https://itch.io/user/settings/api-keys**
   (ou: foto de perfil → *Settings* → na barra da esquerda, *API keys*)
3. O itch pede sua senha de novo. Digite.
4. Clique em **Generate new API key**.
5. Aparece uma linha nova na tabela com *Source* = `web`. Clique em **View**.
6. Copie o valor que aparece.

### Onde colar

- Uma conta só: cole essa chave em `ITCH_API_KEYS`.
- As duas: cole as duas **na mesma** variável, separadas por vírgula e **sem espaço**:

```
chaveDaPrimeiraConta,chaveDaSegundaConta
```

Se um dia gerar de novo, é só substituir o secret. Nada mais muda no código.

### O que isso liga

Downloads e visitas por jogo, com o total somado das contas. É a leitura que transforma
a meta **100 downloads** de `NAO_OBSERVAVEL` em número de verdade.

> **Importante:** essa chave dá acesso amplo à conta (é "sem escopo" por decisão do
> próprio itch). Se quiser reduzir risco, crie uma **conta separada** só para leitura e
> adicione ela como membro com permissão nos jogos — mas para o nosso caso (só ler
> contadores) a chave normal resolve.

### O que o itch **não** tem

Seguidores. O pedido de `my-followers` está aberto no fórum do itch desde 2020 e nunca
foi implementado. Por isso a meta `itch_seguidores=10` vai continuar `NAO_OBSERVAVEL`
para sempre — e isso está escrito no placar, não escondido.

---

# 2. YouTube — 5 minutos, e é de graça

Aqui tem uma pegadinha que vale explicar: **existem duas coisas diferentes** com nomes
parecidos.

| Objetivo | O que precisa | Dificuldade |
|---|---|---|
| **Ler** inscritos, vídeos, shorts (a meta) | *chave de API* | fácil — 5 min |
| **Enviar** vídeo/short automaticamente | *OAuth* com você logado | difícil — exige autorização manual |

Vamos fazer a primeira agora, que é o que falta para a **meta de 40 inscritos** sair do
`NAO_OBSERVAVEL`. A segunda dá para fazer depois, se você quiser que a casa publique
vídeo sozinha.

### Passo a passo

1. Entre em **https://console.cloud.google.com** com a conta Google que é dona do canal.
2. No topo, clique no seletor de projeto → **New Project** → nome `rebocl-marketing` →
   **Create**. (Não pede cartão, não cobra nada.)
3. Confirme que o projeto novo está selecionado no topo.
4. Abra **https://console.cloud.google.com/apis/library/youtube.googleapis.com** →
   **Enable** (ativar).
5. Vá em **https://console.cloud.google.com/apis/credentials** → **Create credentials**
   → **API key**.
6. Copia a chave que aparece (começa com `AIza…`).
7. **Não feche ainda:** na mesma tela, clique em **Edit** na chave e, em *API
   restrictions*, marque **Restrict key** → escolha **YouTube Data API v3** → **Save**.
   Isso garante que, se a chave vazar, ela não serve para mais nada.
8. Cole em `YT_API_KEY`.

### O que isso liga

Inscritos, total de vídeos, visualizações e **quantos shorts** existem (o medidor lê a
playlist de envios e conta os vídeos de até 61 segundos). Custo de cota: 3 de 10.000
unidades por dia — irrelevante.

O ID do canal já está no código de propósito (`UCQdxKtfRnqNLd1ZOs9B6eaQ`, o mesmo que
está linkado no site). Só preencha `YT_CHANNEL_ID` se um dia trocar de canal.

### Se você quiser upload automático de shorts depois

Aí é OAuth: precisa criar um *OAuth client* (Desktop), baixar o JSON, rodar um script
uma vez no seu computador, autorizar no navegador e guardar o `refresh_token` nos
secrets. Dá para fazer — mas são ~15 minutos, exige sua presença no navegador e é a
única parte que não posso executar por você. Peça quando quiser, que eu preparo o script
e as instruções exatas.

---

# 3. O que a casa vai passar a saber no minuto seguinte

Depois de salvar os dois secrets, rode o diagnóstico:

`https://github.com/reboclbrank-max/site/actions/workflows/diagnostico-da-casa.yml` →
**Run workflow** → **Run workflow**

Em ~2 minutos o placar fica assim, com números no lugar dos `NAO_OBSERVAVEL`:

| meta | alvo | passa a mostrar |
|---|---|---|
| Instagram: posts | 30 | 15 |
| Instagram: seguidores | 50 | 0 |
| Bluesky: seguidores | 50 | 34 |
| YouTube: inscritos | 40 | número real |
| YouTube: shorts | 4 | número real |
| itch: downloads | 100 | número real |
| itch: seguidores | 10 | segue `NAO_OBSERVAVEL` (o itch não fornece) |

Nada disso publica, nada faz commit, nada gasta cota de repositório privado.

> Resumo em uma frase: **itch = 1 minuto e resolve downloads; YouTube = 5 minutos e
> resolve inscritos.** O resto do trabalho já está no repositório.

---

# Resultado medido em 24/10/2026 (produção, secrets reais)

| leitura | valor | o que significa |
|---|---|---|
| itch: downloads | **45** (Ceifalume 40 · Prancheta 5) | linha de partida em 13/10 era 44 |
| itch: visitas | **175** | ~3,9 visitas por download |
| YouTube: inscritos | **24** | era 24 em 13/10 — onze dias, zero líquido |
| YouTube: vídeos | **160** | média de 33 visualizações por vídeo |
| YouTube: shorts | **5** (de 100 conferidos) | meta de 4 shorts: **ATINGIDA** |
| Instagram: seguidores | **0** (15 posts) | 13 dos 15 posts sem nenhum engajamento |
| Bluesky: seguidores | **34** | 338 posts publicados |

A leitura do itch cobre uma conta só: a chave de `reboclbrank-max` devolve **os dois
jogos**, porque o itch publica sob o subdomínio `rebocl-brank.itch.io`. Não é preciso
gerar uma segunda chave. Os links do site (`reboclbrank-max.itch.io/...`) funcionam:
o itch responde nos dois endereços.

## Problema de segurança encontrado no teste da chave do YouTube

A chave responde à API do YouTube **e** ao Geocoding do Google Maps. Ou seja: ela não
está restrita, e uma chave sem restrição pode ser usada em qualquer API habilitada no
projeto, com a cobrança caindo na conta do dono.

**Corrigir (1 minuto):** https://console.cloud.google.com/apis/credentials → clique na
chave → *API restrictions* → **Restrict key** → marque só **YouTube Data API v3** →
**Save**.

**Recomendação adicional:** a chave foi digitada em conversa, então o valor já saiu do
cofre. Depois de restringir, o mais seguro é **gerar uma nova** no mesmo painel,
substituir o secret `YT_API_KEY` em `site/settings/secrets/actions` e apagar a antiga.
Enquanto a restrição existir, o risco fica limitado à cota gratuita do YouTube.

## Onde a chave do YouTube está guardada (ordem do dono, 24/10/2026)

O dono pediu: *"pode ficar com a chave completa para usar, deixe salvo dentro do
repositório para não perder"*. Ela está em **dois lugares**, e nenhum deles é público:

| lugar | serve para |
|---|---|
| `base/ferramentas/cofare.json` (repo **privado**) | cópia de segurança, junto das outras chaves da casa |
| `site` → Settings → Secrets → `YT_API_KEY` | é a cópia que o robô realmente usa |

**Por que não no `site`:** o `site` é um repositório **público**. Qualquer chave
commitada ali fica vísivel para o mundo em segundos — robôs varrem o GitHub procurando
exatamente o padrão `AIza…`. Salvar lá não seria "não perder", seria entregar a chave
para estranhos e assumir o risco de cobrança na conta do dono. O `base` é privado e já
guarda as outras chaves desde 17/09, então é o lugar certo para a cópia de segurança.

**Consequência a ter em mente:** se o repositório `base` um dia virar público, **todas**
as chaves dele vazam de uma vez. Isso está escrito no próprio cofre.
