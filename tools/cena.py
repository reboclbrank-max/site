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

# ---- PRANCHETA: o segundo jogo da casa, com as suas próprias estratégias ------------------
# Até 06/11/2026 o PRANCHETA era gravado sempre pelo mesmo caminho (menu → carreira → clube →
# staff → prancheta → partida, sempre com a instrução padrão e ritmo normal). O gravador roda
# 3x/dia desde 27/10 e o vídeo saía igual todo dia: gravar outro jogo não é, por si só, gravar
# outra cena. Estas estratégias usam botões que o jogo JÁ tem (lidos em 27/10/2026, 1280x720):
#   instrucao: "+ Pressionar" (110,608) ou "Seguir sem mexer" (636,573)
#   ritmo:     "Rápida" (700,685)
#   pular_fim: "Pular para o fim" (900,705) — muda o que a gravação mostra da partida
ESTRATEGIAS_PRANCHETA = {
    "pressao_rapida": {
        "instrucao": "pressionar", "ritmo": "rapida", "pular_fim": True,
        "porque": "instrução de pressão e velocidade rápida, cortando para o fim do jogo"},
    "posse_normal": {
        "instrucao": "seguir", "ritmo": "normal", "pular_fim": False,
        "porque": "sem instrução, ritmo normal: a partida inteira no tempo do jogo"},
    "contra_ataque": {
        "instrucao": "seguir", "ritmo": "rapida", "pular_fim": True,
        "porque": "sem instrução e velocidade rápida, mostrando a virada em vez do plano"},
}
ORDEM_PRANCHETA = ("pressao_rapida", "posse_normal", "contra_ataque")

# jogo -> (estratégias, ordem)
JOGOS = {
    "ceifalume": (ESTRATEGIAS, ORDEM),
    "prancheta": (ESTRATEGIAS_PRANCHETA, ORDEM_PRANCHETA),
}


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


def proxima(registro, jogo="ceifalume"):
    """A estratégia da vez: a que faz mais tempo que não sai — e nunca a mesma de antes."""
    estrategias, ordem = JOGOS.get(jogo, (ESTRATEGIAS, ORDEM))
    partidas = [p for p in ((registro or {}).get("partidas") or [])
                if (p.get("jogo") or "ceifalume") == jogo]
    ultima = partidas[-1].get("estrategia") if partidas else None
    ultimo_uso = {}
    for i, p in enumerate(partidas):
        ultimo_uso[p.get("estrategia")] = i
    candidatas = [e for e in ordem if e != ultima] or list(ordem)
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


def assinatura_prancheta(relatorio, estrategia):
    """Impressão digital de uma gravação do PRANCHETA: a sequência de decisões do gravador.

    O relatório (`prancheta-cru-decisoes.json`) traz cada passo com tempo, motivo e ação. Duas
    gravações que atravessam o jogo igual, com a mesma estratégia, têm a mesma assinatura — e a
    segunda não entra no registro. Se o tempo de cada passo mudasse a assinatura, toda gravação
    seria "nova" e a régua não valeria nada: por isso o tempo entra arredondado a 1 s.
    """
    r = relatorio or {}
    passos = r.get("decisoes") or r.get("passos") or []
    marcas = []
    for p in passos:
        if isinstance(p, dict):
            marcas.append([str(p.get("acao") or p.get("motivo") or ""),
                           round(float(p.get("t") or 0), 0)])
        else:
            marcas.append([str(p), 0])
    corpo = {
        "jogo": r.get("jogo") or "prancheta",
        "estrategia": estrategia,
        "passos": marcas,
        "toques_partida": r.get("toques_partida"),
        "passos_confirmados": r.get("passos_confirmados"),
    }
    bruto = json.dumps(corpo, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:12], corpo


def registrar(relatorio, estrategia, registro=None, caminho=None, quando=None, forcar=False,
              jogo="ceifalume"):
    """Grava a partida. Devolve (ok, motivo, assinatura). Duas iguais NÃO entram."""
    registro = registro if registro is not None else carregar(caminho)
    if jogo == "prancheta":
        assin, corpo = assinatura_prancheta(relatorio, estrategia)
    else:
        assin, corpo = assinatura(relatorio, estrategia)
    antes = repetida(registro, assin)
    if antes and not forcar:
        return (False, "partida repetida: mesma assinatura de %s (%s) — gravar de novo não é novidade"
                % (antes.get("quando"), antes.get("estrategia")), assin)
    linha = {
        "quando": quando or _quando(), "estrategia": estrategia, "assinatura": assin,
        "resumo": corpo,
    }
    if jogo != "ceifalume":
        linha["jogo"] = jogo
    registro.setdefault("partidas", []).append(linha)
    # SÓ grava quando o chamador diz ONDE: escrever no registro da casa por omissão já custou
    # caro — um teste que rodava "só na memória" escreveu 8 partidas de mentira em
    # posts/cenas.json, e a rotação passou a escolher a cena errada em produção.
    if caminho is not None:
        gravar(registro, caminho)
    return (True, "partida nova: %s (%s)" % (assin, estrategia), assin)


def main(argv):
    ap = argparse.ArgumentParser(description="estratégia e assinatura das cenas gravadas")
    ap.add_argument("acao", choices=["proxima", "registrar", "lista"])
    ap.add_argument("--relatorio", help="arquivo *-decisoes.json do gravador")
    ap.add_argument("--estrategia")
    ap.add_argument("--jogo", default="ceifalume", choices=sorted(JOGOS))
    ap.add_argument("--registro", default=REGISTRO)
    a = ap.parse_args(argv[1:])
    registro = carregar(a.registro)
    if a.acao == "proxima":
        e = proxima(registro, a.jogo)
        print(e)
        print("# " + JOGOS.get(a.jogo, (ESTRATEGIAS, ORDEM))[0][e]["porque"], file=sys.stderr)
        return 0
    if a.acao == "lista":
        for p in registro.get("partidas") or []:
            print("%s  %-10s %s" % (p.get("quando"), p.get("estrategia"), p.get("assinatura")))
        return 0
    estrategia = a.estrategia or proxima(registro, a.jogo)
    if not a.relatorio or not os.path.exists(a.relatorio):
        print("✘ falta o relatório do gravador (--relatorio)", file=sys.stderr)
        return 2
    with open(a.relatorio, encoding="utf-8") as f:
        relatorio = json.load(f)
    ok, motivo, assin = registrar(relatorio, estrategia, registro, a.registro, jogo=a.jogo)
    print(("✓ " if ok else "✘ ") + motivo)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
