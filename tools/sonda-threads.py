#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonda do Threads: provar até onde a casa CHEGA, sem publicar nada.

POR QUE EXISTE (06/11/2026). O Threads era o canal com credencial e sem prova: `THREADS_TOKEN`
e `THREADS_USER_ID` estão nos segredos desde 13/10, o postador tem o caminho de envio escrito,
e nunca se conferiu se ele funciona. Credencial guardada não é canal; é promessa.

Mesma disciplina da sonda do Instagram: três perguntas ao servidor e parada antes do ponto sem
volta.

  1. IDENTIDADE  — GET /me: quem é a conta.
  2. PERMISSÃO   — GET /{id}/threads_publishing_limit: quantas publicações a API deixa fazer
                   nas últimas 24 h. Se o número existe, a permissão de publicar existe.
  3. CAMINHO     — POST /{id}/threads com `media_type=TEXT`: cria o CONTAINER e espera o
                   `status` virar FINISHED. Isso prova que o servidor aceita o token, aceita o
                   texto e monta o post.

E PÁRA: `threads_publish` não é chamado aqui. Container não publicado não aparece para
ninguém e expira sozinho.

O token nunca é impresso: só o prefixo e o tamanho.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

VERSAO = "v1.0"
BASE = "https://graph.threads.net/" + VERSAO
UA = {"User-Agent": "rebocl-sonda/1"}

TEXTO_DE_SONDA = ("sonda técnica da casa — este container NÃO é publicado "
                  "(o servidor só confirma token, texto e montagem)")


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
    """Mensagem da API sem vazar token (a Meta não ecoa o token em mensagem de erro)."""
    try:
        corpo = erro.read().decode()
        dados = json.loads(corpo)
        e = (dados.get("error") or {})
        return "HTTP %s · %s (código %s)" % (getattr(erro, "code", "?"),
                                             (e.get("message") or corpo)[:160], e.get("code"))
    except Exception:
        return str(erro)[:160]


def sonda(token=None, threads_user_id=None, http=None, pausa=time.sleep, tentativas=6, intervalo=3):
    """Devolve o relatório {passos, conclusao}. Nunca lança e NUNCA publica."""
    http = http or http_verdade
    token = token if token is not None else os.environ.get("THREADS_TOKEN")
    threads_user_id = threads_user_id if threads_user_id is not None else os.environ.get("THREADS_USER_ID")
    relatorio = {"_o_que_e": "relatório da sonda do Threads",
                 "_nunca_faz": "threads_publish — container não publicado expira sozinho",
                 "token": mascara(token), "conta": mascara(threads_user_id), "passos": {}}
    if not token or not threads_user_id:
        relatorio["conclusao"] = "SEM_CREDENCIAL: falta THREADS_TOKEN ou THREADS_USER_ID"
        return relatorio

    # 1. identidade
    try:
        me = http("GET", BASE + "/me?fields=id,username&access_token=" + token)
        relatorio["passos"]["identidade"] = {"ok": True, "username": me.get("username")}
    except Exception as erro:
        relatorio["passos"]["identidade"] = {"ok": False, "erro": _erro_legivel(erro)}
        relatorio["conclusao"] = "TOKEN_INVALIDO: nem a identidade respondeu"
        return relatorio

    # 2. permissão de publicar
    try:
        limite = http("GET", BASE + "/" + str(threads_user_id) +
                      "/threads_publishing_limit?fields=quota_usage,config&access_token=" + token)
        dados = (limite.get("data") or [{}])[0]
        relatorio["passos"]["permissao"] = {"ok": True, "quota_usada": dados.get("quota_usage"),
                                            "config": dados.get("config")}
    except Exception as erro:
        relatorio["passos"]["permissao"] = {"ok": False, "erro": _erro_legivel(erro)}
        relatorio["conclusao"] = ("SEM_PERMISSAO_DE_PUBLICAR: o token lê, mas não publica — "
                                  "publicar no Threads exige a permissão threads_content_publish")
        return relatorio

    # 3. caminho: container de texto + processamento (sem publicar)
    try:
        criado = http("POST", BASE + "/" + str(threads_user_id) + "/threads",
                      {"media_type": "TEXT", "text": TEXTO_DE_SONDA, "access_token": token})
        container = criado.get("id")
    except Exception as erro:
        relatorio["passos"]["caminho"] = {"ok": False, "erro": _erro_legivel(erro)}
        relatorio["conclusao"] = "TOKEN_OK_SEM_CAMINHO: identidade e quota ok, container recusado"
        return relatorio

    estado = None
    for _ in range(max(1, tentativas)):
        pausa(intervalo)
        try:
            consulta = http("GET", BASE + "/" + str(container) +
                            "?fields=status,error_message&access_token=" + token)
            estado = consulta.get("status")
            if estado in ("FINISHED", "ERROR", "EXPIRED", "PUBLISHED"):
                break
        except Exception as erro:
            relatorio["passos"]["caminho"] = {"ok": False, "container": container,
                                              "erro": _erro_legivel(erro)}
            relatorio["conclusao"] = "CONTAINER_CRIADO_SEM_LEITURA_DE_ESTADO"
            return relatorio

    relatorio["passos"]["caminho"] = {"ok": estado == "FINISHED", "container": container,
                                      "status": estado}
    relatorio["conclusao"] = {
        "FINISHED": "CAMINHO_INTEIRO_PROVADO: o token publica e o servidor monta o post. "
                    "Falta só o ciclo escolher texto no portão e publicar.",
        "ERROR": "CONTAINER_COM_ERRO: o servidor aceitou a chamada e recusou o conteúdo.",
        "PUBLISHED": "ATENCAO: o container apareceu como publicado — a sonda não chama "
                     "threads_publish; conferir se outra rotina publicou.",
    }.get(estado, "CONTAINER_NAO_FICOU_PRONTO_A_TEMPO: %s" % estado)
    return relatorio


def main(argv):
    relatorio = sonda()
    print(json.dumps(relatorio, ensure_ascii=False, indent=1))
    bom = relatorio.get("conclusao", "").startswith(("CAMINHO_INTEIRO_PROVADO", "CONTAINER_COM_ERRO"))
    return 0 if bom else 1


if __name__ == "__main__":  # pragma: no cover - uso manual
    raise SystemExit(main(sys.argv[1:]))
