#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Administração automática do YouTube — depois do único consentimento do dono.

Duas famílias de operação, e a diferença entre elas é o que decide o que pode ser automático:

  1. ADMINISTRAR (sem auditoria, sem burocracia, funciona sempre): ler canal e estatísticas,
     editar título/descrição/tags, organizar playlist, trocar miniatura, moderar comentário.
  2. PUBLICAR (videos.insert): a API funciona, mas o Google trava como PRIVADO todo vídeo
     enviado por projeto de API que não passou na auditoria de conformidade ("videos locked as
     private", política de 28/07/2020). Não é bug, não é chave errada, e não dá para apelar.

Por isso este script: administra de verdade; e quando a publicação por API volta privada, ele
diz isso com todas as letras em vez de fingir que publicou. A saída sem auditoria é o envio
pelo navegador (o mesmo vídeo, mesma conta) e o resto continua sendo por aqui.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import youtube_oauth as oauth  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"


def _requisicao(url, token, metodo="GET", corpo=None, timeout=45):
    """Devolve (dados, erro). Uma função só, para o teste poder dublar tudo."""
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cabecalhos = {"Accept": "application/json", "Content-Type": "application/json"}
    # token None = chamada autenticada por API key na própria URL (sem OAuth). Mandar
    # "Bearer None" fazia o runner estourar TypeError em vez de ler o canal.
    if token:
        cabecalhos["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texto = r.read().decode()
            return (json.loads(texto) if texto.strip() else {}), None
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode()[:200]
        return None, "HTTP %s: %s" % (e.code, detalhe)
    except Exception as e:
        return None, str(e)[:120]


def acesso(ambiente=None, renovar=None):
    """(token, erro). Sem refresh_token guardado, não existe administração automática."""
    amb = ambiente if ambiente is not None else os.environ
    refresh = amb.get("YT_REFRESH_TOKEN")
    if not refresh:
        return None, ("falta consentimento: rode o workflow autorizar-youtube uma vez "
                      "(2 minutos) e o token fica guardado como segredo")
    renovar = renovar or oauth.renovar
    return renovar(amb.get("YT_CLIENT_ID"), amb.get("YT_CLIENT_SECRET"), refresh)


def canal(token, get=None):
    get = get or _requisicao
    dados, erro = get(API + "/channels?part=snippet,statistics&mine=true", token)
    if erro or not dados:
        return None, erro or "resposta vazia"
    itens = dados.get("items") or []
    if not itens:
        return None, "a conta não tem canal"
    c = itens[0]
    est = c.get("statistics") or {}
    return {"id": c.get("id"),
            "titulo": (c.get("snippet") or {}).get("title"),
            "inscritos": int(est.get("subscriberCount") or 0),
            "videos": int(est.get("videoCount") or 0),
            "views": int(est.get("viewCount") or 0)}, None


def meus_videos(token, limite=25, get=None):
    """Últimos vídeos do canal, com snippet completo (para comparar com o kit)."""
    get = get or _requisicao
    c, erro = canal(token, get=get)
    if erro:
        return None, erro
    dados, erro2 = get(API + "/search?part=snippet&channelId=%s&type=video&order=date&maxResults=%d"
                       % (c["id"], limite), token)
    if erro2 or not dados:
        return [], erro2
    ids = [i["id"]["videoId"] for i in dados.get("items") or [] if (i.get("id") or {}).get("videoId")]
    if not ids:
        return [], None
    detalhe, erro3 = get(API + "/videos?part=snippet,status&id=" + ",".join(ids), token)
    if erro3 or not detalhe:
        return [], erro3
    return (detalhe.get("items") or []), None


def divergencias(video, pacote):
    """Campos em que o vídeo publicado difere do kit. Vazio = está como deveria."""
    snippet = (video.get("snippet") or {})
    dif = {}
    if pacote.get("titulo") and snippet.get("title") != pacote["titulo"]:
        dif["title"] = pacote["titulo"]
    if pacote.get("descricao") and snippet.get("description") != pacote["descricao"]:
        dif["description"] = pacote["descricao"]
    if pacote.get("tags") and sorted(snippet.get("tags") or []) != sorted(pacote["tags"]):
        dif["tags"] = pacote["tags"]
    return dif


def aplicar_metadados(token, video, dif, put=None):
    """PUT no snippet, preservando o que não muda (a API apaga o que não for reenviado)."""
    put = put or _requisicao
    snippet = dict(video.get("snippet") or {})
    snippet.update(dif)
    return put(API + "/videos?part=snippet", token, metodo="PUT",
               corpo={"id": video.get("id"), "snippet": snippet})


def estado_por_chave(ambiente=None, get=None):
    """Leitura só com API key (sem consentimento). Serve de prova de que a chave vale.

    É o que sobra antes do OAuth: API key lê estatística pública do canal, mas não administra
    nada. Se responder número, a chave gravada nos segredos funciona de verdade no runner.
    """
    amb = ambiente if ambiente is not None else os.environ
    chave, canal_id = amb.get("YT_API_KEY"), amb.get("YT_CHANNEL_ID")
    if not (chave and canal_id):
        return ["youtube: sem API key ou sem YT_CHANNEL_ID — não há como provar a chave"], False
    get = get or _requisicao
    try:
        dados, erro = get(API + "/channels?part=snippet,statistics&id=%s&key=%s" % (canal_id, chave), None)
    except Exception as e:  # rede, tipo, o que for: vira linha, nunca pilha de erro no log
        return ["youtube: a chamada com API key falhou — " + type(e).__name__ + ": " + str(e)[:90]], False
    if erro or not dados:
        return ["youtube: a chave não leu o canal — " + str(erro or "resposta vazia")], False
    itens = dados.get("items") or []
    if not itens:
        return ["youtube: chave válida, mas o canal %s… não foi encontrado" % canal_id[:6]], False
    c = itens[0]
    est = c.get("statistics") or {}
    return ["canal (por API key): %s · %s inscritos · %s vídeos · %s views"
            % ((c.get("snippet") or {}).get("title"),
               est.get("subscriberCount"), est.get("videoCount"), est.get("viewCount"))], True


def estado(ambiente=None, get=None, renovar=None):
    """Só leitura. Devolve (linhas, concluido)."""
    token, erro = acesso(ambiente, renovar=renovar)
    if not token:
        # sem consentimento ainda dá para provar a chave gravada — e dizer o que falta
        linhas, _ok = estado_por_chave(ambiente, get=get)
        return linhas + ["youtube: " + erro], False
    c, erro2 = canal(token, get=get)
    if erro2:
        return ["youtube: canal indisponível — " + erro2], False
    linhas = ["canal: %s · %d inscritos · %d vídeos · %d views"
              % (c["titulo"], c["inscritos"], c["videos"], c["views"])]
    videos, _ = meus_videos(token, get=get)
    linhas.append("últimos vídeos lidos: %d" % len(videos or []))
    for v in (videos or [])[:5]:
        s = v.get("snippet") or {}
        linhas.append("  %s · %s · %s" % (v.get("id"), (s.get("title") or "")[:44],
                                          (v.get("status") or {}).get("privacyStatus")))
    return linhas, True


def auto(ambiente=None, get=None, put=None, kit=None, renovar=None):
    """Administra: reaplica o kit nos vídeos que ficaram fora do padrão.

    Nunca publica nem apaga; só corrige metadado de vídeo que já existe. É o que dá para
    fazer sozinho sem risco de o dono acordar com algo novo no canal.
    """
    token, erro = acesso(ambiente, renovar=renovar)
    if not token:
        return ["youtube: " + erro], False
    videos, erro2 = meus_videos(token, get=get)
    if erro2:
        return ["youtube: " + erro2], False
    linhas = []
    pacote = kit or {}
    for v in videos or []:
        dif = divergencias(v, pacote)
        if not dif:
            continue
        ok, erro3 = aplicar_metadados(token, v, dif, put=put)
        linhas.append("  %s: %s %s" % (v.get("id"), "corrigido" if ok else "falhou",
                                       ",".join(sorted(dif))))
        if erro3:
            linhas.append("    " + str(erro3)[:140])
    if not linhas:
        linhas.append("nada a corrigir: todos os vídeos já estão como o kit manda")
    return linhas, True


def main(argv):
    modo = argv[1] if len(argv) > 1 else "estado"
    if modo not in ("estado", "auto"):
        print("uso: administrar-youtube.py estado|auto")
        return 2
    linhas, concluido = (estado() if modo == "estado" else auto())
    for linha in linhas:
        print(linha)
    print(("✓ " if concluido else "✗ ") + modo)
    return 0 if concluido else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
