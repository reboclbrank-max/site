#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guarda da higiene dos workflows: 32 arquivos é gente demais para conferir no olho.

POR QUE EXISTE (30/10/2026): os defeitos que mais custaram nesta casa não estavam no jogo, e sim
no encanamento dos runs:
  * `git push` seco derrubou o PRANCHETA (run 41030633953) com o vídeo gravado e fora do repo;
  * três tentativas de push falhando e o run terminando VERDE (run 41090257198);
  * `metricas-youtube` fazia push seco — o mesmo defeito, esperando a vez;
  * dois workflows sem `timeout-minutes` (um run travado pode segurar a fila por horas);
  * vinte sem `concurrency` (dois runs do mesmo fluxo disputam o mesmo JSON e o mesmo push).

Este teste é estático e roda em segundos: ele não executa workflow nenhum.
"""
import glob
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, ".github", "workflows")

certos, falhas = [], []


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos.append(nome)
        print("OK  " + nome)
    else:
        falhas.append((nome, detalhe))
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe else ""))


def fontes():
    return {os.path.basename(f): open(f, encoding="utf-8").read()
            for f in sorted(glob.glob(os.path.join(PASTA, "*.yml")))}


def main():
    wfs = fontes()
    ok("os workflows foram lidos", len(wfs) >= 20, len(wfs))

    # 1. Push tem que sobreviver a outro commit no main e NUNCA falhar calado.
    secos = [n for n, s in wfs.items()
             if re.search(r"^\s*git push\s*$", s, re.M)]
    ok("nenhum workflow faz push seco", not secos, secos)
    sem_trava = [n for n, s in wfs.items()
                 if re.search(r"^\s*git push", s, re.M)
                 and "enviado=0" not in s]
    ok("todo workflow que empurra diz se o push entrou (e falha se não)", not sem_trava, sem_trava)
    sem_erro = [n for n, s in wfs.items()
                if re.search(r"^\s*git push", s, re.M) and "::error::" not in s]
    ok("todo workflow que empurra tem erro explícito no fim", not sem_erro, sem_erro)

    # 2. Trava de tempo: um run travado não pode segurar a fila.
    sem_timeout = [n for n, s in wfs.items() if "timeout-minutes" not in s]
    ok("todo workflow tem timeout-minutes", not sem_timeout, sem_timeout)

    # 3. Um run por fluxo por vez (dois ao mesmo tempo disputam o mesmo JSON e o mesmo push).
    sem_conc = [n for n, s in wfs.items() if "concurrency:" not in s]
    ok("todo workflow tem concurrency", not sem_conc, sem_conc)
    sem_grupo = [n for n, s in wfs.items()
                 if "concurrency:" in s and not re.search(r"concurrency:\s*\n\s*group:\s*\S+", s)]
    ok("o concurrency tem grupo nomeado", not sem_grupo, sem_grupo)

    # 4. Suíte órfã: teste que nada executa não protege nada.
    suites = [os.path.basename(f) for f in glob.glob(os.path.join(RAIZ, "tools", "testes-*"))
              if f.endswith((".py", ".js"))]
    juntos = "\n".join(wfs.values())
    orfas = [s for s in suites if s not in juntos]
    ok("toda suíte de teste é executada por algum workflow", not orfas, orfas)
    ok("há suíte suficiente para valer a pena o guarda", len(suites) >= 15, len(suites))

    # 5. Nada de segredo em texto claro no YAML (os valores vêm de secrets).
    vazados = []
    for nome, texto in wfs.items():
        for linha in texto.splitlines():
            if re.search(r"(API_KEY|TOKEN|COOKIE|SECRET)\s*[:=]\s*[A-Za-z0-9_\-]{20,}", linha):
                vazados.append("%s: %s" % (nome, linha.strip()[:60]))
    ok("nenhum segredo escrito no workflow", not vazados, vazados)

    # 6. Cron só em fluxo que faz sentido repetir (sondagem é de uma vez).
    cron_sondagem = [n for n, s in wfs.items()
                     if n.startswith(("sondar-", "provar-")) and re.search(r"^\s*-\s*cron:", s, re.M)]
    ok("sondagem não fica em cron", not cron_sondagem, cron_sondagem)

    print("\n%d/%d verificações de higiene de workflow passaram"
          % (len(certos), len(certos) + len(falhas)))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
