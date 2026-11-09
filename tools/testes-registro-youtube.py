#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do registro do que foi publicado no YouTube — offline, sem rede e sem token.

POR QUE EXISTE (04/11/2026): o registro `posts/youtube-publicados.json` guardou por dias uma
entrada de mentira — id `VIDEO123`, url `https://youtu.be/VIDEO123` — que veio de um teste e
ficou no arquivo de produção. Nada conferia o registro, então ninguém viu.

O que este teste cerca:
  * todo id é id de vídeo do YouTube de verdade (11 caracteres) e a url aponta para ele;
  * nenhuma entrada de teste (`VIDEO123`, `TESTE`, `DEMO`...) sobrevive no arquivo;
  * id repetido não passa;
  * os campos que o chat lê estão todos lá;
  * o workflow de gravação cita a data do commit com o formato entre aspas — o jeito antigo
    gerava mensagem vazia (`... no YouTube ()`).
"""
import datetime
import json
import os
import re
import sys

import importlib.util as _iu

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = _iu.spec_from_file_location("enviar_youtube", os.path.join(RAIZ, "tools", "enviar-youtube.py"))
enviar = _iu.module_from_spec(_spec)
_spec.loader.exec_module(enviar)
REGISTRO = os.path.join(RAIZ, "posts", "youtube-publicados.json")
WORKFLOW = os.path.join(RAIZ, ".github", "workflows", "gravar-gameplay.yml")

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + detalhe if detalhe else ""))


def carrega():
    with open(REGISTRO, encoding="utf-8") as f:
        return json.load(f)


dados = carrega()
publicados = dados.get("publicados") if isinstance(dados, dict) else None

ok("o registro existe e tem a lista de publicados", isinstance(publicados, list),
   "esperava {'publicados': [...]}")

ok("todo id tem 11 caracteres (id do YouTube)", all(
    isinstance(p.get("id"), str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", p.get("id") or "")
    for p in (publicados or [])), "id com tamanho impossível")

ok("a url aponta para o próprio id", all(
    p.get("url") == "https://youtu.be/" + p.get("id", "")
    for p in (publicados or [])), "url não bate com o id")

ok("nenhuma entrada de teste sobreviveu", all(
    not re.match(r"(VIDEO|TESTE|TEST|DEMO|FAKE)", (p.get("id") or "").upper())
    for p in (publicados or [])), "id de teste no registro de produção")

ok("não há id repetido", len({p.get("id") for p in (publicados or [])}) == len(publicados or []))

ok("os campos que o chat lê estão presentes", all(
    all(p.get(campo) for campo in ("id", "url", "slug", "titulo", "arquivo", "quando"))
    for p in (publicados or [])), "campo faltando em alguma entrada")

ok("a data de publicação é ISO-8601", all(
    isinstance(p.get("quando"), str) and datetime.datetime.fromisoformat(p["quando"].replace("Z", "+00:00"))
    for p in (publicados or [])), "data inválida")

texto_workflow = open(WORKFLOW, encoding="utf-8").read() if os.path.exists(WORKFLOW) else ""
ok("o commit do registro cita a data com o formato entre aspas",
   "date -u +'%d/%m %H:%M UTC'" in texto_workflow,
   "o formato sem aspas gera mensagem vazia (...)")

# ---- a descrição guardada não pode mentir sobre o que está no ar ----------------------------
# Medido em 06/11/2026: quatro entradas terminavam em "…A trilha" (corte seco em 400 chars).
# Registro quebrado faz a chamada, o mostruário e a conferência lerem um texto que não existe.
# fim aceitável: pontuação, reticência da marcação de parcial, ou hashtag (as descrições do
# redator terminam com a hashtag da casa — "#jogobrasileiro" é fim de frase, não corte).
def _fim_ok(desc):
    fim = desc.strip()
    if not fim:
        return True
    ultimo = fim.split()[-1]
    return fim[-1] in ".!?…)" or ultimo.startswith("#")


_parciais = [p for p in (publicados or []) if not _fim_ok(p.get("descricao") or "")]
ok("nenhuma descrição do registro termina no meio da frase", not _parciais,
   str([p.get("url") for p in _parciais]))
ok("descrição guardada diz se está inteira ou é parcial",
   all(("descricao_completa" in p) for p in (publicados or []) if (p.get("descricao") or "").strip()),
   str([p.get("url") for p in (publicados or []) if (p.get("descricao") or "").strip()
        and "descricao_completa" not in p]))


# ID PLAUSÍVEL (06/11/2026): o registro já teve um envio falso de id "VIDEO123" gravado por um
# teste que rodava contra o repositório de verdade. Ele travou o envio do trailer do CEIFALUME
# ("vídeo idêntico já publicado, youtu.be/VIDEO123"). Id do YouTube tem 11 caracteres de base64url.
_implausiveis = [p.get("id") for p in (publicados or [])
                 if not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(p.get("id") or ""))]
ok("todo id no registro tem cara de id do YouTube (11 caracteres)", not _implausiveis,
   str(_implausiveis[:5]))
ok("a ferramenta de envio recusa registrar id implausível",
   hasattr(enviar, "id_plausivel") and enviar.id_plausivel("VIDEO123") is False
   and enviar.id_plausivel("dQw4w9WgXcQ") is True)


print("%d/%d contratos do registro do YouTube passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
