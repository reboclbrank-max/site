#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da capa dos vídeos antigos — sem rede, sem YouTube, com a API de mentira.

O dono cobrou: "os seis vídeos antigos seguem com thumbnail automática". A correção precisa
provar, sem tocar no canal: (1) só entra vídeo SEM capa da casa; (2) capa é desenhada com o
título real de cada vídeo, a partir de um quadro do próprio vídeo; (3) falha de envio nunca vira
sucesso nem entra no registro; (4) rodar de novo não repinta; (5) sem a palavra APLICAR, nada sai.
"""
import importlib.util
import json
import os
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = []


def ok(nome, cond, detalhe=""):
    res.append((nome, bool(cond)))
    print(("PASS" if cond else "FAIL") + " — " + nome
          + ("" if cond or not detalhe else "  [%s]" % (detalhe,)))


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


capa = carrega("capa_antigos", "capa-dos-antigos.py")

VIDEOS = [
    {"id": "AAA111", "titulo": "CEIFALUME 0.1 — jogo idle de fazenda noturna", "publicado_em": "2026-11-04"},
    {"id": "BBB222", "titulo": "6 colheitas em 2 min de CEIFALUME 0.1", "publicado_em": "2026-11-06"},
    {"id": "CCC333", "titulo": "Onde jogar CEIFALUME sem instalar loja", "publicado_em": "2026-11-06"},
    {"id": "", "titulo": "sem id não é vídeo", "publicado_em": ""},
]
REG = {"aplicadas": [{"id": "CCC333", "quando": "2026-11-06T18:00:00Z", "sha256": "x"}]}

fila = capa.candidatos(VIDEOS, REG)
ok("só entra vídeo que ainda não tem capa da casa",
   [v["id"] for v in fila] == ["AAA111", "BBB222"], [v["id"] for v in fila])
ok("vídeo sem id é ignorado (não vira entrada vazia)", all(v["id"] for v in fila))
ok("registro ausente não quebra a fila",
   len(capa.candidatos(VIDEOS, {"aplicadas": []})) == 3)

# ---- desenho: precisa de título real e de quadro do próprio vídeo -------------------------
tmp = tempfile.mkdtemp(prefix="capas-antigas-")
try:
    capa.desenhar_capa("AAA111", "", os.path.join(tmp, "q.jpg"), os.path.join(tmp, "s.png"))
    ok("vídeo sem título não recebe capa", False, "desenhou sem título")
except ValueError:
    ok("vídeo sem título não recebe capa", True)

try:
    from PIL import Image
    tem_pil = True
except ImportError:
    tem_pil = False
ok("Pillow disponível para desenhar (o workflow instala)", tem_pil)

desenhos = {}
if tem_pil:
    Image.new("RGB", (1280, 720), (18, 22, 30)).save(os.path.join(tmp, "quadro.jpg"), "JPEG")
    for v, t in (("AAA111", VIDEOS[0]["titulo"]), ("BBB222", VIDEOS[1]["titulo"])):
        saida = os.path.join(tmp, "%s.png" % v)
        r = capa.desenhar_capa(v, t, os.path.join(tmp, "quadro.jpg"), saida)
        desenhos[v] = r
    ok("a capa é desenhada do quadro do vídeo e tem tamanho de capa",
       all(r["bytes"] > 10_000 for r in desenhos.values()) and len(desenhos) == 2,
       {k: r["bytes"] for k, r in desenhos.items()})
    ok("duas capas do mesmo quadro saem diferentes (título diferente, sha diferente)",
       desenhos["AAA111"]["sha256"] != desenhos["BBB222"]["sha256"])

# ---- aplicação com API de mentira ---------------------------------------------------------
aplicadas_api = []


def aplicar_ok(token, vid, caminho, fn=None):
    aplicadas_api.append((vid, os.path.basename(caminho)))
    return True, "capa aplicada no vídeo " + vid


def aplicar_falha(token, vid, caminho, fn=None):
    return False, "não consegui aplicar a capa: HTTP 403"


def listar_falso(token, maximo=50):
    return list(VIDEOS)


def baixar_falso(vid, destino, abrir=None):
    if tem_pil:
        from PIL import Image
        os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
        Image.new("RGB", (1280, 720), (30, 40, 50)).save(destino, "JPEG")
        return destino
    return None


reg_caminho = os.path.join(tmp, "capas-aplicadas.json")
ok_rel = os.path.join(tmp, "nao-usado.json")

sem_palavra, rel = capa.executar("tok", "", raiz=tmp, limite=6, registro_caminho=reg_caminho,
                                 listar=listar_falso, baixar=baixar_falso,
                                 aplicar_fn=aplicar_ok, escrever=lambda *a, **k: None)
ok("sem a palavra APLICAR nada é aplicado",
   sem_palavra is False and rel["aplicadas"] == [] and "APLICAR" in rel["motivo"], rel["motivo"])
ok("e nada é escrito no registro", not os.path.exists(reg_caminho))

ok_apl, rel = capa.executar("tok", "APLICAR", raiz=tmp, limite=6, registro_caminho=reg_caminho,
                            listar=listar_falso, baixar=baixar_falso,
                            aplicar_fn=aplicar_ok, escrever=lambda *a, **k: None)
ok("com a palavra, aplica nos que faltam", ok_apl is True and len(rel["aplicadas"]) == 3,
   len(rel["aplicadas"]))
gravado = json.load(open(reg_caminho, encoding="utf-8"))
ok("o registro guarda id, quando e sha de cada capa",
   len(gravado["aplicadas"]) == 3 and all(x.get("sha256") and x.get("quando")
                                         for x in gravado["aplicadas"]))
ok("o registro não inventa capa para quem não recebeu", all(x["id"] for x in gravado["aplicadas"]))

segunda = capa.executar("tok", "APLICAR", raiz=tmp, limite=6, registro_caminho=reg_caminho,
                        listar=listar_falso, baixar=baixar_falso, aplicar_fn=aplicar_ok,
                        escrever=lambda *a, **k: None)[1]
ok("rodar de novo não repinta ninguém", segunda["aplicadas"] == [], segunda["aplicadas"])

reg2 = os.path.join(tmp, "reg2.json")
falhou = capa.executar("tok", "APLICAR", raiz=tmp, limite=1, registro_caminho=reg2,
                       listar=listar_falso, baixar=baixar_falso, aplicar_fn=aplicar_falha,
                       escrever=lambda *a, **k: None)
ok("falha do thumbnails/set NÃO vira sucesso", falhou[0] is False and falhou[1]["aplicadas"] == [],
   falhou[1])
ok("e falha não entra no registro", not os.path.exists(reg2) or
   json.load(open(reg2, encoding="utf-8"))["aplicadas"] == [])

so_um = capa.executar("tok", "APLICAR", raiz=tmp, limite=1, registro_caminho=os.path.join(tmp, "r3.json"),
                      listar=listar_falso, baixar=baixar_falso, aplicar_fn=aplicar_ok,
                      escrever=lambda *a, **k: None)[1]
ok("o limite é respeitado (um run não varre o canal inteiro)", len(so_um["aplicadas"]) == 1)

so_escolhido = capa.executar("tok", "APLICAR", raiz=tmp, limite=6,
                             registro_caminho=os.path.join(tmp, "r4.json"),
                             listar=listar_falso, baixar=baixar_falso, aplicar_fn=aplicar_ok,
                             escrever=lambda *a, **k: None, somente=["BBB222"])[1]
ok("--so aplica só nos ids pedidos", [x["id"] for x in so_escolhido["aplicadas"]] == ["BBB222"],
   so_escolhido["aplicadas"])

# ---- o workflow ---------------------------------------------------------------------------
wf = open(os.path.join(RAIZ, ".github", "workflows", "capas-dos-antigos.yml"),
          encoding="utf-8").read()
ok("existe workflow para rodar isso sem depender da máquina de ninguém", "capa-dos-antigos" in wf)
ok("o workflow usa os segredos do YouTube", "secrets.YT_REFRESH_TOKEN" in wf)
ok("o workflow exige a palavra antes de aplicar", "APLICAR" in wf)
ok("o workflow versiona o registro das capas", "posts/capas-aplicadas.json" in wf)

certos = sum(1 for _, c in res if c)
print("\n%d/%d contratos da capa dos antigos passaram" % (certos, len(res)))
raise SystemExit(0 if certos == len(res) else 1)
