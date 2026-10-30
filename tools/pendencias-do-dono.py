#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O que falta, o que depende do dono — e o que já se resolveu sozinho.

POR QUE EXISTE (30/10/2026): sobrou UM passo que nenhum servidor consegue fazer — publicar no
painel do itch. O painel é bloqueado por reputação de IP (medido nos três sistemas de runner e com
navegador real: docs/sondagens/ITCH-403-CLOUDFLARE.json). Em vez de deixar isso como "pendência"
vaga na conversa, este script:

  1. MEDE o estado sem precisar do painel — o devlog do itch é público, então dá para ver de fora
     se o post saiu (https://rebocl-brank.itch.io/ceifalume/devlog);
  2. diz exatamente qual é o clique que falta, com o texto já pronto;
  3. avisa por ntfy quando o estado MUDA (não todo dia: aviso repetido vira ruído).

Nada aqui publica nada, e nada aqui usa o cookie do itch: são leituras públicas.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA_JSON = os.path.join(RAIZ, "posts", "pendencias-do-dono.json")
SAIDA_MD = os.path.join(RAIZ, "posts", "pendencias-do-dono.md")
DEVLOG_PUBLICO = "https://rebocl-brank.itch.io/ceifalume/devlog"
PAGINA_JOGO = "https://rebocl-brank.itch.io/ceifalume"
YOUTUBE_GAMEPLAY = "https://youtu.be/GuE7af6dYo8"
AGENTE = "Mozilla/5.0 (compatible; rebocl-pendencias/1.0)"

# Marcas que provam que o post do vídeo saiu: o link do vídeo ou uma frase que só ele tem.
MARCAS_DEVLOG = ("gue7af6dyo8", "jogando sozinho", "gameplay com as instrucoes",
                 "gameplay com as instruções")


def buscar(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(200_000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, "erro: %s" % str(e)[:120]


def texto_de(html):
    limpo = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I)
    limpo = re.sub(r"<[^>]+>", " ", limpo)
    return re.sub(r"\s+", " ", limpo).strip()


def devlog_do_video_saiu(html):
    """True quando o post do gameplay já aparece na página pública de devlog."""
    baixo = texto_de(html).casefold()
    return any(m in baixo for m in MARCAS_DEVLOG)


def posts_visiveis(html):
    """Títulos dos posts que a página pública de devlog mostra.

    Medido na página real (30/10): cada post é um <a class="title" href=".../devlog/<id>/<slug>">.
    """
    titulos = []
    for bruto in re.findall(r'<a[^>]+class="[^"]*title[^"]*"[^>]*href="([^"]*\/devlog\/[^"]*)"[^>]*>'
                            r'(.*?)</a>', html or "", flags=re.S | re.I):
        t = texto_de(bruto[1])
        if t and t not in titulos:
            titulos.append(t)
    for bruto in re.findall(r'<a[^>]+href="([^"]*\/devlog\/[^"]*)"[^>]+class="[^"]*title[^"]*"[^>]*>'
                            r'(.*?)</a>', html or "", flags=re.S | re.I):
        t = texto_de(bruto[1])
        if t and t not in titulos:
            titulos.append(t)
    return titulos[:8]


def montar(estado_anterior=None):
    anterior = estado_anterior or {}
    itens = []

    # 1) Devlog do itch com o vídeo — o único passo que sobra para o dono.
    status, html = buscar(DEVLOG_PUBLICO)
    saiu = status == 200 and devlog_do_video_saiu(html)
    itens.append({
        "id": "itch-devlog-gameplay",
        "titulo": "publicar o devlog do gameplay no itch",
        "estado": "feito" if saiu else "esperando o dono",
        "medido": ("o post aparece em %s" % DEVLOG_PUBLICO) if saiu
                  else ("a página pública de devlog respondeu %s e não tem o post do vídeo" % status),
        "por_que_e_do_dono": ("a Cloudflare do itch devolve 403 em /dashboard para IP de "
                              "datacenter — medido em Ubuntu, macOS, Windows e com Chromium real "
                              "(docs/sondagens/ITCH-403-CLOUDFLARE.json)"),
        "como_fazer": ("abrir itch/devlog-gameplay-bookmarklet.txt como favorito em qualquer "
                       "página do itch, logado; ele descobre o formulário e posta o texto de "
                       "posts/devlog-itch-gameplay.json"),
        "texto_pronto": "posts/devlog-itch-gameplay.json",
        "favorito": "itch/devlog-gameplay-bookmarklet.txt",
    })

    # 2) Build no ar com o selo do gameplay — também depende da palavra PUBLICAR.
    status_jogo, html_jogo = buscar(PAGINA_JOGO)
    itens.append({
        "id": "itch-build-selo",
        "titulo": "subir o build com o selo do gameplay (modo push + PUBLICAR)",
        "estado": "esperando o dono",
        "medido": ("página do jogo respondeu %s%s" % (
            status_jogo, "" if status_jogo == 200 else " (sem leitura)")),
        "por_que_e_do_dono": ("build ao vivo substitui o que o jogador baixa; a regra da casa é "
                              "não publicar por conta própria"),
        "como_fazer": ("workflow enviar-itch, jogo=ceifalume, modo=push, confirmacao=PUBLICAR "
                       "(o selo do vídeo já está em ceifalume/index.html)"),
    })

    # 3) O que já está feito, para não virar pendência fantasma.
    publicados = []
    try:
        with open(os.path.join(RAIZ, "posts", "youtube-publicados.json"), encoding="utf-8") as f:
            publicados = json.load(f).get("publicados") or []
    except OSError:
        pass
    tem_video = any(YOUTUBE_GAMEPLAY.split("/")[-1] in (p.get("url") or "") for p in publicados)
    itens.append({
        "id": "youtube-gameplay",
        "titulo": "vídeo de gameplay no YouTube",
        "estado": "feito" if tem_video else "pendente",
        "medido": "registro em posts/youtube-publicados.json" if tem_video
                  else "não achei o registro",
        "como_fazer": "nada: já publicado" if tem_video else "rodar o workflow com PUBLICAR",
    })

    pendentes = [i for i in itens if i["estado"] != "feito"]
    # Aviso só quando MUDA: 1 clique pendente todo dia vira ruído e a pessoa para de ler.
    estado_atual = sorted(i["id"] for i in pendentes)
    mudou = estado_atual != sorted(anterior.get("pendentes_em") or [])
    relatorio = {
        "quando": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "itens": itens,
        "pendentes_em": estado_atual,
        "mudou_desde_o_ultimo": mudou,
        "devlog_publico_titulos": posts_visiveis(html) if status == 200 else [],
    }
    return relatorio


def texto_do_aviso(relatorio):
    linhas = ["Pendência do dono (1 clique):"]
    for i in relatorio["itens"]:
        if i["estado"] == "feito":
            continue
        linhas.append("· %s — %s" % (i["titulo"], i["como_fazer"]))
    linhas.append("devlog público: " + DEVLOG_PUBLICO)
    return "\n".join(linhas)


def escrever(relatorio):
    with open(SAIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
        f.write("\n")
    linhas = ["# Pendências do dono", "",
              "Medido em %s (o devlog do itch é público: dá para conferir de fora)." % relatorio["quando"],
              "", "| item | estado | como |", "| --- | --- | --- |"]
    for i in relatorio["itens"]:
        linhas.append("| %s | %s | %s |" % (i["titulo"], i["estado"], i["como_fazer"]))
    linhas += ["", "## Por que só o dono pode", ""]
    for i in relatorio["itens"]:
        if i["estado"] != "feito":
            linhas.append("- **%s**: %s" % (i["titulo"], i["por_que_e_do_dono"]))
    linhas += ["", "## Medições", ""]
    for i in relatorio["itens"]:
        linhas.append("- **%s**: %s" % (i["titulo"], i["medido"]))
    if relatorio["devlog_publico_titulos"]:
        linhas += ["", "## Posts já no devlog público", ""]
        linhas += ["- " + t for t in relatorio["devlog_publico_titulos"]]
    with open(SAIDA_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


def main(argv):
    anterior = None
    try:
        with open(SAIDA_JSON, encoding="utf-8") as f:
            anterior = json.load(f)
    except (OSError, ValueError):
        anterior = None
    relatorio = montar(anterior)
    escrever(relatorio)
    for i in relatorio["itens"]:
        print("%-12s %-28s %s" % (("✔" if i["estado"] == "feito" else "…"), i["titulo"], i["medido"][:90]))
    print("\npendentes: %d · mudou desde o último: %s"
          % (len(relatorio["pendentes_em"]), "sim" if relatorio["mudou_desde_o_ultimo"] else "não"))
    if os.environ.get("PEDIR_AVISO") == "1" and relatorio["mudou_desde_o_ultimo"] and relatorio["pendentes_em"]:
        topico = os.environ.get("NTFY_TOPIC")
        if topico:
            try:
                req = urllib.request.Request("https://ntfy.sh/" + topico,
                                             data=texto_do_aviso(relatorio).encode("utf-8"),
                                             method="POST")
                urllib.request.urlopen(req, timeout=20).read()
                print("aviso enviado ao ntfy")
            except Exception as e:  # noqa: BLE001
                print("aviso não enviado:", str(e)[:80])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
