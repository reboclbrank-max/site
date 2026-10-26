#!/usr/bin/env python3
"""Apaga os vídeos de sonda que as minhas próprias medições deixaram no canal.

Só toca em vídeo cujo título seja exatamente um dos títulos de sonda conhecidos
("teste interno", "Sondagem automática da casa..."). Nunca apaga vídeo do dono.
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
TITULOS_DE_SONDA = ("teste interno", "sondagem automática da casa", "sondagem automatica da casa")


def pedir(url, metodo="GET", token=None):
    r = urllib.request.Request(url, method=metodo, headers={"Authorization": "Bearer " + token})
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    refresh = os.environ.get("YT_REFRESH_TOKEN")
    if not refresh:
        print("FALHOU  sem consentimento")
        return 1
    token, erro = oauth.renovar(os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"), refresh)
    if erro:
        print("FALHOU  token: %s" % erro)
        return 1

    s, c = pedir(API + "/search?part=snippet&forMine=true&type=video&maxResults=50&order=date", token=token)
    if s != 200:
        print("FALHOU  busca -> HTTP %s" % s)
        return 1
    ids = [i["id"]["videoId"] for i in json.loads(c).get("items") or []]
    if not ids:
        print("nada a limpar")
        return 0
    s, c = pedir(API + "/videos?part=snippet,status&id=" + ",".join(ids), token=token)
    if s != 200:
        print("FALHOU  videos.list -> HTTP %s" % s)
        return 1
    apagados = 0
    for item in json.loads(c).get("items") or []:
        titulo = (item.get("snippet", {}).get("title") or "").strip().lower()
        if any(titulo.startswith(alvo) for alvo in TITULOS_DE_SONDA):
            s2, _ = pedir(API + "/videos?id=" + item["id"], "DELETE", token=token)
            print("%s  apagado '%s' (%s) -> HTTP %s"
                  % ("OK" if s2 in (200, 204) else "FALHOU",
                     item["snippet"]["title"][:45], item["id"], s2))
            apagados += 1
    print("total apagado: %d" % apagados)
    return 0


if __name__ == "__main__":
    sys.exit(main())
