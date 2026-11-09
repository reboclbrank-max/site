#!/usr/bin/env python3
"""Lê comentários dos vídeos usando só a API key (dado público), sem OAuth.

Medido em 26/10/2026: commentThreads devolve 403 insufficientPermissions com o token
do device flow (que só tem escopo auth/youtube). Com API key, comentário PÚBLICO é
leitura liberada — é o suficiente para saber quando alguém comentou e o que disse.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3"


def pedir(url):
    try:
        return 200, urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    chave = os.environ.get("YT_API_KEY")
    canal_id = os.environ.get("YT_CHANNEL_ID")
    if not chave or not canal_id:
        print("FALHOU  faltam YT_API_KEY/YT_CHANNEL_ID")
        return 1

    # últimos vídeos públicos do canal (via uploads playlist = barato e sem OAuth)
    s, c = pedir(API + "/channels?part=contentDetails,snippet&id=%s&key=%s" % (canal_id, chave))
    if s != 200:
        print("FALHOU  channels -> %s %s" % (s, c[:120]))
        return 1
    dados = (json.loads(c).get("items") or [{}])[0]
    uploads = dados.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    print("canal:", dados.get("snippet", {}).get("title"), "| uploads:", uploads)

    s, c = pedir(API + "/playlistItems?part=contentDetails&maxResults=25&playlistId=%s&key=%s" % (uploads, chave))
    ids = [i["contentDetails"]["videoId"] for i in json.loads(c).get("items") or []] if s == 200 else []
    print("vídeos lidos:", len(ids))

    total, com_comentario = 0, 0
    for vid in ids:
        s, c = pedir(API + "/commentThreads?part=snippet&maxResults=5&order=time&videoId=%s&key=%s" % (vid, chave))
        if s != 200:
            continue
        itens = json.loads(c).get("items") or []
        if itens:
            com_comentario += 1
            total += json.loads(c).get("pageInfo", {}).get("totalResults", len(itens))
            for it in itens[:2]:
                sn = it["snippet"]["topLevelComment"]["snippet"]
                print("  · %s: %s" % (sn.get("authorDisplayName"), sn.get("textDisplay", "")[:70].replace("\n", " ")))
    print("RESUMO: %d vídeo(s) com comentário · %d comentário(s) lidos" % (com_comentario, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
