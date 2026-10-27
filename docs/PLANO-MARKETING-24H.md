# Plano de marketing 24h — arquitetura medida

> Escrito em 26/10/2026. Cada afirmação abaixo ou é medida nesta sessão, ou está marcada
> como **não medida** com o teste que falta. Número inventado não entra neste arquivo.

## 1. O que "24h" pode significar de verdade

| mecanismo | roda 24h? | limite real |
|---|---|---|
| GitHub Actions (cron) | sim | o cron é **melhor esforço**: dispara a cada ~15 min, mas pode atrasar; não é "a cada segundo" |
| Actions sem custo | sim | repositório **público** = minutos ilimitados; concorrência limitada |
| Navegador logado do dono | não | só quando o dono abre; não faz parte do ciclo |
| itch.io (escrita de conteúdo) | **não** | Cloudflare devolve 403 ao IP de datacenter — medido em `/login`, `/dashboard`, `/game/edit/<id>` |
| YouTube (API) | sim | `videos.insert` 200, `videos.update` 200, `thumbnails.set` 200, comentários 200 (force-ssl) |

Conclusão honesta: **24h sim, "a cada segundo" não.** O ciclo roda em pulsos de ~15 minutos
dentro da janela 09h–22h (Brasília) e em pulsos de medição/pesquisa fora dela.

## 2. As cinco camadas (e o que cada uma faz em cada pulso)

```
        ┌──────────────────────────────────────────────────────────┐
        │  ORQUESTRADOR  (a cada 15 min, com estado no repositório)│
        └───────────────┬──────────────────────────────────────────┘
                        │ decide UMA ação por pulso, por prioridade
   ┌────────────────────┼────────────────────┬──────────────────┐
   ▼                    ▼                    ▼                  ▼
1 PESQUISA          2 PLANO              3 PRODUÇÃO         4 PUBLICAÇÃO
oportunidade,       o que sai hoje,      texto + arte       Bluesky, IG,
tema, horário       prioridade por       + vídeo            Threads, Nostr,
                    meta em risco                           YouTube
                        │
                        ▼
5 MEDIÇÃO + APRENDIZADO  (placar, engajamento por hora, o que repetir)
```

### Camada 1 — Pesquisa (um pulso por dia, 03h local)
- lê as próprias medições de 7 dias;
- identifica **meta em risco** (a que mais se afasta do ritmo necessário por dia);
- escolhe tema do banco existente (40 temas) com regra: nunca repetir o que teve 0 de engajamento;
- procura oportunidade externa: data/jam/efeméride ligada ao jogo (ex.: jam de idle, halloween).
- **saída:** `posts/plano-do-dia.json` (tema, canal-alvo, horário, ângulo).

### Camada 2 — Plano (mesmo pulso da pesquisa)
- cruza meta em risco + janela de horário + teto diário → 5 ciclos do dia;
- cada ciclo recebe **tempo** (um dos 5 slots) e **destino canônico** (site, nunca link quebrado);
- grava o plano. O plano é dado, não código: posso revisá-lo sem tocar em lógica.

### Camada 3 — Produção (por ciclo)
- **texto:** motor do postador (já tem 2 motores + reserva, medido);
- **arte:** arte reserva + captura real do jogo;
- **vídeo/gameplay:** *não medido ainda* — ver §5. Só entra depois do teste de captura.

### Camada 4 — Publicação (por ciclo)
- canais vivos hoje, medidos no último ciclo: Bluesky ✅, Instagram ✅, Threads ✅, Nostr ✅, ntfy ✅;
- ausentes por falta de chave: Telegram, Mastodon, Discord (não é limitação técnica, é credencial);
- YouTube: upload **só com palavra do dono** (regra mantida).

### Camada 5 — Medição e aprendizado (a cada 6h + fechamento diário)
- **mede** o que saiu: engajamento por post, seguidores, downloads, visitas;
- **aprende** uma coisa só por dia: melhor horário. Regra estatística fechada:
  **só troca o horário quando a amostra do horário candidato tiver ≥ 30 posts e a diferença
  sobreviver a um teste simples de ruído** (o relatório atual diz explicitamente que a
  diferença por hora está dentro do ruído — então hoje **não se troca nada**);
- **descarta** o formato com 40%+ de zeros (hoje: comentário em post alheio, 41,7%);
- **reporta** no chat: saiu, cresceu, parou, e o que muda amanhã.

## 3. Metas e prioridade automática

`posts/metas.json` (aprovado 15/10) com prazo **12/11/2026**. Prioridade calculada assim:

```
risco = falta / (dias_restantes × ritmo_por_dia_necessário)
```

| meta | observado | alvo | falta | por dia | leitura |
|---|---|---|---|---|---|
| Instagram seguidores | 0 | 50 | 50 | 2,94 | pior risco |
| itch downloads | 46 | 100 | 54 | 3,18 | segundo |
| Bluesky seguidores | 32 | 50 | 18 | 1,06 | terceiro |
| YouTube inscritos | 24 | 40 | 16 | 0,94 | quarto |
| Instagram posts | 20 | 30 | 10 | 0,59 | fecha no ritmo |
| YouTube shorts | 5 | 4 | 0 | — | atingido |

**A camada 1 ataca sempre o primeiro da lista.** Hoje: Instagram seguidores → a única ação
grátis e mensurável é a **ponte entre canais** (quem já segue no Bluesky saber que o
Instagram existe), porque o Instagram tem 20 posts e 0 seguidores: não é falta de post.

## 4. Invariantes que o orquestrador nunca viola

1. Janela 09h–22h (Brasília) e teto de 5 ciclos/dia — `posts/calendario.json`.
2. Distância mínima de 2h entre ciclos.
3. Fila só com destino canônico e texto ≤ 220 caracteres (barreira de autonomia 63/63).
4. Nenhum número publicado sem fonte medida; `NAO_OBSERVAVEL` ≠ zero.
5. Vídeo no YouTube só com confirmação explícita do dono.
6. Nada de conteúdo pessoal; credenciais só em segredo.
7. Uma ação por pulso: se falhar, o estado registra e o próximo pulso tenta de novo — sem duplicar.

## 5. Vídeo / gameplay — a parte que ainda não está medida

Desenho pretendido: Chromium headless abre a página do jogo (Godot web), grava 15–20 s de
tela via screencast, ffmpeg converte em MP4 vertical, áudio sintetizado, YouTube API envia.

**Riscos medidos/previstos:**
- Godot web precisa de **WebGL**; em runner headless costuma exigir SwiftShader — **não testado**;
- upload do YouTube funciona (200 medido), mas vídeo por API pode ficar `private` se o projeto
  não passou por auditoria — **nesta conta não trava** (medido antes);
- custo: cada vídeo é minutos de runner — ok em repositório público.

**Regra que eu me imponho:** só prometo vídeo depois de uma execução real que produza um MP4
com duração > 0 e o upload devolver 200. Antes disso, vídeo é plano, não entrega.

## 6. O que fica com o dono (e não por escolha minha)

| item | por quê |
|---|---|
| postar no itch (devlog/página) | 403 Cloudflare no meu IP; só o navegador dele alcança |
| aprovar upload de vídeo | regra dele, mantida |
| credenciais ausentes (Telegram/Mastodon/Discord) | falta a chave, não a capacidade |
| Instagram: por que 0 seguidores | exige ponte + conteúdo próprio; post sozinho não resolve |

## 7. Ordem de implantação

1. **Orquestrador 24h** (este commit): pulso de 15 min, estado no repositório, decide e executa.
2. **Aprendizado de horário** com a regra estatística acima (não mexe em nada até ter amostra).
3. **Captura de gameplay** — só depois do teste de WebGL/ffmpeg.
4. **Ponte entre canais** (a ação que ataca o pior risco).
5. **Relatório diário no chat** com números medidos.
