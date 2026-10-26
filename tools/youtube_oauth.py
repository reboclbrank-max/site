#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OAuth do YouTube sem servidor local e sem software na máquina do dono.

POR QUE EXISTE (26/10/2026): o canal da casa publica 96 vídeos de outros jogos para cada 4
dos jogos da casa, e os da casa rendem quase o dobro por vídeo. Enviar vídeo por API exige
OAuth — a chave guardada é só de leitura. OAuth é PERMISSÃO, não custo: só o dono concede.

Este módulo faz a parte chata do consentimento: fluxo de DISPOSITIVO (device flow), que não
precisa de servidor local nem de redirecionamento — o dono abre uma URL, digita um código
curto e aprova. Depois disso o token fica guardado como segredo do repositório e o envio
passa a ser automático.

Regras que este arquivo respeita:
  * valor de segredo NUNCA é impresso: só nome, tamanho e prefixo de 4 caracteres;
  * dependência de rede só nas funções de rede, injetáveis para teste (barreira hermética);
  * o escopo é o mínimo necessário: só envio (youtube.upload).
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Escopo de administração completa, e não só de envio: o dono pediu "postar E administrar de
# forma automática". `youtube` inclui upload e cobre editar título/descrição/tags, playlist,
# thumbnail e comentários. Pedir só upload obrigaria um SEGUNDO consentimento depois — e
# consentimento é o único passo que depende dele, então tem de ser um só.
ESCOPO = "https://www.googleapis.com/auth/youtube"
URL_CODIGO = "https://oauth2.googleapis.com/device/code"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_SEGREDO = "https://api.github.com/repos/{repo}/actions/secrets/{nome}"
URL_CHAVE = "https://api.github.com/repos/{repo}/actions/secrets/public-key"
UA = "rebocl-oauth/1.0"


def resumo_de_segredo(valor):
    """O que pode aparecer em log: nome, tamanho e 4 primeiros caracteres. Nunca o valor."""
    valor = str(valor or "")
    if not valor:
        return "(vazio)"
    return "prefixo %s… · %d caracteres" % (valor[:4], len(valor))


def _post_json(url, dados, timeout=45, cabecalhos=None):
    """POST de formulário devolvendo JSON. Separado para poder ser trocado no teste."""
    corpo = urllib.parse.urlencode(dados).encode()
    req = urllib.request.Request(url, data=corpo, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "User-Agent": UA, **(cabecalhos or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), r.status
    except urllib.error.HTTPError as e:
        # o Google devolve erro útil em JSON no corpo (authorization_pending etc.)
        try:
            return json.loads(e.read().decode("utf-8")), e.code
        except Exception:
            return {"error": "http_%d" % e.code}, e.code


def pedir_codigo(client_id, post=_post_json):
    """Pede um código de dispositivo. Devolve (dados, erro)."""
    if not client_id:
        return None, "sem client_id (crie um cliente OAuth 'TV e dispositivos de entrada limitada')"
    dados, status = post(URL_CODIGO, {"client_id": client_id, "scope": ESCOPO})
    if status not in (200, 201) or "device_code" not in (dados or {}):
        return None, "o Google recusou o pedido (%s)" % ((dados or {}).get("error") or status)
    return dados, None


def trocar_token(client_id, client_secret, device_code, post=_post_json,
                 esperar=5, tentativas=1, dormir=time.sleep):
    """Troca o código aprovado por refresh_token. Devolve (dados, erro).

    `authorization_pending` e `slow_down` não são falha: são o dono ainda não aprovou.
    """
    for _ in range(max(1, tentativas)):
        dados, status = post(URL_TOKEN, {
            "client_id": client_id, "client_secret": client_secret,
            "device_code": device_code, "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        erro = (dados or {}).get("error")
        if status == 200 and (dados or {}).get("refresh_token"):
            return dados, None
        if erro in ("authorization_pending", "slow_down"):
            dormir(esperar if erro == "authorization_pending" else esperar + 5)
            continue
        return None, "troca recusada: %s" % (erro or status)
    return None, "o código expirou antes da aprovação"


def renovar(client_id, client_secret, refresh_token, post=_post_json):
    """Access token de curta duração a partir do refresh_token. Devolve (token, erro)."""
    if not (client_id and client_secret and refresh_token):
        return None, "faltam client_id, client_secret ou refresh_token"
    dados, status = post(URL_TOKEN, {
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    })
    token = (dados or {}).get("access_token")
    if status != 200 or not token:
        return None, "renovação recusada: %s" % ((dados or {}).get("error") or status)
    return token, None


# ------------------------------------------------------------------ guardar segredo
def _selar(chave_publica_b64, valor):
    """Sela o segredo no formato que o GitHub exige (libsodium sealed box)."""
    from nacl import encoding, public  # dependência instalada no workflow
    chave = public.PublicKey(chave_publica_b64.encode(), encoding.Base64Encoder())
    caixa = public.SealedBox(chave)
    return base64.b64encode(caixa.encrypt(str(valor).encode())).decode()


def gravar_segredo(repo, nome, valor, pat, get=None, put=None, selar=None):
    """Cria/atualiza um segredo do repositório. Devolve (ok, mensagem). Nunca imprime valor."""
    get = get or _get_json
    put = put or _put_json
    selar = selar or _selar
    if not (repo and nome and valor and pat):
        return False, "dados insuficientes para gravar o segredo"
    chave, erro = get(URL_CHAVE.format(repo=repo), pat)
    if erro or not chave.get("key"):
        return False, "não consegui a chave pública do repositório (%s)" % (erro or "sem key")
    try:
        selado = selar(chave["key"], valor)
    except Exception as e:
        return False, "não consegui selar o segredo (%s)" % type(e).__name__
    ok, erro = put(URL_SEGREDO.format(repo=repo, nome=nome), pat,
                   {"encrypted_value": selado, "key_id": chave["key_id"]})
    if not ok:
        return False, "o GitHub recusou o segredo (%s)" % (erro or "?")
    return True, "%s gravado no repositório %s (%s)" % (nome, repo, resumo_de_segredo(valor))


def _get_json(url, pat):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + pat,
                                               "Accept": "application/vnd.github+json",
                                               "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()), None
    except Exception as e:
        return {}, str(e)[:80]


def _put_json(url, pat, dados):
    req = urllib.request.Request(url, data=json.dumps(dados).encode(), method="PUT",
                                 headers={"Authorization": "Bearer " + pat,
                                          "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json",
                                          "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status in (200, 201, 204), None
    except Exception as e:
        return False, str(e)[:80]


def fluxo_completo(client_id, client_secret, repo, pat, esperar=5, limite_s=900,
                   post=_post_json, dormir=time.sleep, relogio=time.time, escrever=print):
    """Fluxo inteiro: pede código, mostra ao dono, espera a aprovação, grava o segredo.

    Devolve (ok, mensagem). Mostra o CÓDIGO (público, de uso único) e nunca o token.
    """
    codigo, erro = pedir_codigo(client_id, post=post)
    if erro:
        return False, erro
    escrever("1) Abra: " + codigo.get("verification_url", "https://www.google.com/device"))
    escrever("2) Digite o código: " + str(codigo.get("user_code")))
    escrever("3) Aprove o acesso do canal da casa ao YouTube (só envio de vídeo).")
    escrever("   esperando aprovação…")
    tentativas = max(1, int(limite_s / max(1, esperar)))
    dados, erro = trocar_token(client_id, client_secret, codigo["device_code"],
                               post=post, esperar=esperar, tentativas=tentativas, dormir=dormir)
    if erro:
        return False, erro
    ok, msg = gravar_segredo(repo, "YT_REFRESH_TOKEN", dados["refresh_token"], pat)
    if not ok:
        return False, msg
    escrever("   " + msg)
    escrever("   pronto: o envio de vídeo passa a ser automático neste repositório.")
    return True, "autorizado"


def main(argv):
    client_id = os.environ.get("YT_CLIENT_ID", "")
    client_secret = os.environ.get("YT_CLIENT_SECRET", "")
    repo = os.environ.get("REPO_ENVIO", "site")
    pat = os.environ.get("GHPAT", "")
    print("escopo pedido:", ESCOPO)
    print("client_id:", resumo_de_segredo(client_id))
    ok, msg = fluxo_completo(client_id, client_secret, repo, pat)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
