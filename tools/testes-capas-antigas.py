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
# ---- LISTAR O CANAL INTEIRO (07/11/2026) -------------------------------------------------
# MEDIDO: o canal respondeu "50" e o registro tinha 51 capas. Não eram 50 vídeos: era o tamanho
# da página (maxResults=50, nextPageToken ignorado). Contagem truncada que parece exata é pior
# que contagem ausente — e é ela que alimenta o "estado da casa".
class _Resp(object):
    def __init__(self, dados):
        self._dados = dados

    def read(self):
        return json.dumps(self._dados).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _abrir_falso(paginas):
    pedidos = []

    def abrir(req, timeout=60):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        pedidos.append(url)
        if "playlistItems" not in url:
            return _Resp({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]})
        if "pageToken=PAGINA2" in url:
            return _Resp(paginas[1])
        return _Resp(paginas[0])

    return abrir, pedidos


_paginas = [
    {"items": [{"snippet": {"resourceId": {"videoId": "V%02d" % i}, "title": "vídeo %d" % i,
                            "publishedAt": "2026-11-01"}} for i in range(50)],
     "nextPageToken": "PAGINA2"},
    {"items": [{"snippet": {"resourceId": {"videoId": "V50"}, "title": "vídeo 50",
                            "publishedAt": "2026-10-01"}}]},
]
_abrir, _pedidos = _abrir_falso(_paginas)
_listados = capa.listar_videos("token-de-mentira", abrir=_abrir)
ok("lê o canal inteiro, não só a primeira página", len(_listados) == 51, len(_listados))
ok("o último da segunda página entra", _listados and _listados[-1]["id"] == "V50",
   _listados[-1] if _listados else None)
ok("pede a segunda página com pageToken", any("pageToken=PAGINA2" in u for u in _pedidos), _pedidos[-1:])
ok("não pede página depois da última", len([u for u in _pedidos if "playlistItems" in u]) == 2,
   len(_pedidos))

_uma_pagina, _ = _abrir_falso([{"items": [{"snippet": {"resourceId": {"videoId": "S1"},
                                                       "title": "curto"}}]}])
ok("canal curto (uma página) não entra em laço", len(capa.listar_videos("t", abrir=_uma_pagina)) == 1)

# ---- vídeo de OUTRO jogo não é dívida de capa (07/11/2026) --------------------------------
# O dono perguntou pelos "118 sem capa": medido, eles são vídeos de outros jogos. O retrato
# passa a dizer isso com nome, para o número parar de parecer trabalho pendente.
import importlib as _il
_capa_estado = _il.util.spec_from_file_location("capa_estado2", os.path.join(RAIZ, "tools",
                                                                             "capa-dos-antigos.py"))
_m = _il.util.module_from_spec(_capa_estado)
_capa_estado.loader.exec_module(_m)
_bancada = tempfile.mkdtemp(prefix="retrato-")
_m.CAMINHO_ESTADO = os.path.join(_bancada, "capas-estado.json")
_m._token = lambda: "x"
_m.listar_videos = lambda t: [
    {"id": "CASA1", "publicado_em": "2026-11-01", "titulo": "CEIFALUME 0.1 — colheitas"},
    {"id": "OUTRO1", "publicado_em": "2026-10-01", "titulo": "gameplay de outro jogo qualquer"},
    {"id": "OUTRO2", "publicado_em": "2026-09-01", "titulo": "mais um jogo de terceiros"},
]
_m.main(["capa", "--ensaio", "--registro", os.path.join(_bancada, "vazio.json")])
_retrato = json.load(open(_m.CAMINHO_ESTADO, encoding="utf-8"))
ok("o retrato conta os vídeos de outros jogos", _retrato.get("outros_jogos") == 2,
   _retrato.get("outros_jogos"))
ok("o retrato conta os da casa", _retrato.get("da_casa") == 1, _retrato.get("da_casa"))
ok("o retrato diz a decisão (outros jogos ficam sem capa por regra)",
   "por regra" in (_retrato.get("_decisao") or ""), _retrato.get("_decisao"))

tmp = tempfile.mkdtemp(prefix="capas-antigas-")
# o ensaio grava o retrato da cobertura; a suíte aponta para o tmp para não escrever na casa
capa.CAMINHO_ESTADO = os.path.join(tmp, "capas-estado.json")
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

# ---- --forcar: repintar quando o desenho melhora ------------------------------------------
reg_for = os.path.join(tmp, "reg-forcar.json")
_1 = capa.executar("tok", "APLICAR", raiz=tmp, limite=6, registro_caminho=reg_for,
                   listar=listar_falso, baixar=baixar_falso, aplicar_fn=aplicar_ok,
                   escrever=lambda *a, **k: None)[1]
_2 = capa.executar("tok", "APLICAR", raiz=tmp, limite=6, registro_caminho=reg_for,
                   listar=listar_falso, baixar=baixar_falso, aplicar_fn=aplicar_ok,
                   escrever=lambda *a, **k: None, forcar=True, somente=["AAA111", "BBB222"])[1]
ok("--forcar repinta quem já tem capa (desenho melhor não fica preso ao antigo)",
   [x["id"] for x in _2["aplicadas"]] == ["AAA111", "BBB222"], _2["aplicadas"])
ok("repintar não duplica a linha no registro",
   len([x for x in json.load(open(reg_for, encoding="utf-8"))["aplicadas"]
        if x["id"] == "AAA111"]) == 1)

# ---- só conteúdo da casa por omissão (06/11/2026) -----------------------------------------
# A lista real do canal tem 34 uploads sem capa da casa, e 29 deles são de 2025 com títulos que
# não são da casa (Racing Master, Cooking Bride, Summoners War...). O padrão tem de ser o seguro.
VIDEOS_MISTOS = VIDEOS + [
    {"id": "ZZZ999", "titulo": "Racing Master: O MELHOR jogo de carros realista de 2025!"},
    {"id": "YYY888", "titulo": "Cooking Bride to Primrose Lake"},
]
ok("vídeo que não cita jogo da casa fica de fora por omissão",
   "ZZZ999" not in [v["id"] for v in capa.candidatos(VIDEOS_MISTOS, {"aplicadas": []})],
   [v["id"] for v in capa.candidatos(VIDEOS_MISTOS, {"aplicadas": []})])
ok("com --todos ele entra (quem manda é o dono, não a ferramenta)",
   "ZZZ999" in [v["id"] for v in capa.candidatos(VIDEOS_MISTOS, {"aplicadas": []},
                                                  so_da_casa=False)])
ok("o relatório conta quantos ficaram fora por não serem da casa",
   "fora_da_casa" in capa.executar("tok", "APLICAR", raiz=tmp, limite=1,
                                   registro_caminho=os.path.join(tmp, "r5.json"),
                                   listar=lambda t, m=50: VIDEOS_MISTOS, baixar=baixar_falso,
                                   aplicar_fn=aplicar_ok, escrever=lambda *a, **k: None)[1])

# ---- os dois caminhos de capa falam o MESMO registro (06/11/2026) -------------------------
import importlib.util as _iu
_s = _iu.spec_from_file_location("enviar_yt", os.path.join(RAIZ, "tools", "enviar-youtube.py"))
enviar_yt = _iu.module_from_spec(_s)
_s.loader.exec_module(enviar_yt)
reg_unico = os.path.join(tmp, "capas-unificado.json")
from PIL import Image as _Im
if tem_pil:
    _capa = os.path.join(tmp, "capa-envio.png")
    _Im.new("RGB", (1280, 720), (9, 9, 9)).save(_capa)
    linha = enviar_yt.registrar_capa_aplicada("CCC333", "título do envio", _capa, raiz=tmp)
    ok("o envio registra a capa que aplicou", bool(linha and linha.get("sha256")), linha)
    lido = capa.carregar_registro(os.path.join(tmp, "posts", "capas-aplicadas.json"))
    ok("a ferramenta das capas lê o que o envio registrou",
       any(x["id"] == "CCC333" for x in lido["aplicadas"]), lido)
    # caminho ABSOLUTO não entra no registro versionado: registro é fato público
    linha_abs = enviar_yt.registrar_capa_aplicada("DDD444", "título do envio",
                                                  os.path.abspath(_capa), raiz=tmp)
    ok("caminho absoluto é gravado relativo ao repositório",
       linha_abs and not os.path.isabs(linha_abs.get("capa", "/")), linha_abs and linha_abs.get("capa"))
    enviar_yt.registrar_capa_aplicada("CCC333", "título do envio", _capa, raiz=tmp)
    lido2 = capa.carregar_registro(os.path.join(tmp, "posts", "capas-aplicadas.json"))
    ok("registrar duas vezes não duplica (upsert por id)",
       len([x for x in lido2["aplicadas"] if x["id"] == "CCC333"]) == 1)

# ---- o workflow ---------------------------------------------------------------------------
wf = open(os.path.join(RAIZ, ".github", "workflows", "capas-dos-antigos.yml"),
          encoding="utf-8").read()
ok("existe workflow para rodar isso sem depender da máquina de ninguém", "capa-dos-antigos" in wf)
ok("o workflow usa os segredos do YouTube", "secrets.YT_REFRESH_TOKEN" in wf)
ok("o workflow exige a palavra antes de aplicar", "APLICAR" in wf)
ok("o workflow versiona o registro das capas", "posts/capas-aplicadas.json" in wf)
# o passo de commit do envio precisa versionar o registro (a capa morria no stash do run)
_fluxos = {n: open(os.path.join(RAIZ, ".github", "workflows", n), encoding="utf-8").read()
           for n in ("gravar-prancheta.yml", "gravar-gameplay.yml")}
for _nome, _fonte in _fluxos.items():
    ok("%s versiona o registro das capas no commit do envio" % _nome,
       "git add posts/capas-aplicadas.json" in _fonte)

# ---- o QUADRO da capa é o melhor quadro, não o primeiro que baixar (07/11/2026) ------------
# A capa do _ffmjSMsW0Y saiu com um quadro preto: o "quadro" era o maxresdefault, que é a própria
# capa antiga quando o vídeo já tem miniatura enviada.
if tem_pil:
    from PIL import ImageDraw as _ID
    _preto = os.path.join(tmp, "quadro-preto.jpg")
    _Im.new("RGB", (480, 360), (2, 2, 2)).save(_preto, "JPEG")
    _vivo = os.path.join(tmp, "quadro-vivo.jpg")
    _im = _Im.new("RGB", (480, 360), (30, 60, 90))
    _d = _ID.Draw(_im)
    for _i in range(0, 480, 40):
        _d.rectangle([_i, 0, _i + 20, 360], fill=(200, 180, 40))
    _im.save(_vivo, "JPEG")
    ok("quadro preto pontua menos que quadro com imagem",
       capa._movimento(_preto) < capa._movimento(_vivo), (capa._movimento(_preto), capa._movimento(_vivo)))

    class _Resposta:
        def __init__(self, dados):
            self._dados = dados

        def read(self):
            return self._dados

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    _pedidos = []

    def _abrir(request, timeout=None):
        url = getattr(request, "full_url", str(request))
        _pedidos.append(url)
        nome = url.rsplit("/", 1)[-1].replace(".jpg", "")
        if nome in ("hq1", "maxresdefault"):
            return _Resposta(open(_preto, "rb").read())
        if nome in ("hq2", "sddefault"):
            return _Resposta(open(_vivo, "rb").read())
        raise OSError("404")

    _escolhido = capa.baixar_quadro("ZZZTESTE123", os.path.join(tmp, "q.jpg"), abrir=_abrir)
    ok("o quadro escolhido é o que tem imagem, não o primeiro que responde",
       _escolhido and capa._movimento(_escolhido) == capa._movimento(_vivo),
       capa._movimento(_escolhido or _preto))
    _pedidos.clear()
    capa.baixar_quadro("ZZZTESTE123", os.path.join(tmp, "q2.jpg"), abrir=_abrir, incluir_maxres=False)
    ok("com incluir_maxres=False, o maxresdefault nem é pedido",
       not any("maxresdefault" in u for u in _pedidos), _pedidos)
    _pedidos.clear()
    _fresco = capa.baixar_quadro("ZZZTESTE123", os.path.join(tmp, "q3.jpg"), abrir=_abrir, incluir_maxres=True)
    ok("com incluir_maxres=True (vídeo nunca pintado), o maxresdefault é tentado",
       any("maxresdefault" in u for u in _pedidos) and _fresco, _pedidos)
    ok("nenhum candidato responde → None",
       capa.baixar_quadro("ZZZTESTE123", os.path.join(tmp, "q4.jpg"),
                          abrir=lambda *a, **k: (_ for _ in ()).throw(OSError("sem rede"))) is None)
else:
    print("○ desenho → SKIP: sem Pillow nesta máquina")

# ---- o ensaio responde em NÚMEROS, mesmo quando não falta nada (06/11/2026) ----------------
import io as _io
import contextlib as _ctx
_canal = [{"id": "ZZZ1", "publicado_em": "2025-03-04", "titulo": "CEIFALUME — gravação antiga"},
          {"id": "ZZZ2", "publicado_em": "2025-03-05", "titulo": "CEIFALUME — outra gravação"}]
_orig_videos, _orig_token = capa.listar_videos, capa._token
capa.listar_videos, capa._token = (lambda _t: list(_canal)), (lambda: "token-de-teste")
try:
    _saida = _io.StringIO()
    with _ctx.redirect_stdout(_saida):
        _rc = capa.main(["capa-dos-antigos.py", "--ensaio", "--registro",
                         os.path.join(tmp, "registro-vazio.json")])
    _texto = _saida.getvalue()
    ok("o ensaio lista os dois vídeos sem capa", _texto.count("ZZZ") == 2, _texto.strip().splitlines())
    ok("o ensaio fecha com a contagem (não é log vazio)", "2 vídeo(s) sem capa" in _texto, _texto)
    _registro_cheio = os.path.join(tmp, "registro-cheio.json")
    with open(_registro_cheio, "w", encoding="utf-8") as _f:
        json.dump({"_o_que_e": "teste", "aplicadas": [
            {"id": "ZZZ1", "quando": "2026-01-01T00:00:00Z", "titulo": "a", "capa": "x.png"},
            {"id": "ZZZ2", "quando": "2026-01-01T00:00:00Z", "titulo": "b", "capa": "y.png"}]}, _f)
    _saida2 = _io.StringIO()
    with _ctx.redirect_stdout(_saida2):
        capa.main(["capa-dos-antigos.py", "--ensaio", "--registro", _registro_cheio])
    ok("com todos no registro, o ensaio diz zero em vez de não dizer nada",
       "0 vídeo(s) sem capa" in _saida2.getvalue(), _saida2.getvalue())
finally:
    capa.listar_videos, capa._token = _orig_videos, _orig_token

certos = sum(1 for _, c in res if c)
print("\n%d/%d contratos da capa dos antigos passaram" % (certos, len(res)))
raise SystemExit(0 if certos == len(res) else 1)
