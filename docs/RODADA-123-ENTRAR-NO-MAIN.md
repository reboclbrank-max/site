# Rodada 123 — "resolva tudo": os runs vermelhos, o motivo deles e o conserto medido

Pedido do dono: *"resolva tudo"*. Antes de mexer em qualquer coisa, medi o que estava de fato
quebrado — não o que eu achava que estava. Três coisas apareceram: **nada no código do jogo**, e
sim no encanamento dos runs.

## O que estava vermelho, com número

| onde | quantas vezes | motivo medido |
| --- | --- | --- |
| `postagem-diaria` | 2 (runs `41128039668`, `41128399021`) | `3 tentativas e o ciclo não entrou no main` — o laço de rebase parava em conflito e o log do ciclo ficava preso dentro do run |
| `marketing-continuo` | 8 seguidas até 30/10 22h | teste do gravador cobrava navegador instalado num workflow que não instala (`92/93`) — já corrigido no commit `c671904`, conferido: **93/93** hoje |
| `enviar-itch` | 1 falso-verde (run `41151339470`) | `--hidden` recusado pelo itch + `\| tee` sem `pipefail` — corrigido na rodada 122 |
| `pages build and deployment` | 19 `cancelled` | não é defeito: é o Pages cancelando a publicação antiga quando chega commit novo. Sem ação |

O que **não** estava quebrado e eu conferi antes de mexer: `marketing-continuo` com run
`in_progress` há 2 horas é o **bloco contínuo de 5 h**, não run travado (`timeout-minutes: 355`).

## O defeito de verdade: rebase é a ferramenta errada para arquivo gerado

Sete workflows escrevem no `main`, cada um com o seu laço "rebase e tenta de novo". Só que
`marketing.html`, `publicacoes.json` e `posts/log.md` são **regerados** por cada run: os dois
lados sempre mudam as mesmas linhas, e o rebase para em conflito **todas as vezes**. Retentar
rebase é retentar a mesma colisão.

`tools/entrar-no-main.sh` (novo) resolve na origem do problema:

1. `fetch` e tenta **rebase** — caminho barato, quando não há colisão;
2. se o rebase parar em conflito, desfaz e faz **merge**: conflito em arquivo **gerado** é
   resolvido pelo próprio gerador — fica a versão do main e logo depois `$GERAR` reescreve o
   arquivo **a partir da fonte** (`posts/`, `docs/`). Arquivo gerado não tem informação própria;
   quem tem é a fonte dele;
3. conflito em arquivo que **não** é gerado (código, workflow, documento escrito à mão) **não**
   é resolvido no chute: o merge é desfeito e o script sai com 1 dizendo qual arquivo é;
4. se o workflow não configurou identidade, o script configura — o `empty ident name` já custou
   rodada nesta casa e aqui apareceria disfarçado de "push recusado".

Ligado em: `postagem-diaria` (3 blocos), `pendencias-do-dono`, `metricas-youtube`,
`marketing-24h`. `gravar-*` e `editar-itch` continuam com o laço próprio de propósito: eles
mandam binário, não regeram arquivo e não colidem.

## A prova, com repositórios de verdade

`tools/testes-entrar-no-main.py` monta um `origin` bare e dois clones e mede os três casos reais:

| caso | resultado |
| --- | --- |
| main andou sem tocar no meu arquivo | entra por rebase, ninguém perde nada |
| main mexeu no MESMO arquivo gerado | entra por merge; o gerado final é o da **fonte** (`v2`), o meu trabalho também entra, sem `.orig`/`.rej` e sem merge pendente |
| main mexeu em código que não é gerado | **recusa**, diz qual arquivo, desfaz o merge, código do outro intacto, meu commit preservado |

**21/21**.

## Pendência fantasma do dono — resolvida com medida, não com texto

`posts/pendencias-do-dono.md` pedia ao dono *"subir o build com o selo do gameplay"* **depois** de
o build já estar no ar (build `2257110`). A causa: a única medida daquele item era "a página do
jogo respondeu 200", que é verdade mesmo sem build nenhum.

Agora o item é medido por `posts/itch-builds.json` com o mesmo critério do cofre — precisa de
**id de build E prova** (run do push + run da conferência). Resultado no relatório:

```
✔ subir o build com o selo do gameplay — build 2257110 no ar (versão 2026.10.31-0046,
  https://rebocl-brank.itch.io/ceifalume) — push run 41151936756; status run 41152028164 IGUAL
```

**Pendentes para o dono: 1** (era 2) — só o devlog do itch, que a Cloudflare bloqueia para IP de
datacenter (`docs/sondagens/ITCH-403-CLOUDFLARE.json`). Esse continua sendo o único passo que
depende de sessão humana logada, e o conteúdo dele já está publicado no blog da casa
(`tools/devlog.py`), onde não existe trava.

## Higiene nova nos workflows (o que faltava para não repetir)

`tools/testes-workflows.py` passou de 11 para **21** verificações. As novas:

- todo workflow que escreve no `main` usa o `entrar-no-main.sh` (exceção declarada: `gravar-*`);
- o ajudante existe, é executável e recusa conflito fora dos gerados;
- `postagem-diaria` não voltou ao laço de rebase cego;
- **todo bloco `run:` dos 32 workflows é shell válido** — `bash -n` em cada um, sem executar.
  Esse pegou um erro que eu mesmo quase introduzi nesta rodada.

## O teste de fogo: o ciclo diário no ar, com o ajudante no caminho

Run `41153030523` (success). O log mostra o ajudante encontrando exatamente a colisão que antes
derrubava o ciclo — e saindo dela:

```
[painel e log do ciclo] regerando: python3 tools/melhorias.py && python3 tools/publicacoes.py …
[painel e log do ciclo] no main por rebase (tentativa 1)
[ciclo e devlog] push recusado: hint: use 'git pull' before pushing again
[ciclo e devlog] conflito em arquivo gerado: docs/PUBLICACOES.md (fica a versão do main; o gerador reescreve)
[ciclo e devlog] conflito em arquivo gerado: posts/publicacoes.json
[ciclo e devlog] conflito em arquivo gerado: publicacoes.html
[ciclo e devlog] regerando: python3 tools/melhorias.py && python3 tools/publicacoes.py
[ciclo e devlog] no main por merge resolvido nos gerados (tentativa 2)
[medição do ciclo] no main por rebase (tentativa 1)
```

Antes, esse mesmo conflito era o "3 tentativas e o ciclo não entrou no main". Depois do conserto:
**run verde, os três blocos no main**. `diagnostico-da-casa` (`41153170075`) e `metricas-youtube`
(`41153273006`) também verdes com o ajudante novo.

O push recusado agora **aparece com o motivo** — e foi assim que eu descobri, no meu próprio
teste, que o script de credencial em `/home/user/tools/` estava sem permissão de execução. Antes
o script repetia "push recusado" seis vezes sem dizer nada.

## O único pendente do dono, remedido hoje

`https://itch.io/dashboard` → redireciona para `/login` e responde **403 com "Just a moment"
(Cloudflare)**. Continua valendo o que foi medido em três sistemas e com Chromium real
(`docs/sondagens/ITCH-403-CLOUDFLARE.json`): o painel do itch não abre para IP de datacenter.
O material do clique está pronto e conferido: `itch/devlog-gameplay-bookmarklet.txt` (5.344 B) e
`posts/devlog-itch-gameplay.json` (1.281 B). E o texto **não fica preso**: ele já está público em
`blog/ceifalume-gameplay.html`, no site da casa.

## Números desta rodada

| prova | resultado |
| --- | --- |
| suítes locais | **33 suítes, 0 falhas** (era 32 — entrou `testes-entrar-no-main`) |
| `testes-entrar-no-main` | 21/21 |
| `testes-workflows` | 21/21 (eram 11) |
| `testes-pendencias` | 24/24 (eram 19) |
| `testes-gameplay` | 93/93 |
| `testes-publicacoes` | 42/42 |
| `testes-enviar-itch` | 68/68 |
| pendências do dono | **1** (era 2) |
| builds no itch (id + prova) | 1 — build `2257110` |
| vídeos no YouTube (id real) | 2 |
