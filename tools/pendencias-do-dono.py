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

    # 1) Devlog do itch com o vídeo.
    #
    # MEDIDO EM 31/10/2026 (docs/sondagens/ITCH-DEVLOG-SEM-CAMINHO-AUTOMATICO.json): este item
    # NÃO é tarefa do dono, é uma limitação do itch:
    #   * /dashboard e /game/edit/<id> → 403 com desafio do Cloudflare para IP de datacenter;
    #   * a API oficial não tem endpoint de devlog (o api.itch.io responde 401 e NÃO tem
    #     bloqueio de Cloudflare — se houvesse rota, ela seria usável; não há);
    #   * o próprio itch diz que não oferece API de publicação, para não virar spam.
    # Ficar pedindo o clique todo dia era empurrar no dono uma coisa que a casa não consegue
    # fazer e que já está entregue por outros três canais. O item continua VISÍVEL aqui, com a
    # medição, mas não conta como pendência.
    status, html = buscar(DEVLOG_PUBLICO)
    saiu = status == 200 and devlog_do_video_saiu(html)
    itens.append({
        "id": "itch-devlog-gameplay",
        "titulo": "publicar o devlog do gameplay no itch",
        "estado": "feito" if saiu else "sem caminho automático",
        "caminho_automatico": True if saiu else False,
        "coberto_em": [] if saiu else [
            "blog/ceifalume-gameplay.html (site da casa, sem trava nenhuma)",
            "https://youtu.be/GuE7af6dYo8 (YouTube, público)",
            "vídeo dentro da pasta do jogo (media/) — vai junto de qualquer build futuro",
        ],
        "medido_em": "2026-10-31",
        "sondagem": "docs/sondagens/ITCH-DEVLOG-SEM-CAMINHO-AUTOMATICO.json",
        "medido": ("o post aparece em %s" % DEVLOG_PUBLICO) if saiu
                  else ("a página pública de devlog respondeu %s e não tem o post; o painel do "
                        "itch responde 403 (Cloudflare) para IP de datacenter e a API oficial "
                        "não tem endpoint de devlog — medido em 31/10/2026" % status),
        "por_que_e_do_dono": ("a Cloudflare do itch devolve 403 em /dashboard para IP de "
                              "datacenter — medido em Ubuntu, macOS, Windows e com Chromium real "
                              "(docs/sondagens/ITCH-403-CLOUDFLARE.json)"),
        "como_fazer": ("nada obrigatório: o conteúdo já chega ao jogador pelo build, pelo blog "
                       "e pelo YouTube. Se quiser a cópia editorial no itch: abrir "
                       "itch/devlog-gameplay-bookmarklet.txt como favorito em qualquer página "
                       "do itch, logado — ele acha o formulário e posta posts/devlog-itch-gameplay.json"),
        "texto_pronto": "posts/devlog-itch-gameplay.json",
        "favorito": "itch/devlog-gameplay-bookmarklet.txt",
    })

    # 2) Build no ar com o selo do gameplay.
    #
    # DEFEITO MEDIDO (31/10/2026): este item ficava "esperando o dono" PARA SEMPRE, porque a
    # única medição era "a página do jogo respondeu 200" — que é verdade mesmo sem build nenhum.
    # Resultado: o build entrou (2257110) e o relatório continuou pedindo ao dono o que já
    # estava feito. Agora a medida é o registro com id de build E prova (run do push + run da
    # conferência), o mesmo critério do cofre em tools/publicacoes.py.
    build_no_ar = None
    try:
        with open(os.path.join(RAIZ, "posts", "itch-builds.json"), encoding="utf-8") as f:
            for b in json.load(f).get("builds") or []:
                if str(b.get("build") or "").strip() and str(b.get("prova") or "").strip():
                    build_no_ar = b
                    break
    except (OSError, ValueError):
        pass
    status_jogo, html_jogo = buscar(PAGINA_JOGO)
    itens.append({
        "id": "itch-build-selo",
        "titulo": "subir o build com o selo do gameplay (modo push + PUBLICAR)",
        "estado": "feito" if build_no_ar else "esperando o dono",
        "medido": ("build %s no ar (versão %s, %s) — %s" % (
            build_no_ar.get("build"), build_no_ar.get("versao") or "sem carimbo",
            build_no_ar.get("link") or PAGINA_JOGO, build_no_ar.get("prova"))
            if build_no_ar else
            ("página do jogo respondeu %s%s" % (
                status_jogo, "" if status_jogo == 200 else " (sem leitura)"))),
        "por_que_e_do_dono": ("build ao vivo substitui o que o jogador baixa; a regra da casa é "
                              "não publicar por conta própria"),
        "como_fazer": ("workflow enviar-itch, jogo=ceifalume, modo=push, confirmacao=PUBLICAR "
                       "(o selo do vídeo já está em ceifalume/index.html)"),
    })

    # 2b) O jogo no itch ENTREGAR o jogo do repositório — e o vídeo chegar a quem joga lá.
    #
    # HISTÓRICO DESTE ITEM (31/10/2026), para não repetir a confusão:
    #   1o — o cofre dizia "build no ar" só porque o butler tinha enviado. Falso: o jogador não
    #        recebia aquele upload.
    #   2o — corrigido para "o jogador NÃO abre o build enviado": certo quanto ao upload, mas
    #        INCOMPLETO. Comparando arquivo por arquivo (enviar-itch.py conferir), index.js,
    #        index.pck e index.wasm servidos pelo itch são byte a byte IGUAIS aos do repositório.
    #        O jogo no itch está atualizado; o que difere é só a casca HTML.
    #   3o — o vídeo chega a quem está no itch pelo GIF da descrição, que é servido por nós e
    #        agora leva o selo carimbado. Logo: nada aqui depende de clique do dono.
    conferencia, ressalva = {}, ""
    try:
        with open(os.path.join(RAIZ, "posts", "itch-builds.json"), encoding="utf-8") as f:
            for b in json.load(f).get("builds") or []:
                if b.get("conferencia_do_servido"):
                    conferencia = b["conferencia_do_servido"]
                    ressalva = b.get("ressalva") or ""
                    break
    except (OSError, ValueError):
        pass
    jogo_igual = conferencia.get("jogo_igual_ao_repo") is True
    itens.append({
        "id": "itch-pagina-abre-build",
        "titulo": "o jogo no itch entregar o conteúdo do repositório (e o vídeo chegar lá)",
        "estado": "feito" if jogo_igual else "sem caminho automático",
        "caminho_automatico": jogo_igual,
        "coberto_em": [] if jogo_igual else [
            "blog/ceifalume-gameplay.html e a página do jogo no site da casa",
            "https://youtu.be/GuE7af6dYo8 (YouTube)",
        ],
        "sondagem": "docs/sondagens/ITCH-DEVLOG-SEM-CAMINHO-AUTOMATICO.json",
        "medido": ("conferência do servido (sha256, arquivo por arquivo): %s — o jogo que o jogador "
                   "recebe é o do repositório; o vídeo chega pelo GIF da descrição, que é servido "
                   "por nós. %s" % (
                       ", ".join("%s %s" % (k, v) for k, v in
                                 sorted((conferencia.get("arquivos") or {}).items())),
                       ressalva)) if jogo_igual else
                  "a página do itch entrega conteúdo diferente do repositório — sem caminho "
                  "automático para trocar (painel 403, API sem endpoint)",
        "por_que_e_do_dono": ("trocar o upload que a página abre é só pelo painel do itch — 403 "
                              "do Cloudflare para IP de datacenter, e a API oficial não tem "
                              "endpoint para isso"),
        "como_fazer": ("nada obrigatório: o jogo no itch já é o do repositório e o vídeo chega "
                       "pelo GIF da descrição"),
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

    # Pendência é o que o dono pode resolver com um clique. O que não tem caminho automático e
    # já está entregue em outro canal fica listado (para não esconder nada), mas fora da conta:
    # pedir o impossível todo dia é o jeito mais rápido de a pessoa parar de ler o aviso.
    pendentes = [i for i in itens if i["estado"] not in ("feito", "sem caminho automático")]
    sem_caminho = [i for i in itens if i["estado"] == "sem caminho automático"]
    # Aviso só quando MUDA: 1 clique pendente todo dia vira ruído e a pessoa para de ler.
    estado_atual = sorted(i["id"] for i in pendentes)
    mudou = estado_atual != sorted(anterior.get("pendentes_em") or [])
    relatorio = {
        "quando": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "itens": itens,
        "pendentes_em": estado_atual,
        "sem_caminho_automatico_em": sorted(i["id"] for i in sem_caminho),
        "mudou_desde_o_ultimo": mudou,
        "devlog_publico_titulos": posts_visiveis(html) if status == 200 else [],
    }
    return relatorio


def texto_do_aviso(relatorio):
    linhas = ["Pendência do dono (1 clique):"]
    for i in relatorio["itens"]:
        if i["estado"] != "esperando o dono":
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
    _do_dono = [i for i in relatorio["itens"] if i["estado"] == "esperando o dono"]
    if not _do_dono:
        linhas.append("Nada. Nenhuma pendência depende de clique do dono nesta medição.")
    for i in _do_dono:
        linhas.append("- **%s**: %s" % (i["titulo"], i["por_que_e_do_dono"]))

    # O que NÃO depende do dono não some daqui: fica com a medição e com onde o conteúdo chega.
    linhas += ["", "## Sem caminho automático (medido, não pedido)", ""]
    _sem = [i for i in relatorio["itens"] if i["estado"] == "sem caminho automático"]
    if not _sem:
        linhas.append("Nada nessa situação.")
    for i in _sem:
        linhas.append("- **%s** — %s" % (i["titulo"], i["medido"]))
        if i.get("sondagem"):
            linhas.append("  - sondagem: `%s`" % i["sondagem"])
        for onde in i.get("coberto_em") or []:
            linhas.append("  - chega ao jogador por: %s" % onde)
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
    _marca = {"feito": "✔", "sem caminho automático": "—", "esperando o dono": "…"}
    for i in relatorio["itens"]:
        print("%-2s %-52s %s" % (_marca.get(i["estado"], "?"), i["titulo"], i["medido"][:110]))
    print("\npendentes do dono: %d · sem caminho automático: %d · mudou desde o último: %s"
          % (len(relatorio["pendentes_em"]), len(relatorio["sem_caminho_automatico_em"]),
             "sim" if relatorio["mudou_desde_o_ultimo"] else "não"))
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
