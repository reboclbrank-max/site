#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede se a trava de "vídeo privado por projeto não auditado" vale para esta conta.

A política do Google diz que vídeo enviado por API de projeto não auditado fica travado como
privado. Mas há relato de que, quando quem autoriza é o dono do projeto, o vídeo sai com a
privacidade pedida. Em vez de acreditar em qualquer um dos dois, isto mede:

  1. sobe um vídeo REAL do repositório pedindo `unlisted` (não listado: aparece só para quem
     tem o link — não vai para o feed, não aparece na busca, não notifica inscrito);
  2. lê de volta o `privacyStatus` que o YouTube realmente aplicou;
  3. apaga o vídeo em seguida (videos.delete), deixando o canal exatamente como estava.

Veredito:
  * voltou `unlisted` → a trava NÃO vale aqui: envio por API pode publicar.
  * voltou `private` → a trava vale: só auditoria (ou envio pelo navegador) destrava.

Nada é publicado. O teste usa o próprio conteúdo da casa, não lixo.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import youtube_oauth as oauth  # noqa: E402
from importlib import util as _util

_spec = _util.spec_from_file_location("adm_yt", os.path.join(RAIZ, "tools", "administrar-youtube.py"))
adm = _util.module_from_spec(_spec)
_spec.loader.exec_module(adm)

API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
ARQUIVO_PADRAO = "media/reel.mp4"


def metadados(titulo):
    return {
        "snippet": {"title": titulo[:100],
                    "description": "Sondagem automática da casa para medir a política de "
                                   "privacidade da API. Apagada em seguida.",
                    "tags": ["sondagem"], "categoryId": "20"},
        "status": {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False},
    }


def abrir_sessao(token, tamanho, corpo, post=None):
    """Inicia o upload resumable. Devolve (url_da_sessao, erro)."""
    post = post or adm._requisicao
    dados, erro = post(UPLOAD, token, metodo="POST", corpo=corpo)
    return dados, erro


def subir(url_sessao, caminho, put=None, raiz=RAIZ):
    """PUT do arquivo inteiro na sessão. Devolve (video, erro)."""
    put = put or _put_binario
    with open(os.path.join(raiz, caminho), "rb") as f:
        conteudo = f.read()
    return put(url_sessao, conteudo)


def _put_binario(url, conteudo):
    req = urllib.request.Request(url, data=conteudo, method="PUT",
                                 headers={"Content-Type": "video/mp4",
                                          "Content-Length": str(len(conteudo))})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode()), None
    except Exception as e:
        corpo = getattr(e, "read", lambda: b"")()
        return None, str(e)[:120] + " " + corpo.decode()[:200]


def ler_privacidade(token, video_id, get=None):
    get = get or adm._requisicao
    dados, erro = get(API + "/videos?part=status,snippet&id=" + video_id, token)
    if erro or not dados:
        return None, erro or "resposta vazia"
    itens = dados.get("items") or []
    if not itens:
        return None, "vídeo não encontrado na listagem"
    return (itens[0].get("status") or {}), None


def apagar(token, video_id, deletar=None):
    deletar = deletar or _deletar
    return deletar(API + "/videos?id=" + video_id, token)


def _deletar(url, token):
    req = urllib.request.Request(url, method="DELETE",
                                 headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True, "apagado (%d)" % r.status
    except Exception as e:
        return False, str(e)[:100]


def veredito(privacidade):
    if privacidade == "unlisted":
        return "sem_trava", "o YouTube aplicou 'não listado' como pedido → envio por API pode publicar"
    if privacidade == "private":
        return "com_trava", "pedimos 'não listado' e o YouTube forçou 'privado' → trava de projeto não auditado"
    return "indefinido", "privacidade inesperada: %r" % privacidade


def main(argv):
    titulo = argv[1] if len(argv) > 1 else "Sondagem automática da casa (apagada em seguida)"
    ambiente = os.environ
    token, erro = adm.acesso(ambiente)
    if not token:
        print("✗ " + erro)
        return 1
    caminho = ARQUIVO_PADRAO
    tamanho = os.path.getsize(os.path.join(RAIZ, caminho))
    print("arquivo: %s (%d KB) · privacidade pedida: unlisted" % (caminho, tamanho // 1024))
    sessao, erro2 = abrir_sessao(token, tamanho, metadados(titulo))
    if erro2 or not sessao:
        print("✗ não abriu sessão de upload: " + str(erro2)[:300])
        return 1
    url = sessao.get("upload_url") or sessao.get("location") or sessao.get("id")
    if not url:
        print("✗ resposta sem URL de upload: " + str(sessao)[:300])
        return 1
    video, erro3 = subir(url, caminho)
    if erro3 or not video:
        print("✗ upload falhou: " + str(erro3)[:400])
        return 1
    vid = video.get("id")
    print("enviado: id=" + str(vid))
    priv, erro4 = ler_privacidade(token, vid)
    if erro4:
        print("✗ não consegui ler a privacidade: " + erro4)
    aplicado = (priv or {}).get("privacyStatus")
    tipo, frase = veredito(aplicado)
    print("privacidade aplicada: " + str(aplicado))
    print(("✓ " if tipo == "sem_trava" else "✗ ") + tipo + ": " + frase)
    if (priv or {}).get("uploadStatus"):
        print("uploadStatus: " + str(priv.get("uploadStatus")))
    ok_del, msg_del = apagar(token, vid)
    print(("✓ " if ok_del else "✗ ") + "limpeza: " + str(msg_del))
    print("VEREDITO=" + tipo)
    return 0 if tipo == "sem_trava" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
