#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Roda TODAS as suítes de contrato da casa, uma atrás da outra, e prova que elas não sujam o repo.

POR QUE EXISTE (06/11/2026): o ciclo vinha rodando 21 suítes "de estimação" e chamando isso de
"tudo testado". O repositório tem 52. Quando rodei as 52 pela primeira vez, três defeitos
apareceram de uma vez:

  * quatro suítes ESCREVIAM nos arquivos da casa (posts/fila-tarefas.json, posts/memoria.json,
    posts/placar-metas.md, posts/pendencias-do-dono.*) — e duas delas reescreviam também o
    registro do itch, com "restaura no fim" que não restaura se o teste estourar no meio;
  * rodar em paralelo fazia essas quatro brigarem pelo mesmo arquivo, e o resultado de uma
    suíte dependia da sorte de quem leu primeiro (testes-publicacoes chegou a falhar 5 vezes
    sem nada de errado no produto);
  * duas suítes de vídeo estouravam com FileNotFoundError quando não havia ffmpeg, em vez de
    dizer "não dá para medir aqui".

Este runner roda em série, mede o repositório antes e depois de CADA suíte, e falha se qualquer
uma mexer em arquivo versionado. É a diferença entre "eu acho que está testado" e "está medido".

Uso:
    python3 tools/rodar-todas-as-suites.py            # tudo
    python3 tools/rodar-todas-as-suites.py -v         # mostra a saída das que falham
    python3 tools/rodar-todas-as-suites.py --so vídeo  # só as que casam com o filtro

Códigos de saída: 0 tudo passou · 1 alguma suíte falhou (ou sujou o repositório).
"""
import os
import re
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, "tools")
LIMITE = 900          # segundos por suíte; nenhuma passa de 12 s hoje, o limite é rede de segurança

OK, SKIP, FALHOU = "OK", "SKIP", "FALHOU"


def sujas():
    """Arquivos versionados que estão diferentes do commit (o que a suíte não pode mexer)."""
    saida = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ,
                           capture_output=True, text=True)
    if saida.returncode != 0:      # fora do git: não há o que comparar
        return set()
    return {linha[3:] for linha in saida.stdout.splitlines() if linha.strip()}


def restaurar(arquivos):
    """Devolve os arquivos ao estado do commit, para a próxima suíte não herdar a sujeira."""
    if not arquivos:
        return
    subprocess.run(["git", "checkout", "--"] + sorted(arquivos), cwd=RAIZ,
                   capture_output=True, text=True)


def contar(saida):
    """Último par n/m do texto — o resumo que cada suíte imprime no fim."""
    pares = re.findall(r"(\d+)/(\d+)", saida)
    if not pares:
        return None
    return int(pares[-1][0]), int(pares[-1][1])


def rodar(arquivo, filtro=None):
    nome = os.path.basename(arquivo)
    if filtro and filtro not in nome:
        return None
    antes = sujas()
    inicio = time.time()
    try:
        r = subprocess.run([sys.executable, arquivo], cwd=RAIZ, capture_output=True,
                           text=True, timeout=LIMITE)
        saida, rc, motivo = (r.stdout or "") + (r.stderr or ""), r.returncode, ""
    except subprocess.TimeoutExpired:
        saida, rc, motivo = "", 1, "passou de %d s e foi interrompido" % LIMITE
    durou = time.time() - inicio

    depois = sujas()
    sujou = sorted(depois - antes)
    restaurar(sujou)

    if rc == 0 and not sujou:
        estado = OK
    elif rc == 2 and not sujou:
        estado = SKIP
    else:
        estado = FALHOU
    if sujou:
        motivo = (motivo + "; " if motivo else "") + "escreveu no repositório: " + ", ".join(sujou)
    if rc not in (0, 2) and not motivo:
        # primeira linha que parece erro, para o resumo não ficar mudo
        for linha in reversed(saida.splitlines()):
            if linha.strip() and not linha.startswith(("OK ", "PASS", "✔")):
                motivo = linha.strip()[:120]
                break
    return {"nome": nome, "estado": estado, "rc": rc, "segundos": durou,
            "contagem": contar(saida), "motivo": motivo, "saida": saida, "sujou": sujou}


def main(argv):
    filtro = None
    if "--so" in argv:
        filtro = argv[argv.index("--so") + 1]
    verboso = "-v" in argv or "--verboso" in argv

    arquivos = sorted(os.path.join(PASTA, a) for a in os.listdir(PASTA)
                      if a.startswith("testes-") and a.endswith(".py"))
    estado_inicial = sujas()          # o que já estava diferente ANTES (edições em andamento)
    resultados = [r for r in (rodar(a, filtro) for a in arquivos) if r]

    print("\n%-32s %-6s %7s  %s" % ("suíte", "estado", "tempo", "contratos"))
    print("-" * 78)
    for r in resultados:
        c = "%d/%d" % r["contagem"] if r["contagem"] else "—"
        print("%-32s %-6s %6.1fs  %s" % (r["nome"][:-3], r["estado"], r["segundos"], c))
        if r["motivo"]:
            print("    ↳ " + r["motivo"])

    certos = sum(1 for r in resultados if r["estado"] == OK)
    puladas = [r for r in resultados if r["estado"] == SKIP]
    falhas = [r for r in resultados if r["estado"] == FALHOU]
    contratos = sum(r["contagem"][0] for r in resultados if r["contagem"])
    total_contratos = sum(r["contagem"][1] for r in resultados if r["contagem"])

    print("-" * 78)
    print("%d suítes · %d passaram · %d puladas por ambiente · %d falharam"
          % (len(resultados), certos, len(puladas), len(falhas)))
    print("contratos: %d/%d" % (contratos, total_contratos))
    for r in puladas:
        print("  pulada: %s — %s" % (r["nome"][:-3], r["motivo"] or "ambiente incompleto"))
    if falhas:
        print("\nFALHAS:")
        for r in falhas:
            print("  %s (código %d)" % (r["nome"][:-3], r["rc"]))
        if verboso:
            for r in falhas:
                print("\n=== %s ===\n%s" % (r["nome"][:-3], r["saida"][-2500:]))
        return 1
    novas = sorted(sujas() - estado_inicial)
    if novas:
        print("\naviso: as suítes deixaram arquivos diferentes do estado inicial: %s"
              % ", ".join(novas))
        return 1
    print("\nrepositório intacto: nenhuma suíte mexeu em arquivo versionado")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
