# Rodada 115 — marketing autônomo: o que já roda sozinho, medido

A pergunta foi: *"é possível o chat gerenciar o marketing e as redes sociais de forma autônoma?"*

A resposta honesta é que **a máquina já existia e já roda sozinha** — o que faltava era
ela **ser legível** e **não mentir** quando um canal está desligado. Esta rodada não
inventou canal novo: tornou o que existe auditável.

## O que roda sem ninguém apertar nada

`postagem-diaria` dispara **8 ciclos por dia** (0h, 3h, 6h, 9h, 12h, 15h, 18h, 21h UTC)
mais um pulso de retaguarda a cada 20 min. Cada ciclo passa por 11 suítes offline antes
de tocar em qualquer rede. O gate `PUBLICAR` vale **só** para YouTube e itch; as redes
sociais não pedem aprovação.

Medido no último ciclo publicado (`marketing.html`, ciclo de 30/10/2026 21:04 UTC,
102 ciclos no log):

| canal | estado | segredo que usa |
| --- | --- | --- |
| Bluesky | publicando (99/102) | `BLUESKY_HANDLE` + `BLUESKY_APPPASS` |
| Threads | publicando (99/102) | `THREADS_USER_ID` + `THREADS_TOKEN` |
| Nostr | publicando (100/102) | `NOSTR_KEY` |
| Aviso no celular (ntfy) | publicando (102/102) | `NTFY_TOPIC` |
| Instagram | publicando (39/102) — **por desenho**: 1 post/6 h, 1 reel/semana | `IG_TOKEN` + `IG_USER_ID` |
| Telegram | **desligado** | `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` |
| Mastodon | **desligado** | `MASTODON_URL` + `MASTODON_TOKEN` |
| Discord | **desligado** | `DISCORD_WEBHOOK` |

Além dos posts, o ciclo também faz sozinho: aula do cérebro (texto novo validado),
descobridor de redes, censo mundial, vigia da caixa (auto-recovery), caçador de
oportunidades e a régua de metas (medição de seguidores/downloads).

## O que mudou nesta rodada

1. **`tools/painel-marketing.py` → `marketing.html`**: painel público gerado do
   **mesmo `posts/log.md`** que o ciclo acabou de escrever, commitado pelo runner e
   publicado pelo Pages. Autonomia com vitrine, não com promessa.
2. **Canal desligado diz o nome do segredo**: `postador.py` ganhou
   `SEGREDOS_DO_CANAL` / `segredos_que_faltam()`; a linha vira
   `⚪ falta o segredo TELEGRAM_TOKEN + TELEGRAM_CHAT` em vez de
   "configuracao de publicacao ausente".
3. **Trava não é falha**: janela anti-spam, cadência diária e "sai no sábado" contam
   como ➖ espera, não como erro. O painel separa OK / desligado / espera.
4. **Push silencioso morreu**: o commit do ciclo e o commit do painel falham alto
   (`::error::` + `exit 1`) se não entrarem no `main` — antes o run ficava verde com o
   log só no runner. Falha do painel **não** aborta o ciclo: devlog e log entram, e o
   run termina vermelho com o motivo medido.

## Provas

- Run `41128891896` — `postagem-diaria` **success**, com o passo de barreira rodando
  `testes-painel-marketing.py` **18/18** e `testes-autonomia-marketing.py` **75/75**.
- Commit `7850b77` — *"marketing: painel e log do ciclo (30/10 21:09 UTC)"*, escrito
  **pelo runner**, não por mim.
- `https://reboclbrank-max.github.io/site/marketing.html` — 102 ciclos, último ciclo
  21:04 UTC, tabela acima.
- Suítes locais: **24 de 25 verdes**; a única falha (`testes-gameplay.py`) é de
  ambiente (sem navegador instalado no sandbox), não do código.

## O que nunca será autônomo (e por quê)

- **Devlog do itch**: sem API de escrita; o Cloudflare devolve 403 por reputação de IP
  mesmo em Chrome estável (rodada 114). Caminho sem clique só com `ITCH_PROXY` do dono.
- **Upload no YouTube**: depende do OAuth do dono (`YT_*`) e do gate `PUBLICAR`
  explícito. O ciclo **produz** o kit; publicar é decisão, não rotina.

## Como ligar os três canais desligados

Criar os segredos no repositório (`Settings → Secrets and variables → Actions`) com os
nomes exatos da tabela. Nada mais: o próximo pulso já publica neles.
