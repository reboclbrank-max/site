#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tira do ar vídeos repetidos do canal — só os ids informados, só com a palavra certa.

POR QUE EXISTE (04/11/2026): o mesmo gameplay do CEIFALUME foi gravado e publicado três vezes
(27/10, 30/10 e 04/11) com o mesmo título. Vídeo repetido divide clique e a plataforma pode ler
como repetição. `limpar-youtube.py` não serve aqui: ele apaga só vídeo de SONDA e nunca toca em
vídeo do dono — e é assim que tem de ser.

Duas ações, com palavras diferentes de propósito:

  privar -> deixa o vídeo privado. É REVERSÍVEL: volta a público com o mesmo comando.
  apagar -> remove de vez. NÃO volta. Exige digitar APAGAR.

O script não varre o canal em busca de alvo: só mexe no que vier escrito em IDS. Nenhum título,
descrição ou tag é alterado — a chamada usa `part=status` e manda apenas `privacyStatus`.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import youtube_oauth as oauth  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"
PALAVRAS = {"privar": "PRIVAR", "apagar": "APAGAR"}
ACOES = tuple(PALAVRAS)


def separar_ids(texto):
    """Aceita 'a,b c' e devolve a lista sem vazios."""
    return [parte for parte in re.split(r"[\s,;]+", (texto or "").strip()) if parte]


def validar_ids(ids):
    """(erros) — o id do YouTube tem 11 caracteres, mas não se assume o tamanho: aceita 6..24."""
    erros = []
    if not ids:
        erros.append("nenhum id informado")
    for item in ids:
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,24}", item):
            erros.append("id inválido: " + item)
    if len(set(ids)) != len(ids):
        erros.append("id repetido na lista")
    return erros


def exigir_ambiente(acao, confirmacao, ids_texto):
    """(erros) — nada sai daqui sem ação conhecida, palavra certa e id válido."""
    erros = []
    acao = (acao or "").strip().lower()
    if acao not in ACOES:
        erros.append("ação desconhecida: " + (acao or "(vazia)"))
        return erros
    esperada = PALAVRAS[acao]
    if (confirmacao or "").strip().upper() != esperada:
        erros.append("para %s é preciso digitar %s no campo de confirmação" % (acao, esperada))
    erros += validar_ids(separar_ids(ids_texto))
    return erros


def decisao(video, acao):
    """O que fazer com UM vídeo do `videos.list`. Recusa o que não é alvo ou já está feito."""
    if not video or not video.get("id"):
        return "recusar", "vídeo não encontrado na conta"
    status = video.get("status") or {}
    if status.get("privacyStatus") == "private" and acao == "privar":
        return "nada", "já estava privado"
    if status.get("privacyStatus") == "private" and acao == "apagar":
        return "apagar", "privado e repetido: pode sair de vez"
    return acao, "ok"


def corpo_privado(video_id):
    """Só o status. Título, descrição e tags ficam intocados (part=status)."""
    return {"id": video_id, "status": {"privacyStatus": "private"}}


def pedir(url, metodo="GET", token=None, corpo=None):
    dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(url, method=metodo, data=dados,
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    acao = (os.environ.get("ACAO") or "").strip().lower()
    ids_texto = os.environ.get("IDS") or ""
    confirmacao = os.environ.get("CONFIRMACAO")
    erros = exigir_ambiente(acao, confirmacao, ids_texto)
    if erros:
        for erro in erros:
            print("FALHOU  " + erro)
        return 1

    refresh = os.environ.get("YT_REFRESH_TOKEN")
    if not refresh:
        print("FALHOU  sem consentimento")
        return 1
    token, erro = oauth.renovar(os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"), refresh)
    if erro:
        print("FALHOU  token: %s" % erro)
        return 1

    ids = separar_ids(ids_texto)
    s, c = pedir(API + "/videos?part=snippet,status&id=" + ",".join(ids), token=token)
    if s != 200:
        print("FALHOU  videos.list -> HTTP %s" % s)
        return 1
    encontrados = {item["id"]: item for item in (json.loads(c).get("items") or [])}

    feitos = 0
    for video_id in ids:
        video = encontrados.get(video_id)
        o_que, motivo = decisao(video, acao)
        if o_que == "recusar":
            print("RECUSEI  %s — %s" % (video_id, motivo))
            continue
        if o_que == "nada":
            print("NADA     %s — %s" % (video_id, motivo))
            continue
        titulo = ((video.get("snippet") or {}).get("title") or "")[:48]
        if o_que == "privar":
            s2, _ = pedir(API + "/videos?part=status", "PUT", token=token, corpo={"id": video_id, "status": {"privacyStatus": "private"}})
            rotulo = "privado"
        else:
            s2, _ = pedir(API + "/videos?id=" + video_id, "DELETE", token=token)
            rotulo = "apagado"
        certo = s2 in (200, 204)
        print("%s  %s '%s' (%s) -> HTTP %s" % ("OK" if certo else "FALHOU", rotulo, titulo, video_id, s2))
        if certo:
            feitos += 1
    print("total ajustado: %d de %d" % (feitos, len(ids)))
    return 0 if feitos == len(ids) else 1


if __name__ == "__main__":
    sys.exit(main())
