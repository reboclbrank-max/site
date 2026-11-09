#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da auditoria de agendas.

Tudo com arquivos de amostra em pasta temporária — nenhum contrato mexe na base da casa.
"""
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("auditar", os.path.join(RAIZ, "tools", "auditar-agendas.py"))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


def escreve(raiz, caminho, dados):
    destino = os.path.join(raiz, caminho)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as fp:
        fp.write(dados)


# ------------------------------------------------------------------ partes / _expandir
ok("cron simples vira uma hora", a.partes("0 17 * * *")[0] == [17], a.partes("0 17 * * *"))
ok("cron com faixa conta as horas", a.partes("*/20 12-23 * * *")[0] == [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
   a.partes("*/20 12-23 * * *"))
ok("cron com passo conta disparos", a.partes("*/20 0,6,7,12-23 * * *")[2] == 45,
   a.partes("*/20 0,6,7,12-23 * * *")[2])
ok("cron com dia da semana nao e diario", a.partes("0 17 * * 1")[2] is None,
   a.partes("0 17 * * 1")[2])

# ------------------------------------------------------------------ crons de seguranca
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, ".github", "workflows"), exist_ok=True)
    escreve(tmp, ".github/workflows/corrente.yml",
            "name: corrente\n"
            "on:\n"
            "  schedule:\n"
            "    # CRON_SEGURANCA: este cron nao e agenda de entrega\n"
            "    - cron: \"0 */3 * * *\"\n"
            "permissions:\n"
            "  contents: read\n")
    crons = a.crons_do_repositorio(tmp)
    ok("cron de seguranca eh marcado", len(crons) == 1 and crons[0][2] is True,
       crons)

with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, ".github", "workflows"), exist_ok=True)
    escreve(tmp, ".github/workflows/marketing.yml",
            "name: marketing\n"
            "on:\n"
            "  schedule:\n"
            "    - cron: \"*/20 12-23 * * *\"\n"
            "permissions:\n"
            "  contents: write\n")
    crons = a.crons_do_repositorio(tmp)
    ok("cron sem marcador nao e de seguranca", len(crons) == 1 and crons[0][2] is False,
       crons)

# ------------------------------------------------------------------ auditar
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, ".github", "workflows"), exist_ok=True)
    escreve(tmp, ".github/workflows/corrente.yml",
            "name: corrente\n"
            "on:\n"
            "  schedule:\n"
            "    # CRON_SEGURANCA: partida de seguranca\n"
            "    - cron: \"0 */3 * * *\"\n"
            "permissions:\n"
            "  contents: read\n")
    escreve(tmp, ".github/workflows/marketing.yml",
            "name: marketing\n"
            "on:\n"
            "  schedule:\n"
            "    - cron: \"*/20 12-23 * * *\"\n"
            "permissions:\n"
            "  contents: write\n")
    linhas = a.auditar(tmp)
    nomes = {l["workflow"] for l in linhas}
    ok("corrente aparece na auditoria", "corrente" in nomes, nomes)
    ok("marketing aparece na auditoria", "marketing" in nomes, nomes)
    corrente = next(l for l in linhas if l["workflow"] == "corrente")
    marketing = next(l for l in linhas if l["workflow"] == "marketing")
    ok("corrente tem seguranca=True", corrente["seguranca"] is True,
       corrente["seguranca"])
    ok("marketing tem seguranca=False", marketing["seguranca"] is False,
       marketing["seguranca"])

# ------------------------------------------------------------------ resumo
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, ".github", "workflows"), exist_ok=True)
    escreve(tmp, ".github/workflows/corrente.yml",
            "name: corrente\n"
            "on:\n"
            "  schedule:\n"
            "    # CRON_SEGURANCA: partida de seguranca\n"
            "    - cron: \"0 */3 * * *\"\n"
            "permissions:\n"
            "  contents: read\n")
    escreve(tmp, ".github/workflows/marketing.yml",
            "name: marketing\n"
            "on:\n"
            "  schedule:\n"
            "    - cron: \"*/20 12-23 * * *\"\n"
            "permissions:\n"
            "  contents: write\n")
    r = a.resumo(tmp)
    ok("resumo nao conta cron de seguranca nos disparos",
       r["disparos_por_dia"] == 36, r)  # marketing: 3 por hora * 12 horas = 36
    ok("resumo nao conta cron de seguranca como fora da janela",
       r["crons_fora_da_janela"] == 0, r)  # marketing 12-23 está na janela
    ok("resumo conta 1 workflow com agenda",
       r["workflows_com_agenda"] == 1, r)
    ok("resumo conta 2 crons no total (incluindo seguranca)",
       r["crons"] == 2, r)

print("\n%d/%d contratos da auditoria de agendas passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
