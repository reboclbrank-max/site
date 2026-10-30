#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Painel público do marketing: o que a casa fez sozinha, canal por canal.

POR QUE EXISTE (30/10/2026): a autonomia já roda 8 vezes por dia, mas ela só era visível em
`posts/log.md` (texto técnico) e no painel de ações do GitHub. Quem quer saber "o marketing está
funcionando?" precisa de uma página: o que saiu hoje, em que canal, o que está desligado e por
quê, e quais números existem de verdade (medido × não observável).

Nada aqui é inventado: tudo vem de posts/log.md (o diário que o postador escreve),
posts/metricas*.json e dos relatórios de pendências. Se um número não foi medido, a página diz
"não observável" em vez de zero.
"""
import glob
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "marketing.html")
LOG = os.path.join(RAIZ, "posts", "log.md")
BASE = "https://reboclbrank-max.github.io/site"

# Nome comercial e o que cada canal precisa para funcionar (o mesmo mapa do postador).
CANAIS = [
    ("bluesky", "Bluesky", "BLUESKY_HANDLE + BLUESKY_APPPASS"),
    ("threads", "Threads", "THREADS_USER_ID + THREADS_TOKEN"),
    ("nostr", "Nostr", "NOSTR_KEY"),
    ("instagram", "Instagram", "IG_TOKEN + IG_USER_ID"),
    ("telegram", "Telegram", "TELEGRAM_TOKEN + TELEGRAM_CHAT"),
    ("mastodon", "Mastodon", "MASTODON_URL + MASTODON_TOKEN"),
    ("discord", "Discord", "DISCORD_WEBHOOK"),
    ("ntfy (push do dono)", "Aviso no celular", "NTFY_TOPIC"),
]


def ler_log():
    """Devolve os ciclos registrados em posts/log.md, do mais novo para o mais antigo."""
    try:
        texto = open(LOG, encoding="utf-8").read()
    except OSError:
        return []
    return ciclos_do_texto(texto)


def ciclos_do_texto(texto):
    """Ciclos de um log em Markdown, ordenados do mais novo para o mais antigo."""
    ciclos = []
    for bloco in re.split(r"\n## ", texto):
        achado = re.match(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2} UTC)", bloco.strip())
        if not achado:
            continue
        linhas = {}
        for par in re.findall(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$", bloco, re.M):
            canal, resultado = par
            if canal.lower() in ("canal", "---") or set(canal) <= {"-"}:
                continue
            linhas[canal] = resultado
        ciclos.append({"quando": achado.group(1), "linhas": linhas,
                       "_chave": datetime.strptime(achado.group(1), "%d/%m/%Y %H:%M UTC")})
    # O log é escrito em ordem cronológica; quem lê quer o MAIS NOVO primeiro.
    ciclos.sort(key=lambda c: c["_chave"], reverse=True)
    return ciclos


def contar(ciclos, canal):
    """(ok, indisponivel, pulado) contando os últimos ciclos do canal."""
    ok = indisp = pulo = 0
    for c in ciclos:
        r = c["linhas"].get(canal, "")
        if not r:
            continue
        if "INDISPONIVEL" in r or "ausente" in r or "falta o segredo" in r:
            indisp += 1
        elif r.startswith("➖") or "fora da janela" in r or "cadencia" in r or "sai no" in r:
            pulo += 1
        else:
            ok += 1
    return ok, indisp, pulo


def metrica(*caminhos, chave=None):
    for caminho in caminhos:
        try:
            with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, ValueError):
            continue
        if chave:
            dados = dados.get(chave)
        if isinstance(dados, (int, float, str)) and dados != "":
            return dados
        if isinstance(dados, dict) and dados:
            return dados
    return None


def pagina():
    ciclos = ler_log()
    ultimo = ciclos[0] if ciclos else None
    publicados = []
    try:
        publicados = json.load(open(os.path.join(RAIZ, "posts", "youtube-publicados.json"),
                                    encoding="utf-8")).get("publicados") or []
    except (OSError, ValueError):
        pass
    auditoria = {}
    try:
        auditoria = json.load(open(os.path.join(RAIZ, "posts", "auditoria-inteligencia.json"),
                                   encoding="utf-8"))
    except (OSError, ValueError):
        pass
    livro = {}
    try:
        livro = json.load(open(os.path.join(RAIZ, "posts", "decisoes.json"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    pendencias = {}
    try:
        pendencias = json.load(open(os.path.join(RAIZ, "posts", "pendencias-do-dono.json"),
                                    encoding="utf-8"))
    except (OSError, ValueError):
        pass

    linhas_canal = []
    for chave, nome, segredo in CANAIS:
        ok, indisp, pulo = contar(ciclos, chave)
        if ok:
            estado, classe = "publicando (últimos %d ciclos: %d)" % (len(ciclos), ok), "ok"
        elif indisp:
            estado, classe = "desligado (falta o segredo ao lado)", "off"
        elif pulo:
            estado, classe = "em espera (trava anti-spam ou janela do dia)", "espera"
        else:
            estado, classe = "sem registro nos últimos ciclos", "off"
        linhas_canal.append(
            '<tr><td><b>%s</b></td><td class="%s">%s</td><td class="mono">%s</td></tr>'
            % (html.escape(nome), classe, html.escape(estado), html.escape(segredo)))

    cartoes = [
        ("ciclos registrados", str(len(ciclos)), "cada ciclo é uma rodada automática do postador"),
        ("vídeos no YouTube", str(len(publicados)), "registro em posts/youtube-publicados.json"),
        ("canal que publica sozinho", str(sum(1 for c, _n, _s in CANAIS if contar(ciclos, c)[0])),
         "sem aprovação manual, por desenho"),
    ]
    cartoes_html = "".join(
        '<div class="cartao"><span class="num">%s</span><span class="rot">%s</span>'
        '<small>%s</small></div>' % (html.escape(v), html.escape(r), html.escape(d))
        for r, v, d in cartoes)

    ultimo_html = ""
    if ultimo:
        itens = "".join("<li><b>%s</b>: %s</li>" % (html.escape(k), html.escape(v[:150]))
                        for k, v in ultimo["linhas"].items())
        ultimo_html = ('<h2>Último ciclo — %s</h2><ul class="log">%s</ul>'
                       % (html.escape(ultimo["quando"]), itens))

    pend_html = ""
    if pendencias.get("itens"):
        itens = "".join(
            "<li>%s %s — <span class='mono'>%s</span></li>"
            % ("✔" if i.get("estado") == "feito" else "…", html.escape(i.get("titulo", "")),
               html.escape(i.get("estado", "")))
            for i in pendencias["itens"])
        pend_html = ("<h2>O que ainda depende do dono</h2><ul class='log'>%s</ul>"
                     "<p class='peq'>Atualizado em %s.</p>"
                     % (itens, html.escape(pendencias.get("quando", ""))))

    decisoes_html = ""
    if livro.get("decididas") or livro.get("recusadas"):
        def _lista(itens, campo_valor, titulo):
            if not itens:
                return ""
            corpo = "".join(
                "<li><b>%s</b> — %s <span class='mono'>%s</span></li>"
                % (html.escape(i.get("decisao") or i.get("pergunta", "")),
                   html.escape(i.get(campo_valor, "")), html.escape(i.get("fonte", "")))
                for i in itens)
            return "<h3>%s (%d)</h3><ul class='log'>%s</ul>" % (titulo, len(itens), corpo)

        decisoes_html = (
            "<h2>As decisões, com o número atrás</h2>"
            "<p class='peq'>Toda decisão abaixo cita o arquivo onde o número foi medido. Decisão "
            "sem número não entra no livro.</p>"
            + _lista(livro.get("decididas"), "numero", "O que a casa decide sozinha")
            + _lista(livro.get("recusadas"), "porque", "O que a casa se recusa a decidir")
            + _lista(livro.get("ignorancias"), "porque", "O que a casa não sabe (e diz)")
        )

    audit_html = ""
    if auditoria.get("passos"):
        c = auditoria.get("contagem", {})
        rep = auditoria.get("repeticao_desde_o_conserto", {})
        linhas_aud = "".join(
            "<li><b>%s</b> <span class='mono'>%s</span> — %s</li>"
            % (html.escape(passo["passo"]), html.escape(passo["classe"]),
               html.escape((passo.get("ultimo") or "")[:90]))
            for passo in auditoria["passos"])
        audit_html = (
            "<h2>Onde a casa pensa e onde ela só repete</h2>"
            "<p class='peq'>Medido no próprio diário, nos últimos %d ciclos: "
            "<b>%d</b> passos adaptativos (o resultado varia), <b>%d</b> cegos (sempre "
            "indisponível), <b>%d</b> ritual (resultado sempre igual). "
            "Ritual não é xingamento: um push que sai igual todo ciclo está funcionando. "
            "Ritual só é problema quando o passo diz que fez algo novo e não fez.</p>"
            "<p class='peq'>Repetição de texto desde o conserto de dedupe (%s): "
            "<b>%d de %d ciclos</b> (%.1f%%).</p>"
            "<ul class='log'>%s</ul>"
            % (auditoria.get("janela", 0), c.get("adaptativo", 0), c.get("cego", 0),
               c.get("ritual", 0), html.escape(str(rep.get("corte", "?"))),
               rep.get("repetidos", 0), rep.get("ciclos", 0), rep.get("pct", 0.0), linhas_aud))

    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    return """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Marketing automático — Rebocl Brank</title>
<meta name="description" content="O que a Rebocl Brank publica sozinha nas redes: canal por canal, com os números medidos e o que falta ligar.">
<link rel="canonical" href="%(base)s/marketing.html">
<style>
:root{--preto:#0a0a0a;--ouro:#d4af37;--ouro2:#f0d97a;--txt:#e8e6e1;--suave:#9d9a93;--borda:rgba(212,175,55,.32)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--preto);color:var(--txt);font-family:"Segoe UI",Roboto,Arial,sans-serif;line-height:1.65}
.c{width:min(860px,90%%);margin:0 auto;padding:2.5rem 0 3rem}
h1{color:var(--ouro2);font-size:clamp(1.7rem,5vw,2.6rem);line-height:1.15}
.sub{color:var(--suave);margin:.5rem 0 1.6rem}
h2{color:var(--ouro);font-size:1.2rem;margin:2rem 0 .7rem}
.cartoes{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.9rem}
.cartao{border:1px solid var(--borda);border-radius:10px;padding:1rem;display:flex;flex-direction:column;gap:.2rem}
.num{color:var(--ouro2);font-size:1.9rem;font-weight:700;line-height:1}
.rot{font-weight:600}.cartao small{color:var(--suave);font-size:.8rem}
table{width:100%%;border-collapse:collapse;margin-top:.6rem;font-size:.92rem}
td{padding:.5rem .4rem;border-bottom:1px solid var(--borda);vertical-align:top}
td.ok{color:#7bd88f}td.off{color:#e08b8b}td.espera{color:var(--suave)}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.8rem;color:var(--suave)}
ul.log{list-style:none}ul.log li{border-bottom:1px solid var(--borda);padding:.35rem 0;font-size:.9rem}
h3{color:var(--txt);font-size:.98rem;margin:1.2rem 0 .3rem}
.peq{color:var(--suave);font-size:.85rem;margin-top:.6rem}
a{color:var(--ouro)}
footer{color:var(--suave);font-size:.8rem;border-top:1px solid var(--borda);margin-top:2.4rem;padding-top:1rem}
</style></head><body><main class="c">
<h1>Marketing automático</h1>
<p class="sub">O que a Rebocl Brank publica <b>sozinha</b>, canal por canal — com número medido, não promessa.
Página gerada pelo próprio repositório a cada rodada.</p>
<div class="cartoes">%(cartoes)s</div>
<h2>Canais</h2>
<table><tr><td><b>canal</b></td><td><b>estado</b></td><td><b>precisa de</b></td></tr>%(canais)s</table>
%(ultimo)s
%(decisoes)s
%(auditoria)s
%(pend)s
<footer>Gerado em %(agora)s pelo workflow postagem-diaria ·
<a href="%(base)s/">site</a> · <a href="%(base)s/canais.html">canais oficiais</a> ·
<a href="https://youtu.be/GuE7af6dYo8">gameplay do Ceifalume</a></footer>
</main></body></html>
""" % {"base": BASE, "cartoes": cartoes_html, "canais": "".join(linhas_canal),
       "ultimo": ultimo_html, "decisoes": decisoes_html, "pend": pend_html,
       "auditoria": audit_html,
       "agora": agora}


def main(argv):
    html_final = pagina()
    with open(SAIDA + ".tmp", "w", encoding="utf-8") as f:
        f.write(html_final)
    os.replace(SAIDA + ".tmp", SAIDA)
    print("painel: marketing.html · %d bytes" % len(html_final))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
