#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lê as estatísticas públicas dos vídeos que a casa publicou e grava um JSON.

POR QUE EXISTE (27/10/2026): o dono perguntou "quantas visualizações?" e o chat não tinha de
onde ler. O envio ao YouTube só registrava id e título (`posts/youtube-publicados.json`); nada
depois disso era medido.

O QUE ESTE SCRIPT NÃO FAZ: não inventa número. Se a API não responder, ele FALHA e o JSON do dia
não é reescrito — número velho com data nova é pior que número nenhum.

Autenticação: `YT_API_KEY` (chave de API, leitura de dados públicos). Não precisa de OAuth e não
toca em nada privado do canal. `videos.list` com `part=snippet,statistics` devolve views, likes e
comentários de vídeo público.

Uso:
  YT_API_KEY=... python3 tools/metricas-youtube.py
  YT_API_KEY=... python3 tools/metricas-youtube.py --saida posts/youtube-metricas.json
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "youtube-publicados.json")
SAIDA = os.path.join(RAIZ, "posts", "youtube-metricas.json")
URL_API = "https://www.googleapis.com/youtube/v3/videos"


def ids_publicados(caminho=REGISTRO):
    try:
        dados = json.load(open(caminho, encoding="utf-8"))
    except Exception:
        return []
    vistos = []
    for item in dados.get("publicados") or []:
        vid = str(item.get("id") or "").strip()
        if vid and vid not in vistos:
            vistos.append(vid)
    return vistos


def consultar(ids, chave, abrir=None, url_api=URL_API):
    """Devolve (lista_de_estatisticas, erro). Sem chave ou sem id é erro, não é zero."""
    abrir = abrir or urllib.request.urlopen
    if not chave:
        return [], "sem YT_API_KEY"
    if not ids:
        return [], "nenhum vídeo publicado registrado"
    parametros = urllib.parse.urlencode({
        "part": "snippet,statistics",
        "id": ",".join(ids[:50]),
        "key": chave,
    })
    try:
        with abrir(url_api + "?" + parametros, timeout=30) as resposta:
            corpo = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return [], "HTTP %s: %s" % (erro.code, (erro.read() or b"")[:160].decode("utf-8", "replace"))
    except Exception as erro:
        return [], str(erro)[:200]

    itens = []
    for item in corpo.get("items") or []:
        estat = item.get("statistics") or {}
        trecho = item.get("snippet") or {}
        itens.append({
            "id": item.get("id"),
            "titulo": (trecho.get("title") or "")[:120],
            "publicado_em": trecho.get("publishedAt") or "",
            "views": int(estat.get("viewCount") or 0),
            "likes": int(estat.get("likeCount") or 0),
            "comentarios": int(estat.get("commentCount") or 0),
        })
    if not itens:
        return [], "a API não devolveu nenhum vídeo para os ids registrados"
    return itens, None


def montar(itens, quando=None):
    total_views = sum(i["views"] for i in itens)
    total_likes = sum(i["likes"] for i in itens)
    total_com = sum(i["comentarios"] for i in itens)
    return {
        "medido_em": quando or datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "fonte": "YouTube Data API v3 · videos.list (part=snippet,statistics)",
        "videos": itens,
        "totais": {"videos": len(itens), "views": total_views, "likes": total_likes,
                   "comentarios": total_com},
    }


def executar(saida=SAIDA, chave=None, abrir=None, escrever=print):
    chave = chave if chave is not None else os.environ.get("YT_API_KEY", "")
    ids = ids_publicados()
    itens, erro = consultar(ids, chave, abrir=abrir)
    if erro:
        escrever("✘ não medi nada: " + erro)
        return False
    relatorio = montar(itens)
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
    escrever("métricas do YouTube: %d vídeo(s) · %d views · %d likes · %d comentários"
             % (len(itens), relatorio["totais"]["views"], relatorio["totais"]["likes"],
                relatorio["totais"]["comentarios"]))
    for item in itens:
        escrever("  %s — %d views · %d likes · %d comentários"
                 % (item["id"], item["views"], item["likes"], item["comentarios"]))
    return True


def main(argv):
    saida = SAIDA
    if "--saida" in argv:
        saida = argv[argv.index("--saida") + 1]
    return 0 if executar(saida=saida) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
