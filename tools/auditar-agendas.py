#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria das agendas: todo cron do repositório, convertido para a hora de Brasília."""
import datetime
import glob
import os
import re

FUSO = datetime.timezone(datetime.timedelta(hours=-3))
linhas = []
for caminho in sorted(glob.glob(".github/workflows/*.yml")):
    texto = open(caminho, encoding="utf-8").read()
    cabeca = texto.split("permissions:")[0]
    for achado in re.finditer(r'^\s*-\s*cron:\s*"([^"]+)"', cabeca, re.M):
        cron = achado.group(1)
        campo_horas = cron.split()[1]
        utc = []
        for parte in campo_horas.split(","):
            if parte.isdigit():
                utc.append(int(parte))
            elif parte == "*":
                utc += list(range(24))
            elif "/" in parte and parte.split("/")[0].isdigit():
                inicio, passo = parte.split("/")
                utc += list(range(int(inicio), 24, int(passo)))
        local = sorted({(h - 3) % 24 for h in utc})
        fora = [h for h in local if not (9 <= h < 22)]
        linhas.append((os.path.basename(caminho)[:-4], cron, local, fora))

print("%-26s %-22s %s" % ("workflow", "cron (UTC)", "Brasília"))
print("-" * 80)
for nome, cron, local, fora in linhas:
    marca = "  <-- FORA DA JANELA: %s" % (fora,) if fora else ""
    mostra = str(local) if len(local) < 14 else "todas as horas"
    print("%-26s %-22s %s%s" % (nome, cron, mostra, marca))

com_agenda = sorted({n for n, _, _, _ in linhas})
print("\nworkflows com agenda: %d de %d" % (len(com_agenda), len(glob.glob('.github/workflows/*.yml'))))
print("crons fora da janela 9-22h de Brasília: %d" % len([1 for _, _, _, f in linhas if f]))
