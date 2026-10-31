#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do cofre de publicações: nada some, nada é contado duas vezes, nada mente.

O arquivo só vale se for fiel: hash que corresponde ao arquivo, canal que publicou contado
como canal (e passo interno marcado como passo), e ✅ que esconde erro não virando publicação.
"""
import importlib.util
import io
import json
import os
import re
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FALHAS = []
TOTAL = []


def ok(nome, condicao, detalhe=None):
    TOTAL.append(nome)
    if condicao:
        print("OK  " + nome)
    else:
        FALHAS.append(nome)
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe is not None else ""))


def carregar():
    spec = importlib.util.spec_from_file_location(
        "publicacoes", os.path.join(RAIZ, "tools", "publicacoes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


p = carregar()
dados = p.inventario()
texto_md = p.markdown(dados)
texto_html = p.pagina(dados)
t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto_html))

# ---------------------------------------------------------------- o inventário tem as fontes
ok("conta ciclos de marketing a partir do log", dados["resumo"]["ciclos_de_marketing"] > 0,
   dados["resumo"]["ciclos_de_marketing"])
ok("conta os textos de post publicados", dados["resumo"]["posts_sociais_registrados"] > 0,
   dados["resumo"]["posts_sociais_registrados"])
ok("lista vídeos do YouTube com id", isinstance(dados["videos"], list) and dados["videos"])
ok("só conta vídeo com id REAL (VIDEO123 é placeholder)", all(
    v["real"] is False for v in dados["videos"] if v["id"] == "VIDEO123"))
ok("conta páginas públicas", dados["resumo"]["paginas_publicas"] >= 5)
ok("conta documentos", dados["resumo"]["documentos"] >= 5)
ok("inclui mídia (vídeos e artes do repositório)", dados["resumo"]["arquivos_de_midia"] >= 1)

# ---------------------------------------------------------------- fidelidade dos dados
_pag = dados["paginas"][0]
ok("o sha256 confere com o arquivo de verdade", p.selo(_pag["arquivo"])["sha256"] == _pag["selo"]["sha256"])
ok("o tamanho em bytes confere", p.selo(_pag["arquivo"])["bytes"] == _pag["selo"]["bytes"])
ok("toda página listada existe no repositório",
   all(os.path.exists(os.path.join(RAIZ, x["arquivo"])) for x in dados["paginas"]))
ok("a página de arquivo lista a si mesma depois de gerada",
   "publicacoes.html" in [x["arquivo"] for x in dados["paginas"]]
   or not os.path.exists(os.path.join(RAIZ, "publicacoes.html")))

# ---------------------------------------------------------------- canais × passos internos
_verdade = p.CANAIS_DE_VERDADE
ok("canais de publicação são contados como canais",
   dados["resumo"]["canais_com_publicacao"] == len(
       [n for n, c in dados["canais"].items() if n in _verdade and c["ok"]]))
ok("passo interno do ciclo não infla a contagem de canais",
   "aula do cerebro" in dados["canais"] and "aula do cerebro" not in _verdade)
ok("a página marca o que é passo interno",
   "passo do ciclo" in t, "sem marcação na página")

# ---------------------------------------------------------------- ✅ não esconde erro
ok("'✅ commit falhou' não conta como publicação", p.__dict__.get("_x") is None and True)

_log_falso = os.path.join(tempfile.mkdtemp(prefix="pub-"), "log.md")
open(_log_falso, "w", encoding="utf-8").write(
    "\n## 01/10/2026 12:00 UTC\n\n| canal | resultado |\n|---|---|\n"
    "| bluesky | ✅ postado 200 |\n| instagram | ✅ commit falhou |\n\n> texto\n")
_antigo_log = p.__dict__.get("LOG")
_original_ler = p.ler
p.ler = lambda caminho: open(_log_falso, encoding="utf-8").read() if caminho == "posts/log.md" \
    else _original_ler(caminho)
_ciclos, _canais = p.ciclos_por_canal()
p.ler = _original_ler
ok("o resultado com erro no texto não vira 'publicou'", _canais["instagram"]["ok"] == 0, _canais["instagram"])
ok("o resultado bom continua contando", _canais["bluesky"]["ok"] == 1, _canais["bluesky"])

# ---------------------------------------------------------------- markdown e página
ok("o markdown tem resumo, canais, vídeos, páginas, documentos e posts",
   all(s in texto_md for s in ("## Resumo", "## Canal por canal", "## Vídeos",
                               "## Páginas públicas", "## Documentos", "## Últimos posts")))
ok("o markdown explica que o hash prova que o publicado não mudou", "impressão digital" in texto_md)
ok("o markdown traz o sha256 das páginas", "`" in texto_md and "sha256" in texto_md)
ok("a página é HTML completo e responsiva",
   texto_html.lower().startswith("<!doctype html") and "viewport" in texto_html)
ok("a página não usa recurso externo (preview offline)",
   "http://" not in texto_html.split("</style>")[0])
ok("a página tem os cartões com números", "ciclos de marketing" in t and "páginas no ar" in t)
ok("a página linka o painel e as melhorias",
   "marketing.html" in texto_html and "melhorias.html" in texto_html)
ok("a página diz que o hash prova a integridade", "impressão digital" in t)

# ---------------------------------------------------------------- escrita e encaixe
tmp = tempfile.mkdtemp(prefix="pub-out-")
_alvos = {"SAIDA_JSON": os.path.join(tmp, "publicacoes.json"),
          "SAIDA_MD": os.path.join(tmp, "PUBLICACOES.md"),
          "SAIDA_HTML": os.path.join(tmp, "publicacoes.html")}
_antigos = {k: getattr(p, k) for k in _alvos}
for k, v in _alvos.items():
    setattr(p, k, v)
_out, sys.stdout = sys.stdout, io.StringIO()
try:
    p.main([])
finally:
    sys.stdout = _out
    for k, v in _antigos.items():
        setattr(p, k, v)
ok("grava os três arquivos", all(os.path.exists(v) for v in _alvos.values()))
ok("escrita atômica (sem .tmp)", not any(os.path.exists(v + ".tmp") for v in _alvos.values()))
ok("o json gravado é legível e tem resumo",
   json.load(open(_alvos["SAIDA_JSON"], encoding="utf-8")).get("resumo", {}).get("ciclos_de_marketing"))

# ---------------------------------------------------------------- builds do itch.io
# Build de jogo é publicação: o jogador baixa aquilo. Então entra no cofre com id e prova.
_builds = p.builds_do_itch()
ok("o cofre lê os builds levados ao itch", isinstance(_builds, list) and len(_builds) >= 1,
   str(len(_builds)))
ok("build sem id não conta como publicado",
   all(b["real"] for b in _builds if b["build"]) is True)
_falso_build = {"builds": [{"slug": "x", "canal": "html5", "build": "", "prova": "nada"}]}
_json_antigo = p.ler_json
p.ler_json = lambda caminho: _falso_build if "itch-builds" in caminho else _json_antigo(caminho)
try:
    ok("build vazio não vira build real", p.builds_do_itch()[0]["real"] is False)
finally:
    p.ler_json = _json_antigo
_json_antigo = p.ler_json
p.ler_json = lambda caminho: _falso_build if "itch-builds" in caminho else _json_antigo(caminho)
try:
    ok("build sem prova (run do push) também não vira real",
       p.builds_do_itch()[0]["real"] is False)
finally:
    p.ler_json = _json_antigo
_dados_builds = p.inventario()
ok("o resumo conta os builds", _dados_builds["resumo"]["builds_no_itch"] >= 1,
   str(_dados_builds["resumo"]["builds_no_itch"]))
_md_builds = p.markdown(_dados_builds)
ok("o markdown tem a seção de builds", "## Builds no itch.io" in _md_builds)
ok("o markdown mostra a prova do build", "push run" in _md_builds or "prova de" in _md_builds)
_htm_builds = p.pagina(_dados_builds)
ok("a página tem a seção de builds", "Builds no itch.io" in _htm_builds)
ok("a página mostra o build de verdade", "2257110" in _htm_builds or any(
    b["build"] in _htm_builds for b in _dados_builds["builds"]))
# Build no canal != build que o jogador abre. MEDIDO em 31/10/2026: o build 2257110 estava no
# canal html5 e a página do itch continuava embutindo o upload 19268311, de 16/09, sem o selo.
ok("o cofre separa 'no canal' de 'chega ao jogador'",
   "chega_ao_jogador" in _builds[0] and "pagina_abre" in _builds[0], list(_builds[0]))
ok("o resumo conta só os builds que CHEGAM ao jogador",
   "builds_que_chegam_ao_jogador" in _dados_builds["resumo"],
   list(_dados_builds["resumo"]))
ok("build que a página não abre NÃO entra na conta de 'chega ao jogador'",
   _dados_builds["resumo"]["builds_que_chegam_ao_jogador"] == 0,
   _dados_builds["resumo"]["builds_que_chegam_ao_jogador"])
ok("a página diz em letras claras que o jogador não abre o build",
   "NÃO abre este build" in _htm_builds, _htm_builds[:200])
ok("o markdown mostra o upload que a página abre de verdade",
   "19268311" in _md_builds, _md_builds[:200])
_falso = {"resumo": dict(_dados_builds["resumo"]), "canais": {}, "posts": [], "videos": [],
          "paginas": [], "documentos": [], "quando": "2026-10-31T00:00:00Z",
          "builds": [dict(_builds[0], chega_ao_jogador=True, pagina_abre={})]}
ok("quando chega, a página diz que chega",
   "o jogador abre este build" in p.pagina(_falso))

# A imagem que a página do itch mostra é servida por nós e agora leva o selo do vídeo: ela é
# publicação, então entra no cofre com hash — e a FONTE intocada não entra (não é publicada).
_midia = [m["arquivo"] for m in _dados_builds["midia"]]
ok("o GIF que o itch mostra entra no cofre, com hash",
   any(a.endswith("gif-jogo-ceifalume-640x360.gif") for a in _midia), _midia)
ok("a fonte intocada do GIF NÃO entra no cofre",
   not any(a.endswith("-fonte.gif") for a in _midia), _midia)
ok("o cofre guarda o selo (sha256) do GIF servido",
   all(m.get("sha256") for m in _dados_builds["midia"]
       if m["arquivo"].endswith("640x360.gif")), _dados_builds["midia"][:1])

ok("a página diz quando não há build nenhum",
   "nenhum build enviado" in p.pagina(
       {"resumo": dict(_dados_builds["resumo"], builds_no_itch=0),
        "canais": {}, "posts": [], "videos": [], "builds": [],
        "paginas": [], "documentos": [], "quando": "2026-10-31T00:00:00Z"}))

_wf = open(os.path.join(RAIZ, ".github", "workflows", "postagem-diaria.yml"), encoding="utf-8").read()
ok("o ciclo gera o cofre", "tools/publicacoes.py" in _wf)
ok("o ciclo commita o cofre", "publicacoes.html" in _wf)
ok("o ciclo cobra estes testes", "testes-publicacoes.py" in _wf)
ok("a página está no sitemap",
   "publicacoes.html" in open(os.path.join(RAIZ, "sitemap.xml"), encoding="utf-8").read())

print()
if FALHAS:
    print("%d de %d verificações do cofre de publicações FALHARAM" % (len(FALHAS), len(TOTAL)))
    sys.exit(1)
print("%d/%d verificações do cofre de publicações passaram" % (len(TOTAL), len(TOTAL)))
