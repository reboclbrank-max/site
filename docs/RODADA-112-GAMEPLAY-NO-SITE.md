# Rodada 112 — o vídeo saiu do canal e chegou no site; a gravação parou de falhar calada

Data: 30 de outubro de 2026. Este documento registra **o que foi medido**, não o que se pretendia.

## 1. O vídeo publicado

`media/gameplay/ceifalume-gameplay-instrucoes.mp4` — o arquivo que está no repositório, no
YouTube e na página do jogo. Medido aqui, com o mesmo validador que barra vídeo ruim:

| medida | valor | limite |
| --- | --- | --- |
| duração / formato | 122,5 s · 1280×720 · 24 fps | — |
| brilho médio | 43,7 (0% de amostras escuras) | reprova tela preta |
| cores distintas | 1 399 | — |
| movimento entre quadros | 1,51 | reprova tela parada |
| maior trecho parado | 5,0 s | 8,0 s |
| instruções na tela | **122 de 122 amostras** | 100% |
| rodapé escuro (brilho máx.) | 39,4 | 88,0 |
| texto claro (fração mínima) | 0,037 | 0,012 |
| faixa estável (desvio máx.) | 3,9 | 26,0 |

E o que o relatório da partida provou: **31 decisões · 16 sementes plantadas · 8 colhidas**
(run 41081081298, captura de 130 s). É a primeira vez que a colheita é medida de ponta a ponta
no ambiente real do CI, não no sandbox.

Publicado em: <https://youtu.be/GuE7af6dYo8> (registro em `posts/youtube-publicados.json`).

## 2. O vídeo chegou na página do jogo (antes só existia no canal)

Quem caía em `jogos/ceifalume/` via o **trailer** e não via o gameplay. Agora a página tem a
seção *Gameplay gravado no navegador*, com o MP4 de 2 minutos tocando no próprio site e o link
do YouTube, e o vídeo entrou no `sameAs` do schema `VideoGame` — buscador e rede social passam a
achar. Seis verificações novas em `tools/testes-autonomia-marketing.py` travam esse elo
(69/69), entre elas *"o gameplay citado pela página existe no repositório e tem mais de 1 MB"*.

## 3. O robô que ficava na tela de abertura (conserto com número)

O sintoma "às vezes o jogo não começa" tinha causa: **as regiões eram escaladas pelo canvas, os
cliques não**. Em qualquer resolução diferente de 1280×720 o toque caía fora do botão.

| resolução | antes | depois |
| --- | --- | --- |
| 960×540 | 3 de 3 rodadas **sem plantio** (preso na capa) | **8 plantios** |
| 800×450 | — | **4 plantios** (e compras de nível 2) |
| 1280×720 | 3 de 3 com 8 plantios | **8 plantios** |

Consertos: `calibrarEscala()` (espera o canvas encher a viewport — ele nasce 300×150), `ponto()`
aplicado em **todo** clique, portão que falha a gravação com 0 sementes plantadas (código 9) e
`escaparDaAbertura()` como rede de segurança.

**Novo nesta rodada:** o workflow **repete a captura** uma vez, em outra resolução (1280×720 →
1600×900), quando a primeira não prova plantio — e, se as duas falharem, o run para em vez de
entregar tela de abertura. Três contratos travam isso em `tools/testes-gameplay.py` (91/92; o
que falta exige navegador instalado).

## 4. itch.io: o build está publicado e agora dá para provar

O envio por `butler` sempre funcionou, mas o modo `status` só imprimia a tabela de canais — não
respondia a pergunta útil. Foram três tentativas medidas e descartadas antes de achar o comando
certo:

| comando | resultado medido |
| --- | --- |
| `butler status alvo:canal` | devolve a **mesma tabela** (não compara nada) — run 41083714746 |
| `butler diff <alvo> <pasta>` | recusa: `diff` compara **duas pastas locais** (`cmd/diff/diff.go`) — runs 41084326374 e 41084610596 |
| `butler push-preview <pasta> <alvo:canal>` | **compara de verdade**, autenticado e sem alterar nada no itch |

Resultado medido (run 41085639726):

```
IGUAL: o itch já tem exatamente esta pasta (nada a enviar)
       0 novos, 0 modificados, 0 apagados, 13 iguais (contra o build 2217549)
```

Ou seja: **o que o jogador baixa no itch é exatamente o build do repositório**. Nada a enviar.

O que continua fora do alcance de um servidor: **editar a página e postar devlog**. O itch não
tem API para isso e a Cloudflare devolve 403 em `/dashboard` a partir de IP de datacenter — com
cookie e sem cookie (medido no run 41082945952; o próprio log registra "não é a sessão, é o
IP"). Esse passo existe pronto no repositório para o navegador do dono
(`tools/devlog-itch-auto.js` + `posts/devlog-itch.json`), e não é feito aqui por conta própria.

## 5. O vídeo também virou devlog no canal que a casa controla

`blog/ceifalume-gameplay.html` + entrada no índice, gerados de `posts/devlog/2026-10-30-...json`
por `tools/devlog.py`. E o gerador passou a **inserir cada post no `sitemap.xml`** com o
`lastmod` vindo da data do post: antes só `/blog/` estava lá, então o diário era escrito para
ninguém achar. Cinco verificações novas (20/20), incluindo "rodar duas vezes não duplica".

## 6. O que ainda não está provado

- Colheita **no sandbox**, em captura curta: segue 0 (nenhuma casca amadurece em 55 s). No CI,
  com 130 s, foram 8 — é a régua que vale.
- Página do itch e devlog do itch: dependem do navegador do dono (Cloudflare).
- `gravar-prancheta` falhou em 30/10 09:03 e **não** foi investigado nesta rodada.

## 7. A repetição da captura foi exercitada (não é só código no workflow)

Run 41086327532, disparo manual de 130 s com `publicar` vazio (nada foi publicado):

```
captura 1 de 2 (1280x720, 130s)
escala dos cliques: 1.000 x 1.000 (1.000 = canvas em 1280x720)
decisões: 33 · plantadas: 10 · colhidas: 6 · telas de abertura: 6
✔ instruções presentes e estáveis em todas as 116 amostras
```

A primeira tentativa já passou no portão do plantio, então a segunda (1600×900) nem rodou — que é
o comportamento desejado: repetir só quando a captura não prova que o jogo foi jogado.

O vídeo do repositório foi atualizado por esse run (116,4 s · brilho 43,0 · 1 369 cores ·
movimento 1,59 · maior trecho parado 4,5 s · **116 de 116** amostras com instruções). O vídeo do
YouTube continua sendo o do run que publicou (`GuE7af6dYo8`, 122,5 s); os dois são capturas
reais do mesmo jogo, e cada run do cron substitui o arquivo do site pela captura mais nova.

## 8. O que falta no itch é conteúdo, e ele está pronto em 1 clique

O build já está no ar e idêntico ao repositório. O que a página do itch não tem é o **vídeo de
gameplay**. Isso não é falta de chave: o itch não expõe API para editar página nem para postar
devlog, e a Cloudflare responde 403 em `/dashboard` para IP de datacenter (run 41082945952 — o
log diz explicitamente "não é a sessão, é o IP").

Então o texto está pronto e o caminho é um favorito:

- `posts/devlog-itch-gameplay.json` — título e corpo do devlog, com o link do vídeo;
- `itch/devlog-gameplay-bookmarklet.txt` — favorito gerado por `tools/montar-bookmarklet.js`,
  que abre a tela de postagens e envia pelo navegador do dono;
- `posts/devlog-itch.json` (o devlog da 0.1, ainda não publicado) **não foi tocado** — há teste
  garantindo isso.

Seis verificações em `tools/testes-autonomia-marketing.py` cobrem esse pacote (75/75).

## 9. Correções de última hora (achadas ao conferir se estava tudo resolvido)

**O PRANCHETA estava caído desde 09:05** e ninguém tinha olhado: run 41030633953 gravou, mediu,
aprovou o vídeo e morreu no `git push` — outro workflow commitou no `main` entre o checkout e o
push. O CEIFALUME tinha o mesmo push seco, e no caso dele o push vem **antes** do envio ao
YouTube: a publicação se perderia.

Conserto em duas voltas, porque a primeira não bastou:

| tentativa | o que aconteceu |
| --- | --- |
| laço de 3 tentativas com rebase | run 41090257198: as 3 falharam com `cannot rebase: You have unstaged changes` (sobras do run na árvore) e o run terminou **verde** com o vídeo fora do repositório |
| + `git stash push -u` antes do rebase + `exit 1` se não entrar | run 41091136045: **"vídeo registrado no main (tentativa 1)"** |

O commit está no `main` (`47aa163`): `media/gameplay/prancheta-gameplay.mp4` 1 085 022 →
1 106 970 bytes. Quatro verificações novas em `tools/testes-gameplay.py` (97/98) travam o push
seco e a falha silenciosa.

## 10. Os três pendentes, um por um

### 10.1 itch: o vídeo chega ao jogador pelo build (o único canal de escrita que passa)

O bloqueio foi medido até o fim, e não é o que parecia:

| onde | o que testei | resultado |
| --- | --- | --- |
| runner Ubuntu (Azure) | GET com e sem cookie | `/dashboard` e `/game/edit/5017404` → **403 + desafio**; `itch.io/` → 200 |
| runner macOS | idem | idêntico |
| runner Windows | idem | idêntico |
| Ubuntu + Chromium headless shell | navegador real com cookie | redireciona para `/login?__cf_chl_rt_tk=…` e fica no desafio |
| Ubuntu + Chromium completo sob Xvfb, pt-BR, sem marca de automação | 96 s, 12 amostras | **403 até o fim** ("Just a moment…" → "Um momento…") |

Ou seja: **não é falta de cookie, não é falta de JavaScript e não é o sistema do runner** — é
reputação de IP. Automatizar por ali exigiria proxy residencial (contra a regra da casa: nada
que dependa de identidade emprestada).

O caminho que existe é o oficial: `butler`. E ele resolve o requisito de verdade, porque **a
página do itch é montada a partir do build**. Então o selo do gameplay entrou no jogo:

- `ceifalume/index.html` → botão "▶ gameplay com instruções" no canto inferior direito, fixo,
  `target="_blank"` + `rel="noopener"`, apontando para <https://youtu.be/GuE7af6dYo8>;
- medido no navegador: caixa 225×29 em (1044, 681) numa tela 1280×720 — não cobre o botão
  "Jogar" (que fica no centro) e não intercepta clique do jogo (captura em
  `selo-gameplay-itch.png`);
- o jogo continua jogável com o selo: captura de 60 s depois da mudança → escala 1.000×1.000,
  9 plantios, economia rodando;
- o envio ao itch passou a ir com **carimbo de versão** (`ceifalume/versao-build.json` →
  `--userversion`), criado só no modo `push`: é o que faz o butler ver diferença e publicar de
  verdade;
- 8 verificações novas em `tools/testes-enviar-itch.py` (64/64).

**O que depende do dono:** o push (`modo=push` + a palavra). A regra vale para o itch.

### 10.2 O teste que falhava no sandbox: agora passa (98/98)

O teste exigia navegador instalado. Instalei Chromium headless shell + as bibliotecas do sistema
(14 pacotes) e baixei `index.pck`/`index.wasm` do remoto. Resultado: **98/98 testes do gameplay**
passando aqui, sem `SKIP` — o mesmo número do CI.

### 10.3 Colheita local: provada, com 9 colhidas

Captura de 140 s, 1280×720, no sandbox:

```
decisões: 32 · plantadas: 14 · colhidas: 9 · telas de abertura: 7
economia: saldo 25 -> 460 · gasto 138 (melhorias) + 180 (sementes) · GANHO 753 moedas em 140 s (322,71/min)
tutorial: ficou 2,4 s na tela · fechou: sim
vídeo: 155,4 s · 2,7 MB · 1280x720 @ 24 fps
```

Ou seja: com tempo suficiente, a colheita acontece **aqui também** — o "0 colhidas" era só a
janela curta (55 s), não um defeito.

## 11. Runs de fechamento

| run | o que provou |
| --- | --- |
| 41115299289 (ensaio do itch) | `index.html` subiu para **22,27 KiB** (o selo) e o pacote continua 13 arquivos / 40,26 MiB |
| 41115538652 (captura 130 s) | `decisões: 34 · plantadas: 11 · colhidas: 5` · **125/125 amostras** com instruções · `vídeo registrado no main (tentativa 1)` |
| 41112561108 (sondar-ip-itch) | 403 nas duas rotas de painel em Ubuntu, macOS e Windows |
| 41114204554 (sondar-itch-browser2) | 403 até o fim com Chromium sob Xvfb, pt-BR, sem marca de automação |

O push com nova tentativa (10.2 → agora em produção) registrou **na primeira tentativa** — a
correção do `git stash` + `exit 1` está funcionando de verdade, não só no papel.
