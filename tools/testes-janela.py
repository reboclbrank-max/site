#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira offline da janela de publicação (posts/calendario.json).

Prova, sem rede e sem tocar no postador de verdade:
  - 09h local abre, 03h local fecha, 22h local fecha (fim é exclusivo);
  - a conversão de UTC para America/Fortaleza está certa (UTC 12 = 09 local);
  - arquivo ausente NÃO trava a casa (volta ao comportamento antigo, 24h);
  - teto diário conta os ciclos do dia local, e não os de ontem;
  - o main do postador realmente consulta a janela antes de publicar.
"""
import datetime
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))

import postador  # noqa: E402

UTC = datetime.timezone.utc
falhas = 0


def ok(nome, cond, detalhe=""):
    global falhas
    if cond:
        print("OK  " + nome)
    else:
        falhas += 1
        print("FALHOU  " + nome + ("  <" + str(detalhe) + ">" if detalhe else ""))


CAL = {
    "janela": {"inicio": 9, "fim": 22, "fuso": "America/Fortaleza"},
    "teto_diario": 5,
}


def em_utc(hora_local_desejada, dia=26):
    """Data UTC que corresponde àquela hora em Brasília (UTC-3)."""
    return datetime.datetime(2026, 10, dia, (hora_local_desejada + 3) % 24, 0, tzinfo=UTC)


def main():
    # dentro / fora da janela
    for hora, esperado in [(9, True), (12, True), (15, True), (21, True),
                           (8, False), (22, False), (0, False), (3, False)]:
        pode, motivo = postador.dentro_da_janela(em_utc(hora), CAL)
        ok("hora local %02dh -> %s" % (hora, "abre" if esperado else "fecha"), pode == esperado, motivo)

    # conversão de fuso
    local = postador.hora_local(datetime.datetime(2026, 10, 26, 12, 0, tzinfo=UTC))
    ok("UTC 12h vira 09h local", local.hour == 9, local.strftime("%H:%M %Z"))
    local = postador.hora_local(datetime.datetime(2026, 10, 27, 2, 0, tzinfo=UTC))
    ok("UTC 02h vira 23h local", local.hour == 23, local.strftime("%H:%M %Z"))

    # sem calendário, não bloqueia
    pode, motivo = postador.dentro_da_janela(em_utc(3), None) if False else postador.dentro_da_janela(em_utc(3), {})
    ok("sem calendário não bloqueia", pode is True, motivo)

    # teto diário
    import tempfile
    with tempfile.TemporaryDirectory() as pasta:
        log = os.path.join(pasta, "log.md")
        hoje = postador.hora_local(em_utc(10), CAL["janela"]["fuso"]).strftime("%d/%m/%Y")
        with open(log, "w", encoding="utf-8") as f:
            f.write("## %s 12:00 UTC\n| canal | resultado |\n" % hoje)
            f.write("## %s 15:00 UTC\n| canal | resultado |\n" % hoje)
            f.write("## 25/10/2026 21:00 UTC\n| canal | resultado |\n")
        ok("conta só os ciclos de hoje", postador.ciclos_hoje(em_utc(18), log, CAL) == 2,
           postador.ciclos_hoje(em_utc(18), log, CAL))

        cal_teto = dict(CAL, teto_diario=2)
        pode, motivo = postador.pode_publicar_agora(em_utc(18), cal_teto, log)
        ok("teto atingido bloqueia", pode is False and "teto" in motivo, motivo)

        cal_folga = dict(CAL, teto_diario=5)
        pode, motivo = postador.pode_publicar_agora(em_utc(18), cal_folga, log)
        ok("com folga libera", pode is True, motivo)

        pode, motivo = postador.pode_publicar_agora(em_utc(3), cal_folga, log)
        ok("de madrugada bloqueia mesmo com folga", pode is False and "janela" in motivo, motivo)

    # o calendário publicado é válido e coerente
    with open(os.path.join(RAIZ, "posts/calendario.json"), encoding="utf-8") as f:
        real = json.load(f)
    j = real["janela"]
    ok("calendário real: janela válida", 0 <= j["inicio"] < j["fim"] <= 24, j)
    ok("calendário real: declara o que não sabe", bool(real.get("_o_que_nao_sei")))
    ok("calendário real: devlog tem gatilho", bool(real.get("_devlog", {}).get("gatilho")))

    # o main consulta a janela
    fonte = open(os.path.join(RAIZ, "tools/postador.py"), encoding="utf-8").read()
    ok("o main consulta pode_publicar_agora", "pode_publicar_agora()" in fonte)
    ok("fora da janela o ciclo para antes de publicar",
       fonte.index("pode_publicar_agora()") < fonte.index("fila = json.load(open(\"posts/fila.json\"))"))

    total = 20
    print("\n%d/%d testes da janela passaram" % (total - falhas, total))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
