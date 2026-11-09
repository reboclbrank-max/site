#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria das agendas: todo cron do repositório, convertido para a hora de Brasília.

Virou biblioteca (07/11/2026): o `o-que-acontece.py` precisa das mesmas contas — quantos
disparos por dia e que horas são em Brasília — e duas contas iguais em dois arquivos é como a
casa já se contradisse antes. A saída da linha de comando continua a mesma.

CRON DE SEGURANÇA (08/11/2026): um workflow pode marcar um cron como `CRON_SEGURANCA` no
cabeçalho (antes de `permissions:`). Esse cron não é agenda de entrega — só existe para
reiniciar um fluxo se ele morrer. Ele não conta nos "disparos automáticos por dia" nem como
"fora da janela" (o horário de disparo não é quando o trabalho acontece).
"""

import glob
import os
import re

FUSO_HORAS = -3


def _expandir(campo, teto):
    """\"17\" -> [17] · \"*\" -> todas · \"*/20\" -> passo · \"12-23\" -> faixa · \"a-b/n\" -> faixa com passo."""
    saida = []
    for parte in campo.split(","):
        parte = parte.strip()
        if not parte:
            continue
        passo = 1
        if "/" in parte:
            parte, passo_txt = parte.split("/", 1)
            passo = int(passo_txt)
        if parte == "*":
            inicio, fim = 0, teto - 1
        elif "-" in parte:
            a, b = parte.split("-", 1)
            inicio, fim = int(a), int(b)
        else:
            inicio = fim = int(parte)
        saida += list(range(inicio, fim + 1, passo))
    return sorted({v % teto for v in saida})


def partes(cron):
    """Devolve (horas_utc, horas_brasilia, disparos_por_dia) de um cron de 5 campos."""
    campos = cron.split()
    minutos = _expandir(campos[0], 60)
    horas = _expandir(campos[1], 24)
    if campos[2] != "*" or campos[4] != "*":
        # cron com dia-do-mês ou dia-da-semana não é diário: a conta de "por dia" mentiria.
        por_dia = None
    else:
        por_dia = len(minutos) * len(horas)
    return horas, sorted({(h + FUSO_HORAS) % 24 for h in horas}), por_dia


def crons_do_repositorio(raiz="."):
    """Lista de (workflow, cron, seguranca) de todos os workflows, na ordem dos arquivos.

    Um cron é de "segurança" quando o cabeçalho do workflow (antes de permissions:)
    contém o marcador `CRON_SEGURANCA` na mesma seção do schedule.
    """
    achados = []
    for caminho in sorted(glob.glob(os.path.join(raiz, ".github/workflows/*.yml"))):
        texto = open(caminho, encoding="utf-8").read()
        cabeca = texto.split("permissions:")[0]
        tem_seguranca = "CRON_SEGURANCA" in cabeca
        for achado in re.finditer(r'^\s*-\s*cron:\s*"([^"]+)"', cabeca, re.M):
            achados.append((os.path.basename(caminho)[:-4], achado.group(1),
                            tem_seguranca))
    return achados


def auditar(raiz="."):
    """Uma linha por cron: nome, cron, horas de Brasília, horas fora da janela 9-22h, por dia."""
    linhas = []
    for nome, cron, seguranca in crons_do_repositorio(raiz):
        _, local, por_dia = partes(cron)
        fora = [h for h in local if not (9 <= h < 22)]
        linhas.append({"workflow": nome, "cron": cron, "brasilia": local,
                       "fora_da_janela": fora, "por_dia": por_dia,
                       "seguranca": seguranca})
    return linhas


def resumo(raiz="."):
    linhas = auditar(raiz)
    # Crons de segurança não são agenda de entrega: não contam nos disparos
    # automáticos por dia nem como "fora da janela".
    reais = [l for l in linhas if not l["seguranca"]]
    total = sum(l["por_dia"] or 0 for l in reais)
    fora = sum(1 for l in reais if l["fora_da_janela"])
    return {"crons": len(linhas), "disparos_por_dia": total, "crons_fora_da_janela": fora,
            "workflows_com_agenda": len({l["workflow"] for l in reais}),
            "workflows": len(glob.glob(os.path.join(raiz, ".github/workflows/*.yml")))}


def main():
    linhas = auditar()
    print("%-26s %-22s %s" % ("workflow", "cron (UTC)", "Brasília"))
    print("-" * 80)
    for l in linhas:
        if l["seguranca"]:
            marca = "  <-- CRON DE SEGURANCA (nao e agenda de entrega)"
        elif l["fora_da_janela"]:
            marca = "  <-- FORA DA JANELA: %s" % (l["fora_da_janela"],)
        else:
            marca = ""
        mostra = str(l["brasilia"]) if len(l["brasilia"]) < 14 else "todas as horas"
        print("%-26s %-22s %s%s" % (l["workflow"], l["cron"], mostra, marca))
    r = resumo()
    print("\nworkflows com agenda: %d de %d" % (r["workflows_com_agenda"], r["workflows"]))
    print("crons fora da janela 9-22h de Brasília: %d" % r["crons_fora_da_janela"])
    print("disparos automáticos por dia: %d" % r["disparos_por_dia"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
