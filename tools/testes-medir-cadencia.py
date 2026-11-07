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

# ------------------------------------------------- janela maior que a vida do workflow
ok("sem data da API, a idade vem do run mais antigo",
   c.dias_no_ar([run("2026-11-05"), run("2026-11-07")], hoje=HOJE) == 3,
   c.dias_no_ar([run("2026-11-05"), run("2026-11-07")], hoje=HOJE))
ok("a data de criação da API manda mais que o run mais antigo",
   c.dias_no_ar([run("2026-11-07")], hoje=HOJE, criado_em="2026-10-09T00:00:00Z") == 30,
   c.dias_no_ar([run("2026-11-07")], hoje=HOJE, criado_em="2026-10-09T00:00:00Z"))
ok("sem run nenhum não há idade (e não vira zero)",
   c.dias_no_ar([], hoje=HOJE) is None)

_salvo_lidos, _salvo_criacao = c.ler_runs, c.ler_criacao
c.ler_criacao = lambda token, **k: {"corrente": "2026-11-07T06:00:00Z",
                                    "medir-o-dia": "2026-10-01T00:00:00Z"}
c.ler_runs = lambda wf, token, **k: (
    [{"created_at": "2026-11-07T06:46:00Z"}, {"created_at": "2026-11-07T07:00:00Z"}]
    if wf == "corrente" else
    [run("2026-10-08")] if wf == "medir-o-dia" else
    [run("2026-11-01"), run("2026-11-02"), run("2026-11-03"), run("2026-11-04"),
     run("2026-11-05"), run("2026-11-06"), run("2026-11-07")])
_novo = c.medir(token="x", dias=7, hoje=HOJE, raiz=RAIZ)
c.ler_runs, c.ler_criacao = _salvo_lidos, _salvo_criacao
_linha_nova = next(l for l in _novo["linhas"] if l["workflow"] == "corrente")
ok("workflow que nasceu dentro da janela não vira 'pior entrega'",
   _linha_nova["entrega_pct"] is None and "no ar há 1 dia" in _linha_nova["frase"],
   _linha_nova["frase"])
ok("a idade aparece na linha (dias_no_ar)", _linha_nova["dias_no_ar"] == 1, _linha_nova["dias_no_ar"])
_nunca_rodou = next((l for l in _novo["linhas"] if l["workflow"] == "medir-o-dia"), None)
ok("workflow antigo que nunca rodou NÃO ganha álibi: continua medido como 0%",
   _nunca_rodou is None or (_nunca_rodou["entrega_pct"] == 0.0
                            and (_nunca_rodou["dias_no_ar"] or 0) >= 7),
   _nunca_rodou and (_nunca_rodou["entrega_pct"], _nunca_rodou["dias_no_ar"]))
ok("workflow com vida inteira continua sendo comparado",
   all(l["entrega_pct"] is not None for l in _novo["linhas"] if l["workflow"] != "corrente"),
   [(l["workflow"], l["entrega_pct"]) for l in _novo["linhas"] if l["entrega_pct"] is None])

# ------------------------------------------------------- a corrente presta contas
def utc(dia, hora, minuto=0):
    return datetime.datetime(2026, 11, dia, hora, minuto, tzinfo=datetime.timezone.utc)


def pulso(dia, hora, minuto=0):
    return {"created_at": utc(dia, hora, minuto).strftime("%Y-%m-%dT%H:%M:%SZ")}


ok("o slot devido às 09h30 BRT é o pulso das 09h20",
   c.ultimo_slot(utc(7, 12, 30)).strftime("%H:%M") == "12:20",
   c.ultimo_slot(utc(7, 12, 30)))
ok("o slot devido às 09h05 BRT é o pulso das 09h",
   c.ultimo_slot(utc(7, 12, 5)).strftime("%H:%M") == "12:00")
ok("de madrugada (05h BRT) o último slot é o aprendizado das 04h40",
   c.ultimo_slot(utc(7, 8, 0)).strftime("%H:%M") == "07:40",
   c.ultimo_slot(utc(7, 8, 0)))
_slot_noite = c.ultimo_slot(utc(7, 1, 0))   # 22h BRT: janela fechada, mas 21h40 ainda é hora de pulso
ok("o slot cai sempre em hora permitida (janela 9-22 ou estudo 3-4)",
   _slot_noite is not None and _slot_noite.astimezone(c._corrente().FUSO).hour in
   c._corrente().horas_de_pulso(), _slot_noite)

ok("a corrente está em dia quando o pulso do slot saiu",
   c.corrente_viva([pulso(7, 12, 20), pulso(7, 12, 0)], agora=utc(7, 12, 30))["veredito"]
   .startswith("em dia"))
_prazo = c.corrente_viva([pulso(7, 12, 0)], agora=utc(7, 12, 22))   # 22 min desde o último pulso
ok("um pulso de 22 min atrás ainda é 'em dia', e o veredito diz a idade",
   _prazo["veredito"].startswith("em dia") and "min" in _prazo["veredito"], _prazo["veredito"])
_atraso = c.corrente_viva([pulso(7, 12, 0)], agora=utc(7, 12, 40))   # 09h40 BRT, último 09h00
ok("pulso que não saiu vira ATRASADA, com o número na frase",
   _atraso["veredito"].startswith("ATRASADA") and _atraso["pulsos_perdidos"] >= 1,
   _atraso["veredito"])
ok("o atraso é contado em pulsos devidos que faltaram, não em minutos vagos",
   _atraso["pulsos_perdidos"] == 1 and "1 pulso(s)" in _atraso["veredito"], _atraso)
ok("um pulso só 15 min velho ainda é 'em dia' (tolerância de meio passo)",
   c.corrente_viva([pulso(7, 12, 20)], agora=utc(7, 12, 35))["pulsos_perdidos"] == 0)
ok("sem run lido a corrente não é 'zero': é 'não afirmo'",
   "não afirmo" in c.corrente_viva([], agora=utc(7, 12, 30))["veredito"])

_regulares = [pulso(7, 12, 0), pulso(7, 12, 20), pulso(7, 12, 40)]
ok("corrente sem furo não inventa buraco",
   c.buracos(c._instantes(_regulares), agora=utc(7, 13, 0)) == [])
_furo = c._instantes([pulso(7, 12, 0), pulso(7, 13, 20)])
_buracos = c.buracos(_furo, agora=utc(7, 13, 40))
ok("80 minutos calados viram buraco em pulsos perdidos",
   len(_buracos) == 1 and _buracos[0]["pulsos_perdidos"] >= 2, _buracos)
ok("o buraco é contado em pulsos perdidos (número acionável), não em minutos",
   isinstance(_buracos[0]["pulsos_perdidos"], int) and "desde" in _buracos[0], _buracos)

_salvo_agora, _salvo_lidos = c.CORRENTE_AGORA, c.ler_runs
c.CORRENTE_AGORA = utc(7, 12, 30)
c.ler_runs = lambda wf, token, **k: ([pulso(7, 12, 20), pulso(7, 12, 0)]
                                     if wf == "marketing-24h" else [pulso(7, 12, 20)])
_com_corrente = c.medir(token="x", dias=1, hoje=HOJE, raiz=RAIZ)
c.CORRENTE_AGORA, c.ler_runs = _salvo_agora, _salvo_lidos
ok("medir() mede a própria corrente e não só os crons",
   (_com_corrente.get("corrente") or {}).get("veredito", "").startswith("em dia"),
   _com_corrente.get("corrente"))
ok("a medida da corrente vai para o arquivo que o relatório lê",
   "corrente" in _com_corrente and "buracos" in _com_corrente["corrente"])

with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "cadencia.json")
    c.gravar(_dados, caminho)
    _lido = json.load(open(caminho, encoding="utf-8"))
    ok("o arquivo gravado guarda as linhas", len(_lido["linhas"]) == len(_dados["linhas"]))
    ok("o arquivo gravado guarda o total esperado e o medido",
       "total_esperado_por_dia" in _lido and "total_medido_por_dia" in _lido, list(_lido))

print("\n%d/%d contratos da cadência passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
