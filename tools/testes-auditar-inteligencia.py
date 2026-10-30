#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes da auditoria de inteligência: ritual, fachada, cego e adaptativo têm de ser distinguíveis.

Se esta auditoria errar, ela mente sobre a própria casa — então ela é medida como o resto.
"""
import importlib.util
import json
import os
import re
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
    caminho = os.path.join(RAIZ, "tools", "auditar-inteligencia.py")
    spec = importlib.util.spec_from_file_location("auditar", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


a = carregar()
tmp = tempfile.mkdtemp(prefix="auditoria-")


def log_de(linhas_por_ciclo, textos=None):
    """Monta um log sintético: lista de (quando, [(passo, resultado)])."""
    partes = []
    for i, (quando, linhas) in enumerate(linhas_por_ciclo):
        texto = (textos[i] if textos else "texto %d" % i)
        corpo = "\n".join("| %s | %s |" % (n, r) for n, r in linhas)
        partes.append("\n## %s\n\n| canal | resultado |\n|---|---|\n%s\n\n> %s\n" % (quando, corpo, texto))
    caminho = os.path.join(tmp, "log-%d.md" % len(os.listdir(tmp)))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("".join(partes))
    return caminho


def quando(i):
    return "0%d/10/2026 12:00 UTC" % ((i % 9) + 1)


# ---------- classificação por passo ----------
_ciclos = []
for i in range(8):
    _ciclos.append((quando(i), [
        ("varia", "✅ leitura %d obtida" % (i * 7)),
        ("repetido", "✅ rota oficial catalogo"),
        ("fachada", "✅ censo de hoje ja registrado (1 por dia)"),
        ("cego", "⚪ falta o segredo TELEGRAM_TOKEN + TELEGRAM_CHAT"),
        ("binario", "✅ postado 200" if i % 3 else "➖ fora da janela"),
    ]))
_caminho = log_de(_ciclos, textos=["texto distinto %d" % i for i in range(8)])
_dados = a.auditar(_caminho, janela=8)
_classes = {linha["passo"]: linha["classe"] for linha in _dados["passos"]}
ok("passo cujo resultado varia é ADAPTATIVO", _classes.get("varia") == "adaptativo", _classes)
ok("passo com sempre o mesmo resultado é RITUAL", _classes.get("repetido") == "ritual", _classes)
ok("passo que diz ✅ e confessa 'já registrado' é FACHADA", _classes.get("fachada") == "fachada", _classes)
ok("passo sempre indisponível é CEGO", _classes.get("cego") == "cego", _classes)
ok("passo liga/desliga é BINÁRIO", _classes.get("binario") == "binário", _classes)

# ---------- amostra pequena não vira classe ----------
_curto = log_de([(quando(i), [("novo", "✅ ok %d" % i)]) for i in range(3)])
_d2 = a.auditar(_curto, janela=10)
ok("passo com menos de 5 ciclos fica SEM AMOSTRA",
   all(l["classe"] == "sem amostra" for l in _d2["passos"]), _d2["passos"])

# ---------- repetição de texto ----------
_rep = log_de([(quando(i), [("a", "✅ x")]) for i in range(6)],
              textos=["mesma frase", "mesma frase", "outra", "mesma frase", "nova", "nova"])
_d3 = a.auditar(_rep, janela=6)
ok("repetição conta só o que já tinha saído antes", _d3["texto"]["repeticao_pct"] == 50.0,
   _d3["texto"])
ok("conta os textos distintos da janela", _d3["texto"]["distintos"] == 3, _d3["texto"])

# ---------- o recorte é dos ciclos MAIS RECENTES (regressão 30/10) ----------
_antigos = [("0%d/10/2026 12:00 UTC" % (i + 1), [("a", "✅ x")]) for i in range(10)]
_recentes = [("2%d/10/2026 12:00 UTC" % i, [("a", "✅ x")]) for i in range(5)]
_misto = log_de(_antigos + _recentes,
                textos=["velho"] * 10 + ["bem novo %d" % i for i in range(5)])
_d4 = a.auditar(_misto, janela=5)
ok("a janela é dos ciclos mais recentes, não dos primeiros do arquivo",
   _d4["texto"]["repeticao_pct"] == 0.0 and _d4["texto"]["distintos"] == 5, _d4["texto"])

# ---------- recorte por data: antes/depois do conserto ----------
_d5 = a.auditar(_caminho, janela=8)
ok("mede a repetição desde o conserto de dedupe (corte declarado)",
   _d5["repeticao_desde_o_conserto"]["corte"] == "26/10/2026", _d5["repeticao_desde_o_conserto"])
ok("o recorte pós-conserto tem ciclos e percentual numéricos",
   isinstance(_d5["repeticao_desde_o_conserto"]["ciclos"], int)
   and isinstance(_d5["repeticao_desde_o_conserto"]["pct"], float))

# ---------- o repositório de verdade ----------
_real = a.auditar()
ok("a auditoria do repositório roda e devolve passos",
   _real["passos"] and _real["janela"] > 0, _real.get("janela"))
ok("a lei da auditoria está escrita no arquivo",
   "mudança de comportamento" in _real.get("_lei", ""))
_md = a.markdown(_real)
ok("o markdown explica as classes", all(c in _md for c in ("adaptativo", "ritual", "fachada", "cego")))
ok("o markdown mostra a repetição e o recorte pós-conserto",
   "repetição de" in _md and "Desde o conserto" in _md)

# ---------- escrita ----------
_json, _md_path = os.path.join(tmp, "s.json"), os.path.join(tmp, "s.md")
_antigo_json, _antigo_md = a.SAIDA_JSON, a.SAIDA_MD
a.SAIDA_JSON, a.SAIDA_MD = _json, _md_path
import io
_stdout, sys.stdout = sys.stdout, io.StringIO()
try:
    a.main([])
finally:
    sys.stdout = _stdout
    a.SAIDA_JSON, a.SAIDA_MD = _antigo_json, _antigo_md
ok("grava json e markdown", os.path.exists(_json) and os.path.exists(_md_path))
ok("sem .tmp sobrando (escrita atômica)",
   not os.path.exists(_json + ".tmp") and not os.path.exists(_md_path + ".tmp"))
ok("o json gravado tem contagem e passos",
   json.load(open(_json, encoding="utf-8")).get("passos") is not None)

print()
if FALHAS:
    print("%d de %d verificações da auditoria FALHARAM" % (len(FALHAS), len(TOTAL)))
    sys.exit(1)
print("%d/%d verificações da auditoria de inteligência passaram" % (len(TOTAL), len(TOTAL)))
