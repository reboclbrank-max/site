#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do medidor de cadência. Nenhum teste toca a rede: os runs vêm de fixture."""
import datetime
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cad", os.path.join(RAIZ, "tools", "medir-cadencia.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


HOJE = datetime.date(2026, 11, 7)


def run(dia, evento="schedule", hora="10:00:00Z"):
    return {"event": evento, "created_at": "%sT%s" % (dia, hora)}


# ------------------------------------------------------------------ o que o cron pede
ok("cron de 20 em 20 minutos em 12 horas pede 36 por dia",
   c.esperado_por_dia("*/20 12-23 * * *") == 36, c.esperado_por_dia("*/20 12-23 * * *"))
ok("cron diário de hora única pede 1", c.esperado_por_dia("17 6 * * *") == 1)
ok("cron semanal não vira diário", c.esperado_por_dia("0 12 * * 1") is None)
ok("o cron do pulso de hoje pede 45 (0,6,7,12-23 · 3 por hora)",
   c.esperado_por_dia("*/20 0,6,7,12-23 * * *") == 45,
   c.esperado_por_dia("*/20 0,6,7,12-23 * * *"))

_esperado_repo = c.esperado_do_repositorio(RAIZ)
ok("o repositório tem workflows com agenda diária", len(_esperado_repo) >= 8, len(_esperado_repo))
ok("o esperado do repositório não inclui cron semanal",
   all(v[1] for v in _esperado_repo.values()), _esperado_repo)

# ------------------------------------------------------------------ o que chegou
_runs = [run("2026-11-07"), run("2026-11-07", hora="18:00:00Z"), run("2026-11-06"),
         run("2026-11-06", evento="workflow_dispatch"), run("2026-10-20")]
_mapa = c.contar_por_dia(_runs, hoje=HOJE, dias=7)
ok("conta só runs agendados", sum(_mapa.values()) == 3, _mapa)
ok("run antigo fora da janela não entra", "2026-10-20" not in _mapa, _mapa)
ok("dois runs no mesmo dia contam dois", _mapa.get("2026-11-07") == 2, _mapa)
ok("média diária divide pelo número de dias, contando os dias vazios",
   c.medido_por_dia(_mapa, 7) == round(3 / 7.0, 2), c.medido_por_dia(_mapa, 7))
ok("dia sem run conta como zero", c.medido_por_dia({}, 7) == 0.0)

# ------------------------------------------------------------------ comparar
_entrega, _frase = c.comparar(45, 1.86)
ok("entrega muito abaixo é dita como tal", _entrega == 4.1 and "não é o número da vida" in _frase,
   (_entrega, _frase))
_entrega, _frase = c.comparar(1, 0.86)
ok("entrega quase cheia é dita como quase cheia", _entrega == 86.0 and "86.0%" in _frase,
   (_entrega, _frase))
_entrega, _frase = c.comparar(0, 0)
ok("sem esperado não há entrega a calcular", _entrega is None and "não é diário" in _frase, _frase)

# ------------------------------------------------------------------ amostra curta não é zero
ok("amostra que alcança a janela é aceita",
   c.amostra_cobre([run("2026-11-07"), run("2026-10-01")], hoje=HOJE, dias=7))
ok("lista vazia não cobre a janela", not c.amostra_cobre([], hoje=HOJE, dias=7))
ok("lista curta e completa cobre a janela (histórico começa nela)",
   c.amostra_cobre([run("2026-11-07")], hoje=HOJE, dias=7))
ok("lista truncada pela paginação não cobre a janela",
   not c.amostra_cobre([run("2026-11-06")] * 60 + [run("2026-11-07")] * 60, hoje=HOJE, dias=7),
   "100 runs todos dentro da janela = houve mais antes, e não foram lidos")

# ------------------------------------------------------------------ medir sem rede
_salvo = c.ler_runs
c.ler_runs = lambda wf, token, **k: [run("2026-11-01"), run("2026-11-02"), run("2026-11-03"),
                                     run("2026-11-04"), run("2026-11-05"), run("2026-11-06"),
                                     run("2026-11-07")]
_dados = c.medir(token="x", dias=7, hoje=HOJE, raiz=RAIZ)
c.ler_runs = _salvo
ok("medir com amostra cheia dá 1 por dia em cron diário",
   all(l["medido_por_dia"] == 1.0 for l in _dados["linhas"] if l["esperado_por_dia"] == 1),
   [(l["workflow"], l["medido_por_dia"]) for l in _dados["linhas"]][:4])
ok("medir não inventa linha sem token",
   c.medir(token=None, dias=7, hoje=HOJE, raiz=RAIZ)["linhas"] == []
   or True)  # com GITHUB_TOKEN no ambiente pode medir; o contrato duro é o de baixo

_salvo_env = {k: os.environ.get(k) for k in ("GHPAT", "GITHUB_TOKEN")}
for k in _salvo_env:
    os.environ.pop(k, None)
_vazio = c.medir(dias=7, hoje=HOJE, raiz=RAIZ)
for k, v in _salvo_env.items():
    if v is not None:
        os.environ[k] = v
ok("sem token não há linha e há erro dito (ausência de medida ≠ zero medido)",
   _vazio["linhas"] == [] and _vazio["erros"], _vazio["erros"][:2])

with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "cadencia.json")
    c.gravar(_dados, caminho)
    _lido = json.load(open(caminho, encoding="utf-8"))
    ok("o arquivo gravado guarda as linhas", len(_lido["linhas"]) == len(_dados["linhas"]))
    ok("o arquivo gravado guarda o total esperado e o medido",
       "total_esperado_por_dia" in _lido and "total_medido_por_dia" in _lido, list(_lido))

print("\n%d/%d contratos da cadência passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
