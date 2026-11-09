#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calibração da régua de qualidade ("graça"): a nota tem de separar o molde antigo do texto novo.

POR QUE EXISTE (06/11/2026). A nota baixa que o dono recusou dizia: "o portão não mede graça".
Verdade pela metade — o juízo da casa já tinha traços declarados, mas a nota dele era OPCIONAL no
portão e o redator usava OUTRA escala. Agora existe uma régua só, normalizada em 0..1, com
mínimo calibrado na história da casa. Este arquivo prova a calibração com os textos reais:

  1. a régua recusa a maior parte do que a casa publicava antes do conserto (molde);
  2. a régua aprova o que a casa escreve depois do conserto;
  3. cada defeito nomeado derruba a nota (a nota não é enfeite: ela reage);
  4. a mesma entrada dá a mesma nota (determinística).
"""
import importlib.util
import os
import re
import statistics

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


juizo = carrega("juizo", "juizo.py")
portao = carrega("portao", "portao-publicacao.py")

resultados = []


def ok(nome, cond, detalhe=""):
    resultados.append((nome, bool(cond)))
    print(("PASS" if cond else "FAIL") + " — " + nome
          + ("" if cond or detalhe == "" else "  [%s]" % (detalhe,)))


# ---- 1. o corpus real da casa: o molde antigo e o texto de depois do conserto ----------------
texto_md = open(os.path.join(RAIZ, "posts", "posts-publicados.md"), encoding="utf-8").read()
blocos = [b.strip() for b in re.split(r"\n## ", texto_md) if b.strip()]
postos = []
for b in blocos:
    linhas = b.split("\n")
    if len(linhas) < 2:
        continue
    data = linhas[0].split()[0]
    postos.append((data, " ".join(linhas[1:]).strip()))


def dia(txt):
    d, m, a = txt.split("/")
    return (int(a), int(m), int(d))


# DATA DE REFERÊNCIA DO CORPUS (06/11/2026): a calibração vale para o que a casa publicou ATÉ
# esta data. Se o arquivo for reescrito ou podado, o contrato acusa em vez de recalibrar sozinho.
DATA_DO_CORPUS = (2026, 11, 6)
molde = [juizo.nota(t)[0] for q, t in postos if dia(q) < DATA_DO_CORPUS]
ok("o corpus de referência tem pelo menos 100 posts antes de 06/11/2026",
   len(molde) >= 100, len(molde))
ok("o corpus do molde antigo existe (100+ posts)", len(molde) >= 100, len(molde))

abaixo = sum(1 for n in molde if n < juizo.NOTA_MINIMA)
fracao = abaixo / float(len(molde))
ok("a régua recusa a maior parte do molde antigo (>= 70%)", fracao >= 0.70,
   "%.0f%% (%d de %d)" % (100 * fracao, abaixo, len(molde)))
ok("a mediana do molde antigo fica abaixo do mínimo",
   statistics.median(molde) < juizo.NOTA_MINIMA,
   "mediana %.3f vs mínimo %.2f" % (statistics.median(molde), juizo.NOTA_MINIMA))

# ---- 2. o texto que a casa escreve agora passa -------------------------------------------------
NOVOS = [
    "Já se achou preso na hora do milho no Ceifalume? Se plantar a flor de lume junto à abóbora, "
    "o tempo de colheita abre de 30 para 20 segundos. Grátis no navegador. #ceifalume",
    "Qual ferramenta da Prancheta do Android você acha mais útil para acompanhar as trocas? "
    "Durante a partida o técnico faz até 5 trocas e o placar muda. #prancheta",
]
for i, texto in enumerate(NOVOS):
    nota = juizo.nota(texto)[0]
    ok("texto novo %d passa no mínimo da régua" % (i + 1), nota >= juizo.NOTA_MINIMA, nota)

# e passa no portão de verdade, com a nota calculada por ele (não passada à mão)
r = portao.avalia({"titulo": "Como a flor de lume adianta a colheita do Ceifalume",
                   "texto": NOVOS[0]},
                  canal="bluesky", publicacoes=[],
                  calendario={"janela": {"inicio": 9, "fim": 22}}, hora_local=12,
                  credencial_disponivel=True)
ok("o portão calcula a nota sozinho", r["numeros"].get("nota_juizo") is not None, r["numeros"])
ok("o portão aprova o texto novo pela régua", r["publica"] is True and
   r["numeros"]["nota_juizo"] >= juizo.NOTA_MINIMA, (r["publica"], r["numeros"].get("nota_juizo")))

# ---- 3. a nota reage a cada defeito nomeado ----------------------------------------------------
BASE = ("O milho do Ceifalume leva 116 segundos para ficar pronto. Se você colher na hora certa, "
        "o celeiro não trava. Grátis no navegador. #ceifalume")
base_nota = juizo.nota(BASE)[0]
defeitos = {
    "sem pontuação no fim": BASE.replace(" #ceifalume", ""),
    "corte no meio com reticência solta": BASE[:40] + "…",
    "grito de caixa alta": "O MILHO DO CEIFALUME LEVA 116 SEGUNDOS PARA FICAR PRONTO, O CELEIRO NÃO TRAVA, GRÁTIS NO NAVEGADOR #CEIFALUME",
    "molde de dois jogos": "Dois mundos, um dev solo: Ceifalume e Prancheta, os dois no Godot, "
                           "grátis no navegador, feitos no Brasil com carinho. #ceifalume",
}
for nome, texto in defeitos.items():
    nota = juizo.nota(texto)[0]
    ok("defeito \"%s\" derruba a nota" % nome, nota < base_nota, "%.3f vs %.3f" % (nota, base_nota))

# ---- 4. determinística ------------------------------------------------------------------------
ok("a mesma entrada dá a mesma nota", juizo.nota(BASE)[0] == juizo.nota(BASE)[0])
ok("a nota fica no intervalo 0..1", all(0.0 <= juizo.nota(t)[0] <= 1.0 for _q, t in postos[:60]))

# ---- 5. uma régua só: redator e portão falam a mesma língua ------------------------------------
redator = carrega("redator", "redator.py")
nota_redator, _detalhe = redator.nota_do_texto(BASE)
ok("o redator usa a mesma régua do portão", abs(nota_redator - base_nota) <= 0.001,
   (nota_redator, base_nota))
ok("o ciclo não tem nota mínima paralela",
   redator.NOTA_MINIMA_DO_CICLO is None or abs(redator.NOTA_MINIMA_DO_CICLO - juizo.NOTA_MINIMA) < 1e-9,
   redator.NOTA_MINIMA_DO_CICLO)

certos = sum(1 for _, ok_ in resultados if ok_)
print("%d/%d contratos da régua de qualidade passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
