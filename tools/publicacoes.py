#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cofre das publicações: inventário do que a casa já publicou — nada some sem deixar rastro.

POR QUE EXISTE (31/10/2026, pedido do dono: "deixar toda publicação que fez, salva"). O que a
casa publica está espalhado em seis lugares e cada um envelhece do seu jeito:

  posts/log.md              → cada ciclo e em que canal saiu (com id quando a rede devolve)
  posts/posts-publicados.md → o TEXTO de cada post publicado
  posts/youtube-publicados.json → vídeos com id
  docs/RODADA-*.md          → o que mudou e por quê
  blog/*.html               → devlogs publicados no domínio da casa
  *.html                    → páginas públicas do site

Este script junta tudo num inventário ÚNICO, com data, tamanho e impressão digital (sha256) de
cada item, gera uma página pública (`publicacoes.html`) e uma versão em texto (`docs/PUBLICACOES.md`).
A impressão digital é o que permite provar depois que o arquivo publicado não mudou — "salvo" sem
hash é só uma lista de nomes.

O que ele NÃO faz: republicar, corrigir ou apagar nada. É arquivo, não editor.
"""
import datetime
import glob
import hashlib
import html
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA_JSON = os.path.join(RAIZ, "posts", "publicacoes.json")
SAIDA_MD = os.path.join(RAIZ, "docs", "PUBLICACOES.md")
SAIDA_HTML = os.path.join(RAIZ, "publicacoes.html")
BASE = "https://reboclbrank-max.github.io/site"

# Canais de publicação de verdade (o resto da tabela são passos internos do ciclo: medir,
# aprender, vigia... — eles aparecem, mas marcados, para não inflar "quantos canais publicam").
CANAIS_DE_VERDADE = {"bluesky", "threads", "nostr", "instagram", "telegram", "mastodon",
                     "discord", "ntfy (push do dono)"}


def agora_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ler(caminho):
    try:
        with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def ler_json(caminho):
    try:
        with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def selo(caminho):
    """(bytes, sha256) de um arquivo do repositório. None se não existir."""
    completo = os.path.join(RAIZ, caminho)
    try:
        with open(completo, "rb") as f:
            dados = f.read()
    except OSError:
        return None
    return {"bytes": len(dados), "sha256": hashlib.sha256(dados).hexdigest()[:16]}


# ---------------------------------------------------------------- fontes
def ciclos_por_canal():
    """Do log: quantos ciclos, e o último resultado de cada canal (com id quando existe)."""
    texto = ler("posts/log.md")
    try:
        spec = importlib_spec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location(
            "painel", os.path.join(RAIZ, "tools", "painel-marketing.py"))
        mod = importlib_spec.loader and __import__("importlib.util", fromlist=["util"]).module_from_spec(spec)
        spec.loader.exec_module(mod)
        ciclos = mod.ciclos_do_texto(texto)
    except Exception:
        ciclos = []
    canais = {}
    for ciclo in ciclos:
        for nome, resultado in (ciclo.get("linhas") or {}).items():
            canais.setdefault(nome, {"ciclos": 0, "ok": 0, "ultimo": "", "quando": ""})
            canais[nome]["ciclos"] += 1
            # "publicou" = saiu de verdade. Resultado com erro no texto não conta como
            # publicação, mesmo com ✅ na frente (ex.: "✅ commit falhou").
            if "✅" in resultado and not any(e in resultado.lower() for e in
                                            ("falhou", "falha", "erro", "indisponivel")):
                canais[nome]["ok"] += 1
                canais[nome]["ultimo"] = resultado[:120]
                canais[nome]["quando"] = ciclo.get("quando", "")
    return len(ciclos), canais


def posts_sociais():
    """O texto de cada post publicado (posts-publicados.md), do mais novo para o mais antigo."""
    texto = ler("posts/posts-publicados.md")
    itens = []
    for bloco in re.split(r"\n## ", texto):
        achado = re.match(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2} UTC)\n(.+)", bloco.strip(), re.S)
        if achado:
            corpo = " ".join(achado.group(2).split())
            itens.append({"quando": achado.group(1), "texto": corpo[:220]})
    itens.reverse()
    return itens


def videos_youtube():
    dados = ler_json("posts/youtube-publicados.json")
    saida = []
    for item in dados.get("publicados") or []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "")
        saida.append({"slug": item.get("slug"), "id": ident,
                      "titulo": (item.get("titulo") or "")[:120],
                      "quando": item.get("quando"),
                      "link": ("https://youtu.be/" + ident) if ident and ident != "VIDEO123" else "",
                      "real": bool(ident) and ident != "VIDEO123"})
    return saida


def builds_do_itch():
    """Builds de jogo que foram para o itch.io — publicação de verdade, não post.

    Fica fora dos canais de propósito: um build não é texto em rede social, é o que o jogador
    baixa. Só conta como real quando o registro traz id de build e a prova (run do push + run
    do status comparando com a pasta do repositório).
    """
    dados = ler_json("posts/itch-builds.json")
    saida = []
    for item in dados.get("builds") or []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("build") or "").strip()
        prova = str(item.get("prova") or "").strip()
        saida.append({"slug": item.get("slug"), "canal": item.get("canal"),
                      "build": ident, "versao": item.get("versao"),
                      "arquivos": item.get("arquivos"), "quando": item.get("quando"),
                      "link": item.get("link") or "",
                      "prova": prova[:200],
                      "real": bool(ident) and bool(prova)})
    return saida


def documentos():
    itens = []
    for caminho in sorted(glob.glob(os.path.join(RAIZ, "docs", "*.md"))):
        nome = os.path.basename(caminho)
        if nome == "PUBLICACOES.md":
            continue
        titulo = ""
        for linha in open(caminho, encoding="utf-8"):
            if linha.startswith("# "):
                titulo = linha[2:].strip()
                break
        itens.append({"arquivo": "docs/" + nome, "titulo": titulo or nome, "selo": selo("docs/" + nome)})
    return itens


def paginas():
    itens = []
    for padrao in ("*.html", "blog/*.html", "jogos/*/index.html"):
        for caminho in sorted(glob.glob(os.path.join(RAIZ, padrao))):
            rel = os.path.relpath(caminho, RAIZ).replace(os.sep, "/")
            info = selo(rel)
            if not info:
                continue
            itens.append({"arquivo": rel, "selo": info,
                          "url": BASE + "/" + rel.replace("index.html", "")})
    return itens


def midia():
    itens = []
    for padrao in ("media/*/*.mp4", "media/*.mp4", "media/*/*.png"):
        for caminho in sorted(glob.glob(os.path.join(RAIZ, padrao))):
            rel = os.path.relpath(caminho, RAIZ).replace(os.sep, "/")
            info = selo(rel)
            if info:
                itens.append({"arquivo": rel, **info})
    return itens


# ---------------------------------------------------------------- inventário
def inventario():
    ciclos, canais = ciclos_por_canal()
    sociais = posts_sociais()
    videos = videos_youtube()
    builds = builds_do_itch()
    return {
        "quando": agora_iso(),
        "_lei": "tudo o que a casa publicou fica aqui com data, tamanho e impressão digital; "
                "hash é o que prova que o publicado não mudou desde então.",
        "resumo": {
            "ciclos_de_marketing": ciclos,
            "posts_sociais_registrados": len(sociais),
            "canais_com_publicacao": sum(1 for n, c in canais.items()
                                         if n in CANAIS_DE_VERDADE and c["ok"]),
            "videos_no_youtube": len([v for v in videos if v["real"]]),
            "builds_no_itch": len([b for b in builds if b["real"]]),
            "documentos": len(documentos()),
            "paginas_publicas": len(paginas()),
            "arquivos_de_midia": len(midia()),
        },
        "canais": canais,
        "posts": sociais[:200],
        "videos": videos,
        "builds": builds,
        "documentos": documentos(),
        "paginas": paginas(),
        "midia": midia(),
    }


def markdown(dados):
    r = dados["resumo"]
    linhas = [
        "# O que a casa publicou (arquivo)", "",
        "Gerado em %s. Este arquivo é o inventário do que já foi publicado, com data, tamanho e "
        "impressão digital (sha256, 16 primeiros caracteres)." % dados["quando"], "",
        "> %s" % dados["_lei"], "",
        "## Resumo", "",
        "| o quê | quantos |", "| --- | --- |",
        "| ciclos de marketing | %d |" % r["ciclos_de_marketing"],
        "| posts sociais registrados | %d |" % r["posts_sociais_registrados"],
        "| canais que já publicaram | %d |" % r["canais_com_publicacao"],
        "| vídeos no YouTube (com id real) | %d |" % r["videos_no_youtube"],
        "| builds no itch.io (com id real) | %d |" % r["builds_no_itch"],
        "| documentos | %d |" % r["documentos"],
        "| páginas públicas | %d |" % r["paginas_publicas"],
        "| arquivos de mídia | %d |" % r["arquivos_de_midia"],
        "", "## Canal por canal", "",
        "| canal | ciclos | publicou | último resultado |", "| --- | --- | --- | --- |",
    ]
    for nome, info in sorted(dados["canais"].items(), key=lambda kv: -kv[1]["ok"]):
        linhas.append("| %s | %d | %d | %s |" % (nome, info["ciclos"], info["ok"],
                                                 (info["ultimo"] or "").replace("|", "/")[:90]))
    linhas += ["", "## Vídeos", ""]
    for v in dados["videos"]:
        linhas.append("- %s `%s` — %s%s" % (v["slug"], v["id"], v["titulo"],
                                            (" · " + v["link"]) if v["link"] else " · (sem id real)"))
    linhas += ["", "## Builds no itch.io", ""]
    if dados["builds"]:
        linhas += ["| jogo | canal | build | versão | arquivos | quando |", "| --- | --- | --- | --- | --- | --- |"]
        for b in dados["builds"]:
            linhas.append("| %s | %s | `%s` | %s | %s | %s |" % (
                b["slug"], b["canal"], b["build"], b["versao"] or "—",
                b["arquivos"] if b["arquivos"] is not None else "—", b["quando"] or "—"))
        for b in dados["builds"]:
            linhas.append("- prova de %s:`%s` — %s" % (b["slug"], b["build"], b["prova"] or "sem prova"))
    else:
        linhas.append("Nenhum build enviado até agora.")
    linhas += ["", "## Páginas públicas", "", "| arquivo | bytes | sha256 |", "| --- | --- | --- |"]
    for p in dados["paginas"]:
        linhas.append("| %s | %d | `%s` |" % (p["arquivo"], p["selo"]["bytes"], p["selo"]["sha256"]))
    linhas += ["", "## Documentos", "", "| documento | título | sha256 |", "| --- | --- | --- |"]
    for d in dados["documentos"]:
        linhas.append("| %s | %s | `%s` |" % (d["arquivo"], d["titulo"].replace("|", "/"),
                                              (d["selo"] or {}).get("sha256", "ausente")))
    linhas += ["", "## Últimos posts registrados (texto)", ""]
    for p in dados["posts"][:25]:
        linhas.append("- **%s** — %s" % (p["quando"], p["texto"][:160]))
    return "\n".join(linhas) + "\n"


def pagina(dados):
    r = dados["resumo"]
    cartoes = "".join(
        '<div class="cartao"><span class="num">%s</span><span class="rot">%s</span></div>'
        % (valor, rotulo) for rotulo, valor in [
            ("ciclos de marketing", r["ciclos_de_marketing"]),
            ("posts sociais", r["posts_sociais_registrados"]),
            ("canais que publicaram", r["canais_com_publicacao"]),
            ("vídeos no YouTube", r["videos_no_youtube"]),
            ("builds no itch.io", r["builds_no_itch"]),
            ("páginas no ar", r["paginas_publicas"]),
            ("documentos", r["documentos"]),
        ])
    def _ordem(kv):
        return (kv[0] not in CANAIS_DE_VERDADE, -kv[1]["ok"])
    linhas_canais = "".join(
        "<tr><td><b>%s</b>%s</td><td>%d</td><td class='%s'>%d</td><td class='mono'>%s</td></tr>"
        % (html.escape(nome), "" if nome in CANAIS_DE_VERDADE else " <span class='mono'>(passo do ciclo)</span>",
           info["ciclos"], "ok" if info["ok"] else "off", info["ok"],
           html.escape((info["ultimo"] or "—")[:90]))
        for nome, info in sorted(dados["canais"].items(), key=_ordem))
    linhas_videos = "".join(
        "<li><b>%s</b> — %s %s</li>"
        % (html.escape(str(v["slug"])), html.escape(v["titulo"][:80]),
           ("<a href='%s'>%s</a>" % (html.escape(v["link"]), html.escape(v["id"]))) if v["link"]
           else "<span class='mono'>(sem id real)</span>")
        for v in dados["videos"])
    linhas_builds = "".join(
        "<li><b>%s</b> · canal %s · build <span class='mono'>%s</span> · versão %s · %s arquivos · %s</li>"
        % (html.escape(str(b["slug"])), html.escape(str(b["canal"])), html.escape(b["build"]),
           html.escape(str(b["versao"] or "—")), html.escape(str(b["arquivos"])),
           ("<a href='%s'>%s</a>" % (html.escape(b["link"]), html.escape(b["link"]))) if b["link"]
           else "<span class='mono'>(sem link)</span>")
        for b in dados["builds"]) or "<li class='mono'>nenhum build enviado até agora</li>"
    linhas_paginas = "".join(
        "<tr><td><a href='%s'>%s</a></td><td>%d</td><td class='mono'>%s</td></tr>"
        % (html.escape(p.get("url", "")), html.escape(p["arquivo"]), p["selo"]["bytes"],
           html.escape(p["selo"]["sha256"]))
        for p in dados["paginas"])
    linhas_posts = "".join(
        "<li><span class='mono'>%s</span> %s</li>" % (html.escape(p["quando"]), html.escape(p["texto"][:170]))
        for p in dados["posts"][:20])
    return """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>O que a casa publicou — Rebocl Brank</title>
<meta name="description" content="Arquivo público de tudo o que a automação da Rebocl Brank já publicou: ciclos, canais, vídeos, páginas e documentos, com data e impressão digital.">
<link rel="canonical" href="%(base)s/publicacoes.html">
<style>
:root{--preto:#0a0a0a;--ouro:#d4af37;--ouro2:#f0d97a;--txt:#e8e6e1;--suave:#9d9a93;--borda:rgba(212,175,55,.32)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--preto);color:var(--txt);font-family:"Segoe UI",Roboto,Arial,sans-serif;line-height:1.65}
.c{width:min(900px,90%%);margin:0 auto;padding:2.5rem 0 3rem}
h1{color:var(--ouro2);font-size:clamp(1.7rem,5vw,2.6rem);line-height:1.15}
.sub{color:var(--suave);margin:.5rem 0 1.6rem}
h2{color:var(--ouro);font-size:1.2rem;margin:2rem 0 .7rem}
.cartoes{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.9rem}
.cartao{border:1px solid var(--borda);border-radius:10px;padding:1rem;display:flex;flex-direction:column;gap:.2rem}
.num{color:var(--ouro2);font-size:1.7rem;font-weight:700;line-height:1.1}
.rot{font-weight:600;font-size:.85rem}
table{width:100%%;border-collapse:collapse;margin-top:.6rem;font-size:.9rem}
td{padding:.45rem .4rem;border-bottom:1px solid var(--borda);vertical-align:top}
td.ok{color:#7bd88f}td.off{color:var(--suave)}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.78rem;color:var(--suave)}
ul.log{list-style:none}ul.log li{border-bottom:1px solid var(--borda);padding:.3rem 0;font-size:.88rem}
.peq{color:var(--suave);font-size:.85rem;margin-top:.6rem}
a{color:var(--ouro)}
footer{color:var(--suave);font-size:.8rem;border-top:1px solid var(--borda);margin-top:2.4rem;padding-top:1rem}
</style></head><body><main class="c">
<h1>O que a casa publicou</h1>
<p class="sub">Arquivo de tudo o que a automação já publicou. Cada arquivo tem impressão digital
(sha256): é o que prova que o publicado não mudou desde então.</p>
<div class="cartoes">%(cartoes)s</div>

<h2>Canal por canal</h2>
<table><tr><td><b>canal</b></td><td><b>ciclos</b></td><td><b>publicou</b></td><td><b>último resultado</b></td></tr>%(canais)s</table>

<h2>Vídeos</h2>
<ul class="log">%(videos)s</ul>

<h2>Builds no itch.io</h2>
<ul class="log">%(builds)s</ul>

<h2>Páginas no ar</h2>
<table><tr><td><b>arquivo</b></td><td><b>bytes</b></td><td><b>sha256</b></td></tr>%(paginas)s</table>

<h2>Últimos posts (texto)</h2>
<ul class="log">%(posts)s</ul>

<footer>Gerado em %(quando)s pelo workflow postagem-diaria ·
<a href="%(base)s/melhorias.html">melhorias</a> ·
<a href="%(base)s/marketing.html">painel do marketing</a> ·
<a href="%(base)s/">site</a></footer>
</main></body></html>
""" % {"base": BASE, "cartoes": cartoes, "canais": linhas_canais, "videos": linhas_videos, "builds": linhas_builds,
       "paginas": linhas_paginas, "posts": linhas_posts, "quando": dados["quando"]}


def escrever(caminho, texto):
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(caminho + ".tmp", caminho)


def main(argv):
    dados = inventario()
    escrever(SAIDA_JSON, json.dumps(dados, ensure_ascii=False, indent=1) + "\n")
    escrever(SAIDA_MD, markdown(dados))
    escrever(SAIDA_HTML, pagina(dados))
    r = dados["resumo"]
    print("arquivo: %d ciclos · %d posts · %d canais com publicação · %d vídeos · %d páginas · %d docs"
          % (r["ciclos_de_marketing"], r["posts_sociais_registrados"], r["canais_com_publicacao"],
             r["videos_no_youtube"], r["paginas_publicas"], r["documentos"]))
    print("gravado em posts/publicacoes.json, docs/PUBLICACOES.md e publicacoes.html")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
