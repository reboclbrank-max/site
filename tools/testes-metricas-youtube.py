#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do medidor de métricas do YouTube (sem rede: a API é substituída)."""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "metricas", os.path.join(RAIZ, "tools", "metricas-youtube.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

total = 0
falhas = []


def ok(nome, cond, detalhe=""):
    global total
    total += 1
    if cond:
        print("OK  " + nome)
    else:
        falhas.append(nome)
        print("FALHOU  " + nome + ("  <" + str(detalhe) + ">" if detalhe else ""))


class Resposta:
    def __init__(self, corpo):
        self._corpo = json.dumps(corpo).encode()

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def abrir_com(corpo):
    def abrir(url, timeout=None):
        abrir.chamada = url
        return Resposta(corpo)
    abrir.chamada = ""
    return abrir


CORPO = {"items": [
    {"id": "abc", "snippet": {"title": "CEIFALUME", "publishedAt": "2026-10-27T15:34:14Z"},
     "statistics": {"viewCount": "12", "likeCount": "3", "commentCount": "1"}},
    {"id": "def", "snippet": {"title": "PRANCHETA"},
     "statistics": {"viewCount": "5"}},
]}

# 1. sem chave não mede nada (e não devolve zero)
itens, erro = m.consultar(["abc"], "")
ok("sem chave a medição falha (não inventa zero)", itens == [] and "YT_API_KEY" in erro, erro)

# 2. sem id registrado também é erro explícito
itens, erro = m.consultar([], "chave")
ok("sem vídeo registrado a medição falha", itens == [] and "registrado" in erro, erro)

# 3. leitura normal
abrir = abrir_com(CORPO)
itens, erro = m.consultar(["abc", "def"], "chave", abrir=abrir)
ok("lê views, likes e comentários", erro is None and itens[0]["views"] == 12
   and itens[0]["likes"] == 3 and itens[0]["comentarios"] == 1, itens)
ok("vídeo sem like/comentário conta como 0 (não quebra)",
   itens[1]["likes"] == 0 and itens[1]["comentarios"] == 0, itens[1])
ok("a chamada usa a API oficial de vídeos e os dois parts",
   "youtube/v3/videos" in abrir.chamada and "part=snippet" in abrir.chamada
   and "statistics" in abrir.chamada, abrir.chamada)

# 4. a API sem itens é erro, não relatório vazio
itens, erro = m.consultar(["abc"], "chave", abrir=abrir_com({"items": []}))
ok("resposta vazia da API falha em vez de gravar zeros", itens == [] and erro, erro)

# 5. o relatório gravado tem os totais somados e a fonte
relatorio = m.montar([
    {"id": "abc", "titulo": "CEIFALUME", "publicado_em": "", "views": 12, "likes": 3,
     "comentarios": 1},
    {"id": "def", "titulo": "PRANCHETA", "publicado_em": "", "views": 5, "likes": 0,
     "comentarios": 0},
])
ok("totais somam os vídeos", relatorio["totais"] == {"videos": 2, "views": 17, "likes": 3,
                                                     "comentarios": 1}, relatorio["totais"])
ok("o relatório diz de onde veio o número", "YouTube Data API" in relatorio["fonte"],
   relatorio["fonte"])
ok("o relatório tem data de medição", bool(relatorio.get("medido_em")), relatorio.get("medido_em"))

# 6. ids do registro são lidos e deduplicados
import tempfile
with tempfile.TemporaryDirectory() as pasta:
    caminho = os.path.join(pasta, "reg.json")
    json.dump({"publicados": [{"id": "abc"}, {"id": "abc"}, {"id": "def"}, {"id": ""}]},
              open(caminho, "w"))
    ok("o registro é lido sem duplicar id", m.ids_publicados(caminho) == ["abc", "def"],
       m.ids_publicados(caminho))

# 7. o workflow usa o segredo e não publica nada
fonte_wf = open(os.path.join(RAIZ, ".github", "workflows", "metricas-youtube.yml"),
                encoding="utf-8").read()
ok("o workflow usa YT_API_KEY de secrets", "secrets.YT_API_KEY" in fonte_wf)
ok("o workflow não escreve nada além das métricas",
   fonte_wf.count("git add") == 1 and "youtube-metricas.json" in fonte_wf)

print("\n%d/%d testes do medidor de métricas passaram" % (total - len(falhas), total))
sys.exit(1 if falhas else 0)
