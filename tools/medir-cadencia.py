#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quanto o GitHub entrega de cada cron — o que a agenda promete contra o que acontece.

POR QUE EXISTE (07/11/2026): a casa documentava "45 pulsos por dia" (cron `*/20 0,6,7,12-23`)
e "72 pulsos por dia" no despertador. Medindo os runs de verdade na API: **2 a 5 por dia**. O
GitHub não garante agenda: cron de repositório é melhor esforço e, com cron de 20 em 20 minutos,
o agendador entrega uma fração. Todo número derivado disso — "o pulso decide de 20 em 20 minutos",
"a janela tem 39 pulsos" — estava errado por um fator de 10.

Este medidor não conserta nada: ele diz o número. Sem ele, a casa continua escrevendo agenda no
papel e vivendo outra na prática.

Uso:
    python3 tools/medir-cadencia.py            # mede pela API do GitHub (precisa de token)
    python3 tools/medir-cadencia.py --dias 7   # janela da amostra (padrão 7)
"""
import datetime
import json
import os
import sys
import urllib.request

import importlib.util

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "posts", "cadencia.json")
REPO = "reboclbrank-max/site"
CORRENTE_AGORA = None       # injetável nos testes: sem isso cada contrato dependeria do relógio


def _agendas():
    caminho = os.path.join(RAIZ, "tools", "auditar-agendas.py")
    spec = importlib.util.spec_from_file_location("auditar_agendas", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def esperado_por_dia(cron):
    """Quantos disparos o cron pede por dia (None quando o cron não é diário)."""
    return _agendas().partes(cron)[2]


def esperado_do_repositorio(raiz=RAIZ):
    """{workflow: (cron, esperado_por_dia)} de todos os que têm agenda diária."""
    agendas = _agendas()
    saida = {}
    for nome, cron in agendas.crons_do_repositorio(raiz):
        diario = esperado_por_dia(cron)
        if diario is None:
            continue
        # um workflow com mais de um cron soma: os dois disparam
        anterior = saida.get(nome)
        saida[nome] = (cron if not anterior else anterior[0] + " + " + cron,
                       diario + (anterior[1] if anterior else 0))
    return saida


def contar_por_dia(runs, hoje=None, dias=7):
    """Quantos runs AGENDADOS por dia, na janela dos últimos `dias` (o dia de hoje conta)."""
    hoje = hoje or datetime.date.today()
    limite = hoje - datetime.timedelta(days=dias - 1)
    por_dia = {}
    for run in runs:
        if (run.get("event") or "") != "schedule":
            continue
        quando = str(run.get("created_at") or "")[:10]
        try:
            dia = datetime.date.fromisoformat(quando)
        except ValueError:
            continue
        if dia < limite or dia > hoje:
            continue
        por_dia[dia.isoformat()] = por_dia.get(dia.isoformat(), 0) + 1
    return por_dia


def medido_por_dia(por_dia, dias=7):
    """Média diária medida na amostra. Dia sem run conta como zero — é isso que se quer saber."""
    if not dias:
        return 0.0
    return round(sum(por_dia.values()) / float(dias), 2)


def comparar(esperado, medido):
    """(entrega, frase): a diferença entre o que o cron pede e o que o GitHub entregou."""
    if not esperado:
        return None, "cron não é diário: não há esperado para comparar"
    entrega = round(100.0 * medido / esperado, 1)
    if entrega >= 90:
        frase = "o agendador entrega o que o cron pede"
    elif entrega >= 50:
        frase = "o agendador entrega %s%% do cron" % entrega
    else:
        frase = ("o agendador entrega %s%% do cron: o número do papel não é o número da vida"
                 % entrega)
    return entrega, frase


def ler_runs(workflow, token, repo=REPO, por_pagina=100):
    """Runs do workflow pela API. Erro de rede/rede levantado, nunca engolido."""
    url = ("https://api.github.com/repos/%s/actions/workflows/%s.yml/runs?per_page=%d"
           % (repo, workflow, por_pagina))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token,
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())["workflow_runs"]


def amostra_cobre(runs, hoje=None, dias=7, por_pagina=100):
    """A lista de runs permite afirmar "quantos por dia" na janela?

    Duas armadilhas, e as duas já enganaram a casa noutro lugar ("sem leitura" virando "zero"):
      - lista vazia: não é zero, é ausência de dado;
      - lista TRUNCADA pela paginação (100 runs) com o run mais antigo ainda dentro da janela:
        houve runs antes que não foram lidos — a conta sairia menor do que a verdade.

    Fora desses dois casos a conta fecha: se o histórico começa dentro da janela, os dias
    anteriores a ele realmente não tiveram run.
    """
    hoje = hoje or datetime.date.today()
    limite = hoje - datetime.timedelta(days=dias - 1)
    datas = []
    for run in runs:
        try:
            datas.append(datetime.date.fromisoformat(str(run.get("created_at") or "")[:10]))
        except ValueError:
            continue
    if not datas:
        return False
    if min(datas) <= limite:
        return True                      # a amostra alcança o começo da janela
    return len(runs) < por_pagina        # curta e completa: o histórico começa na janela


def _corrente():
    """As réguas da corrente (passo, horas de pulso, fuso) vêm do próprio `corrente.py`.

    Duas cópias do passo de 20 minutos seriam duas verdades: no dia em que uma mudasse, o
    medidor estaria medindo outra coisa que não a corrente.
    """
    caminho = os.path.join(RAIZ, "tools", "corrente.py")
    spec = importlib.util.spec_from_file_location("corrente_medida", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _instantes(runs):
    """created_at dos runs como datetime UTC, do mais velho para o mais novo."""
    achados = []
    for run in runs:
        texto = str(run.get("created_at") or "")
        if texto.endswith("Z"):
            texto = texto[:-1] + "+00:00"
        try:
            achados.append(datetime.datetime.fromisoformat(texto).astimezone(datetime.timezone.utc))
        except ValueError:
            continue
    return sorted(achados)


def ultimo_slot(agora, horas=None, passo=None):
    """O último horário em que a corrente DEVERIA ter disparado, até `agora` (inclusive).

    Se agora são 10h30 e o passo é de 20 minutos, o pulso devido é o de 10h20. Fora das horas
    permitidas o último slot pode estar ontem — e é isso mesmo: de madrugada não se exige pulso.
    """
    corrente = _corrente()
    horas = set(corrente.horas_de_pulso() if horas is None else horas)
    passo = passo or corrente.PASSO_MINUTOS
    local = agora.astimezone(corrente.FUSO).replace(second=0, microsecond=0)
    cand = local.replace(minute=local.minute - local.minute % passo)
    for _ in range(24 * 60 // passo + 1):
        if cand.hour in horas and cand <= local:
            return cand.astimezone(datetime.timezone.utc)
        cand -= datetime.timedelta(minutes=passo)
    return None


def _slots_perdidos(desde, ate, horas=None, passo=None, tolerancia=None):
    """Quantos pulsos DEVIDOS caíram entre dois instantes e não saíram.

    Conta em pulsos, não em minutos: "2 pulsos não saíram" é uma frase acionável; "47 minutos de
    silêncio" não diz quanta coisa deixou de rodar. A tolerância existe porque um run recém-
    disparado pode ainda não ter aparecido na lista.
    """
    corrente = _corrente()
    horas = set(corrente.horas_de_pulso() if horas is None else horas)
    passo = passo or corrente.PASSO_MINUTOS
    if tolerancia is None:
        tolerancia = datetime.timedelta(minutes=tolerancia_da_corrente(passo))
    cand, perdidos = desde + datetime.timedelta(minutes=passo), 0
    while cand < ate - tolerancia:
        if cand.astimezone(corrente.FUSO).hour in horas:
            perdidos += 1
        cand += datetime.timedelta(minutes=passo)
    return perdidos


def corrente_viva(runs_pulso, agora=None, tolerancia_min=10, horas=None, passo=None):
    """A corrente está entregando? Sem esta pergunta, a corrente vira a mentira seguinte.

    O cron falhava calado: 45 pedidos, 1,86 entregues, e a casa só descobriu medindo. Aqui a
    conta é a mesma dos buracos: entre o último pulso e agora, quantos pulsos DEVIDOS ficaram
    para trás. Zero é em dia; um já é atraso com número.
    """
    corrente = _corrente()
    passo = passo or corrente.PASSO_MINUTOS
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    instantes = _instantes(runs_pulso)
    slot = ultimo_slot(agora, horas=horas, passo=passo)
    dados = {"agora": agora.isoformat(), "ultimo_pulso": None, "idade_min": None,
             "slot_devido": slot.isoformat() if slot else None, "atraso_min": None,
             "pulsos_perdidos": None, "veredito": "não sei", "buracos": []}
    if not instantes:
        dados["veredito"] = "nenhum pulso lido: não afirmo"
        return dados
    ultimo = instantes[-1]
    dados["ultimo_pulso"] = ultimo.isoformat()
    dados["idade_min"] = round((agora - ultimo).total_seconds() / 60.0, 1)
    if slot is not None:
        dados["atraso_min"] = round((agora - slot).total_seconds() / 60.0, 1)
    dados["pulsos_perdidos"] = _slots_perdidos(ultimo, agora, horas=horas, passo=passo,
                                               tolerancia=datetime.timedelta(minutes=tolerancia_min))
    quando = lambda t: t.astimezone(corrente.FUSO).strftime("%d/%m %H:%M")
    if dados["pulsos_perdidos"] == 0:
        dados["veredito"] = "em dia (último pulso %s, há %.0f min)" % (quando(ultimo),
                                                                      dados["idade_min"])
    else:
        dados["veredito"] = "ATRASADA: %d pulso(s) não saíram desde %s (último há %.0f min)" % (
            dados["pulsos_perdidos"], quando(ultimo), dados["idade_min"])
    dados["buracos"] = buracos(instantes, agora=agora, horas=horas, passo=passo)
    return dados


def buracos(instantes, agora=None, horas=None, passo=None, horas_24=24):
    """Intervalos em que a corrente deveria ter pulsado e não pulsou, nas últimas 24 horas."""
    corrente = _corrente()
    passo = passo or corrente.PASSO_MINUTOS
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    desde = agora - datetime.timedelta(hours=horas_24)
    achados = [i for i in instantes if desde <= i <= agora]
    resultado = []
    for antes, depois in zip(achados, achados[1:] + [agora]):
        perdidos = _slots_perdidos(antes, depois, horas=horas, passo=passo)
        if perdidos >= 2:      # um pulso perdido isolado acontece; dois é buraco
            resultado.append({"desde": antes.isoformat(), "ate": depois.isoformat(),
                              "pulsos_perdidos": perdidos})
    return resultado


def tolerancia_da_corrente(passo):
    """Um run pode demorar para nascer; meio passo de folga antes de chamar de perdido."""
    return max(1, passo // 2)


def medir(token=None, dias=7, hoje=None, raiz=RAIZ):
    token = token or os.environ.get("GHPAT") or os.environ.get("GITHUB_TOKEN")
    esperado = esperado_do_repositorio(raiz)
    linhas, erros, lidos = [], [], {}
    for nome, (cron, pede) in sorted(esperado.items()):
        if not token:
            erros.append("%s: sem token" % nome)
            continue
        try:
            runs = ler_runs(nome, token)
        except Exception as erro:  # noqa: BLE001
            erros.append("%s: %s" % (nome, str(erro)[:80]))
            continue
        lidos[nome] = runs
        dias_map = contar_por_dia(runs, hoje=hoje, dias=dias)
        medido = medido_por_dia(dias_map, dias)
        entrega, frase = comparar(pede, medido)
        cobre = amostra_cobre(runs, hoje=hoje, dias=dias)
        if not cobre:
            # LISTA CURTA NÃO É ZERO: se o histórico lido nem alcança a janela, o honesto é dizer
            # "não sei" — foi assim que a casa confundiu "sem leitura" com "0 seguidores" antes.
            entrega, frase = None, ("amostra não cobre a janela (%d run(s) lido(s)): não afirmo "
                                    "quantos por dia" % len(runs))
        linhas.append({"workflow": nome, "cron": cron, "esperado_por_dia": pede,
                       "medido_por_dia": None if not cobre else medido, "entrega_pct": entrega,
                       "frase": frase, "por_dia": dias_map, "amostra_cobre": cobre,
                       "runs_lidos": len(runs)})
    total_esperado = sum(l["esperado_por_dia"] for l in linhas)
    total_medido = round(sum(l["medido_por_dia"] or 0 for l in linhas), 2)
    dados = {"medido_em": (hoje or datetime.date.today()).isoformat(),
             "janela_dias": dias, "linhas": linhas, "erros": erros,
             "total_esperado_por_dia": total_esperado, "total_medido_por_dia": total_medido}
    # A CORRENTE TAMBÉM PRESTA CONTAS (07/11/2026): trocar o cron pela corrente sem medir a
    # corrente seria repetir o erro com outro nome. Só mede se o pulso foi lido.
    if lidos.get("marketing-24h"):
        dados["corrente"] = corrente_viva(lidos["marketing-24h"], agora=CORRENTE_AGORA
                                          if CORRENTE_AGORA else None)
    return dados


def gravar(dados, caminho=SAIDA):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return caminho


def main(argv):
    dias = 7
    if "--dias" in argv:
        try:
            dias = int(argv[argv.index("--dias") + 1])
        except (IndexError, ValueError):
            print("uso: medir-cadencia.py [--dias N]")
            return 2
    dados = medir(dias=dias)
    if not dados["linhas"]:
        print("não deu para medir: " + ("; ".join(dados["erros"]) or "nenhum workflow com agenda"))
        return 3
    print("%-24s %-6s %-9s %-9s %s" % ("workflow", "pede", "entregou", "entrega", "leitura"))
    for l in dados["linhas"]:
        print("%-24s %-6s %-9s %-9s %s" % (
            l["workflow"], l["esperado_por_dia"],
            "?" if l["medido_por_dia"] is None else l["medido_por_dia"],
            "?" if l["entrega_pct"] is None else "%s%%" % l["entrega_pct"], l["frase"]))
    print("\ntotal: o cron pede %s disparos/dia · o GitHub entregou %s/dia (janela de %d dia(s))"
          % (dados["total_esperado_por_dia"], dados["total_medido_por_dia"], dias))
    if dados.get("corrente"):
        print("corrente: " + dados["corrente"]["veredito"]
              + (" · %d buraco(s) nas últimas 24h" % len(dados["corrente"]["buracos"])
                 if dados["corrente"]["buracos"] else ""))
    if dados["erros"]:
        print("sem medida em: " + "; ".join(dados["erros"]))
    print("gravado em " + os.path.relpath(gravar(dados), RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
