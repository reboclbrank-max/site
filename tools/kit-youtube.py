#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kit de envio para o YouTube — o que dá para automatizar sem OAuth.

POR QUE EXISTE (26/10/2026): o canal tem 4 vídeos da casa (média 66,8 views) e 96 de outros
jogos (36,0) — o conteúdo da casa rende quase o dobro por vídeo e ocupa 4% do canal. Enviar
vídeo pela API exige OAuth do dono (a chave guardada é só de leitura, e o próprio cofre diz
isso). OAuth é permissão, não custo: não é meu para criar.

O que sobra é o resto — e é quase tudo: título, descrição com links oficiais, tags, hashtags,
arquivo certo, ordem de envio. Este script monta o pacote a partir de FATOS medidos, com os
links da lista fechada, e escreve `posts/kit-youtube.json` e `posts/kit-youtube.md`.

O robô NÃO envia nada. Ele deixa a parte do dono no menor tamanho possível (colar e clicar) e
recusa qualquer texto que não venha dos fatos da casa.
"""
import datetime
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))

SAIDA_JSON = os.path.join(RAIZ, "posts", "kit-youtube.json")
SAIDA_MD = os.path.join(RAIZ, "posts", "kit-youtube.md")

# Fonte única dos fatos. Se um dia mudar a versão do jogo, muda AQUI — nunca no texto solto.
JOGOS = {
    "prancheta": {
        "nome": "PRANCHETA",
        "o_que_e": "simulador de gestão de futebol 100% fictício",
        "como_joga": "você desenha a bola parada na prancheta e vê a partida simular",
        "onde": "grátis no navegador ou no APK",
        "feito_com": "Godot, feito no Brasil",
        "link": "https://reboclbrank-max.github.io/site/jogos/prancheta/",
        # a casa não tem vídeo próprio do PRANCHETA além do reel vertical do Instagram
        "video": "media/reel.mp4",
        "capa": "media/prancheta/capa-630x500.png",
        "tags": ["prancheta", "manager de futebol", "jogo de futebol", "jogo indie brasileiro",
                 "godot", "futebol ficticio", "jogo de navegador"],
    },
    "ceifalume": {
        "nome": "CEIFALUME",
        "versao": "0.1",
        "o_que_e": "jogo idle de fazenda noturna",
        "como_joga": "plante, colha e negocie à luz da lanterna",
        "onde": "grátis no navegador ou no Android, sem conta",
        "diferencial": "as plantações crescem por até 8 horas mesmo com o jogo fechado",
        "feito_com": "Godot, feito no Brasil",
        "link": "https://reboclbrank-max.github.io/site/jogos/ceifalume/",
        # o trailer 16:9 já existe no repositório e é o material mais honesto do jogo
        "video": "media/ceifalume/ceifalume-trailer-0.1.mp4",
        "capa": "media/ceifalume/perfil-rb-itch-630x500.png",
        "tags": ["ceifalume", "jogo de fazenda", "idle game", "jogo indie brasileiro",
                 "godot", "jogo offline", "fazenda noturna"],
    },
}

HUB_CANAIS = "https://reboclbrank-max.github.io/site/canais.html"
LIMITE_TITULO = 100       # limite do YouTube
LIMITE_DESCRICAO = 5000   # limite do YouTube
LIMITE_TAGS_CARACTERES = 500

# Frases que NÃO podem aparecer: promessa que a casa não sustenta. O kit se recusa a escrever.
PROIBIDO = re.compile(r"\b(?:em breve|em desenvolvimento|maior|melhor do mundo|garantido|"
                      r"premiado|milhões|viral)\b", re.I)


def _verificar_arquivo(relativo):
    caminho = os.path.join(RAIZ, relativo)
    return os.path.exists(caminho) and os.path.getsize(caminho) > 0


def dimensoes_mp4(relativo):
    """(largura, altura) do primeiro 'tkhd' — sem dependência externa.

    Serve para decidir se o arquivo vira Short: o YouTube considera Short até 3 minutos em
    9:16. Reel do Instagram é vertical; trailer é 16:9. Não adivinhar, medir.
    """
    try:
        with open(os.path.join(RAIZ, relativo), "rb") as f:
            dados = f.read()
    except OSError:
        return None
    i = dados.find(b"tkhd")
    if i < 0:
        return None
    ini = i - 4
    tamanho = int.from_bytes(dados[ini:ini + 4], "big")
    corpo = dados[i + 4:ini + tamanho]
    try:
        largura = int.from_bytes(corpo[-8:-4], "big") / 65536.0
        altura = int.from_bytes(corpo[-4:], "big") / 65536.0
        return (int(largura), int(altura)) if largura and altura else None
    except Exception:
        return None


def titulo(slug):
    j = JOGOS[slug]
    versao = (" " + j["versao"]) if j.get("versao") else ""
    t = "%s%s — %s (%s)" % (j["nome"], versao, j["o_que_e"], "jogo indie brasileiro")
    return t[:LIMITE_TITULO]


def descricao(slug):
    """Descrição com fatos medidos + links oficiais. Sem promessa, sem número inventado."""
    j = JOGOS[slug]
    versao = (" " + j["versao"]) if j.get("versao") else ""
    linhas = [
        "%s%s — %s." % (j["nome"], versao, j["o_que_e"]),
        "",
        "Como funciona: %s." % j["como_joga"],
    ]
    if j.get("diferencial"):
        linhas.append("O que chama atenção: %s." % j["diferencial"])
    linhas += [
        "Onde jogar: %s." % j["onde"],
        "Feito com %s." % j["feito_com"],
        "",
        "Jogar: " + j["link"],
        "Todos os canais da casa: " + HUB_CANAIS,
        "",
        "Canal de dev solo: bastidores, versões e o que quebrou no caminho.",
        "",
        "#indiedev #gamedev #godot #jogobrasileiro",
    ]
    texto = "\n".join(linhas)
    return texto[:LIMITE_DESCRICAO]


def tags(slug):
    j = JOGOS[slug]
    escolhidas, total = [], 0
    for t in j["tags"]:
        # o YouTube conta o conjunto inteiro (com vírgulas) até 500 caracteres
        if total + len(t) + 1 > LIMITE_TAGS_CARACTERES:
            break
        escolhidas.append(t)
        total += len(t) + 1
    return escolhidas


def pacote(slug):
    j = JOGOS[slug]
    d = dimensoes_mp4(j["video"]) if _verificar_arquivo(j["video"]) else None
    vertical = bool(d and d[1] > d[0])
    aviso = None
    if d:
        razao = d[0] / float(d[1])
        if vertical and abs(razao - 9 / 16.0) > 0.02:
            aviso = ("vertical %dx%d (%.2f:1), não 9:16 — o Short aceita vertical, mas o "
                     "padrão é 9:16; recortar exige ffmpeg, que a casa não tem"
                     % (d[0], d[1], razao))
    p = {
        "slug": slug,
        "arquivo": j["video"],
        "arquivo_existe": _verificar_arquivo(j["video"]),
        "capa": j.get("capa"),
        "capa_existe": bool(j.get("capa") and _verificar_arquivo(j["capa"])),
        "dimensoes": d,
        "formato": "Short (vertical)" if vertical else "vídeo normal (16:9)",
        "aviso_formato": aviso,
        "titulo": titulo(slug),
        "descricao": descricao(slug),
        "tags": tags(slug),
        "idioma": "pt-BR",
        "categoria": "Gaming",
        "visibilidade": "público",
        "feito_para_criancas": "não",
        "passos_do_dono": [
            "1. Abrir https://studio.youtube.com e escolher 'Criar > Enviar vídeos'",
            "2. Arrastar %s" % j["video"],
            "3. Colar o título e a descrição deste pacote (copiar dos blocos abaixo)",
            "4. Marcar como %s e publicar" % ("Short" if vertical else "vídeo normal"),
        ],
    }
    return p


def validar(p):
    """Recusa o pacote inteiro se qualquer regra da casa for violada."""
    erros = []
    if not (1 <= len(p["titulo"]) <= LIMITE_TITULO):
        erros.append("título fora do limite")
    if not (1 <= len(p["descricao"]) <= LIMITE_DESCRICAO):
        erros.append("descrição fora do limite")
    junto = p["titulo"] + "\n" + p["descricao"]
    if PROIBIDO.search(junto):
        erros.append("promessa que a casa não sustenta: " + PROIBIDO.search(junto).group(0))
    for link in (JOGOS[p["slug"]]["link"], HUB_CANAIS):
        if link not in p["descricao"]:
            erros.append("link oficial ausente: " + link)
    if not p["arquivo_existe"]:
        erros.append("arquivo de vídeo ausente: " + p["arquivo"])
    soma = sum(len(t) + 1 for t in p["tags"])
    if soma > LIMITE_TAGS_CARACTERES:
        erros.append("tags acima do limite (%d)" % soma)
    if len(p["descricao"].split()) < 15:
        erros.append("descrição curta demais para indexar")
    return erros


def montar():
    pacotes, problemas = [], {}
    for slug in JOGOS:
        p = pacote(slug)
        erros = validar(p)
        if erros:
            problemas[slug] = erros
        pacotes.append(p)
    resultado = {
        "gerado_em": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "por_que": ("envio por API exige OAuth do dono; a chave da casa é só de leitura. "
                    "Este kit reduz o trabalho do dono a colar e clicar — e nada é enviado "
                    "pelo robô."),
        "pacotes": pacotes,
        "problemas": problemas,
    }
    return resultado


def escrever(dados):
    with open(SAIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    linhas = ["# Kit de envio para o YouTube", "",
              "> Montado a partir dos fatos medidos da casa. O robô não envia nada: o envio",
              "> depende do OAuth do dono, que é permissão, não custo.", ""]
    if dados["problemas"]:
        linhas += ["## Pacotes recusados (corrigir antes de usar)", ""]
        for slug, erros in dados["problemas"].items():
            linhas.append("- **%s**: %s" % (slug, "; ".join(erros)))
        linhas.append("")
    linhas += ["| jogo | arquivo | formato | título | tags |", "|---|---|---|---|---|"]
    for p in dados["pacotes"]:
        linhas.append("| %s | %s | %s | %s | %d |" % (
            p["slug"], p["arquivo"], p["formato"], p["titulo"][:60], len(p["tags"])))
    for p in dados["pacotes"]:
        linhas += ["", "---", "", "## " + p["slug"].upper(), "",
                   "**Arquivo:** `%s` (%s×%s)" % (p["arquivo"], *(p["dimensoes"] or ("?", "?"))),
                   "", "**Passos do dono:**"]
        linhas += ["- " + passo for passo in p["passos_do_dono"]]
        linhas += ["", "**Título (copiar):**", "", "```", p["titulo"], "```",
                   "", "**Descrição (copiar):**", "", "```", p["descricao"], "```",
                   "", "**Tags (copiar):**", "", "```", ", ".join(p["tags"]), "```"]
    with open(SAIDA_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    return SAIDA_MD


def main(argv):
    dados = montar()
    if "--json" in argv:
        print(json.dumps(dados, ensure_ascii=False, indent=1))
        return 0
    caminho = escrever(dados)
    print("🎬 kit do YouTube")
    for p in dados["pacotes"]:
        estado = "RECUSADO" if p["slug"] in dados["problemas"] else "pronto"
        print("   %-10s %-22s %s" % (p["slug"], p["formato"], estado))
    if dados["problemas"]:
        print("   problemas:", json.dumps(dados["problemas"], ensure_ascii=False))
    print("   gravado em", os.path.relpath(caminho, RAIZ))
    return 0 if not dados["problemas"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
