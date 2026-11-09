# Rodada 111 — vídeo de gameplay com as instruções de como jogar na tela, sempre

Requisito do dono, palavra por palavra: **"no vídeo as instruções de como jogar não saem da tela
em momento algum"**. O vídeo que a casa tinha não cumpria: as instruções apareciam só no tutorial
do começo e sumiam dali em diante.

## O que mudou

| peça | o que faz |
| --- | --- |
| `tools/desenhar-faixa.py` | desenha a faixa com o texto das instruções (PIL; o ffmpeg da casa não tem `drawtext`) |
| `tools/legenda-guia.js` | queima a faixa no rodapé do vídeo, do primeiro ao último quadro, e gera a trilha |
| `tools/validar-instrucoes.py` | MEDE se a faixa está lá: rodapé escuro, texto claro e assinatura estável em todas as amostras |
| `tools/testes-instrucoes-video.py` | 5 contratos: com faixa passa; sem faixa reprova; faixa que some no meio reprova; texto apagado reprova; faixa pequena demais é recusada |
| `gravar-gameplay.yml` | novo passo depois da pós-produção; o vídeo com instruções é o que vai para o repositório, o artefato e o kit de envio |
| `produzir-video.py` | `LEGENDA_MARGEM_V` (padrão 28, 176 no fluxo): a legenda sobe para não ficar embaixo da faixa |

O texto da faixa vem do que é fato: o tutorial do próprio jogo (escolher semente, plantar, "Fazer
um bico" +1 moeda, colher quando aparecer "pronto") e o kit oficial da casa (navegador, sem conta,
cresce até 8 h com o jogo fechado, Godot, feito no Brasil). Nenhuma promessa nova.

## Prova medida (arquivo real, não descrição)

`media/gameplay/ceifalume-gameplay-instrucoes.mp4` — 88,0 s · 1280×720 · 24 fps · 3,0 MB

```
validar-video.py        : brilho médio 41.8 · 1374 cores · movimento 1.40 · parado no máx 3.5 s  ✔
validar-instrucoes.py   : 88 de 88 amostras com faixa escura e texto claro · desvio máx 5.2       ✔
testes-instrucoes-video : 5/5 contratos                                                            ✔
testes-gameplay.py      : 83/84 (a que falta depende de navegador instalado nesta máquina)
```

O vídeo foi produzido assim: gravação real do build (`tools/gravar-gameplay.js`, WebGL por
software), corte automático + legendas + trilha (`tools/produzir-video.py --trechos-auto`, com
`LEGENDA_MARGEM_V=176`) e a faixa fixa (`tools/legenda-guia.js`). Cada etapa reprova sozinha se o
resultado não tiver jogo na tela, som, legenda ou instruções.

## O que NÃO foi feito, e por quê

**Não publiquei no YouTube.** A regra da casa é do dono e está escrita nos workflows: publicação só
com a palavra `PUBLICAR` no campo de confirmação, e o dono pediu para postar "na hora certa". O
arquivo está pronto e é o que o kit (`posts/kit-gameplay.json`) aponta — o envio é um comando
explícito, não um passo automático.
