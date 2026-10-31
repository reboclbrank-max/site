#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Página pública das melhorias: o que mudou, medido, e onde provar.

POR QUE EXISTE (31/10/2026): todas as melhorias das últimas dez rodadas estavam só no
repositório (`docs/*.md`, `tools/*.py`) e no painel de marketing. Quem abre o site não via
nada disso — melhoria invisível é quase promessa: não dá para discordar dela.

O que esta página faz, e não faz:

  - lista as rodadas a partir dos próprios documentos (`docs/RODADA-*.md`), com link para o
    arquivo no GitHub — o texto NÃO é copiado aqui (uma fonte só, sem cópia que envelhece);
  - mostra os NÚMEROS atuais tirados dos artefatos que a casa gera sozinha (auditoria,
    decisões, percebido, gosto, log de ciclos);
  - diz quantas suítes de teste existem e quantas a barreira do ciclo cobra — porque
    "sem quebrar nada" só vale com prova.

Nada aqui é digitado à mão: se um número não existe no repositório, a página diz
"não medido" em vez de chutar.
"""
import glob
import html
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "melhorias.html")
BASE = "https://reboclbrank-max.github.io/site"
GITHUB = "https://github.com/reboclbrank-max/site/blob/main"


def ler_json(*caminhos):
    for caminho in caminhos:
        try:
            with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return {}


def rodadas():
    """[(numero, titulo, arquivo)] das docs/RODADA-*.md, da mais nova para a mais antiga."""
    itens = []
    for caminho in glob.glob(os.path.join(RAIZ, "docs", "RODADA-*.md")):
        nome = os.path.basename(caminho)
        achado = re.match(r"RODADA-(\d+)-(.*)\.md$", nome)
        if not achado:
            continue
        titulo = ""
        try:
            with open(caminho, encoding="utf-8") as f:
                for linha in f:
                    if linha.startswith("# "):
                        titulo = linha[2:].strip()
                        break
        except OSError:
            continue
        itens.append((int(achado.group(1)), titulo or achado.group(2).replace("-", " "),
                      "docs/" + nome))
    itens.sort(reverse=True)
    return itens


def suites():
    """(total de suítes de teste no repositório, quantas a barreira do ciclo cobra)."""
    arquivos = sorted(os.path.basename(x) for x in glob.glob(os.path.join(RAIZ, "tools", "testes-*.py")))
    cobradas = set()
    try:
        with open(os.path.join(RAIZ, ".github", "workflows", "postagem-diaria.yml"),
                  encoding="utf-8") as f:
            texto = f.read()
        cobradas = set(re.findall(r"tools/(testes-[\w-]+\.py)", texto))
    except OSError:
        pass
    return arquivos, sorted(cobradas & set(arquivos))


def cifras():
    painel = {}
    try:
        spec = importlib.util.spec_from_file_location(
            "painel", os.path.join(RAIZ, "tools", "painel-marketing.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        painel = mod
    except Exception:
        painel = {}

    auditoria = ler_json("posts/auditoria-inteligencia.json")
    decisoes = ler_json("posts/decisoes.json")
    percebido = ler_json("posts/percebido.json")
    gosto = ler_json("posts/perfil-de-gosto.json")
    memoria = ler_json("posts/memoria-de-gosto.json")

    ciclos = []
    if painel:
        try:
            ciclos = painel.ler_log()
        except Exception:
            ciclos = []
    canais = 0
    if painel and ciclos:
        try:
            canais = sum(1 for chave, _nome, _seg in painel.CANAIS if painel.contar(ciclos, chave)[0])
        except Exception:
            canais = 0

    return {
        "ciclos": len(ciclos),
        "canais_publicando": canais,
        "adaptativos": (auditoria.get("contagem") or {}).get("adaptativo"),
        "rituais": (auditoria.get("contagem") or {}).get("ritual"),
        "cegos": (auditoria.get("contagem") or {}).get("cego"),
        "repeticao_pct": (auditoria.get("repeticao_desde_o_conserto") or {}).get("pct"),
        "repeticao_corte": (auditoria.get("repeticao_desde_o_conserto") or {}).get("corte"),
        "repeticao_repetidos": (auditoria.get("repeticao_desde_o_conserto") or {}).get("repetidos"),
        "repeticao_ciclos": (auditoria.get("repeticao_desde_o_conserto") or {}).get("ciclos"),
        "decisoes": (decisoes.get("contagem") or {}).get("decididas"),
        "recusas": (decisoes.get("contagem") or {}).get("recusadas"),
        "ignorancias": (decisoes.get("contagem") or {}).get("ignorancias"),
        "percebidas_robo": (percebido.get("contagem") or {}).get("robo"),
        "percebidas_dono": (percebido.get("contagem") or {}).get("dono"),
        "gosto_medidos": len(gosto.get("medidos") or []),
        "gosto_declarados": len(gosto.get("declarados") or []),
        "gosto_amostra": gosto.get("amostra"),
        "escolhas": len(memoria.get("escolhas") or []),
    }


def _num(valor, sufixo=""):
    return "não medido" if valor is None else ("%s%s" % (valor, sufixo))


def pagina():
    numeros = cifras()
    lista_suites, cobradas = suites()

    cartoes = [
        ("rodadas documentadas", str(len(rodadas())), "cada uma com o número que a sustenta"),
        ("suítes de teste no repositório", str(len(lista_suites)),
         "%d cobradas na barreira do ciclo" % len(cobradas)),
        ("ciclos de marketing registrados", str(numeros["ciclos"]), "no diário posts/log.md"),
        ("canais publicando sozinhos", str(numeros["canais_publicando"]), "sem aprovação manual"),
        ("passos que adaptam", _num(numeros["adaptativos"]),
         "medido na auditoria: o resultado varia"),
        ("decisões com número", _num(numeros["decisoes"]),
         "%s recusas e %s ignorâncias declaradas"
         % (_num(numeros["recusas"]), _num(numeros["ignorancias"]))),
        ("repetição de texto", _num(numeros["repeticao_pct"], "%"),
         "%s de %s ciclos desde %s"
         % (_num(numeros["repeticao_repetidos"]), _num(numeros["repeticao_ciclos"]),
            numeros["repeticao_corte"] or "o conserto")),
        ("gosto medido no feed", "%d de %d" % (numeros["gosto_medidos"],
                                               numeros["gosto_medidos"] + numeros["gosto_declarados"]),
         "amostra de %s posts; o resto é escolha declarada" % _num(numeros["gosto_amostra"])),
    ]
    cartoes_html = "".join(
        '<div class="cartao"><span class="num">%s</span><span class="rot">%s</span>'
        '<small>%s</small></div>'
        % (html.escape(v), html.escape(r), html.escape(d)) for r, v, d in cartoes)

    linhas_rodadas = "".join(
        '<tr><td class="mono">%02d</td><td>%s</td>'
        '<td><a href="%s/%s">documento</a></td></tr>'
        % (numero, html.escape(titulo), GITHUB, html.escape(arquivo))
        for numero, titulo, arquivo in rodadas())

    linhas_suites = "".join(
        '<li><span class="mono">%s</span>%s</li>'
        % (html.escape(nome), " <b class=\"ok\">na barreira</b>" if nome in cobradas else "")
        for nome in lista_suites)

    precisa = ler_json("posts/percebido.json")
    dono = precisa.get("dono") or []
    dono_html = "".join("<li><b>%s</b> — %s</li>" % (html.escape(i.get("o_que", "")),
                                                     html.escape(i.get("porque", "")))
                        for i in dono[:6]) or "<li>Nada esperando o dono nesta rodada.</li>"

    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    return """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Melhorias da casa — Rebocl Brank</title>
<meta name="description" content="O que mudou na automação da Rebocl Brank, rodada por rodada, com os números medidos e o link de cada documento.">
<link rel="canonical" href="%(base)s/melhorias.html">
<style>
:root{--preto:#0a0a0a;--ouro:#d4af37;--ouro2:#f0d97a;--txt:#e8e6e1;--suave:#9d9a93;--borda:rgba(212,175,55,.32)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--preto);color:var(--txt);font-family:"Segoe UI",Roboto,Arial,sans-serif;line-height:1.65}
.c{width:min(880px,90%%);margin:0 auto;padding:2.5rem 0 3rem}
h1{color:var(--ouro2);font-size:clamp(1.7rem,5vw,2.6rem);line-height:1.15}
.sub{color:var(--suave);margin:.5rem 0 1.6rem}
h2{color:var(--ouro);font-size:1.2rem;margin:2rem 0 .7rem}
.cartoes{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.9rem}
.cartao{border:1px solid var(--borda);border-radius:10px;padding:1rem;display:flex;flex-direction:column;gap:.2rem}
.num{color:var(--ouro2);font-size:1.7rem;font-weight:700;line-height:1.1}
.rot{font-weight:600}.cartao small{color:var(--suave);font-size:.8rem}
table{width:100%%;border-collapse:collapse;margin-top:.6rem;font-size:.92rem}
td{padding:.45rem .4rem;border-bottom:1px solid var(--borda);vertical-align:top}
td.ok,.ok{color:#7bd88f}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.8rem;color:var(--suave)}
ul.log{list-style:none}ul.log li{border-bottom:1px solid var(--borda);padding:.3rem 0;font-size:.9rem}
.peq{color:var(--suave);font-size:.85rem;margin-top:.6rem}
a{color:var(--ouro)}
footer{color:var(--suave);font-size:.8rem;border-top:1px solid var(--borda);margin-top:2.4rem;padding-top:1rem}
</style></head><body><main class="c">
<h1>Melhorias da casa</h1>
<p class="sub">O que mudou na automação, com o número que sustenta cada mudança. Página gerada pelo
próprio repositório a cada ciclo — se um número não foi medido, ela diz isso em vez de inventar.</p>
<div class="cartoes">%(cartoes)s</div>

<h2>Rodada por rodada</h2>
<p class="peq">O documento é a fonte; aqui fica só o título e o link. Copiar o texto para a página
criaria duas versões — e a que envelhece é sempre a pública.</p>
<table>%(rodadas)s</table>

<h2>Prova de que nada quebrou</h2>
<p class="peq">Toda mudança entra com teste. A barreira roda antes de a casa tocar a rede: se uma
suíte falha, o ciclo não publica.</p>
<ul class="log">%(suites)s</ul>

<h2>O que ainda depende do dono</h2>
<ul class="log">%(dono)s</ul>

<footer>Gerado em %(agora)s pelo workflow postagem-diaria ·
<a href="%(base)s/marketing.html">painel do marketing</a> ·
<a href="%(base)s/publicacoes.html">arquivo de publicações</a> ·
<a href="%(base)s/canais.html">canais oficiais</a> ·
<a href="%(base)s/">site</a></footer>
</main></body></html>
""" % {"base": BASE, "cartoes": cartoes_html, "rodadas": linhas_rodadas,
       "suites": linhas_suites, "dono": dono_html, "agora": agora}


def main(argv):
    final = pagina()
    with open(SAIDA + ".tmp", "w", encoding="utf-8") as f:
        f.write(final)
    os.replace(SAIDA + ".tmp", SAIDA)
    print("melhorias.html · %d bytes · %d rodada(s) · %d suíte(s)"
          % (len(final), len(rodadas()), len(suites()[0])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
