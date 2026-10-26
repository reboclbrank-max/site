# Guia do YouTube — 4 passos, com link direto

Estado hoje, conferido por API: dos três segredos que a automação usa, existem **zero**.
Faltam `YT_CLIENT_ID`, `YT_CLIENT_SECRET` e `YT_REFRESH_TOKEN` (o último o robô cria sozinho).

> O console do Google mudou de nome e de endereço em 2025/2026: o antigo "Tela de
> consentimento OAuth" hoje é a **Google Auth Platform**, dividida em *Marca / Público /
> Acesso a dados / Clientes*. Os links abaixo já são os novos — tutoriais antigos mandam para
> telas que não existem mais.

## Resumo em 4 linhas

| # | o que | link direto |
|---|---|---|
| 1 | criar projeto | https://console.cloud.google.com/projectcreate |
| 2 | ativar YouTube Data API v3 | https://console.cloud.google.com/apis/library/youtube.googleapis.com |
| 3 | consentimento + **Publicar app** + cliente OAuth | https://console.cloud.google.com/auth/overview/create |
| 4 | rodar o robô e digitar o código | https://github.com/reboclbrank-max/site/actions/workflows/autorizar-youtube.yml |

---

## Passo 1 — projeto no Google Cloud

🔗 **https://console.cloud.google.com/projectcreate**

- **Nome do projeto:** `rebocl-casa` (é só rótulo)
- **Localização:** *Sem organização* (conta pessoal)
- Clique **Criar** e espere o sino avisar que terminou.

Anote o **ID do projeto** (algo como `rebocl-casa-482713`), que aparece no topo da página e no
seletor de projetos. Ele entra no fim dos links seguintes como `?project=SEU_ID`.
Guarde também o **número** do projeto (só dígitos): o formulário de auditoria, no fim deste
guia, pede o número, não o ID. Ele está em https://console.cloud.google.com/home/dashboard.

*Não precisa de cartão de crédito.* A YouTube Data API é gratuita nessa faixa de uso.

## Passo 2 — ativar a API

🔗 **https://console.cloud.google.com/apis/library/youtube.googleapis.com?project=SEU_ID**

- Confira no topo se o projeto selecionado é o que você acabou de criar.
- Clique **Ativar** (*Enable*). Leva uns 30 segundos.
- Deve aparecer "API ativada" e o botão virar **Gerenciar**.

## Passo 3 — consentimento, publicação e cliente OAuth

### 3a. Criar a tela de consentimento

🔗 **https://console.cloud.google.com/auth/overview/create?project=SEU_ID**

| campo | o que pôr |
|---|---|
| Nome do app | `Rebocl Casa` (é o nome que aparece na tela de aprovação) |
| E-mail de suporte | seu Gmail |
| Público / User type | **Externo** ← se escolher *Interno*, só funciona com Google Workspace, que você não tem |
| E-mail de contato | seu Gmail |
| Política de privacidade | `https://reboclbrank-max.github.io/site/privacidade.html` |
| Termos de serviço | `https://reboclbrank-max.github.io/site/` |

Marque o aceite e clique **Criar**.

### 3b. Declarar o escopo (o que o robô pode fazer)

🔗 **https://console.cloud.google.com/auth/scopes?project=SEU_ID**

- **Adicionar ou remover escopos** → na caixa de filtro cole:
  `https://www.googleapis.com/auth/youtube`
- Marque essa linha → **Atualizar** → **Salvar**.

Esse escopo único cobre enviar vídeo **e** administrar (título, descrição, tags, playlist,
miniatura, comentários). Não adicione outros: cada escopo a mais é burocracia a mais.

### 3c. Publicar o app — **o passo que quase todo mundo esquece**

🔗 **https://console.cloud.google.com/auth/audience?project=SEU_ID**

- Em **Status de publicação**, hoje deve estar *Em teste / Testing*.
- Clique **Publicar app** (*Publish app*) → **Confirmar**.
- Tem de ficar **Em produção / In production**.

**Por que isso importa:** com o app em *Testing*, o Google expira todo refresh token em **7
dias**. A automação funciona uma semana e morre no sábado — e o log parece bug. Publicado, o
token dura até você revogar.

Se o Google avisar que "escopos restritos exigem verificação": pode ignorar e publicar. Só você
usa o app; na hora de autorizar vai aparecer um aviso de app não verificado, com o caminho
*"Avançado → Acessar (não seguro)"*. É o esperado.

### 3d. Criar o cliente OAuth

🔗 **https://console.cloud.google.com/auth/clients/create?project=SEU_ID**

- **Tipo de aplicativo:** **TVs e dispositivos de entrada limitada**
  (*TVs and Limited Input devices*). Tem de ser esse: o robô usa o fluxo de dispositivo, que
  não precisa de servidor nem de porta aberta na sua máquina.
- **Nome:** `casa-tv`
- **Criar** → aparece uma janela com **ID do cliente** e **Chave secreta do cliente**.

Copie os dois. Não feche a janela antes de copiar — a chave secreta pode não ser mostrada de
novo (se perder, é só criar outro cliente).

## Passo 4 — colar as duas chaves e autorizar

### 4a. Guardar as chaves no repositório

🔗 **https://github.com/reboclbrank-max/site/settings/secrets/actions**

Clique **New repository secret** duas vezes, com estes nomes **exatos** (sem espaço, maiúsculas
como está):

| nome | valor |
|---|---|
| `YT_CLIENT_ID` | o ID do cliente do passo 3d |
| `YT_CLIENT_SECRET` | a chave secreta do passo 3d |

Não me mande esses valores pelo chat, e eles não entram em arquivo nenhum do repositório.

### 4b. Rodar a autorização

🔗 **https://github.com/reboclbrank-max/site/actions/workflows/autorizar-youtube.yml**

- Botão **Run workflow** → branch `main` → **Run workflow**.
- Abra a execução que aparecer. Em ~1 minuto o resumo mostra:

```
Para autorizar, abra:      https://www.google.com/device
E digite este código:      XXXX-XXXX
```

- Abra o link, digite o código, escolha **a conta que é dona do canal**, e aprove tudo.
- Volte à execução: ela detecta a aprovação, grava `YT_REFRESH_TOKEN` sozinha e mostra só o
  prefixo e o tamanho do segredo. O valor nunca aparece em log.

O robô fica esperando até 15 minutos. Se o código expirar, rode de novo — não tem limite de
tentativas.

### 4c. Provar que funcionou

🔗 **https://github.com/reboclbrank-max/site/actions/workflows/administrar-youtube.yml**

**Run workflow** → modo `estado`. A saída tem de mostrar:

```
canal: <nome do canal> · <inscritos> inscritos · <vídeos> vídeos · <views> views
```

Se aparecer `falta consentimento`, o passo 4b não terminou. Se aparecer `invalid_client`, as
duas chaves do passo 4a estão trocadas ou o cliente não é do tipo *TVs e dispositivos*.

---

## Depois disso: o que fica automático e o que não fica

| operação | automático? |
|---|---|
| ler inscritos, views, vídeos | ✅ |
| editar título, descrição, tags | ✅ (cron diário) |
| playlist, miniatura, comentários | ✅ |
| **envio de vídeo** | ✅ técnico — mas o vídeo pode sair **travado como privado** |
| deixar o vídeo público | ⚠️ **depende da auditoria** (abaixo) |

### A auditoria (só se o vídeo sair privado)

O Google trava como privado todo vídeo enviado por API de projeto não auditado, e isso **não
tem recurso** — nem você pelo YouTube Studio consegue liberar. A saída é o formulário de
auditoria de conformidade, gratuito:

🔗 **https://support.google.com/youtube/contact/yt_api_form**

Não precisa preencher hoje. Primeiro rode um envio e veja o `privacyStatus` — se o vídeo sair
público, a auditoria é desnecessária. Se sair privado, o formulário pede:

- **Tipo de solicitação:** *Complete a compliance audit to request for additional quota*
- **Número do projeto:** o número (só dígitos) do passo 1
- **Descrição do uso:** "Canal próprio de um único desenvolvedor. O cliente envia e administra
  apenas vídeos do próprio canal, com conteúdo de autoria própria, em volume de cerca de um
  vídeo por dia. Não há usuários terceiros, não há coleta de dados de espectadores."
- **Endpoints:** `videos.insert`, `videos.update`, `thumbnails.set`, `playlistItems.insert`,
  `channels.list`, `videos.list`
- **Política de privacidade:** `https://reboclbrank-max.github.io/site/privacidade.html`
  (verificada agora: responde 200)
- **Conta de demonstração:** o próprio canal; não há tela de terceiro para revisar

Prazo não é publicado pelo Google; relatos vão de uma a quatro semanas. Aprovado, o envio por
API passa a sair público e o resto continua como está.

## Números corretos (corrigindo o que eu disse antes)

Eu falei "≈6 vídeos/dia" porque usei a regra antiga (1.600 unidades por envio dentro de 10.000).
Desde 01/06/2026 o `videos.insert` tem cota própria: **100 envios por dia** e **100 buscas por
dia**, mais 10.000 unidades para o resto. Ou seja: volume não é o seu problema — a trava do
privado é.
