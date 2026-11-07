#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da corrente de pulsos. Nenhum teste dorme nem chama a API: tudo injetado."""
import datetime
import importlib.util
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("corr", os.path.join(RAIZ, "tools", "corrente.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

certos, falhas = 0, 0
BRT = datetime.timezone(datetime.timedelta(hours=-3))
UTC = datetime.timezone.utc


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


def local(h, m=0, dia=8):
    return datetime.datetime(2026, 11, dia, h, m, tzinfo=BRT)


# ------------------------------------------------------------------ quando acordar
_d = c.proximo_disparo(local(9, 7))
ok("às 09h07 acorda às 09h20 (alinhado ao passo de 20 min)",
   _d.astimezone(BRT).strftime("%H:%M") == "09:20", _d.astimezone(BRT))
ok("o horário de acordar está sempre no futuro", _d > local(9, 7).astimezone(UTC))
ok("o horário é múltiplo de 20 minutos", _d.astimezone(BRT).minute % 20 == 0,
   _d.astimezone(BRT).minute)

_d = c.proximo_disparo(local(21, 41))
ok("depois do último pulso da janela, acorda na pesquisa de amanhã (03h)",
   _d.astimezone(BRT).strftime("%d/%m %H:%M") == "09/11 03:00", _d.astimezone(BRT))

_d = c.proximo_disparo(local(23, 30))
ok("de madrugada fora das janelas, acorda às 03h", _d.astimezone(BRT).strftime("%H:%M") == "03:00",
   _d.astimezone(BRT))
_d = c.proximo_disparo(local(3, 30))
ok("às 03h30 (pesquisa) acorda às 03h40", _d.astimezone(BRT).strftime("%H:%M") == "03:40",
   _d.astimezone(BRT))
_d = c.proximo_disparo(local(4, 50))
ok("às 04h50 (fim do aprendizado) acorda às 09h", _d.astimezone(BRT).strftime("%H:%M") == "09:00",
   _d.astimezone(BRT))
_d = c.proximo_disparo(local(12, 0))
ok("meio da janela acorda 20 min depois", _d.astimezone(BRT).strftime("%H:%M") == "12:20",
   _d.astimezone(BRT))

# a janela do calendário manda: com 10-20, 09h não é hora de pulso
_d = c.proximo_disparo(local(9, 30), horas=c.horas_de_pulso(10, 20))
ok("horas de pulso respeitam a janela do calendário", _d.astimezone(BRT).hour == 10,
   _d.astimezone(BRT))

_todas_as_horas = c.horas_de_pulso()
ok("a janela 9-22 entra nas horas de pulso", {9, 15, 21} <= _todas_as_horas, sorted(_todas_as_horas))
ok("a janela de estudo entra", {3, 4} <= _todas_as_horas)
ok("22h não é hora de publicar", 22 not in _todas_as_horas)

# ------------------------------------------------------------------ motivo
ok("o motivo da janela aberta é dito", "janela aberta" in c.motivo(local(15, 0)))
ok("o motivo da janela de estudo é dito", "janela de estudo (3h)" in c.motivo(local(3, 20)))
ok("fora da janela não acontece (a conta mira só a janela)",
   "não deveria acontecer" in c.motivo(local(6, 0)))

# ------------------------------------------------------------------ o passo da corrente
_chamadas = []
_feito = c.ciclo(agora_fn=lambda: local(15, 5),
                 pulso_fn=lambda: _chamadas.append("pulso"),
                 si_fn=lambda: _chamadas.append("corrente"),
                 dormir=lambda s: _chamadas.append(("dormiu", s)),
                 token="x", parado_fn=lambda: False)
ok("a corrente acorda o pulso e se reagenda", _chamadas and _chamadas[-2:] == ["pulso", "corrente"],
   _chamadas)
ok("ela dorme antes de disparar", isinstance(_chamadas[0], tuple) and _chamadas[0][0] == "dormiu",
   _chamadas[:2])
ok("o sono é de 15 minutos quando faltam 15", _chamadas[0][1] == 15 * 60, _chamadas[0])
ok("o registro diz que disparou e quando", _feito["acao"] == "disparou" and _feito["em"], _feito)
ok("o registro diz o motivo", "janela aberta" in _feito["motivo"], _feito)

_chamadas_vazias = []
_parado = c.ciclo(agora_fn=lambda: local(15, 5),
                  pulso_fn=lambda: _chamadas_vazias.append("pulso"),
                  si_fn=lambda: _chamadas_vazias.append("corrente"),
                  dormir=lambda s: None, token="x", parado_fn=lambda: True)
ok("com posts/PARAR, nada é disparado", _chamadas_vazias == [], _chamadas_vazias)
ok("com posts/PARAR, a corrente diz que parou", _parado["acao"] == "parar" and "PARAR" in _parado["motivo"],
   _parado)

# PARAR que aparece durante a espera também para tudo
_estado = {"parado": False}


def _parado_depois(s):
    _estado["parado"] = True


_chamadas_durante = []
_meio = c.ciclo(agora_fn=lambda: local(15, 5),
                pulso_fn=lambda: _chamadas_durante.append("pulso"),
                si_fn=lambda: _chamadas_durante.append("corrente"),
                dormir=_parado_depois, token="x", parado_fn=lambda: _estado["parado"])
ok("se PARAR aparece durante a espera, não dispara", _chamadas_durante == [], _chamadas_durante)
ok("e diz por que parou", "durante a espera" in _meio["motivo"], _meio)

# ------------------------------------------------------------------ limites
_esperado = c.esperar(10 ** 6, dormir=lambda s: None)
ok("a espera nunca passa de 5h20 (job do GitHub morre em 6h)",
   _esperado == int(c.ESPERA_MAXIMA.total_seconds()), _esperado)

# ------------------------------------------------------------------ disparar de verdade (sem rede)
class _Resposta:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


_salvo = c.urllib.request.urlopen
c.urllib.request.urlopen = lambda req, timeout=None: _Resposta()
try:
    ok("disparo com HTTP 204 é sucesso", c.disparar("marketing-24h", "x") is True)

    class _Erro(_Resposta):
        status = 500

    c.urllib.request.urlopen = lambda req, timeout=None: _Erro()
    try:
        c.disparar("marketing-24h", "x")
        ok("HTTP diferente de 204/201 não é sucesso", False)
    except RuntimeError as erro:
        ok("HTTP diferente de 204/201 não é sucesso", "500" in str(erro), erro)
finally:
    c.urllib.request.urlopen = _salvo

# O PULSO VAI POR `repository_dispatch` (07/11/2026). O primeiro run de verdade morreu com
# HTTP 422: `marketing-24h` exige a entrada `confirmacao` e a corrente não a mandava. Mandar
# PUBLICAR daqui seria a automação digitando autorização de gente — então o pulso tem gatilho
# próprio, e o corpo enviado é provado abaixo.
_enviados = []


class _Captura(_Resposta):
    def __init__(self, status=204):
        self.status = status


def _capturar(req, timeout=None):
    _enviados.append({"url": req.full_url, "corpo": (req.data or b"").decode()})
    return _Captura()


_guarda = c.urllib.request.urlopen
c.urllib.request.urlopen = _capturar
try:
    c.disparar_pulso("x")
    c.disparar("corrente", "x")
finally:
    c.urllib.request.urlopen = _guarda
ok("o pulso é acordado pelo `repository_dispatch`",
   _enviados and _enviados[0]["url"].endswith("/repos/reboclbrank-max/site/dispatches"),
   _enviados[:1])
ok("o corpo do pulso diz o evento, não uma palavra de confirmação",
   '"event_type": "pulso"' in _enviados[0]["corpo"] and "PUBLICAR" not in _enviados[0]["corpo"],
   _enviados[0]["corpo"])
ok("a corrente se reagenda pelo `workflow_dispatch` (só ele dispara a si mesmo)",
   _enviados[1]["url"].endswith("/actions/workflows/corrente.yml/dispatches"), _enviados[1]["url"])
ok("a corrente nunca digita PUBLICAR por ninguém",
   all("PUBLICAR" not in e["corpo"] for e in _enviados), _enviados)

c.urllib.request.urlopen = lambda req, timeout=None: _Captura(422)
try:
    c.disparar_pulso("x")
    ok("HTTP 422 do pulso não é sucesso", False)
except RuntimeError as erro:
    ok("HTTP 422 do pulso não é sucesso", "422" in str(erro), erro)
finally:
    c.urllib.request.urlopen = _guarda

# o ciclo de verdade usa esses dois caminhos (não o `disparar('marketing-24h')` antigo)
_origem = c.disparar_pulso, c.disparar
_chamou = []
c.disparar_pulso = lambda token=None, **k: _chamou.append("pulso")
c.disparar = lambda wf, token=None, **k: _chamou.append(wf)
try:
    c.ciclo(agora_fn=lambda: local(15, 5), dormir=lambda s: None, token="x",
            parado_fn=lambda: False)
finally:
    c.disparar_pulso, c.disparar = _origem
ok("o ciclo padrao acorda o pulso pelo caminho novo e reagenda a corrente",
   _chamou == ["pulso", "corrente"], _chamou)

# sem token, a linha de comando não dispara às cegas
_salvo_token = {k: os.environ.pop(k, None) for k in ("GHPAT", "GITHUB_TOKEN")}
_codigo = c.main([])
for k, v in _salvo_token.items():
    if v is not None:
        os.environ[k] = v
ok("sem token a corrente para com código 3 (não finge que disparou)", _codigo == 3, _codigo)

print("\n%d/%d contratos da corrente passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
