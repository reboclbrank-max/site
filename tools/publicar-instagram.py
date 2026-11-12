#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publicação autônoma no Instagram — cria container, espera processar e publica.

Fluxo (três chamadas à Graph API da Meta):
  1. POST /{ig-user-id}/media  -> cria o container de mídia (image_url + caption)
  2. GET  /{container-id}?fields=status_code,status  -> aguarda FINISHED
  3. POST /{ig-user-id}/media_publish  -> publica o container (creation_id)

O passo 3 é o que a sonda (sonda-instagram.py) NÃO faz — de propósito, para não publicar
sem decisão do ciclo. Este script é o caminho de publicação de verdade.

Variáveis de ambiente:
  IG_TOKEN        — token de acesso da Graph API (obrigatório)
  IG_USER_ID      — ID da conta do Instagram (obrigatório)
  IG_IMAGE_URL    — URL da imagem a publicar (padrão: imagem de sonda da casa)
  IG_CAPTION      — legenda do post (padrão: legenda automática)
  IG_PUBLICAR     — "1" para publicar de verdade; qualquer outro valor roda só até o
                    container FINISHED e imprime o creation_id sem publicar (ensaio)

Saída: JSON com os três passos e a conclusão. Código de saída:
  0 = publicado com sucesso
  1 = erro em qualquer passo
  2 = ensaio (container pronto, não publicado)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

VERSAO = "v21.0"
BASE = "https://graph.instagram.com/" + VERSAO
UA = {"User-Agent": "rebocl-instagram/1"}

IMAGEM_PADRAO = (
    "https://img.itch.zone/aW1hZ2UvNTAxNzQwNC8zMDA0MDAyNy5wbmc=/original/sNW2uy.png"
)
LEGENDA_PADRAO = (
    "Postagem automática da casa — conteúdo gerado pelo ciclo de marketing.\n"
    "#Prancheta #Ceifalume #GamingDev"
)


def mascara(valor):
    valor = str(valor or "")
    return "(vazio)" if not valor else valor[:4] + "…" + str(len(valor)) + " caracteres"


def http(metodo, url, dados=None):
    corpo = urllib.parse.urlencode(dados).encode() if dados else None
    req = urllib.request.Request(url, data=corpo, headers=dict(UA))
    if metodo != "GET":
        req.method = metodo
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _erro_legivel(erro):
    texto = str(erro)
    try:
        corpo = erro.read().decode()
        dados = json.loads(corpo)
        e = (dados.get("error") or {})
        return "HTTP %s · %s (código %s)" % (
            getattr(erro, "code", "?"),
            (e.get("message") or corpo)[:160],
            e.get("code"),
        )
    except Exception:
        return texto[:160]


def publicar(
    token=None,
    ig_user_id=None,
    image_url=None,
    caption=None,
    publicar_de_verdade=False,
    http_fn=None,
    pausa=time.sleep,
    tentativas=8,
    intervalo=3,
):
    """Devolve o relatório {passos, conclusao}. Nunca lança."""
    http_fn = http_fn or http
    token = token if token is not None else os.environ.get("IG_TOKEN")
    ig_user_id = ig_user_id if ig_user_id is not None else os.environ.get("IG_USER_ID")
    image_url = image_url if image_url is not None else os.environ.get(
        "IG_IMAGE_URL", IMAGEM_PADRAO)
    caption = caption if caption is not None else os.environ.get(
        "IG_CAPTION", LEGENDA_PADRAO)

    relatorio = {
        "_o_que_e": "relatório de publicação no Instagram",
        "token": mascara(token),
        "conta": mascara(ig_user_id),
        "passos": {},
    }

    if not token or not ig_user_id:
        relatorio["conclusao"] = "SEM_CREDENCIAL: falta IG_TOKEN ou IG_USER_ID"
        return relatorio

    # Passo 1: cria o container de mídia
    try:
        criado = http_fn(
            "POST",
            BASE + "/" + str(ig_user_id) + "/media",
            {
                "image_url": image_url,
                "caption": caption,
                "access_token": token,
            },
        )
        container_id = criado.get("id")
        relatorio["passos"]["criar_container"] = {
            "ok": bool(container_id),
            "container_id": container_id,
            "resposta": criado,
        }
    except Exception as erro:
        relatorio["passos"]["criar_container"] = {
            "ok": False,
            "erro": _erro_legivel(erro),
        }
        relatorio["conclusao"] = "FALHA_NO_CONTAINER: não foi possível criar o container de mídia"
        return relatorio

    if not container_id:
        relatorio["passos"]["criar_container"]["ok"] = False
        relatorio["conclusao"] = "CONTAINER_SEM_ID: a API não devolveu o id do container"
        return relatorio

    # Passo 2: aguarda o container ficar FINISHED
    estado = None
    for _ in range(max(1, tentativas)):
        pausa(intervalo)
        try:
            consulta = http_fn(
                "GET",
                BASE + "/" + str(container_id) + "?fields=status_code,status",
                {"access_token": token},
            )
            estado = consulta.get("status_code")
            if estado in ("FINISHED", "ERROR", "EXPIRED"):
                break
        except Exception as erro:
            relatorio["passos"]["aguardar_processamento"] = {
                "ok": False,
                "container": container_id,
                "erro": _erro_legivel(erro),
            }
            relatorio["conclusao"] = "CONTAINER_CRIADO_SEM_LEITURA_DE_ESTADO"
            return relatorio

    relatorio["passos"]["aguardar_processamento"] = {
        "ok": estado == "FINISHED",
        "container": container_id,
        "status_code": estado,
    }

    if estado != "FINISHED":
        relatorio["conclusao"] = {
            "ERROR": "CONTAINER_COM_ERRO: o servidor recebeu e recusou a mídia.",
            "EXPIRED": "CONTAINER_EXPIRADO: o container expirou antes de processar.",
        }.get(estado, "CONTAINER_NAO_FICOU_PRONTO_A_TEMPO: %s" % estado)
        return relatorio

    # Passo 3: publica o container (media_publish)
    if not publicar_de_verdade:
        relatorio["conclusao"] = {
            "ok": True,
            "container": container_id,
            "mensagem": "ensaio: container pronto para publicar (FINISHED), mas IG_PUBLICAR != 1",
        }
        return relatorio

    try:
        publicado = http_fn(
            "POST",
            BASE + "/" + str(ig_user_id) + "/media_publish",
            {
                "creation_id": container_id,
                "access_token": token,
            },
        )
        media_id = publicado.get("id")
        relatorio["passos"]["publicar"] = {
            "ok": bool(media_id),
            "media_id": media_id,
            "resposta": publicado,
        }
        if media_id:
            relatorio["conclusao"] = "PUBLICADO: mídia %s está no ar no Instagram" % media_id
        else:
            relatorio["conclusao"] = "PUBLICACAO_SEM_ID: a API não devolveu o id da mídia publicada"
    except Exception as erro:
        relatorio["passos"]["publicar"] = {
            "ok": False,
            "container": container_id,
            "erro": _erro_legivel(erro),
        }
        relatorio["conclusao"] = "FALHA_NA_PUBLICACAO: container criado e processado, mas media_publish falhou"
        return relatorio

    return relatorio


def main(argv):
    publicar_de_verdade = os.environ.get("IG_PUBLICAR", "").strip() == "1"
    relatorio = publicar(publicar_de_verdade=publicar_de_verdade)
    print(json.dumps(relatorio, ensure_ascii=False, indent=1))

    conclusao = str(relatorio.get("conclusao", ""))
    if conclusao.startswith("PUBLICADO"):
        return 0
    if "ensaio" in conclusao.lower():
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover - uso manual
    raise SystemExit(main(sys.argv[1:]))
