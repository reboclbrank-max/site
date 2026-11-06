#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cena: cada vídeo da casa tem que ser uma partida DIFERENTE — e isso é medido, não prometido.

POR QUE EXISTE (06/11/2026). O dono olhou três vídeos no ar e disse o que o número já dizia:
"três vídeos dizem quase a mesma coisa". Verdade medida: as três gravações de 06/11 saíram da
mesma partida de 2 minutos (Dia 1, mesmas células, mesma semente), e o primeiro quadro dos três
era o mesmo. Trocar o título de uma gravação igual não é novidade — é molde com outra etiqueta.

O que este arquivo faz:
  1. ROTACIONA a estratégia da próxima gravação. A estratégia não é enfeite: ela muda o que
     aparece na tela — teto de semente (nabo/milho/trigo) e quantas células o agente cultiva.
  2. ASSINA a partida a partir do relatório do próprio gravador (plantadas, colhidas, bicos,
     sementes usadas, melhorias, verde final). Mesma assinatura = mesma partida.
  3. RECUSA registrar duas partidas com a mesma assinatura. Recusa aqui é a prova de que o
     vídeo novo não é o velho com outro texto.

O que NÃO faz: escrever título, gravar, publicar. Ele só garante que o material é outro.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "cenas.json")

# Cada estratégia é um viés DECLARADO do agente. O que muda na tela:
#   teto_semente: até qual semente o robô sobe (0 nabo, 1 milho, 2 trigo, 3 tomate...).
#                 Semente diferente = sprite diferente, tempo de crescimento diferente.
#   teto_celulas: em quantas células ele planta (campo cheio x campo pela metade).
ESTRATEGIAS = {
    "nabo":      {"teto_semente": 0, "teto_celulas": 9, "porque": "só nabo: ciclo curtíssimo, campo cheio, sem troca de semente"},
    "milho":     {"teto_semente": 1, "teto_celulas": 9, "porque": "sobe para milho e fica: ciclo médio, campo cheio"},
    "trigo":     {"teto_semente": 2, "teto_celulas": 4, "porque": "trigo em campo pequeno: poucas células, planta cara"},
    "cara":      {"teto_semente": 9, "teto_celulas": 9, "porque": "sem teto: persegue a semente mais cara que o caixa cobre"},
    "meia-cela": {"teto_semente": 1, "teto_celulas": 4, "porque": "milho em metade do campo: sobra tempo de bico"},
}

ORDEM = ("nabo", "milho", "trigo", "cara", "meia-cela")


def _quando():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def carregar(caminho=None):
    caminho = caminho or REGISTRO
    if not os.path.exists(caminho):
        return {"_o_que_e": "uma linha por partida gravada; assinatura igual = partida repetida",
                "partidas": []}
    with open(caminho, encoding="utf-8") as f:
        dado = json.load(f)
    if not isinstance(dado, dict) or not isinstance(dado.get("partidas"), list):
        return {"partidas": []}
    return dado


def gravar(registro, caminho=None):
    caminho = caminho or REGISTRO
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=1)
        f.write("\n")


def proxima(registro):
    """A estratégia da vez: a que faz mais tempo que não sai — e nunca a mesma de antes."""
    partidas = (registro or {}).get("partidas") or []
    ultima = partidas[-1].get("estrategia") if partidas else None
    ultimo_uso = {}
    for i, p in enumerate(partidas):
        ultimo_uso[p.get("estrategia")] = i
    candidatas = [e for e in ORDEM if e != ultima] or list(ORDEM)
    candidatas.sort(key=lambda e: ultimo_uso.get(e, -1))
    return candidatas[0]


def assinatura(relatorio, estrategia):
    """Impressão digital da PARTIDA (não do arquivo): o que o agente fez na tela."""
    r = relatorio or {}
    economia = r.get("economia") or {}
    sementes = economia.get("sementes") or []
    if isinstance(sementes, list):
        marcas = [str(s.get("para") if isinstance(s, dict) else s) for s in sementes]
    else:
        marcas = [str(sementes)]
    corpo = {
        "estrategia": estrategia,
        "plantadas": r.get("plantadas"),
        "colhidas": r.get("colhidas"),
        "bicos": r.get("bicos"),
        "sementes": marcas,
        "melhorias": economia.get("melhorias") or [],
        "verde_final": r.get("verde_final"),
    }
    bruto = json.dumps(corpo, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:12], corpo


def repetida(registro, assin):
    for p in (registro or {}).get("partidas") or []:
        if p.get("assinatura") == assin:
            return p
    return None


def registrar(relatorio, estrategia, registro=None, caminho=None, quando=None, forcar=False):
    """Grava a partida. Devolve (ok, motivo, assinatura). Duas iguais NÃO entram."""
    registro = registro if registro is not None else carregar(caminho)
    assin, corpo = assinatura(relatorio, estrategia)
    antes = repetida(registro, assin)
    if antes and not forcar:
        return (False, "partida repetida: mesma assinatura de %s (%s) — gravar de novo não é novidade"
                % (antes.get("quando"), antes.get("estrategia")), assin)
    registro.setdefault("partidas", []).append({
        "quando": quando or _quando(), "estrategia": estrategia, "assinatura": assin,
        "resumo": corpo,
    })
    if caminho is not None or registro is not None:
        gravar(registro, caminho)
    return (True, "partida nova: %s (%s)" % (assin, estrategia), assin)


def main(argv):
    ap = argparse.ArgumentParser(description="estratégia e assinatura das cenas gravadas")
    ap.add_argument("acao", choices=["proxima", "registrar", "lista"])
    ap.add_argument("--relatorio", help="arquivo *-decisoes.json do gravador")
    ap.add_argument("--estrategia")
    ap.add_argument("--registro", default=REGISTRO)
    a = ap.parse_args(argv[1:])
    registro = carregar(a.registro)
    if a.acao == "proxima":
        e = proxima(registro)
        print(e)
        print("# " + ESTRATEGIAS[e]["porque"], file=sys.stderr)
        return 0
    if a.acao == "lista":
        for p in registro.get("partidas") or []:
            print("%s  %-10s %s" % (p.get("quando"), p.get("estrategia"), p.get("assinatura")))
        return 0
    estrategia = a.estrategia or proxima(registro)
    if not a.relatorio or not os.path.exists(a.relatorio):
        print("✘ falta o relatório do gravador (--relatorio)", file=sys.stderr)
        return 2
    with open(a.relatorio, encoding="utf-8") as f:
        relatorio = json.load(f)
    ok, motivo, assin = registrar(relatorio, estrategia, registro, a.registro)
    print(("✓ " if ok else "✘ ") + motivo)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
