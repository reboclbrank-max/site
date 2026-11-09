# Rodada 116 — a sabedoria das decisões (o que a casa decide, o que ela recusa, o que ela não sabe)

A pergunta foi: *"mas ele não consegue ser 100% autônomo — ter o controle e a sabedoria das
decisões?"*

Controle e sabedoria não são a mesma coisa, e a diferença é o que esta rodada tornou visível:

- **controle** = executar, medir o resultado e corrigir sem ninguém mandar;
- **sabedoria** = decidir **com o número na mão**, e **saber onde parar** — recusar decisão que
  os dados não sustentam, e nomear o que não sabe.

A casa já tinha a segunda parte escrita em dois lugares e não cobrava nenhum dos dois:

1. `tools/aprender-horario.py` — a regra "só troca horário com amostra ≥ 30 por hora **e** ganho
   maior que um desvio padrão" existia **e nunca era executada** por nenhum workflow. A decisão
   estava parada em 27/10, sem teste e sem cobrança.
2. `posts/placar-metas.md` — já declarava, com todas as letras: *"Manter o canal ou aposentá-lo é
   decisão do dono, com este número na mão — o robô não decide isso e não vai fingir que decide."*
   Era uma frase bonita num arquivo que ninguém lia.

## O que foi entregue

### 1. O aprendizado passou a rodar (e a ser cobrado)

- `aprender-horario.py` entrou no passo de medição do `postagem-diaria` e grava
  `posts/aprendizado.json` a cada ciclo.
- `tools/testes-aprender-horario.py` — **16/16**: amostra pequena → MANTER com motivo; diferença
  dentro do ruído → MANTER; sinal maior que o desvio → TROCAR; sem leitura → não inventa hora.
- Na barreira offline de cada ciclo e no `diagnostico-da-casa`.

### 2. O livro de decisões (`tools/decisoes.py`)

Gera `posts/decisoes.json` + `posts/decisoes.md`, derivado **só** de arquivos do repositório, em
três listas:

| lista | o que é | exemplo medido hoje |
| --- | --- | --- |
| **decididas** | cada decisão com o número que a sustenta e o arquivo de origem | *priorizar itch: downloads — faltam 54 (3.38 por dia)*; *parar de insistir no formato que devolve zero: 41.5% de zeros em 217 tentativas* |
| **recusadas** | decisões que o robô **não toma**, e por quê | *trocar horário: recusada por falta de prova — diferença dentro do ruído (amostra 300, mínimo 30/hora)*; *manter ou aposentar um canal: escolha de vida do projeto, não conta de máquina* |
| **ignorâncias** | perguntas que a casa **não sabe** responder | *o texto do post é bom?* · *vale a pena continuar com esse público?* |

Regra embutida e testada: **decisão sem número não entra**. Se a fonte não existe, o item desce
para "falta de medida" em vez de virar palpite com cara de dado.

### 3. Vitrine: a sabedoria aparece no painel público

`marketing.html` ganhou a seção **"As decisões, com o número atrás"**, com as três listas e a
fonte de cada número. `tools/testes-painel-marketing.py` foi de 18 para **22/22** cobrindo a
seção (inclusive "não promete publicação sem prova").

## Por que "100% autônomo" é a pergunta errada

O que a casa **já** decide sozinha, sem aprovação: o que postar, em que canal, em que horário,
quantas vezes, quando parar um formato que só devolve zero, e quando uma meta batida deixa de
merecer esforço.

O que ela **se recusa** a decidir — e essa recusa é o produto, não a falha:

- **aposentar um canal** que não devolve número (17 dias sem retorno em Instagram: seguidores e
  YouTube: inscritos). Isso é escolha de vida do projeto; o robô entrega o número e para;
- **trocar horário sem prova estatística** (diferença dentro do ruído — mantém, com o desvio
  registrado);
- **publicar o que o dono vetou** (`posts/nunca-publicar.json`: pedido de 26/10);
- **publicar sem `PUBLICAR`** no YouTube/itch (decisão do dono, sempre).

E o que **nenhuma métrica do repositório responde**: se o texto é bom, e se vale a pena continuar
existindo com esse público. Um robô que respondesse isso estaria inventando.

## Provas

- `tools/testes-decisoes.py` — **28/28**
- `tools/testes-aprender-horario.py` — **16/16**
- `tools/testes-painel-marketing.py` — **22/22** (era 18)
- Suítes locais: **26 de 27 verdes**; a única falha (`testes-gameplay.py`) é de ambiente (sandbox
  sem navegador), não do código.
- `postagem-diaria` e `diagnostico-da-casa` rodam as duas suítes novas a cada ciclo.
