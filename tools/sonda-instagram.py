#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonda do Instagram: provar até onde a casa CHEGA, sem publicar nada.

POR QUE EXISTE (06/11/2026). O que estava provado até hoje sobre o Instagram era pouco:
uma leitura de identidade ("vivo — @reboclbrank") e um post de 03/11 que pode ter vindo do
`agente`. Não havia prova de que o caminho de publicação (criar container → processar mídia)
funciona com o token que a casa tem. Sem essa prova, "ligar o Instagram" é fé.

Esta sonda faz três perguntas ao servidor e para antes do ponto sem volta:

  1. IDENTIDADE  — GET /me: quem é a conta, que tipo de conta, quantos posts.
  2. PERMISSÃO   — GET /{id}/content_publishing_limit: quantas publicações a API deixa
                   fazer nas últimas 24 h. Se este número existe, a permissão de publicar
                   existe; se der erro, o token é de leitura e publicar não vai funcionar.
  3. CAMINHO     — POST /{id}/media com uma imagem real da casa: cria o CONTAINER e espera
                   o `status_code` virar FINISHED. Isso prova que o servidor aceita o token,
                   baixa a imagem e processa a mídia.

E PÁRA. A última chamada — `media_publish` — NÃO é feita aqui, de propósito: container não
publicado expira sozinho em 24 h e nada aparece no perfil. Publicar de verdade é decisão do
ciclo, com texto aprovado pelo portão.

O token nunca é impresso: só o prefixo e o tamanho.
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
UA = {"User-Agent": "rebocl-sonda/1"}

# Imagem de sonda: página pública da casa (a mesma família usada pelo postador).
IMAGEM_DE_SONDA = ("https://img.itch.zone/aW1hZ2UvNTAxNzQwNC8zMDA0MDAyNy5wbmc=/original/sNW2uy.png")
LEGENDA_DE_SONDA = ("sonda técnica da casa — este container NÃO é publicado "
                    "(o servidor só confirma token, imagem e processamento)")


def mascara(valor):
    valor = str(valor or "")
    return "(vazio)" if not valor else valor[:4] + "…" + str(len(valor)) + " caracteres"


def http_verdade(metodo, url, dados=None):
    corpo = urllib.parse.urlencode(dados).encode() if dados else None
    req = urllib.request.Request(url, data=corpo, headers=dict(UA))
    if metodo != "GET":
        req.method = metodo
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _erro_legivel(erro):
    """Mensagem da API sem vazar token (o token não aparece em mensagem de erro da Meta)."""
    texto = str(erro)
    try:
        corpo = erro.read().decode()
        dados = json.loads(corpo)
        e = (dados.get("error") or {})
        return "HTTP %s · %s (código %s)" % (getattr(erro, "code", "?"),
                                             (e.get("message") or corpo)[:160], e.get("code"))
    except Exception:
        return texto[:160]


def sonda(token=None, ig_user_id=None, http=None, pausa=time.sleep, tentativas=6, intervalo=3):
    """Devolve o relatório {passos, conclusao}. Nunca lança e NUNCA publica."""
    http = http or http_verdade
    token = token if token is not None else os.environ.get("IG_TOKEN")
    ig_user_id = ig_user_id if ig_user_id is not None else os.environ.get("IG_USER_ID")
    relatorio = {"_o_que_e": "relatório da sonda do Instagram",
                 "_nunca_faz": "media_publish — container não publicado expira sozinho",
                 "token": mascara(token), "conta": mascara(ig_user_id), "passos": {}}
    if not token or not ig_user_id:
        relatorio["conclusao"] = "SEM_CREDENCIAL: falta IG_TOKEN ou IG_USER_ID"
        return relatorio

    # 1. identidade
    try:
        me = http("GET", BASE + "/me?fields=id,username,account_type,media_count&access_token=" + token)
        relatorio["passos"]["identidade"] = {"ok": True, "username": me.get("username"),
                                             "tipo": me.get("account_type"),
                                             "posts": me.get("media_count")}
    except Exception as erro:
        relatorio["passos"]["identidade"] = {"ok": False, "erro": _erro_legivel(erro)}
        relatorio["conclusao"] = "TOKEN_INVALIDO: nem a identidade respondeu"
        return relatorio

    # 2. permissão de publicar
    try:
        limite = http("GET", BASE + "/" + str(ig_user_id) +
                      "/content_publishing_limit?fields=quota_usage,config&access_token=" + token)
        dados = (limite.get("data") or [{}])[0]
        relatorio["passos"]["permissao"] = {"ok": True,
                                            "quota_usada": dados.get("quota_usage"),
                                            "config": dados.get("config")}
    except Exception as erro:
        relatorio["passos"]["permissao"] = {"ok": False, "erro": _erro_legivel(erro)}
        relatorio["conclusao"] = ("SEM_PERMISSAO_DE_PUBLICAR: o token lê, mas não publica — "
                                  "publicar pelo Instagram exige conta profissional e a "
                                  "permissão instagram_content_publish")
        return relatorio

    # 3. caminho: container + processamento (sem publicar)
    try:
        criado = http("POST", BASE + "/" + str(ig_user_id) + "/media",
                      {"image_url": IMAGEM_DE_SONDA, "caption": LEGENDA_DE_SONDA,
                       "access_token": token})
        container = criado.get("id")
    except Exception as erro:
        relatorio["passos"]["caminho"] = {"ok": False, "erro": _erro_legivel(erro)}
        relatorio["conclusao"] = "TOKEN_OK_SEM_CAMINHO: identidade e quota ok, container recusado"
        return relatorio

    estado = None
    for _ in range(max(1, tentativas)):
        pausa(intervalo)
        try:
            consulta = http("GET", BASE + "/" + str(container) + "?fields=status_code,status&access_token=" + token)
            estado = consulta.get("status_code")
            if estado in ("FINISHED", "ERROR", "EXPIRED"):
                break
        except Exception as erro:
            relatorio["passos"]["caminho"] = {"ok": False, "container": container,
                                              "erro": _erro_legivel(erro)}
            relatorio["conclusao"] = "CONTAINER_CRIADO_SEM_LEITURA_DE_ESTADO"
            return relatorio
    relatorio["passos"]["caminho"] = {"ok": estado == "FINISHED", "container": container,
                                      "status_code": estado}
    relatorio["conclusao"] = {
        "FINISHED": "CAMINHO_INTEIRO_PROVADO: token publica, servidor baixa e processa a "
                    "imagem. Falta só o ciclo escolher texto no portão e publicar.",
        "ERROR": "CONTAINER_COM_ERRO: o servidor recebeu e recusou a mídia (ver status).",
    }.get(estado, "CONTAINER_NAO_FICOU_PRONTO_A_TEMPO: %s" % estado)
    return relatorio


def main(argv):
    relatorio = sonda()
    print(json.dumps(relatorio, ensure_ascii=False, indent=1))
    bom = relatorio.get("conclusao", "").startswith(("CAMINHO_INTEIRO_PROVADO", "CONTAINER_COM_ERRO"))
    return 0 if bom else 1


if __name__ == "__main__":  # pragma: no cover - uso manual
    raise SystemExit(main(sys.argv[1:]))
