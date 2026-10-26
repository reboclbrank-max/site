# Kit do itch.io — colar e clicar

O itch **não tem API** para criar página nem para publicar devlog. Então este arquivo é o que
sobra para você: texto pronto, campo por campo, e a lista curta dos cliques que só o dono da
conta pode dar. Nada aqui precisa ser escrito por você.

O que já está provado (ensaio `--dry-run` no runner, 26/10): o build do CEIFALUME está inteiro
e subiria **13 arquivos / 40,26 MiB**. Foi só ensaio: nada foi enviado.

---

## 1. Devlog do CEIFALUME (colar)

Ir em: `rebocl-brank.itch.io/ceifalume` → **Edit game** → **Devlog** → *New post*.

**Título:**

    O CEIFALUME agora abre no navegador

**Corpo:**

    O jogo saiu do arquivo de Android e virou build de navegador.

    Antes, para jogar, era preciso baixar o APK e instalar. Agora a mesma build abre direto na
    página, sem instalação e sem ocupar espaço no celular. O download do APK continua lá, para
    quem preferir jogar com o aplicativo.

    O que mudou por dentro:

    - o jogo foi exportado de novo para a web (mesmo motor, mesma build, outro empacotamento);
    - o download do Android segue disponível, sem alteração;
    - quem já tinha o aplicativo não precisa fazer nada.

    Se a página abrir preta: é a caixa *SharedArrayBuffer* desligada nas opções de embed.
    Avisa que eu ligo.

    Comentário, bug e sugestão: é aqui nos comentários mesmo.

**Tags:** `godot`, `web`, `android`, `atualização`

---

## 2. Um clique que só você pode dar (e que muda o jogo)

Na página de edição do CEIFALUME, em **Embed options → Frame options**, marcar:

    [x] SharedArrayBuffer support   (Experimental)

**Por quê, medido:** o build é Godot **4.0.10** e o `index.js` consulta `crossOriginIsolated`.
Build dessa geração **não roda sem** esses cabeçalhos, e o itch só os envia quando a caixa está
marcada. Sem o clique, a página abre preta mesmo com o build certo.

**Efeito colateral honesto:** com a caixa ligada, embeds de terceiros na página (vídeo do
YouTube em comentário, por exemplo) podem parar de carregar. É o preço do cabeçalho estrito.

---

## 3. Publicar o Toque Rápido (1 clique, ganho imediato)

Estado medido na API hoje: **Toque Rápido — 2 downloads, 16 visitas, `publicado = não`**.
Já tem página e já tem download; falta o botão **Publicar**. Enquanto está em rascunho, ninguém
chega nele por busca nem por listagem.

Se você publicar, eu passo a medir os três jogos no placar em vez de dois.

---

## 4. Página nova: o que o itch pede, e o que eu não posso preencher

Para **criar** página o itch exige, na mão: título, URL do projeto, classificação, tipo de
projeto, preço, descrição, tags e imagem de capa (630x500 ou maior).

**Só que não existe jogo novo para pagina** — e isso é medida, não preguiça:

| jogo | tem build? | dá para subir? |
|---|---|---|
| CEIFALUME | sim (`index.wasm` 38 MB + `.pck` + `.js`) | sim, é o do ensaio acima |
| PRANCHETA | **não** — nenhum `.zip/.apk/project.godot` em repositório algum | não, não há o que enviar |
| Toque Rápido | já está no itch, em rascunho | só publicar (item 3) |

Para a PRANCHETA sair do papel falta o que eu não posso inventar: o **projeto Godot**
(`project.godot`, pastas de cena/código) ou um **export**. Sem isso, "página nova" viraria
página vazia, e página vazia é pior que página nenhuma.

---

## 5. O que eu faço sozinho assim que você disser a palavra

- `modo push` no workflow `enviar-itch.yml`, com a palavra **PUBLICAR** → sobe o canal `html5`
  do CEIFALUME pelo butler. O canal entra **oculto** de propósito: o build fica no itch, mas não
  vira download na cara do jogador antes de você ver.
- Depois disso, `modo status` a cada rodada para provar o que mudou, e o placar do itch passa a
  contar os três jogos.

## 6. O que eu não faço nem com a palavra

- Não entro na sua conta do itch para clicar em Publicar, marcar caixa ou escrever devlog:
  a conta é sua e o itch não oferece API para isso.
- Não publico devlog nem anuncio lançamento em rede social sem pedido explícito.
