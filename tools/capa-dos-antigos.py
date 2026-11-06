#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capa própria para os vídeos que subiram com a thumbnail automática do YouTube.

O QUE ESTAVA ERRADO (06/11/2026). Quando a casa passou a desenhar capa (tools/desenhar-capa.py),
os vídeos NOVOS ganharam capa única — e os antigos ficaram com o quadro automático do YouTube:
três vídeos com o mesmo tipo de imagem e título pequeno no canto. O dono viu no grid e cobrou.

O QUE ESTE ARQUIVO FAZ, em ordem:
  1. LISTA os vídeos do canal pela API (canal -> playlist de uploads), o que o token já permite;
  2. tira da lista os que já têm capa da casa (posts/capas-aplicadas.json);
  3. para cada um que sobra: baixa um QUADRO DO PRÓPRIO VÍDEO (i.ytimg.com), desenha o título
     real do vídeo por cima e aplica com thumbnails/set;
  4. grava o que aplicou (id, quando, sha256) — rodar de novo não repinta nem duplica.

O que NÃO faz: inventar título (usa o que está no ar, vindo da API), trocar título, publicar,
apagar. Capa é imagem; o vídeo não é tocado.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "capas-aplicadas.json")
PALAVRA = "APLICAR"


def _modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _agora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ registro
def carregar_registro(caminho=None):
    caminho = caminho or REGISTRO
    if not os.path.exists(caminho):
        return {"_o_que_e": "uma linha por vídeo que recebeu capa da casa", "aplicadas": []}
    try:
        with open(caminho, encoding="utf-8") as f:
            dado = json.load(f)
    except (OSError, ValueError):
        return {"aplicadas": []}
    if not isinstance(dado, dict) or not isinstance(dado.get("aplicadas"), list):
        return {"aplicadas": []}
    return dado


def gravar_registro(registro, caminho=None):
    caminho = caminho or REGISTRO
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(caminho + ".tmp", caminho)


def candidatos(videos, registro):
    """Vídeos sem capa da casa, do mais novo para o mais antigo."""
    ja = {str(x.get("id")) for x in (registro or {}).get("aplicadas") or [] if isinstance(x, dict)}
    saida = []
    for v in videos or []:
        vid = str((v or {}).get("id") or "").strip()
        if vid and vid not in ja:
            saida.append(dict(v, id=vid))
    return saida


# ------------------------------------------------------------------ API
def _get_json(url, abrir=None):
    abrir = abrir or urllib.request.urlopen
    with abrir(urllib.request.Request(url, headers={"User-Agent": "rebocl/1"}), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def playlist_de_uploads(access_token, abrir=None):
    dados = _get_json("https://www.googleapis.com/youtube/v3/channels?part=contentDetails"
                      "&mine=true&access_token=" + str(access_token), abrir=abrir)
    itens = dados.get("items") or []
    if not itens:
        return None
    return (((itens[0].get("contentDetails") or {}).get("relatedPlaylists") or {})
            .get("uploads"))


def listar_videos(access_token, maximo=50, abrir=None):
    """[{id, titulo, publicado_em}] direto da playlist de uploads do canal."""
    playlist = playlist_de_uploads(access_token, abrir=abrir)
    if not playlist:
        return []
    dados = _get_json("https://www.googleapis.com/youtube/v3/playlistItems"
                      "?part=snippet&maxResults=%d&playlistId=%s&access_token=%s"
                      % (min(int(maximo), 50), playlist, str(access_token)), abrir=abrir)
    videos = []
    for item in dados.get("items") or []:
        sn = item.get("snippet") or {}
        vid = ((sn.get("resourceId") or {}).get("videoId") or "").strip()
        if vid:
            videos.append({"id": vid, "titulo": (sn.get("title") or "").strip(),
                           "publicado_em": sn.get("publishedAt") or ""})
    return videos


def baixar_quadro(vid, destino, abrir=None):
    """Quadro do próprio vídeo (1280x720 quando existe). Devolve o caminho ou None."""
    abrir = abrir or urllib.request.urlopen
    for nome in ("maxresdefault", "sddefault", "hqdefault"):
        url = "https://i.ytimg.com/vi/%s/%s.jpg" % (vid, nome)
        try:
            with abrir(urllib.request.Request(url, headers={"User-Agent": "rebocl/1"}),
                       timeout=60) as r:
                dados = r.read()
            if len(dados) > 5_000:
                os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
                with open(destino, "wb") as f:
                    f.write(dados)
                return destino
        except Exception:  # noqa: BLE001
            continue
    return None


# ------------------------------------------------------------------ desenho e aplicação
def desenhar_capa(vid, titulo, quadro, saida, raiz=RAIZ):
    """Capa com o título REAL do vídeo por cima de um quadro dele. Devolve o resumo."""
    if not str(titulo or "").strip():
        raise ValueError("vídeo sem título na API: capa sem título é template")
    desenhar = _modulo("desenhar_capa", "desenhar-capa.py")
    return desenhar.desenhar(quadro, saida, titulo, numeros="", assinatura="",
                             marca="reboclbrank-max.github.io/site")


def aplicar(access_token, vid, caminho, aplicar_fn=None):
    if aplicar_fn is None:
        enviar = _modulo("enviar_youtube", "enviar-youtube.py")
        aplicar_fn = enviar.definir_capa
    return aplicar_fn(access_token, vid, caminho)


def executar(access_token, confirmacao, raiz=RAIZ, limite=6, registro_caminho=None,
             listar=None, baixar=None, aplicar_fn=None, escrever=print, somente=None,
             forcar=False):
    """Aplica capa nos vídeos antigos. Devolve (ok, relatório)."""
    if str(confirmacao or "").strip().upper() != PALAVRA:
        return False, {"motivo": "faltou a palavra %s: capa também é publicação, não sai sozinha"
                                 % PALAVRA, "aplicadas": [], "recusadas": []}
    registro = carregar_registro(registro_caminho)
    videos = (listar or listar_videos)(access_token, 50)
    if not videos:
        return False, {"motivo": "a API não devolveu vídeos (token sem permissão?)",
                       "aplicadas": [], "recusadas": []}
    alvos = candidatos(videos, registro)
    if forcar:
        # repintar de propósito: quando o desenho da capa melhora, a capa velha envelhece junto.
        # O registro continua valendo como histórico (o id é reescrito, não duplicado).
        ja = {x["id"] for x in (registro.get("aplicadas") or [])}
        alvos = [v for v in videos if v.get("id")] if not somente else [
            v for v in videos if v.get("id") in set(somente)]
        registro["aplicadas"] = [x for x in (registro.get("aplicadas") or [])
                                 if x.get("id") not in {v["id"] for v in alvos}]
        void = ja
    if somente:
        queridos = {str(x).strip() for x in somente}
        alvos = [v for v in alvos if v["id"] in queridos]
    alvos = alvos[:max(0, int(limite))]
    aplicadas, recusadas = [], []
    for v in alvos:
        quadro = (baixar or baixar_quadro)(v["id"], os.path.join(raiz, "media", "capas",
                                                                 "%s-quadro.jpg" % v["id"]))
        if not quadro:
            recusadas.append({"id": v["id"], "motivo": "não consegui baixar quadro do vídeo"})
            escrever("✘ %s: sem quadro" % v["id"])
            continue
        saida = os.path.join(raiz, "media", "capas", "%s-capa.png" % v["id"])
        try:
            resumo = desenhar_capa(v["id"], v.get("titulo"), quadro, saida, raiz=raiz)
        except Exception as erro:  # noqa: BLE001
            recusadas.append({"id": v["id"], "motivo": "desenho falhou: " + str(erro)[:120]})
            escrever("✘ %s: desenho falhou" % v["id"])
            continue
        ok, msg = aplicar(access_token, v["id"], saida, aplicar_fn)
        if not ok:
            recusadas.append({"id": v["id"], "motivo": msg})
            escrever("✘ %s: %s" % (v["id"], msg))
            continue
        linha = {"id": v["id"], "quando": _agora(), "titulo": v.get("titulo"),
                 "capa": os.path.relpath(saida, raiz), "sha256": resumo["sha256"]}
        registro.setdefault("aplicadas", []).append(linha)
        aplicadas.append(linha)
        escrever("✓ %s · %s · sha %s" % (v["id"], v.get("titulo", "")[:52], resumo["sha256"]))
    if aplicadas and registro_caminho is not None:
        gravar_registro(registro, registro_caminho)
    return bool(aplicadas or not alvos), {"aplicadas": aplicadas, "recusadas": recusadas,
                                          "candidatos": len(candidatos(videos, carregar_registro(
                                              registro_caminho)))}


def main(argv):
    ap = argparse.ArgumentParser(description="capa própria para os vídeos antigos")
    ap.add_argument("--confirmacao", default="")
    ap.add_argument("--limite", type=int, default=6)
    ap.add_argument("--registro", default=REGISTRO)
    ap.add_argument("--so", nargs="*", default=None, help="ids específicos")
    ap.add_argument("--ensaio", action="store_true", help="lista os candidatos e não aplica")
    ap.add_argument("--forcar", action="store_true",
                    help="repinta mesmo quem já tem capa (quando o desenho melhorou)")
    a = ap.parse_args(argv[1:])
    if a.ensaio:
        registro = carregar_registro(a.registro)
        for v in candidatos(listar_videos(_token()), registro)[:a.limite]:
            print("%s  %s  %s" % (v["id"], v.get("publicado_em", "")[:10], v.get("titulo", "")[:60]))
        return 0
    ok, rel = executar(_token(), a.confirmacao, limite=a.limite, registro_caminho=a.registro,
                       somente=a.so, forcar=a.forcar)
    print(json.dumps({k: rel[k] for k in ("aplicadas", "recusadas")}, ensure_ascii=False, indent=1))
    if not ok:
        print("✘ " + rel.get("motivo", "nada aplicado"), file=sys.stderr)
    return 0 if ok else 1


def _token():
    oauth = _modulo("youtube_oauth", "youtube_oauth.py")
    token, erro = oauth.renovar(os.environ.get("YT_CLIENT_ID", ""),
                                os.environ.get("YT_CLIENT_SECRET", ""),
                                os.environ.get("YT_REFRESH_TOKEN", ""))
    if not token:
        raise SystemExit("✘ sem token: " + str(erro))
    return token


if __name__ == "__main__":
    sys.exit(main(sys.argv))
