#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envio de vídeo ao YouTube pelo pacote do kit — só com confirmação explícita.

REGRA DA CASA: publicar só com pedido explícito. Este script se recusa a rodar sem a palavra
de confirmação no argumento do workflow, e o workflow não tem cron: nada sai sozinho.

O que ele faz: pega o pacote já validado em `posts/kit-youtube.json`, renova o token a partir
do refresh_token guardado nos segredos e faz o upload resumable. Tudo o que aparece no vídeo
(título, descrição, tags) vem do kit — aqui não se inventa texto.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import youtube_oauth as oauth


def _validador_do_kit():
    """Importa tools/kit-youtube.py (nome com hífen) e devolve a função de validação."""
    import importlib.util
    caminho = os.path.join(RAIZ, "tools", "kit-youtube.py")
    spec = importlib.util.spec_from_file_location("kit_youtube", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.validar

KIT = os.path.join(RAIZ, "posts", "kit-youtube.json")
URL_UPLOAD = ("https://www.googleapis.com/upload/youtube/v3/videos"
              "?uploadType=resumable&part=snippet,status")
PALAVRA_CONFIRMACAO = "PUBLICAR"


def carregar_kit(caminho=KIT):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def pacote_do_kit(dados, slug):
    for p in dados.get("pacotes") or []:
        if p.get("slug") == slug:
            return p
    return None


def metadados(pacote):
    """Corpo do upload — construído a partir do kit, sem texto novo."""
    return {
        "snippet": {
            "title": pacote["titulo"],
            "description": pacote["descricao"],
            "tags": pacote["tags"],
            "categoryId": "20",           # Gaming
            "defaultLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }


def arquivo_do_video(pacote, raiz=RAIZ):
    return os.path.join(raiz, pacote["arquivo"])


def validar_antes(pacote, raiz=RAIZ, validador=None):
    """(erros). Reaproveita a barreira do kit: kit inválido não vira upload."""
    erros = []
    if not pacote:
        return ["pacote ausente no kit"]
    if validador:
        erros += validador(pacote)
    caminho = arquivo_do_video(pacote, raiz)
    if not os.path.exists(caminho):
        erros.append("arquivo ausente: " + pacote.get("arquivo", "?"))
    elif os.path.getsize(caminho) < 10_000:
        erros.append("arquivo pequeno demais para ser vídeo")
    if not pacote.get("titulo") or not pacote.get("descricao"):
        erros.append("título ou descrição vazios")
    return erros


def iniciar_upload(access_token, metadados_json, tamanho, abrir=None):
    """Abre a sessão de upload resumable. Devolve (url_da_sessao, erro)."""
    abrir = abrir or urllib.request.urlopen
    req = urllib.request.Request(URL_UPLOAD, data=json.dumps(metadados_json).encode(),
                                 method="POST",
                                 headers={"Authorization": "Bearer " + access_token,
                                          "Content-Type": "application/json; charset=UTF-8",
                                          "X-Upload-Content-Length": str(tamanho),
                                          "X-Upload-Content-Type": "video/mp4",
                                          "User-Agent": "rebocl-envio/1.0"})
    try:
        with abrir(req, timeout=60) as r:
            url = r.headers.get("Location")
            if not url:
                return None, "o YouTube não devolveu a URL de sessão"
            return url, None
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")[:200]
        return None, "abertura recusada (%s): %s" % (e.code, corpo)


def enviar_bytes(url_sessao, caminho, abrir=None):
    """Envia o arquivo inteiro numa requisição (vídeos da casa têm poucos MB)."""
    abrir = abrir or urllib.request.urlopen
    with open(caminho, "rb") as f:
        corpo = f.read()
    req = urllib.request.Request(url_sessao, data=corpo, method="PUT",
                                 headers={"Content-Type": "video/mp4",
                                          "Content-Length": str(len(corpo)),
                                          "User-Agent": "rebocl-envio/1.0"})
    try:
        with abrir(req, timeout=600) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, "envio recusado (%s): %s" % (e.code, e.read().decode("utf-8", "replace")[:200])


def executar(slug, confirmacao, raiz=RAIZ, renovar=None, validador=None,
             iniciar=None, enviar=None, escrever=print):
    """Executa o envio. Devolve (ok, mensagem)."""
    if str(confirmacao or "").strip().upper() != PALAVRA_CONFIRMACAO:
        return False, ("faltou a confirmação explícita (palavra %s): a casa não publica "
                       "sozinha" % PALAVRA_CONFIRMACAO)
    dados = carregar_kit(os.path.join(raiz, "posts", "kit-youtube.json"))
    pacote = pacote_do_kit(dados, slug)
    erros = validar_antes(pacote, raiz=raiz,
                          validador=validador or _validador_do_kit())
    if erros:
        return False, "kit recusado: " + "; ".join(erros)
    client_id = os.environ.get("YT_CLIENT_ID", "")
    client_secret = os.environ.get("YT_CLIENT_SECRET", "")
    refresh = os.environ.get("YT_REFRESH_TOKEN", "")
    token, erro = (renovar or oauth.renovar)(client_id, client_secret, refresh)
    if erro:
        return False, erro
    caminho = arquivo_do_video(pacote, raiz)
    tamanho = os.path.getsize(caminho)
    escrever("enviando %s (%d bytes) — %s" % (pacote["arquivo"], tamanho, pacote["titulo"][:60]))
    url, erro = (iniciar or iniciar_upload)(token, metadados(pacote), tamanho)
    if erro:
        return False, erro
    resultado, erro = (enviar or enviar_bytes)(url, caminho)
    if erro:
        return False, erro
    vid = (resultado or {}).get("id")
    if not vid:
        return False, "o YouTube não devolveu o id do vídeo"
    return True, "publicado: https://youtu.be/" + vid


def main(argv):
    slug = argv[0] if argv else "prancheta"
    confirmacao = os.environ.get("CONFIRMACAO", "")
    ok, msg = executar(slug, confirmacao)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
