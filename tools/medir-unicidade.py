#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quantos posts diferentes a casa publicou — medido no registro, não na intenção.

POR QUE EXISTE (07/11/2026): o dono pediu "é essencial que ele crie e produza coisas únicas".
A casa já tinha opinião sobre isso (o portão recusa texto repetido) e nenhum número. Medindo o
registro `posts/posts-publicados.md`:

  - entre 13/10 e 25/10 um MESMO texto saiu 40 vezes, e houve dia com 5 posts e 1 texto único;
  - de 26/10 até hoje, nenhum dia com texto repetido;
  - e o preço disso também é número: a média caiu de 4,5 para 1,4 posts por dia na última semana.

Sem este medidor, "está único" seria lembrança. Com ele, é uma frase com data e contagem — e a
bateria reprova se voltar a repetir.

Uso:
    python3 tools/medir-unicidade.py            # mede e imprime
    python3 tools/medir-unicidade.py --json     # só o JSON
"""
import datetime
import json
import os
import re
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "posts-publicados.md")
SAIDA = os.path.join(RAIZ, "posts", "unicidade.json")

# QUASE-REPETIDO (07/11/2026): com 0,9 um texto de 17 palavras com UMA palavra trocada dava 0,875
# e passava — era o caso do "está fechado" virando "fica fechado", que ninguém no feed lê como
# post novo. Um em cada cinco termos trocados já é o mesmo post: 0,8.
SEMELHANCA_REPETICAO = 0.8


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def assinatura(texto):
    """O esqueleto do texto: sem acento, sem emoji, sem pontuação, minúsculo.

    É a mesma ideia do `_assinatura` do juízo: se dois posts só diferem no enfeite, para quem lê
    no feed é o mesmo post.
    """
    limpo = _sem_acento(str(texto or "")).lower()
    limpo = re.sub(r"[^a-z0-9\s]", " ", limpo)
    return " ".join(limpo.split())


def tokens(texto):
    return set(assinatura(texto).split())


def semelhanca(a, b):
    """Jaccard das palavras. Usado para o quase-repetido, que a assinatura exata não pega."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def ler_posts(caminho=REGISTRO):
    """[(data, texto)] na ordem do registro. O que não tiver data ou texto não entra."""
    try:
        bruto = open(caminho, encoding="utf-8").read()
    except OSError:
        return []
    posts = []
    for bloco in re.split(r"\n## ", bruto)[1:]:
        linhas = bloco.strip().splitlines()
        achado = re.match(r"(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})", linhas[0].strip()) \
            if linhas else None
        if not achado:
            continue
        corpo = " ".join(l.strip() for l in linhas[1:] if l.strip())
        corpo = corpo.replace("⏎", " ").strip()
        if not corpo:
            continue
        try:
            dia = datetime.date(int(achado.group(3)), int(achado.group(2)), int(achado.group(1)))
        except ValueError:
            continue
        posts.append((dia, corpo))
    return posts


def por_dia(posts):
    """{dia: [textos]} — o dia é a unidade em que a repetição machuca (o feed do dia)."""
    mapa = {}
    for dia, texto in posts:
        mapa.setdefault(dia, []).append(texto)
    return mapa


def repetidos(textos):
    """[(assinatura, [textos originais])] só do que saiu mais de uma vez no mesmo dia."""
    grupos = {}
    for texto in textos:
        grupos.setdefault(assinatura(texto), []).append(texto)
    return [(a, t) for a, t in grupos.items() if len(t) > 1]


def quase_repetidos(textos, limite=SEMELHANCA_REPETICAO):
    """Pares de textos diferentes, mas quase iguais — o caso do emoji trocado."""
    achados, chaves = [], sorted({assinatura(t): t for t in textos}.items())
    for i in range(len(chaves)):
        for j in range(i + 1, len(chaves)):
            nota = semelhanca(chaves[i][0], chaves[j][0])
            if nota >= limite:
                achados.append({"a": chaves[i][1][:80], "b": chaves[j][1][:80],
                                "semelhanca": round(nota, 2)})
    return achados


def dias_com_repeticao(posts):
    """[(dia, posts_no_dia, textos_unicos)] ordenado — o histórico do problema."""
    saida = []
    for dia in sorted(por_dia(posts)):
        textos = por_dia(posts)[dia]
        unicos = len({assinatura(t) for t in textos})
        if unicos < len(textos):
            saida.append((dia, len(textos), unicos))
    return saida


def medir(posts=None, hoje=None, dias_recentes=7):
    posts = ler_posts() if posts is None else posts
    hoje = hoje or datetime.date.today()
    dados = {"medido_em": hoje.isoformat(), "posts": len(posts), "dias_com_post": 0,
             "media_por_dia": None, "dias_com_repeticao": [], "ultimo_dia_com_repeticao": None,
             "ultimos_dias": {"janela": dias_recentes, "posts": 0, "textos_unicos": 0,
                              "repetidos": 0},
             "veredito": "sem registro: não afirmo"}
    if not posts:
        return dados
    mapa = por_dia(posts)
    dados["dias_com_post"] = len(mapa)
    dados["de"] = min(mapa).isoformat()
    dados["ate"] = max(mapa).isoformat()
    dados["media_por_dia"] = round(len(posts) / float(len(mapa)), 2)
    dados["dias_com_repeticao"] = [{"dia": d.isoformat(), "posts": n, "unicos": u}
                                   for d, n, u in dias_com_repeticao(posts)]
    dados["ultimo_dia_com_repeticao"] = (dados["dias_com_repeticao"][-1]["dia"]
                                         if dados["dias_com_repeticao"] else None)
    recentes = [(d, t) for d, t in posts if (hoje - d).days < dias_recentes]
    textos = [t for _, t in recentes]
    dados["ultimos_dias"] = {"janela": dias_recentes, "posts": len(textos),
                             "textos_unicos": len({assinatura(t) for t in textos}),
                             "repetidos": len(repetidos(textos)),
                             "quase_repetidos": quase_repetidos(textos)}
    dados["veredito"] = frase(dados)
    return dados


def frase(dados):
    """A frase que o relatório usa — curta, com data e número."""
    if not dados.get("posts"):
        return dados.get("veredito") or "sem registro: não afirmo"
    u = dados["ultimos_dias"]
    if u["posts"] == 0:
        return ("nenhum post nos últimos %d dias (registro com %d posts desde %s)"
                % (u["janela"], dados["posts"], dados["de"]))
    if u["repetidos"] or u["quase_repetidos"]:
        return ("REPETIÇÃO nos últimos %d dias: %d post(s), %d texto(s) único(s), %d repetido(s)"
                % (u["janela"], u["posts"], u["textos_unicos"], u["repetidos"]))
    ultimo = dados.get("ultimo_dia_com_repeticao")
    cauda = ("o último dia com repetição foi %s" % ultimo if ultimo
             else "nunca houve dia com repetição no registro")
    return ("últimos %d dias: %d post(s), todos textos diferentes · média %s/dia · %s"
            % (u["janela"], u["posts"], dados["media_por_dia"], cauda))


def gravar(dados, caminho=SAIDA):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return caminho


def main(argv):
    dados = medir()
    if "--json" in argv:
        print(json.dumps(dados, ensure_ascii=False, indent=1))
        return 0
    if not dados["posts"]:
        print("sem registro de posts: não afirmo nada")
        return 3
    print("registro: %d post(s) em %d dia(s), de %s a %s · média %s/dia"
          % (dados["posts"], dados["dias_com_post"], dados["de"], dados["ate"],
             dados["media_por_dia"]))
    print("dias com repetição: %d%s"
          % (len(dados["dias_com_repeticao"]),
             " (último em %s)" % dados["ultimo_dia_com_repeticao"]
             if dados["ultimo_dia_com_repeticao"] else " (nenhum)"))
    for dia in dados["dias_com_repeticao"][-3:]:
        print("  %s: %d post(s), %d texto(s) único(s)"
              % (dia["dia"], dia["posts"], dia["unicos"]))
    print(frase(dados))
    print("gravado em " + os.path.relpath(gravar(dados), RAIZ))
    return 0 if frase(dados).startswith(("últimos", "nenhum")) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
