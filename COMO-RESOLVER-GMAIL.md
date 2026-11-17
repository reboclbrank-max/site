# Como está o Gmail (RESOLVIDO em 17/11/2026)

## ✅ Funciona. Não precisa fazer nada.

Medido no run #23 de `testar-todas-as-redes.yml`:

```
✅ Gmail IMAP/SMTP: conexão OK | 0 email(s) não lido(s)
```

A senha de app **já existia** desde 13/10/2026, gravada em `GMAIL_CHAT_APPPASS`. O que estava
errado era o CÓDIGO: dois arquivos liam `GMAIL_CHAT_PASS` (a senha comum da conta, que o Google
recusa por definição) **antes** de `GMAIL_CHAT_APPPASS` (a senha de app, que funciona).

O sintoma era `Application-specific password required` — que aponta para o dono ("gere uma senha
de app"), quando a senha de app estava lá, sendo ignorada por uma ordem de `||`.

A prova de que era o código e não a credencial: no run #22, no mesmo minuto, dois testes deram
respostas opostas. O verificador novo (que lia APPPASS primeiro) disse **"LOGIN OK — credencial
válida"**; o antigo disse **"Application-specific password required"**. Vencia o que lia o
secret errado.

Corrigido em `testar-todas-as-apis.js` e `postar-todas-as-redes.js`. Há contrato que falha se a
ordem voltar a se inverter. **O Gmail nunca funcionou para POSTAR por esse motivo** — não era
só o teste que estava vermelho; o envio também estava usando a senha errada.

---

# Se um dia o Gmail parar de funcionar de novo

O diagnóstico automatizado existe e responde três perguntas separadas:

```bash
node tools/marketing/verificar-gmail.js
```

| Código | Veredito | O que significa |
|---|---|---|
| 0 | `OK` | credencial válida — nada a fazer |
| 2 | `FALTA_CREDENCIAL` | o secret não chegou ao runner |
| 3 | `IMAP_NAO_ALCANCADO` | rede/porta — **não** gere senha nova por causa disto |
| 4 | `SENHA_RECUSADA` | aí sim: a senha de app foi revogada/expirada |

Só o caso 4 exige ação do dono. E é o único item da casa que exige navegador, por um motivo
técnico: **o Google não expõe API para criar senha de app.** Nenhum token de serviço substitui
isso numa conta pessoal.

---

## (Histórico) Os passos, caso o caso 4 apareça

---

## Passo 1 — gerar a senha de app (2 minutos, no navegador)

1. Abra <https://myaccount.google.com/security> logado em **reboclbrank@gmail.com**
2. Confirme que **Verificação em duas etapas** está ativa.
   Sem 2FA, o Google **não** oferece senha de app — é o bloqueio mais comum.
3. Abra <https://myaccount.google.com/apppasswords>
4. Nome do app: `casa-rebocl` (qualquer nome serve; é só para você reconhecer depois)
5. **Criar** → o Google mostra **16 letras em 4 grupos** (`abcd efgh ijkl mnop`)
6. Copie **sem os espaços**: `abcdefghijklmnop`

> ⚠️ A senha aparece **uma vez só**. Se fechar a janela sem copiar, gere outra.

## Passo 2 — colar nos secrets (é o único lugar)

A casa lê a credencial por **dois nomes diferentes**, dependendo do repositório. Os dois precisam
do mesmo valor:

| Repositório | Nome do secret | Valor |
|---|---|---|
| `reboclbrank-max/site` | `GMAIL_CHAT_APPPASS` | a senha de 16 letras (sem espaço) |
| `reboclbrank-max/site` | `GMAIL_CHAT_ADDRESS` | `reboclbrank@gmail.com` (conferir se já está) |
| `reboclbrank-max/chat` | `GMAIL_CHAT_PASS` | a mesma senha de 16 letras |
| `reboclbrank-max/chat` | `GMAIL_CHAT_ADDR` | `reboclbrank@gmail.com` |

Pelo navegador:
`https://github.com/reboclbrank-max/site/settings/secrets/actions`
`https://github.com/reboclbrank-max/chat/settings/secrets/actions`

Pela linha de comando (com o `gh` autenticado):

```bash
# cole a senha quando pedir (não fica no histórico do shell)
gh secret set GMAIL_CHAT_APPPASS --repo reboclbrank-max/site
gh secret set GMAIL_CHAT_PASS    --repo reboclbrank-max/chat
```

## Passo 3 — provar que funcionou (automatizado)

Não precisa abrir o Gmail para conferir. O próprio repositório tem o verificador:

```bash
# 1) teste local da conectividade (usa os secrets do ambiente, se existirem)
GMAIL_CHAT_ADDRESS=reboclbrank@gmail.com GMAIL_CHAT_APPPASS='abcdefghijklmnop' \
  node tools/marketing/verificar-gmail.js

# 2) o teste oficial, no GitHub (roda a cada 6h e no botão)
gh workflow run testar-todas-as-redes.yml --repo reboclbrank-max/site
gh run watch --repo reboclbrank-max/site
```

A saída dirá **uma** destas três coisas — e agora elas são distinguíveis:

| Mensagem | Significa | O que fazer |
|---|---|---|
| `✅ Gmail IMAP/SMTP: conexão OK` | resolvido | nada |
| `credencial recusada pelo Gmail` | a senha no secret não vale | refazer o passo 1 e 2 |
| `IMAP não alcançado` | porta 993/saída de rede | não é a senha; é rede do runner |

---

## Por que não é possível automatizar a geração

- O Google **não expõe endpoint** para criar senha de app. Não há OAuth scope que gere uma.
- OAuth2 para IMAP existe (`https://mail.google.com/`), mas exige consentimento interativo **uma
  vez** com um projeto no Google Cloud — ou seja, também passa pelo navegador do dono.
- Guardar a senha principal da conta para derivar senhas de app seria pior: daria acesso total
  em vez de a um protocolo.

**O que a automação faz por conta própria:** verifica, todo dia, se a credencial funciona e diz
exatamente qual dos três casos é. É o máximo que se pode fazer sem a conta na mão.

---

## Depois que a senha for trocada

Nada mais precisa ser feito. O `testar-todas-as-redes.yml` roda sozinho (cron a cada 6h) e o
`health-check.yml` audita a camada `cred-gmail` todo dia às 03:10. O painel passa a mostrar
`ativa` em vez de `ausente` sem nenhum commit.
