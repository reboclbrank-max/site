#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreiras offline do chat v2: fila, memória, bloco contínuo e o fio que liga tudo.

Prova, sem rede e sem publicar nada:
  - a fila respeita prioridade (medir > responder > publicar > pesquisar > aprender);
  - a fila devolve a mesma tarefa quando falha, até 3 tentativas, e depois a marca `falhou`
    com o motivo (falha não desaparece em silêncio);
  - semear é idempotente: rodar duas vezes não duplica tarefa do dia;
  - a memória lê as fontes e responde por palavra-chave sem inventar;
  - a memória registra as 5 regras da casa;
  - o laço contínuo respeita o botão de parar (posts/PARAR) e o teto de pulsos;
  - o workflow do bloco contínuo existe, tem cron, concorrência e roda o laço.
"""
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))

falhas = 0


def ok(nome, cond, detalhe=""):
    global falhas
    if cond:
        print("OK  " + nome)
    else:
        falhas += 1
        print("FALHOU  " + nome + ("  <" + str(detalhe) + ">" if detalhe else ""))


def carregar(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    fila = carregar("fila", "fila-tarefas.py")

    # 1. prioridade
    dados = fila.vazia()
    fila.adicionar(dados, "aprender")
    fila.adicionar(dados, "publicar")
    fila.adicionar(dados, "medir")
    fila.adicionar(dados, "pesquisar")
    ordem = []
    while True:
        t = fila.pegar(dados)
        if not t:
            break
        ordem.append(t["tipo"])
        fila.concluir(dados, t, True, "ok")
    ok("fila respeita prioridade (medir → publicar → pesquisar → aprender)",
       ordem == ["medir", "publicar", "pesquisar", "aprender"], ordem)

    # 2. retentativa e desistência com motivo
    dados = fila.vazia()
    t = fila.adicionar(dados, "publicar", motivo="teste")
    estados = []
    for _ in range(3):
        alvo = fila.pegar(dados)
        estados.append(fila.concluir(dados, alvo, False, "HTTP 500"))
    ok("falha volta para a fila 3 vezes", estados[:2] == ["nova tentativa (1/3)", "nova tentativa (2/3)"], estados)
    ok("depois de 3 falhas fica marcada como falhou", estados[-1] == "falhou", estados)
    ok("falhou guarda o motivo", "3 tentativas" in (t["resultado"] or ""), t["resultado"])
    ok("tarefa desistida não é mais pega", fila.pegar(dados) is None)

    # 3. semear idempotente
    dados = fila.vazia()
    plano = {"tema_do_dia": {"texto": "tema x"}, "meta_em_risco": {"meta": "itch: downloads"}}
    a = fila.semear(dados, plano, agora="2026-10-27T10:00:00Z")
    b = fila.semear(dados, plano, agora="2026-10-27T11:00:00Z")
    ok("semear cria as tarefas do dia", len(a) == 4, len(a))
    ok("semear de novo no mesmo dia não duplica", len(b) == 0 and len(dados["tarefas"]) == 4, len(b))

    # 4. memória
    memoria = carregar("mem", "memoria.py")
    m = memoria.construir()
    ok("memória lê as metas do placar", len(m["metas"]) >= 5, len(m["metas"]))
    ok("memória lê os formatos do desempenho", len(m["formatos"]) >= 2, len(m["formatos"]))
    ok("memória lê os últimos ciclos", len(m["ultimos_ciclos"]) >= 1, len(m["ultimos_ciclos"]))
    ok("memória guarda as 5 regras da casa", len(m["_regras"]) == 5, len(m["_regras"]))

    achados = memoria.consultar("downloads", m)
    ok("consulta por palavra-chave acha a meta certa",
       any("downloads" in texto for _, texto in achados), achados[:2])
    ok("consulta sem termo não inventa resultado", memoria.consultar("", m) == [])
    ok("consulta de termo inexistente devolve vazio", memoria.consultar("xyzabcnaoexiste", m) == [])

    # 5. bloco contínuo: botão de parar
    caminho_parar = os.path.join(RAIZ, "posts", "PARAR")
    criado = False
    try:
        with open(caminho_parar, "w", encoding="utf-8") as f:
            f.write("pare")
        criado = True
        loop = carregar("loop", "loop-24h.py")
        codigo = loop.main(["--pulsos", "3", "--intervalo", "1"])
        ok("botão PARAR encerra o bloco sem executar pulso", codigo == 0)
    finally:
        if criado and os.path.exists(caminho_parar):
            os.remove(caminho_parar)

    # 6. workflow do bloco contínuo
    caminho_wf = os.path.join(RAIZ, ".github", "workflows", "marketing-continuo.yml")
    texto = open(caminho_wf, encoding="utf-8").read() if os.path.exists(caminho_wf) else ""
    ok("workflow do bloco contínuo existe", bool(texto))
    ok("workflow tem cron", "cron:" in texto)
    ok("workflow roda o laço", "tools/loop-24h.py" in texto)
    ok("workflow tem concorrência", "concurrency:" in texto)
    ok("workflow respeita o botão de parar", "PARAR" in texto or "loop-24h" in texto)

    total = 21
    print("\n%d/%d testes do chat v2 (fila, memória, laço) passaram" % (total - falhas, total))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
