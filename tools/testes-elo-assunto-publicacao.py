#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do elo assunto↔publicação: registra só o que saiu na rua.

Tudo com arquivos de amostra em pasta temporária — nenhum contrato mexe na base da casa.
"""
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("postador", os.path.join(RAIZ, "tools", "postador.py"))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


def escreve(raiz, caminho, dados):
    destino = os.path.join(raiz, caminho)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, ensure_ascii=False, indent=1)
        fp.write("\n")


# ------------------------------------------------------------------ registrar_publicacao_real
with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/repertorio.json",
            {"_o_que_e": "memoria de pauta", "usos": [], "publicacoes": []})
    escolha = {
        "pauta": {"angulo": "numero_medido", "assunto": "oficio",
                  "fatos": ["oficio-versao-prancheta"]},
        "texto": "o Prancheta está na versão 0.1 — versão medida direto da página do jogo.",
        "titulo": "Prancheta 0.1",
        "nota": 1.0,
    }
    entrada = p.registrar_publicacao_real(escolha, caminho_repertorio=os.path.join(tmp, "posts", "repertorio.json"))
    ok("registra publicacao real com assunto e angulo",
       entrada is not None and entrada["assunto"] == "oficio" and entrada["angulo"] == "numero_medido",
       entrada)
    ok("texto e titulo sao gravados (truncados)",
       "versão 0.1" in entrada["texto"] and entrada["titulo"] == "Prancheta 0.1",
       (entrada["texto"], entrada["titulo"]))
    ok("tipo é publicacao (diferente de uso)", entrada["tipo"] == "publicacao", entrada["tipo"])

    rep = json.load(open(os.path.join(tmp, "posts", "repertorio.json"), encoding="utf-8"))
    ok("publicacao fica na lista publicacoes do repertorio",
       len(rep["publicacoes"]) == 1 and rep["publicacoes"][0]["assunto"] == "oficio",
       rep["publicacoes"])
    ok("usos nao é tocado (so publicacoes cresce)",
       rep["usos"] == [], rep["usos"])

with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/repertorio.json",
            {"_o_que_e": "memoria de pauta", "usos": [], "publicacoes": []})
    # escolha None nao quebra
    entrada = p.registrar_publicacao_real(None, caminho_repertorio=os.path.join(tmp, "posts", "repertorio.json"))
    ok("escolha None retorna None sem quebrar", entrada is None)

with tempfile.TemporaryDirectory() as tmp:
    # repertorio ausente eh criado do zero
    escolha = {
        "pauta": {"angulo": "bastidor_de_erro", "assunto": "oficio", "fatos": []},
        "texto": "post de bastidor do oficio",
        "titulo": "Bastidor",
        "nota": 0.8,
    }
    p.registrar_publicacao_real(escolha, caminho_repertorio=os.path.join(tmp, "posts", "repertorio.json"))
    rep = json.load(open(os.path.join(tmp, "posts", "repertorio.json"), encoding="utf-8"))
    ok("repertorio ausente eh criado com publicacoes",
       len(rep["publicacoes"]) == 1 and rep["publicacoes"][0]["angulo"] == "bastidor_de_erro",
       rep["publicacoes"])

# ------------------------------------------------------------------ elo na busca de pautas
with tempfile.TemporaryDirectory() as tmp:
    # publicacoes repetidas do mesmo assunto podem ser contadas
    escreve(tmp, "posts/repertorio.json",
            {"_o_que_e": "memoria de pauta", "usos": [], "publicacoes": []})
    for i in range(3):
        p.registrar_publicacao_real({
            "pauta": {"angulo": "numero_medido", "assunto": "oficio", "fatos": []},
            "texto": "post %d sobre oficio" % i,
            "titulo": "T%d" % i,
            "nota": 1.0,
        }, caminho_repertorio=os.path.join(tmp, "posts", "repertorio.json"))
    rep = json.load(open(os.path.join(tmp, "posts", "repertorio.json"), encoding="utf-8"))
    oficios = [e for e in rep["publicacoes"] if e["assunto"] == "oficio"]
    ok("conta publicacoes por assunto", len(oficios) == 3, len(oficios))

print("\n%d/%d contratos do elo assunto↔publicação passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
