#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Devlog automático no site da casa — o canal que a gente controla.

O itch.io não tem API para devlog (decisão deles, não nossa limitação de chave). Então o devlog
passa a ser publicado onde não existe trava: o próprio site, por commit — e o itch continua
recebendo o mesmo texto quando alguém colar lá.

Entrada:  posts/devlog/*.json  (titulo, data, resumo, corpo[], tags[])
Saída:    blog/<slug>.html  +  blog/index.html atualizado (mais recente primeiro)

Nada é inventado aqui: o texto vem do JSON. Se o JSON não existe, nada é publicado.
"""
import glob
import html
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRADA = os.path.join(RAIZ, "posts", "devlog")
BLOG = os.path.join(RAIZ, "blog")
BASE = "https://reboclbrank-max.github.io/site"

ESTILO = """  :root{--preto:#0a0a0a;--dourado:#d4af37;--dourado-escuro:#9c7a24;--texto:#e8e6e1;
    --texto-suave:#9d9a93;--borda-ouro:rgba(212,175,55,.32)}
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:var(--preto);color:var(--texto);line-height:1.7;
    font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
  .container{width:min(760px,88%);margin:0 auto;padding:56px 0}
  a{color:var(--dourado)}
  h1{font-size:1.9rem;line-height:1.25;margin:0 0 10px}
  .data{color:var(--dourado-escuro);font-size:.8rem;letter-spacing:.32em;text-transform:uppercase}
  .resumo{color:var(--texto-suave);font-size:1.05rem;margin:18px 0 28px}
  p{margin:0 0 16px}
  ul{margin:0 0 16px 1.2rem}
  .voltar{display:inline-block;margin-top:34px;border-top:1px solid var(--borda-ouro);
    padding-top:18px;text-decoration:none}"""


def slug_limpo(texto):
    """Slug só com [a-z0-9-]; nada de acento virando caractere estranho em URL."""
    import unicodedata
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "post"


def carregar(raiz=RAIZ):
    """Todos os posts válidos, do mais novo para o mais antigo."""
    posts = []
    for caminho in sorted(glob.glob(os.path.join(raiz, "posts", "devlog", "*.json"))):
        try:
            with open(caminho, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        if not (d.get("titulo") and d.get("corpo")):
            continue
        d["slug"] = slug_limpo(d.get("slug") or d["titulo"])
        d["arquivo"] = os.path.basename(caminho)
        posts.append(d)
    posts.sort(key=lambda d: d.get("data") or "", reverse=True)
    return posts


def corpo_html(blocos):
    saida = []
    for bloco in blocos:
        if isinstance(bloco, dict) and bloco.get("lista"):
            itens = "".join("<li>%s</li>" % html.escape(str(i)) for i in bloco["lista"])
            saida.append("<ul>%s</ul>" % itens)
        else:
            saida.append("<p>%s</p>" % html.escape(str(bloco)))
    return "\n".join(saida)


def pagina(post):
    titulo = html.escape(post["titulo"])
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(titulo)s — Rebocl Brank</title>
<meta name="description" content="%(resumo)s">
<link rel="canonical" href="%(base)s/blog/%(slug)s.html">
<style>
%(estilo)s
</style>
</head>
<body>
<main class="container">
<span class="data">%(data)s</span>
<h1>%(titulo)s</h1>
<p class="resumo">%(resumo)s</p>
%(corpo)s
<a class="voltar" href="%(base)s/blog/">&larr; todos os posts</a>
</main>
</body>
</html>
""" % {"titulo": titulo,
       "resumo": html.escape(post.get("resumo") or ""),
       "slug": post["slug"],
       "data": html.escape(post.get("data") or ""),
       "corpo": corpo_html(post["corpo"]),
       "base": BASE,
       "estilo": ESTILO}


def indice(posts):
    itens = "\n".join(
        '<li><span class="data">%s</span><br><a href="%s/blog/%s.html">%s</a><br>'
        '<span class="resumo">%s</span></li>'
        % (html.escape(p.get("data") or ""), BASE, p["slug"],
           html.escape(p["titulo"]), html.escape(p.get("resumo") or ""))
        for p in posts)
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Diário de bordo — Rebocl Brank</title>
<meta name="description" content="Diário de bordo da Rebocl Brank — bastidores do Ceifalume e do Prancheta, direto do estúdio.">
<link rel="canonical" href="%(base)s/blog/">
<style>
%(estilo)s
  li{list-style:none;margin:0 0 34px;padding-bottom:26px;border-bottom:1px solid var(--borda-ouro)}
  .resumo{color:var(--texto-suave);font-size:.98rem;display:block;margin-top:6px}
</style>
</head>
<body>
<main class="container">
<h1>Diário de bordo</h1>
<p class="resumo">Bastidores do Ceifalume e do Prancheta, publicados direto do estúdio.</p>
<ul>
%(itens)s
</ul>
</main>
</body>
</html>
""" % {"base": BASE, "estilo": ESTILO, "itens": itens}


def publicar(raiz=RAIZ, escrever=None):
    """Escreve as páginas. Devolve a lista de arquivos escritos."""
    escrever = escrever or _escrever
    posts = carregar(raiz)
    if not posts:
        return []
    escritos = []
    pasta = os.path.join(raiz, "blog")
    for p in posts:
        caminho = os.path.join(pasta, p["slug"] + ".html")
        escrever(caminho, pagina(p))
        escritos.append(caminho)
    escrever(os.path.join(pasta, "index.html"), indice(posts))
    escritos.append(os.path.join(pasta, "index.html"))
    # Cada post entra no sitemap com a data do próprio nome do arquivo (2026-10-30-...).
    # Antes, só /blog/ aparecia: o buscador não descobria post nenhum, e o devlog do site era
    # escrito para ninguém achar. A entrada é idempotente — rodar duas vezes não duplica.
    sitemap = os.path.join(raiz, "sitemap.xml")
    if os.path.exists(sitemap):
        with open(sitemap, encoding="utf-8") as f:
            antes = f.read()
        depois = atualizar_sitemap(antes, posts)
        if depois != antes:
            escrever(sitemap, depois)
            escritos.append(sitemap)
    return escritos


def atualizar_sitemap(xml, posts, base=BASE):
    """Acrescenta <url> de cada post do devlog que ainda não está no sitemap.

    Data do lastmod vem do nome do arquivo (posts/devlog/AAAA-MM-DD-...). Se o nome não tiver
    data, a entrada entra sem lastmod — melhor no sitemap sem data do que fora dele.
    """
    for p in posts:
        endereco = "%s/blog/%s.html" % (base, p["slug"])
        if endereco in xml:
            continue
        achado = re.match(r"(\d{4}-\d{2}-\d{2})", p.get("arquivo") or "")
        lastmod = "<lastmod>%s</lastmod>" % achado.group(1) if achado else ""
        entrada = ("  <url><loc>%s</loc>%s<changefreq>monthly</changefreq>"
                   "<priority>0.6</priority></url>\n" % (endereco, lastmod))
        xml = xml.replace("</urlset>", entrada + "</urlset>", 1)
    return xml


def _escrever(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def main(argv):
    escritos = publicar()
    if not escritos:
        print("nada a publicar: posts/devlog/ está vazio")
        return 0
    for e in escritos:
        print("✓ " + os.path.relpath(e, RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
