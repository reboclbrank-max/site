#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memória única da casa — um lugar para consultar, em vez de 8 arquivos .md espalhados.

O que ele NÃO é: um modelo com memória. É um índice durável e auditável do que a casa
mediu, publicou e aprendeu. Quem "pensa" continua sendo o modelo; o que faltava era a
casa lembrar do próprio passado sem reler 8 arquivos a cada pulso.

Fontes (todas já existentes, nada inventado):
  posts/placar-metas.md      -> metas e falta
  posts/desempenho.md        -> engajamento por formato e por hora
  posts/log.md               -> o que cada ciclo publicou/falhou
  posts/aprendizado.json     -> decisão sobre horário
  posts/plano-do-dia.json    -> o que o dia pediu
  posts/orquestrador.json    -> pulsos e histórico
  posts/fila-tarefas.json    -> pendências e falhas

Saída: posts/memoria.json  (estruturado) — e consulta por palavra-chave no terminal.
"""
import datetime
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "posts", "memoria.json")


def ler_texto(rel):
    try:
        with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def ler_json(rel):
    try:
        with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def metas(texto_placar):
    itens = []
    for linha in texto_placar.splitlines():
        if not linha.startswith("|") or "|" not in linha[1:]:
            continue
        p = [x.strip() for x in linha.strip("|").split("|")]
        if len(p) < 6 or p[0].lower().startswith("meta") or set(p[0]) <= {"-"}:
            continue
        itens.append({"meta": p[0], "alvo": p[1], "observado": p[2], "falta": p[3],
                      "por_dia": p[4], "status": p[5]})
    return itens


def formatos(texto_desempenho):
    vistos, itens = set(), []
    for linha in texto_desempenho.splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\(([\d.]+)%\)", linha)
        if not m:
            continue
        nome = m.group(1)
        if nome in vistos:
            continue
        vistos.add(nome)
        itens.append({"formato": nome, "posts": int(m.group(2)), "media": float(m.group(3)),
                      "zeros": int(m.group(5)), "zeros_pct": float(m.group(6))})
    return itens


def ciclos(texto_log, limite=5):
    blocos = [b for b in texto_log.split("\n## ") if b.strip()]
    saida = []
    for bloco in blocos[-limite:]:
        linhas = bloco.strip().splitlines()
        quando = linhas[0].strip() if linhas else ""
        canais = {}
        for linha in linhas:
            m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", linha)
            if m and not m.group(1).startswith("canal") and not m.group(1).startswith("-"):
                canais[m.group(1)] = m.group(2).strip()
        saida.append({"quando": quando, "canais": canais})
    return saida


def construir():
    memoria = {
        "quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metas": metas(ler_texto("posts/placar-metas.md")),
        "formatos": formatos(ler_texto("posts/desempenho.md")),
        "ultimos_ciclos": ciclos(ler_texto("posts/log.md")),
        "aprendizado": ler_json("posts/aprendizado.json"),
        "plano": ler_json("posts/plano-do-dia.json"),
        "orquestrador": {k: v for k, v in ler_json("posts/orquestrador.json").items() if k != "historico"},
        "fila": {t.get("tipo"): t.get("estado") for t in (ler_json("posts/fila-tarefas.json").get("tarefas") or [])[-12:]},
        "_regras": [
            "número sem fonte medida não entra (NAO_OBSERVAVEL não é zero)",
            "horário só muda com amostra >= 30 por hora e ganho acima de um desvio",
            "uma tarefa por pulso",
            "vídeo no YouTube só com confirmação do dono",
            "itch: escrita de conteúdo só no navegador do dono (Cloudflare barra datacenter)",
        ],
    }
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return memoria


def consultar(pergunta, memoria=None):
    """Busca por palavra-chave nas seções. Devolve lista de (secao, achado) em texto."""
    memoria = memoria or construir()
    termo = (pergunta or "").strip().casefold()
    if not termo:
        return []
    achados = []
    for m in memoria.get("metas", []):
        if termo in json.dumps(m, ensure_ascii=False).casefold():
            achados.append(("meta", "%s: %s de %s (falta %s · %s/dia · %s)"
                            % (m["meta"], m["observado"], m["alvo"], m["falta"], m["por_dia"], m["status"])))
    for f in memoria.get("formatos", []):
        if termo in json.dumps(f, ensure_ascii=False).casefold():
            achados.append(("formato", "%s: %d posts · média %.2f · %d sem engajamento (%.1f%%)"
                            % (f["formato"], f["posts"], f["media"], f["zeros"], f["zeros_pct"])))
    for regra in memoria.get("_regras", []):
        if termo in regra.casefold():
            achados.append(("regra", regra))
    aprend = memoria.get("aprendizado") or {}
    if termo in json.dumps(aprend, ensure_ascii=False).casefold() and aprend:
        achados.append(("aprendizado", "%s: %s" % (aprend.get("decisao"), aprend.get("motivo"))))
    return achados


def main(argv):
    if "--pergunta" in argv:
        i = argv.index("--pergunta")
        pergunta = " ".join(argv[i + 1:])
        achados = consultar(pergunta)
        print("pergunta: %s · %d achado(s)" % (pergunta, len(achados)))
        for secao, texto in achados[:12]:
            print("  [%s] %s" % (secao, texto))
        return 0
    memoria = construir()
    print("memória gravada: %d metas · %d formatos · %d ciclos · %d regras"
          % (len(memoria["metas"]), len(memoria["formatos"]),
             len(memoria["ultimos_ciclos"]), len(memoria["_regras"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
