# O que acontece quando você mexe em algo

Gerado por `tools/o-que-acontece.py` a partir dos **42** arquivos de `.github/workflows/` — cada linha vem do próprio workflow, não da minha memória. O `conferir-tudo` falha se este documento deixar de bater com eles.

## 1. Você deu push no `main`

Todo push publica o site (GitHub Pages), sem exceção e sem depender de teste verde. Além do site, roda o que casa com o caminho tocado:

| caminho tocado | roda | o que faz |
| --- | --- | --- |
| `tools/**` | `conferir-tudo` | Roda TODAS as suítes de contrato da casa, em série, e falha se alguma mexer em arquivo versionado. |
| `posts/**` | `conferir-tudo` | Roda TODAS as suítes de contrato da casa, em série, e falha se alguma mexer em arquivo versionado. |
| `.github/workflows/**` | `conferir-tudo` | Roda TODAS as suítes de contrato da casa, em série, e falha se alguma mexer em arquivo versionado. |
| `tools/devlog-itch-auto.js` | `testes-devlog` | Mede o favorito "Postar devlog" num Chromium de verdade, no runner. |
| `tools/testes-devlog-navegador.py` | `testes-devlog` | Mede o favorito "Postar devlog" num Chromium de verdade, no runner. |
| `itch/devlog-bookmarklet.txt` | `testes-devlog` | Mede o favorito "Postar devlog" num Chromium de verdade, no runner. |
| `posts/devlog-itch.json` | `testes-devlog` | Mede o favorito "Postar devlog" num Chromium de verdade, no runner. |
| `.github/workflows/testes-devlog.yml` | `testes-devlog` | Mede o favorito "Postar devlog" num Chromium de verdade, no runner. |

Uma ressalva medida (07/11/2026, run 42340117439): o deploy do Pages pode travar em `syncing_files` e morrer por timeout — foi o que aconteceu naquele run, e o push seguinte publicou tudo. Deploy do site falhando não estraga o repositório; o próximo push reenvia. Se o site parecer velho, confira o último `pages build and deploy`.

**O que NÃO roda no push:** mexer em `ceifalume/`, `jogos/` ou nas páginas da raiz não dispara teste nenhum. O site publica igual; a bateria inteira (`conferir-tudo`) só é chamada quando o push toca `tools/`, `posts/` ou os próprios workflows. Se a dúvida é "será que eu quebrei alguma coisa?", rode `python3 tools/rodar-todas-as-suites.py` antes de empurrar.

## 2. O dia sem você tocar em nada (hora de Brasília)

**71 disparos automáticos por dia**, em 13 workflows com agenda — esse é o que o cron PEDE. O que o GitHub entrega é outra conta (abaixo).

**Entrega medida do agendador** (janela de 7 dia(s), medido em 2026-11-07): **14.02/dia** de 63 pedidos. O pior caso é `medir-o-dia`. O cron do GitHub é melhor esforço: para um pulso de 20 em 20 minutos ele entrega uma fração, e é por isso que a casa precisa de corrente, não de agenda.

| hora (Brasília) | workflow | o que faz |
| --- | --- | --- |
| 00h, 03h, 06h, 09h, 12h, 15h, 18h, 21h | `corrente` | A CORRENTE DE PULSOS (07/11/2026). ⚠️ fora da janela: 00h, 03h, 06h |
| 00h, 06h, 12h, 18h | `metricas-youtube` | Mede o que os vídeos publicados fizeram (views, likes, comentários). ⚠️ fora da janela: 00h, 06h |
| 03h | `administrar-itch` | Administração automática do itch.io: o robô olha o estado, decide e (se for o caso) sobe o build — sem clique do dono. ⚠️ fora da janela: 03h |
| 03h | `administrar-youtube` | Administração automática do YouTube: organiza e corrige o que já está publicado (título, descrição, tags) sem clique do dono. ⚠️ fora da janela: 03h |
| 03h, 04h, 09h–21h | `marketing-24h` | Motor da casa: um pulso a cada 20 minutos decide UMA ação e executa (45 pulsos/dia). ⚠️ fora da janela: 03h, 04h |
| 09h, 16h | `gravar-gameplay` | Grava o jogo rodando de verdade e transforma em arquivo de vídeo. |
| 09h, 13h, 16h | `gravar-prancheta` | Grava o PRANCHETA rodando (o segundo jogo da casa). |
| 09h | `ler-comentarios` | Lê comentários públicos só com a API key (sem OAuth, sem consentimento novo). |
| 09h | `medir-o-dia` | Medido: `posts/placar-metas.md` estava parado em 03/11 06:52Z — dizia "9 dia(s) restante(s)" quando faltavam 5 — e o pulso decidia com aqueles… |
| 09h | `pendencias-do-dono` | Fecha o ciclo do único passo que sobra para o dono (publicar no painel do itch). |
| 09h | `vigia-sessao-itch` | A sessão do itch (segredo ITCH_COOKIE) é o único caminho para escrever na página. |
| 10h, 14h | `chamar-video` | Leva quem já segue a casa até o vídeo que acabou de sair. |
| 10h | `medir-itch` | Placar do itch pela API (que nao passa pela Cloudflare): downloads, visitas, publicacao. |

⚠️ = o workflow roda fora da janela 9h–22h. Não é erro por si: medir de madrugada é legítimo; **publicar** de madrugada não é, e o portão recusa.

## 3. Quem publica e quem só mede

Estes só escrevem no mundo com a palavra digitada no campo de confirmação (**13** workflows):

- `capas-dos-antigos` — `confirmacao` = **APLICAR**
- `duplicados-youtube` — `confirmacao` = **PRIVAR / APAGAR**
- `editar-itch` — `confirmacao` = **EDITAR**
- `enviar-itch` — `confirmacao` = **PUBLICAR**
- `enviar-youtube` — `confirmacao` = **PUBLICAR**
- `gravar-gameplay` — `publicar` = **PUBLICAR**
- `gravar-prancheta` — `publicar` = **PUBLICAR / ENSAIO**
- `marketing-24h` — `confirmacao` = **PUBLICAR**
- `marketing-continuo` — `confirmacao` = **PUBLICAR**
- `postagem-diaria` — `confirmacao` = **PUBLICAR**
- `publicar-devlog-itch` — `confirmacao` = **PUBLICAR**
- `sonda-instagram` — `confirmacao` = **SONDAR**
- `sonda-threads` — `confirmacao` = **SONDAR**

O resto mede, grava ou registra — e o registro é o produto. Quando um run não consegue provar o que fez, ele termina em recusa com o motivo, nunca em sucesso.

## 4. O que só roda quando você pede

**26** workflows não têm agenda: nenhum dispara sozinho, todos dependem de Actions → Run workflow.

- `autorizar-youtube`, `barreira-offline`, `capas-dos-antigos`, `conferir-comentarios`
- `diagnostico-da-casa`, `duplicados-youtube`, `editar-itch`, `enviar-itch`, `enviar-youtube`
- `limpar-youtube`, `marketing-continuo`, `postagem-diaria`, `provar-force-ssl`, `provar-youtube`
- `publicar-devlog-itch`, `sonda-instagram`, `sonda-threads`, `sondar-cookie-itch`, `sondar-cookie2`
- `sondar-devlog`, `sondar-escrita`, `sondar-itch-acesso`, `sondar-itch-chrome`
- `sondar-itch-navegador`, `sondar-login`, `sondar-trava-youtube`

## 5. O que depende de você (e o que sobe sozinho)

O `administrar-itch` conhece **1** projeto(s): `ceifalume`. Só esses recebem build automaticamente (uma vez por dia, madrugada); o resto não sobe sozinho.

| jogo | build versionado aqui | sobe sozinho? |
| --- | --- | --- |
| `ceifalume` | `ceifalume` (13 arquivos) | sim — `administrar-itch` de madrugada |
| `prancheta` | não (só a página em `jogos/prancheta/`) | **não** — atualizar é upload no itch |

Para o jogo que sobe sozinho, a gravação automática filma **o build deste repositório**. Para o que não sobe (o PRANCHETA vive publicado no itch), a gravação filma **a página do itch** — logo, build novo só aparece lá depois de o dono subir.

O build do PRANCHETA que o itch está servindo hoje: **19604665** (a casa viu em 2026-11-07T05:38, pelo `vigia-build-prancheta.py` que roda no relatório diário). Quando muda, vira fato no repertório do redator — não vira post na marra.

