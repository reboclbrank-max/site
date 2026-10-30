#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do aprendizado de horário: só troca com prova; sem prova, mantém e diz por quê.

Este é o teste que faltava (30/10/2026): a regra existia, mas ninguém a executava nem a
cobrava. Agora ela roda todo ciclo e este arquivo impede que ela "aprenda" com ruído.
"""
import importlib.util
import json
import os
import statistics
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FALHAS = []
TOTAL = []


def ok(nome, condicao, detalhe=None):
    TOTAL.append(nome)
    if condicao:
        print("OK  " + nome)
    else:
        FALHAS.append(nome)
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe is not None else ""))


def carregar():
    spec = importlib.util.spec_from_file_location(
        "aprender_horario", os.path.join(RAIZ, "tools", "aprender-horario.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


a = carregar()
tmp = tempfile.mkdtemp(prefix="horario-")

# ---------- leitura do relatório ----------
_relatorio = (
    "# desempenho\n\n"
    "**Horário (Brasília):** 09h=3.0(n=1) · 10h=0.94(n=17) · 11h=1.7(n=10)\n"
    "\n**Horário (Brasília):** 10h=9.9(n=99) · 11h=9.9(n=99)\n"
)
_caminho = os.path.join(tmp, "desempenho.md")
open(_caminho, "w", encoding="utf-8").write(_relatorio)
_horas = a.por_hora(a.ler(_caminho))
ok("lê a linha de horário com hora, média e amostra",
   _horas and _horas[0] == (9, 3.0, 1), _horas)
ok("usa só o relatório mais recente (o primeiro do arquivo)",
   len(_horas) == 3 and 9.9 not in [h[1] for h in _horas], _horas)
ok("relatório ausente não explode", a.por_hora(a.ler(os.path.join(tmp, "nao-existe.md"))) == [])

# ---------- amostra pequena: mantém ----------
_fraco = [(10, 1.4, 17), (11, 2.9, 2), (12, 0.9, 16)]
_conf, _melhor, _motivo, _det = a.decidir(_fraco)
ok("sem hora com amostra mínima, a decisão é MANTER", _conf is False and _melhor is None)
ok("o motivo cita a amostra e o maior n", "amostra insuficiente" in _motivo and "17" in _motivo, _motivo)
ok("mesmo com média alta, amostra pequena NÃO vira escolha",
   _det.get("maior_media_observada", {}).get("hora") == 11, _det.get("maior_media_observada"))

# ---------- diferença dentro do ruído: mantém ----------
_ruido = [(h, 1.2 + (0.1 if h % 2 else -0.1), 40) for h in range(8, 20)]
_conf, _melhor, _motivo, _det = a.decidir(_ruido)
ok("diferença dentro de um desvio não vira troca", _conf is False, _motivo)
ok("o motivo mede ruído (mostra mediana e desvio)",
   "ruído" in _motivo and "desvio" in _motivo, _motivo)

# ---------- sinal forte: troca ----------
_forte = [(10, 0.5, 60), (11, 0.6, 60), (12, 0.5, 60), (19, 3.0, 80)]
_conf, _melhor, _motivo, _det = a.decidir(_forte)
ok("sinal maior que o desvio vira TROCAR", _conf is True and _melhor == 19, (_conf, _melhor, _motivo))
_medias = [h[1] for h in _forte]
ok("a regra é conferível: ganho > desvio",
   (_det["melhor"]["media"] - statistics.median(_medias)) > statistics.pstdev(_medias), _det)

# ---------- nada lido: não inventa ----------
_conf, _melhor, _motivo, _det = a.decidir([])
ok("sem leitura, decisão é MANTER com motivo explícito",
   _conf is False and _melhor is None and "sem leitura" in _motivo, _motivo)

# ---------- main grava o motivo e a regra ----------
_saida = os.path.join(tmp, "aprendizado.json")
open(_caminho, "w", encoding="utf-8").write(_relatorio)
_antigo_desempenho, _antigo_saida = a.DESEMPENHO, a.SAIDA
a.DESEMPENHO, a.SAIDA = _caminho, _saida
import io
_stdout, sys.stdout = sys.stdout, io.StringIO()
try:
    a.main([])
finally:
    sys.stdout = _stdout
    a.DESEMPENHO, a.SAIDA = _antigo_desempenho, _antigo_saida
_dados = json.load(open(_saida, encoding="utf-8"))
ok("grava posts/aprendizado.json com decisão explícita",
   _dados.get("decisao") in ("manter", "trocar"), _dados.get("decisao"))
ok("grava o motivo e a regra auditável",
   bool(_dados.get("motivo")) and "amostra >=" in _dados.get("_regra", ""))
ok("quando mantém, melhor_hora fica nulo (nada de hora inventada)",
   _dados.get("decisao") != "manter" or _dados.get("melhor_hora") is None)

# ---------- o arquivo de verdade do repositório é coerente ----------
_real = json.load(open(os.path.join(RAIZ, "posts", "aprendizado.json"), encoding="utf-8"))
ok("o aprendizado do repositório é coerente consigo mesmo",
   (_real.get("melhor_hora") is None) if _real.get("decisao") == "manter"
   else isinstance(_real.get("melhor_hora"), int), _real.get("decisao"))
ok("o repositório carrega a amostra que sustenta a decisão",
   isinstance(_real.get("detalhe", {}).get("amostra_total"), int), _real.get("detalhe"))

print()
if FALHAS:
    print("%d de %d verificações do aprendizado de horário FALHARAM" % (len(FALHAS), len(TOTAL)))
    sys.exit(1)
print("%d/%d verificações do aprendizado de horário passaram" % (len(TOTAL), len(TOTAL)))
