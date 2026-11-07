#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do medidor de originalidade. Sem rede: tudo vem de texto de amostra."""
import datetime
import importlib.util
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("unic", os.path.join(RAIZ, "tools", "medir-unicidade.py"))
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

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

# ------------------------------------------------------------------ assinatura
ok("a assinatura tira acento", u.assinatura("Colheita e Celeiro") == "colheita e celeiro")
ok("a assinatura tira emoji e pontuação",
   u.assinatura("🌙 Jogou PRANCHETA? Conta pra mim!") == "jogou prancheta conta pra mim",
   u.assinatura("🌙 Jogou PRANCHETA? Conta pra mim!"))
ok("maiúscula e minúscula são o mesmo texto",
   u.assinatura("CEIFALUME") == u.assinatura("ceifalume"))
ok("dois textos que só diferem no emoji têm a MESMA assinatura",
   u.assinatura("🌙 plantações crescem") == u.assinatura("⚽ plantações crescem"))

# ------------------------------------------------------------------ quase-repetição
_a = "o celeiro guarda até 8 horas de colheita enquanto o jogo está fechado e o relógio continua"
_b = "o celeiro guarda ate 8 horas de colheita enquanto o jogo esta fechado e o relogio continua"
ok("semelhança pega acento trocado", u.semelhanca(_a, _b) == 1.0, u.semelhanca(_a, _b))
_c = "o celeiro guarda 8 horas de colheita com o jogo fechado, e o relógio não para nunca"
ok("semelhança separa texto reescrito de texto repetido",
   0.5 < u.semelhanca(_a, _c) < 1.0, u.semelhanca(_a, _c))
ok("texto totalmente outro não é quase-repetido",
   u.semelhanca(_a, "a partida é narrada lance a lance com placar ao vivo") < 0.5)
# par REESCRITO (assinaturas diferentes, frase quase igual): é aqui que o quase-repetido pega
# o que a assinatura exata não pega. _a e _b têm a MESMA assinatura e por isso caem em `repetidos`.
_reescrito = _a.replace("está fechado", "fica fechado")
ok("quase_repetidos acha o par reescrito",
   len(u.quase_repetidos([_a, _reescrito])) == 1, u.quase_repetidos([_a, _reescrito]))
ok("texto só com acento trocado é repetição exata, não quase-repetição",
   u.quase_repetidos([_a, _b]) == [] and len(u.repetidos([_a, _b])) == 1,
   (u.quase_repetidos([_a, _b]), u.repetidos([_a, _b])))
ok("quase_repetidos não acusa dois textos diferentes",
   u.quase_repetidos([_a, "a partida é narrada lance a lance com placar ao vivo"]) == [])

# ------------------------------------------------------------------ leitura do registro
AMOSTRA = """# posts

## 06/11/2026 12:00 UTC
🌙 o celeiro guarda colheita ⏎ com o jogo fechado

## 06/11/2026 15:00 UTC
⚽ a partida é narrada lance a lance

## 07/11/2026 09:00 UTC
o celeiro guarda colheita com o jogo fechado
"""
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts-publicados.md")
    open(caminho, "w", encoding="utf-8").write(AMOSTRA)
    lidos = u.ler_posts(caminho)
ok("o registro é lido com data e texto", len(lidos) == 3, lidos)
ok("a data do cabeçalho vira dia", lidos[0][0] == datetime.date(2026, 11, 6), lidos[0][0])
ok("o marcador de quebra (⏎) não vira parte do texto nem quebra a linha",
   "⏎" not in lidos[0][1] and "com o jogo fechado" in lidos[0][1], lidos[0][1])
# O FEED NÃO SEPARA POR DIA (07/11/2026): o mesmo texto em dois dias é repetição para quem lê.
# O que muda por dia é a contagem de `dias_com_repeticao`, que serve para achar o dia ruim.
ok("o mesmo texto em dias diferentes conta como repetição na janela",
   len(u.repetidos([t for _, t in lidos])) == 1, u.repetidos([t for _, t in lidos]))
ok("mas nenhum dia da amostra tem repetição dentro dele",
   u.dias_com_repeticao(lidos) == [], u.dias_com_repeticao(lidos))

with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "vazio.md")
    open(caminho, "w", encoding="utf-8").write("# nada aqui\n")
    ok("registro sem bloco datado não inventa post", u.ler_posts(caminho) == [])
ok("arquivo ausente não vira erro de contagem", u.ler_posts("/caminho/que/nao/existe") == [])

# ------------------------------------------------------------------ medição
_ruim = [(datetime.date(2026, 10, 25), "o mesmo texto de sempre"),
         (datetime.date(2026, 10, 25), "o mesmo texto de sempre"),
         (datetime.date(2026, 10, 25), "o mesmo texto de sempre")]
_d = u.medir(_ruim, hoje=HOJE)
ok("dia com 3 posts e 1 texto único aparece em dias_com_repeticao",
   len(_d["dias_com_repeticao"]) == 1 and _d["dias_com_repeticao"][0]["unicos"] == 1,
   _d["dias_com_repeticao"])
ok("a data da última repetição fica registrada", _d["ultimo_dia_com_repeticao"] == "2026-10-25")

_bom = [(datetime.date(2026, 11, 6), "o celeiro guarda colheita com o jogo fechado"),
        (datetime.date(2026, 11, 7), "a partida é narrada lance a lance, sem controle do jogador")]
_d = u.medir(_bom, hoje=HOJE)
ok("semana sem repetição é dita assim, com contagem e data do último dia ruim",
   _d["veredito"].startswith("últimos 7 dias") and "todos textos diferentes" in _d["veredito"],
   _d["veredito"])
ok("a média por dia é calculada (1 post em cada um de 2 dias = 1,0/dia)",
   _d["media_por_dia"] == 1.0, _d["media_por_dia"])

_repetiu = [(datetime.date(2026, 11, 6), "🌙 o celeiro guarda colheita com o jogo fechado"),
            (datetime.date(2026, 11, 6), "⚽ o celeiro guarda colheita com o jogo fechado")]
_d = u.medir(_repetiu, hoje=HOJE)
ok("repetição na janela recente vira REPETIÇÃO no veredito",
   _d["veredito"].startswith("REPETIÇÃO"), _d["veredito"])
ok("o veredito diz quantos repetidos", "1 repetido(s)" in _d["veredito"], _d["veredito"])
ok("registro vazio não afirma originalidade", "não afirmo" in u.medir([], hoje=HOJE)["veredito"])

# ------------------------------------------------------------------ a casa de verdade
_salvo_registro, _salvo_saida = u.REGISTRO, u.SAIDA
with tempfile.TemporaryDirectory() as tmp:
    u.SAIDA = os.path.join(tmp, "unicidade.json")
    _codigo = u.main([])
u.REGISTRO, u.SAIDA = _salvo_registro, _salvo_saida
ok("o medidor roda no registro da casa e termina bem quando não há repetição",
   _codigo == 0, _codigo)

_hoje_real = u.medir()
_janela = _hoje_real["ultimos_dias"]
ok("contrato da casa: nenhum post repetido na janela recente do registro real",
   _janela["repetidos"] == 0, [r[1][:60] for r in
                               [(a, t) for a, t in u.repetidos(
                                   [x for d, x in u.ler_posts()
                                    if (_hoje_real.get("ate") and
                                        (datetime.date.fromisoformat(_hoje_real["ate"]) - d).days
                                        < _janela["janela"])])]])
ok("contrato da casa: nenhum quase-repetido na janela recente",
   _janela["quase_repetidos"] == [], _janela["quase_repetidos"])
ok("o medidor grava o arquivo que o relatório lê",
   "unicidade" in _salvo_saida and _salvo_saida.endswith("unicidade.json"))

print("\n%d/%d contratos da originalidade passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
