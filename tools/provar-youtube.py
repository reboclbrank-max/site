#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova, contra a API de verdade, o que a casa consegue fazer no YouTube.

Mede em vez de lembrar. Cada linha é uma chamada real e o código HTTP que voltou.
O que ele NÃO faz, de propósito:
  - não publica vídeo (nenhum byte de vídeo sobe; o upload é só iniciado e abandonado);
  - não deixa rastro: a escrita de metadados grava o MESMO valor que já estava,
    e a playlist de teste é criada privada e apagada na mesma execução.

Saída: uma linha por capacidade, com HTTP e detalhe. Nada de senha/token no log.
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


def pedir(url, metodo="GET", token=None, corpo=None, cru=False):
    dados = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=dados, method=metodo, headers=headers)
    # devolve o corpo INTEIRO: truncar aqui quebrava o json.loads (erro medido)
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers or {})
    except Exception as e:
        return 0, str(e)[:150], {}


def main():
    refresh = os.environ.get("YT_REFRESH_TOKEN")
    if not refresh:
        print("FALHOU  falta consentimento (YT_REFRESH_TOKEN)")
        return 1
    token, erro = oauth.renovar(os.environ.get("YT_CLIENT_ID"),
                                os.environ.get("YT_CLIENT_SECRET"), refresh)
    if erro or not token:
        print("FALHOU  sem token: %s" % (erro,))
        return 1
    print("OK  token renovado pelo refresh_token")

    # 1. escopos concedidos (define o que a API vai aceitar)
    s, c, _ = pedir("https://oauth2.googleapis.com/tokeninfo?access_token=" + urllib.parse.quote(token))
    escopos = []
    if s == 200:
        try:
            escopos = (json.loads(c).get("scope") or "").split()
        except Exception:
            escopos = []
        print("OK  escopos (%d): %s" % (len(escopos), " ".join(e.split("/")[-1] for e in escopos)))
        # auth/youtube é o escopo AMPLO: inclui ler, escrever metadados, playlists e upload.
        # (youtube.readonly seria só leitura; youtube.upload seria só enviar.)
        amplo = any(e.rstrip("/").endswith("/auth/youtube") for e in escopos)
        print("    escopo amplo (auth/youtube) %s" % ("presente — cobre leitura e escrita" if amplo else "AUSENTE"))
        print("    só leitura (youtube.readonly) %s" % ("presente" if any("readonly" in e for e in escopos) else "ausente"))
    else:
        print("FALHOU  tokeninfo -> HTTP %s" % s)

    # 2. leitura do canal
    s, c, _ = pedir(API + "/channels?part=snippet,statistics&mine=true", token=token)
    if s != 200:
        print("      corpo: %s" % c[:200].replace("\n", " "))
    canal = {}
    if s == 200:
        try:
            canal = (json.loads(c).get("items") or [{}])[0]
        except Exception:
            canal = {}
        st = canal.get("statistics", {})
        print("OK  canal lido: %s · inscritos=%s · vídeos=%s · views=%s"
              % (canal.get("snippet", {}).get("title"), st.get("subscriberCount"),
                 st.get("videoCount"), st.get("viewCount")))
    else:
        print("FALHOU  channels.list -> HTTP %s | %s" % (s, c[:120]))

    # 3. lê um vídeo do próprio canal (pega o mais recente da busca interna)
    s, c, _ = pedir(API + "/search?part=snippet&forMine=true&type=video&maxResults=1", token=token)
    vid = {}
    if s == 200:
        itens = json.loads(c).get("items") or []
        vid = itens[0] if itens else {}
        if vid:
            print("OK  busca no próprio canal: %s" % vid["snippet"]["title"][:50])
    if vid:
        vId = vid["id"]["videoId"]
        s, c, _ = pedir(API + "/videos?part=snippet,status&id=" + vId, token=token)
        if s == 200:
            det = (json.loads(c).get("items") or [{}])[0]
            print("OK  videos.list: %s · privacidade=%s"
                  % (det.get("snippet", {}).get("title", "")[:40], det.get("status", {}).get("privacyStatus")))

            # 4. ESCRITA inofensiva: grava o mesmo título/descrição que já estão lá
            sn = det["snippet"]
            corpo = {"id": vId, "snippet": {
                "title": sn["title"],
                "description": sn.get("description", ""),
                "categoryId": sn.get("categoryId", "20"),
            }}
            s, c, _ = pedir(API + "/videos?part=snippet", "PUT", token=token, corpo=corpo)
            print("%s  videos.update (regravando o mesmo texto) -> HTTP %s"
                  % ("OK" if s == 200 else "FALHOU", s))
            if s != 200:
                print("      %s" % c[:160])

    # 5. ESCRITA de playlist: cria privada, apaga em seguida (sem rastro)
    corpo = {"snippet": {"title": "teste interno (apagar)"}, "status": {"privacyStatus": "private"}}
    s, c, _ = pedir(API + "/playlists?part=snippet,status", "POST", token=token, corpo=corpo)
    if s == 200:
        pid = json.loads(c).get("id")
        print("OK  playlists.insert (privada) -> HTTP 200")
        s2, _, _ = pedir(API + "/playlists?id=" + pid, "DELETE", token=token)
        print("%s  playlists.delete -> HTTP %s" % ("OK" if s2 in (200, 204) else "FALHOU", s2))
    else:
        print("FALHOU  playlists.insert -> HTTP %s | %s" % (s, c[:120]))

    # 6. Caminho de upload: inicia a sessão resumable e ABANDONA (sem bytes = sem vídeo)
    corpo = {"snippet": {"title": "teste interno", "description": "", "categoryId": "20"},
             "status": {"privacyStatus": "private"}}
    s, c, h = pedir(API.replace("/youtube/v3", "/upload/youtube/v3") + "/videos?uploadType=resumable&part=snippet,status",
                    "POST", token=token, corpo=corpo)
    print("%s  videos.insert (sessão iniciada, nenhum byte enviado) -> HTTP %s"
          % ("OK" if s == 200 else "FALHOU", s))
    if s != 200:
        print("      %s" % c[:160])

    # 7. comentários: testa os dois jeitos, porque 403 pode ser permissão OU parâmetro
    alvo_com = vid["id"]["videoId"] if vid else ""
    for rotulo, url in [
        ("por vídeo", API + "/commentThreads?part=id&maxResults=1&videoId=" + alvo_com),
        ("por canal", API + "/commentThreads?part=id&maxResults=1&allThreadsRelatedToChannelId=" + (canal.get("id") or "")),
    ]:
        s, c, _ = pedir(url, token=token)
        motivo = ""
        if s != 200:
            try:
                motivo = (json.loads(c).get("error", {}).get("errors") or [{}])[0].get("reason", "")
            except Exception:
                motivo = c[:80]
        print("%s  commentThreads.list %s -> HTTP %s %s"
              % ("OK" if s == 200 else "FALHOU", rotulo, s, motivo))

    # 8. miniatura: tenta regravar a PRÓPRIA miniatura atual (sem mudar nada na tela)
    if vid:
        thumb = (vid["snippet"].get("thumbnails", {}).get("high") or {}).get("url")
        if thumb:
            try:
                img = urllib.request.urlopen(thumb, timeout=45).read()
                fronteira = "----ceifalume"
                corpo = (("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.jpg\"\r\n"
                          "Content-Type: image/jpeg\r\n\r\n" % fronteira).encode() + img +
                         ("\r\n--%s--\r\n" % fronteira).encode())
                r = urllib.request.Request(
                    API.replace("/youtube/v3", "/upload/youtube/v3") + "/thumbnails/set?videoId=" + vId,
                    data=corpo, method="POST",
                    headers={"Authorization": "Bearer " + token,
                             "Content-Type": "multipart/form-data; boundary=" + fronteira})
                resp = urllib.request.urlopen(r, timeout=90)
                print("OK  thumbnails.set (regravando a mesma imagem) -> HTTP %s · %d bytes"
                      % (resp.status, len(img)))
            except urllib.error.HTTPError as e:
                det = e.read()[:160].decode("utf-8", "replace")
                print("FALHOU  thumbnails.set -> HTTP %s | %s" % (e.code, det.replace("\n", " ")))
            except Exception as e:
                print("FALHOU  thumbnails.set -> %s" % str(e)[:120])

    # 9. legendas
    s, c, _ = pedir(API + "/captions?part=id&videoId=" + (vid["id"]["videoId"] if vid else ""), token=token)
    motivo = ""
    if s != 200:
        try:
            motivo = (json.loads(c).get("error", {}).get("errors") or [{}])[0].get("reason", "")
        except Exception:
            motivo = c[:80]
    print("%s  captions.list -> HTTP %s %s" % ("OK" if s == 200 else "FALHOU", s, motivo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
