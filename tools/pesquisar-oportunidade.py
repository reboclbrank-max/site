#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pesquisa diária: qual meta atacar, com que tema, em que horário.

Não inventa nada: tudo sai de arquivos medidos.
  - meta em risco  <- posts/placar-metas.md (falta ÷ dias restantes)
  - temas ruins    <- posts/desempenho.md (formato com muito zero) + histórico
  - horário        <- posts/calendario.json (janela) e posts/aprendizado.json (se já houver prova)

Saída: posts/plano-do-dia.json
"""
import datetime
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACAR = os.path.join(RAIZ, "posts", "placar-metas.md")
DESEMPENHO = os.path.join(RAIZ, "posts", "desempenho.md")
FILA = os.path.join(RAIZ, "posts", "fila.json")
CALENDARIO = os.path.join(RAIZ, "posts", "calendario.json")
APRENDIZADO = os.path.join(RAIZ, "posts", "aprendizado.json")
PLANO = os.path.join(RAIZ, "posts", "plano-do-dia.json")


def ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def metas_em_risco(texto_placar):
    """Lista (meta, falta, por_dia) das linhas EM_CURSO do placar, maior risco primeiro."""
    itens = []
    for linha in texto_placar.splitlines():
        if not linha.startswith("|") or "EM_CURSO" not in linha:
            continue
        partes = [p.strip() for p in linha.strip("|").split("|")]
        if len(partes) < 6:
            continue
        meta, falta, por_dia = partes[0], partes[3], partes[4]
        try:
            itens.append((meta, float(falta.replace(",", ".")), float(por_dia.replace(",", "."))))
        except ValueError:
            continue
    itens.sort(key=lambda x: x[2], reverse=True)
    return itens


def formatos_ruins(texto_desempenho):
    """Formatos com 40%+ de posts sem engajamento, lidos da tabela do relatório."""
    ruins = []
    for linha in texto_desempenho.splitlines():
        m = re.search(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*[\d.]+\s*\|\s*\d+\s*\|\s*(\d+)\s*\(([\d.]+)%\)", linha)
        if not m:
            continue
        nome, zeros, pct = m.group(1), int(m.group(3)), float(m.group(4))
        total = int(m.group(2))
        if total and zeros / total >= 0.40:
            ruins.append({"formato": nome, "zeros": zeros, "total": total, "pct": pct})
    return ruins


def escolher_tema(caminho_fila=FILA, temas_gastos=()):
    """Primeiro tema da fila que ainda parece bom (não está na lista de gastos)."""
    try:
        with open(caminho_fila, encoding="utf-8") as f:
            fila = json.load(f)
    except Exception:
        return None
    for item in fila.get("posts", []):
        texto = (item.get("texto") or "").strip()
        if not texto or len(texto) > 220:
            continue
        if any(gasto.casefold() in texto.casefold() for gasto in temas_gastos if gasto):
            continue
        return {"texto": texto, "url": item.get("url")}
    return None


def horario_do_plano(calendario, aprendizado):
    """O horário só muda com prova; sem prova, mantém a janela do calendário."""
    janela = (calendario or {}).get("janela", {})
    melhor = (aprendizado or {}).get("melhor_hora")
    if melhor and (aprendizado or {}).get("confiavel"):
        return {"hora": melhor, "motivo": "medido com amostra suficiente",
                "amostra": (aprendizado or {}).get("amostra")}
    return {"hora": None, "motivo": "sem prova estatística: mantém a janela do calendário",
            "janela": [janela.get("inicio"), janela.get("fim")]}


def montar(agora=None):
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    placar = ler(PLACAR)
    desempenho = ler(DESEMPENHO)
    try:
        calendario = json.loads(ler(CALENDARIO) or "{}")
    except Exception:
        calendario = {}
    try:
        aprendizado = json.loads(ler(APRENDIZADO) or "{}")
    except Exception:
        aprendizado = {}

    riscos = metas_em_risco(placar)
    ruins = formatos_ruins(desempenho)
    # o relatório repete a tabela em vários dias (um bloco por data): conta uma vez só
    vistos, unicos = set(), []
    for r in ruins:
        if r["formato"] in vistos:
            continue
        vistos.add(r["formato"])
        unicos.append(r)
    ruins = unicos
    temas_gastos = [r["formato"] for r in ruins]
    tema = escolher_tema(temas_gastos=temas_gastos)

    alvo = riscos[0][0] if riscos else None
    plano = {
        "quando": agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta_em_risco": {"meta": alvo,
                          "falta": riscos[0][1] if riscos else None,
                          "por_dia": riscos[0][2] if riscos else None} if riscos else None,
        "ranking_de_risco": [{"meta": m, "falta": f, "por_dia": d} for m, f, d in riscos],
        "formatos_a_evitar": ruins,
        "tema_do_dia": tema,
        "horario": horario_do_plano(calendario, aprendizado),
        "_fonte": "placar-metas.md, desempenho.md, calendario.json, aprendizado.json",
        "_o_que_nao_sei": "não há pesquisa externa de tendência aqui: só dado medido da própria casa",
    }
    with open(PLANO, "w", encoding="utf-8") as f:
        json.dump(plano, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return plano


def main(argv):
    plano = montar()
    risco = plano["meta_em_risco"] or {}
    print("meta em risco: %s (falta %s · %s/dia)" % (risco.get("meta"), risco.get("falta"), risco.get("por_dia")))
    print("formatos a evitar: %s" % ", ".join(f["formato"] for f in plano["formatos_a_evitar"]) or "nenhum")
    print("tema do dia: %s" % ((plano["tema_do_dia"] or {}).get("texto", "(fila vazia)")[:80]))
    print("horário: %s" % plano["horario"]["motivo"])
    print("plano gravado em posts/plano-do-dia.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
