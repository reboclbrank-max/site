#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do devlog do site. Escreve em pasta temporária, nunca no repositório."""
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("devlog", os.path.join(RAIZ, "tools", "devlog.py"))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

certos = [0]
falhas = [0]


def ok(nome, cond, det=""):
    if cond:
        certos[0] += 1; print("✔ " + nome)
    else:
        falhas[0] += 1; print("✗ " + nome + (" — " + str(det)[:200] if det else ""))


# slug
ok("acento vira slug ascii", d.slug_limpo("Ceifalume à noite — jogo grátis") == "ceifalume-a-noite-jogo-gratis",
   d.slug_limpo("Ceifalume à noite — jogo grátis"))
ok("slug vazio não quebra", d.slug_limpo("") == "post")
ok("slug não tem barra (não escapa de blog/)", "/" not in d.slug_limpo("../../etc/passwd"))

# corpo
h = d.corpo_html(["texto <script>", {"lista": ["a", "b"]}])
ok("texto é escapado (sem HTML injetado)", "<script>" not in h and "&lt;script&gt;" in h, h)
ok("lista vira <ul> com itens", "<ul><li>a</li><li>b</li></ul>" in h)

# publicação em pasta temporária
tmp = tempfile.mkdtemp()
os.makedirs(os.path.join(tmp, "posts", "devlog"))
open(os.path.join(tmp, "posts", "devlog", "velho.json"), "w").write(json.dumps(
    {"titulo": "Antigo", "data": "1 de janeiro de 2026", "resumo": "r", "corpo": ["a"]}))
open(os.path.join(tmp, "posts", "devlog", "novo.json"), "w").write(json.dumps(
    {"titulo": "Novo", "data": "26 de outubro de 2026", "resumo": "r2", "corpo": ["b"]}))
open(os.path.join(tmp, "posts", "devlog", "quebrado.json"), "w").write("{ isso não é json }")
open(os.path.join(tmp, "posts", "devlog", "vazio.json"), "w").write(json.dumps({"titulo": "Sem corpo"}))

escritos = d.publicar(raiz=tmp)
ok("publica uma página por post válido", len([e for e in escritos if e.endswith(".html") and "index" not in e]) == 2,
   [os.path.basename(e) for e in escritos])
ok("JSON quebrado é ignorado, não derruba o resto", os.path.exists(os.path.join(tmp, "blog", "novo.html")))
ok("post sem corpo é ignorado", not os.path.exists(os.path.join(tmp, "blog", "sem-corpo.html")))
idx = open(os.path.join(tmp, "blog", "index.html"), encoding="utf-8").read()
ok("o índice lista o mais novo primeiro", idx.index("Novo") < idx.index("Antigo"))
pag = open(os.path.join(tmp, "blog", "novo.html"), encoding="utf-8").read()
ok("a página tem canonical absoluto", "rel=\"canonical\"" in pag and "https://reboclbrank-max.github.io/site/blog/novo.html" in pag)
ok("a página linka de volta ao índice", "/blog/\">" in pag or "todos os posts" in pag)

# o devlog real do CEIFALUME existe e é coerente
real = os.path.join(RAIZ, "posts", "devlog", "2026-10-26-ceifalume-no-navegador.json")
ok("o post real do CEIFALUME existe", os.path.exists(real))
if os.path.exists(real):
    j = json.load(open(real, encoding="utf-8"))
    ok("o post real fala do navegador e do APK",
       "navegador" in j["titulo"].lower() and "APK" in " ".join(str(b) for b in j["corpo"]))
    ok("o post real não promete data de lançamento nova", "lançamento" not in j["resumo"].lower())

# nada de segredo no gerador
fonte = open(os.path.join(RAIZ, "tools", "devlog.py"), encoding="utf-8").read()
ok("o gerador não contém segredo", "AIza" not in fonte and "GOCSPX" not in fonte)

# O sitemap é a porta de entrada do buscador. Antes, só /blog/ estava lá: post novo não era
# descoberto por ninguém. Agora cada post entra, e entrar duas vezes não duplica.
import re as _re
_sitemap = os.path.join(RAIZ, "sitemap.xml")
_xml = open(_sitemap, encoding="utf-8").read()
ok("o sitemap lista a página do diário", "%s/blog/" % d.BASE in _xml)
_posts = d.carregar(RAIZ)
ok("o sitemap lista cada post do diário",
   all("%s/blog/%s.html" % (d.BASE, p["slug"]) in _xml for p in _posts),
   str([p["slug"] for p in _posts]))
ok("nenhum post aparece duas vezes no sitemap",
   all(_xml.count("%s/blog/%s.html" % (d.BASE, p["slug"])) == 1 for p in _posts))
ok("rodar o gerador de novo não duplica entrada",
   d.atualizar_sitemap(_xml, _posts) == _xml)
ok("o lastmod sai do nome do arquivo (data do post, não do run)",
   "<lastmod>%s</lastmod>" % _posts[0]["arquivo"][:10] in _xml)

print("\n%d/%d testes do devlog passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
