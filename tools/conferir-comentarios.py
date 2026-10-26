#!/usr/bin/env python3
"""Confere, com o token atual, se comentários e legendas realmente dependem de force-ssl.

Testa em vídeo PÚBLICO (a sonda anterior usou vídeo privado, o que confunde o resultado)
e mostra o motivo exato que o Google devolve em cada chamada.
"""
import json
import os
import sys
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import youtube_oauth as oauth  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"


def pedir(url, token):
    r = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def motivo(texto):
    try:
        err = json.loads(texto).get("error", {})
        return "%s / %s" % (err.get("status"), (err.get("errors") or [{}])[0].get("reason"))
    except Exception:
        return texto[:80]


def main():
    refresh = os.environ.get("YT_REFRESH_TOKEN")
    token, erro = oauth.renovar(os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"), refresh)
    if erro:
        print("FALHOU  token: %s" % erro)
        return 1
    print("escopo concedido:", oauth.ESCOPO)

    # acha vídeos públicos do próprio canal
    s, c = pedir(API + "/search?part=snippet&forMine=true&type=video&maxResults=50&order=viewCount", token)
    if s != 200:
        print("FALHOU  busca: %s" % motivo(c))
        return 1
    ids = [i["id"]["videoId"] for i in json.loads(c).get("items") or []]
    s, c = pedir(API + "/videos?part=snippet,status&id=" + ",".join(ids[:50]), token)
    publicos = [i for i in json.loads(c).get("items") or []
                if i.get("status", {}).get("privacyStatus") == "public"]
    print("vídeos públicos encontrados: %d" % len(publicos))
    if not publicos:
        print("FALHOU  nenhum vídeo público para testar")
        return 1
    vid = publicos[0]
    print("testando em: %s (%s)" % (vid["snippet"]["title"][:45], vid["id"]))

    provas = [
        ("commentThreads (vídeo público)", API + "/commentThreads?part=id,snippet&maxResults=1&videoId=" + vid["id"]),
        ("commentThreads (canal)", API + "/commentThreads?part=id&maxResults=1&allThreadsRelatedToChannelId=" + vid["snippet"]["channelId"]),
        ("comments (respostas)", API + "/comments?part=id&maxResults=1&videoId=" + vid["id"]),
        ("captions.list", API + "/captions?part=id&videoId=" + vid["id"]),
        ("videos.getRating", API + "/videos/getRating?id=" + vid["id"]),
        ("videos.rate (nota do próprio vídeo)", None),
    ]
    for rotulo, url in provas:
        if url is None:
            r = urllib.request.Request(API + "/videos/rate?id=%s&rating=none" % vid["id"],
                                       method="POST", headers={"Authorization": "Bearer " + token})
            try:
                resp = urllib.request.urlopen(r, timeout=60)
                print("OK    %-38s -> HTTP %s" % (rotulo, resp.status))
            except urllib.error.HTTPError as e:
                print("FALHOU %-37s -> HTTP %s | %s" % (rotulo, e.code, motivo(e.read().decode("utf-8", "replace"))))
            continue
        s, c = pedir(url, token)
        print("%s %-37s -> HTTP %s %s" % ("OK   " if s == 200 else "FALHOU", rotulo, s,
                                          "" if s == 200 else "| " + motivo(c)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
