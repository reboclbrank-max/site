#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da cena: a casa não pode gravar duas vezes a mesma partida.

O defeito que estes contratos impedem (medido em 06/11/2026): três vídeos publicados no mesmo
dia, todos da mesma partida de 2 minutos — mesmo Dia 1, mesmo campo, mesmo primeiro quadro. O
título mudava, o que se via na tela não.
"""
import importlib.util
import json
import os
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cena", os.path.join(RAIZ, "tools", "cena.py"))
cena = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cena)

resultados = []


def checar(nome, condicao, detalhe=""):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome
          + ("" if condicao or not detalhe else "  [%s]" % (detalhe,)))


def bancada():
    return os.path.join(tempfile.mkdtemp(prefix="cenas-"), "cenas.json")


def relatorio(plantadas=15, colhidas=8, bicos=40, sementes=("nabo", "milho"), melhorias=("celeiro",)):
    return {"plantadas": plantadas, "colhidas": colhidas, "bicos": bicos, "verde_final": 0.3,
            "economia": {"sementes": [{"de": "nabo", "para": s} for s in sementes],
                         "melhorias": list(melhorias)}}


# ---- 1. as estratégias existem e dizem o que mudam na tela
checar("há pelo menos 4 estratégias de cena", len(cena.ESTRATEGIAS) >= 4, len(cena.ESTRATEGIAS))
checar("toda estratégia declara teto de semente e de células",
      all("teto_semente" in e and "teto_celulas" in e for e in cena.ESTRATEGIAS.values()))
checar("toda estratégia diz, em português, o que muda na tela",
      all(len(e.get("porque") or "") > 20 for e in cena.ESTRATEGIAS.values()))

# ---- 2. a rotação nunca repete a anterior e dá a volta em todas
caminho_rotacao = bancada()
r = cena.carregar(caminho_rotacao)
sequencia = []
for _ in range(8):
    e = cena.proxima(r)
    sequencia.append(e)
    cena.registrar(relatorio(plantadas=len(sequencia) * 3), e, r,
                   caminho=caminho_rotacao, quando="2026-11-06T1%d:00:00Z" % len(sequencia))
checar("a estratégia da vez nunca é a mesma da gravação anterior",
      all(sequencia[i] != sequencia[i - 1] for i in range(1, len(sequencia))), sequencia)
checar("todas as estratégias têm vez a cada volta",
      set(sequencia[:len(cena.ESTRATEGIAS)]) == set(cena.ESTRATEGIAS),
      sequencia[:len(cena.ESTRATEGIAS)])

# ---- 3. assinatura: igual para a mesma partida, diferente para outra
a1, _ = cena.assinatura(relatorio(), "milho")
a2, _ = cena.assinatura(relatorio(), "milho")
a3, _ = cena.assinatura(relatorio(), "trigo")
a4, _ = cena.assinatura(relatorio(plantadas=16), "milho")
a5, _ = cena.assinatura(relatorio(sementes=("nabo", "trigo")), "milho")
checar("a mesma partida dá a mesma assinatura", a1 == a2, (a1, a2))
checar("estratégia diferente dá assinatura diferente", a1 != a3, (a1, a3))
checar("uma planta a mais já é outra partida", a1 != a4, (a1, a4))
checar("semente diferente já é outra partida", a1 != a5, (a1, a5))

# ---- 4. duas partidas iguais não entram no registro
caminho = bancada()
reg = cena.carregar(caminho)
ok1, m1, s1 = cena.registrar(relatorio(), "milho", reg, caminho)
ok2, m2, s2 = cena.registrar(relatorio(), "milho", reg, caminho)
checar("a primeira partida é registrada", ok1 is True, m1)
checar("a segunda, idêntica, é recusada com motivo e com a assinatura na mão",
      ok2 is False and s1 == s2 and "repetida" in m2, m2)
checar("o registro guarda uma partida, não duas",
      len(json.load(open(caminho, encoding="utf-8"))["partidas"]) == 1)

ok3, _, _ = cena.registrar(relatorio(colhidas=9), "milho", reg, caminho)
checar("partida diferente na mesma estratégia é aceita", ok3 is True)

# ---- 5. o registro é legível por gente e por máquina
dado = json.load(open(caminho, encoding="utf-8"))
p = dado["partidas"][0]
checar("cada linha do registro diz quando, com que estratégia e com que assinatura",
      all(k in p for k in ("quando", "estrategia", "assinatura", "resumo")), list(p))
checar("o resumo guarda o que se viu na tela",
      all(k in p["resumo"] for k in ("plantadas", "colhidas", "sementes", "verde_final")),
      list(p["resumo"]))

# ---- 6. o comando que o workflow usa devolve a estratégia pelada
import subprocess
saida = subprocess.run(["python3", os.path.join(RAIZ, "tools", "cena.py"), "proxima",
                        "--registro", caminho], capture_output=True, text=True)
checar("o comando 'proxima' imprime só o nome da estratégia",
      saida.stdout.strip() in cena.ESTRATEGIAS, saida.stdout.strip())

# ---- 7. registrar sem caminho NÃO escreve no registro real da casa
antes = open(os.path.join(RAIZ, "posts", "cenas.json"), "rb").read() if os.path.exists(
    os.path.join(RAIZ, "posts", "cenas.json")) else b""
mem = {"partidas": []}
cena.registrar(relatorio(plantadas=99), "trigo", mem)
depois = open(os.path.join(RAIZ, "posts", "cenas.json"), "rb").read() if os.path.exists(
    os.path.join(RAIZ, "posts", "cenas.json")) else b""
checar("registrar só na memória não toca o registro versionado", antes == depois)
checar("a partida existe na memória do teste", len(mem["partidas"]) == 1)

# ---- 8. o gravador (JS) e a rotação (Python) falam a MESMA língua
import re
js = open(os.path.join(RAIZ, "tools", "gravar-gameplay.js"), encoding="utf-8").read()
bloco = re.search(r"const CENAS = \{(.+?)\n\};", js, re.S)
nomes_js = set(re.findall(r"'([a-z-]+)':\s*\{", bloco.group(1))) if bloco else set()
checar("o gravador conhece exatamente as estratégias da rotação",
      nomes_js == set(cena.ESTRATEGIAS), (sorted(nomes_js), sorted(cena.ESTRATEGIAS)))
checar("o gravador recebe --estrategia e recusa nome desconhecido",
      "'--estrategia'" in js and "estratégia de cena desconhecida" in js)

certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos da cena passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
