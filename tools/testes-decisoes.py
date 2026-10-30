#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do livro de decisões: decisão sem número não entra, recusa e ignorância aparecem.

Roda offline, com fixtures temporárias — não toca em posts/ de verdade.
"""
import importlib.util
import io
import json
import os
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
        "decisoes", os.path.join(RAIZ, "tools", "decisoes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


d = carregar()
tmp = tempfile.mkdtemp(prefix="decisoes-")


def escrever(nome, texto):
    caminho = os.path.join(tmp, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho


def apontar(plano=None, aprendizado=None, placar=None, nunca=None):
    d.PLANO = plano or os.path.join(tmp, "nao-existe-plano.json")
    d.APRENDIZADO = aprendizado or os.path.join(tmp, "nao-existe-aprendizado.json")
    d.PLACAR = placar or os.path.join(tmp, "nao-existe-placar.md")
    d.NUNCA = nunca or os.path.join(tmp, "nao-existe-nunca.json")


# ---------- 1. o livro de verdade (os arquivos do repositório) ----------
d.PLANO = os.path.join(RAIZ, "posts", "plano-do-dia.json")
d.APRENDIZADO = os.path.join(RAIZ, "posts", "aprendizado.json")
d.PLACAR = os.path.join(RAIZ, "posts", "placar-metas.md")
d.NUNCA = os.path.join(RAIZ, "posts", "nunca-publicar.json")
real = d.livro()

ok("o livro tem as três listas", all(k in real for k in ("decididas", "recusadas", "ignorancias")))
ok("o livro é gerado do repositório, não escrito à mão", "posts/" in json.dumps(real))
ok("toda decisão tem o NÚMERO que a sustenta",
   all(any(ch.isdigit() for ch in str(i["numero"])) for i in real["decididas"]),
   [i["decisao"] for i in real["decididas"] if not any(ch.isdigit() for ch in str(i["numero"]))])
ok("toda decisão cita a fonte e a fonte existe",
   all(i["fonte"].startswith("regra da casa") or os.path.exists(os.path.join(RAIZ, i["fonte"]))
       for i in real["decididas"] + real["recusadas"]),
   [i["fonte"] for i in real["decididas"] + real["recusadas"]
    if not i["fonte"].startswith("regra da casa") and not os.path.exists(os.path.join(RAIZ, i["fonte"]))])
ok("toda recusa explica o porquê", all(i.get("porque") for i in real["recusadas"]))
ok("toda ignorância é uma pergunta nomeada", all(i.get("pergunta") for i in real["ignorancias"]))
ok("a contagem bate com as listas",
   real["contagem"] == {"decididas": len(real["decididas"]), "recusadas": len(real["recusadas"]),
                        "ignorancias": len(real["ignorancias"])}, real["contagem"])
ok("'o texto é bom?' está declarado como ignorância (gosto não se mede no log)",
   any("texto" in i["pergunta"] for i in real["ignorancias"]))

# ---------- 2. amostra pequena vira recusa, nunca decisão ----------
_apr_fraco = escrever("fraco.json", json.dumps({
    "decisao": "manter", "confiavel": False, "melhor_hora": None,
    "motivo": "amostra curta: 3 leituras",
    "detalhe": {"amostra_total": 3, "amostra_minima": 30, "elegiveis": 0}}))
apontar(aprendizado=_apr_fraco)
ok("amostra curta não vira decisão de trocar horário",
   not any("horário" in i["decisao"] for i in d.decididas()))
ok("amostra curta vira recusa declarada",
   any("horário" in i["decisao"] and "falta de prova" in i["porque"] for i in d.recusadas()))
ok("a recusa carrega a amostra, não uma opinião",
   any("mínimo por hora 30" in i["numero"] for i in d.recusadas()))

# ---------- 3. prova boa vira decisão ----------
_apr_forte = escrever("forte.json", json.dumps({
    "decisao": "trocar", "confiavel": True, "melhor_hora": 19,
    "motivo": "melhor 19h (2.40, n=40) supera a mediana 1.20 por mais de um desvio (0.40)",
    "detalhe": {"amostra_total": 400, "amostra_minima": 30, "elegiveis": 5}}))
apontar(aprendizado=_apr_forte)
ok("com prova, a troca de horário é decidida (e mostra a hora)",
   any("horário" in i["decisao"] and "19h" in i["numero"] for i in d.decididas()))

# ---------- 4. sem relatório, a casa diz que não sabe ----------
apontar()
ok("sem relatório de horário, nada é inventado",
   not any("horário" in i["decisao"] for i in d.decididas()))
ok("sem relatório de horário, a recusa é por falta de medida",
   any("falta de medida" in i["porque"] for i in d.recusadas()))

# ---------- 5. SEM_LEITURA é ignorância, não zero ----------
_placar = escrever("placar.md", (
    "| meta | alvo | observado | falta | por dia | status | desde a partida |\n"
    "|---|---|---|---|---|---|---|\n"
    "| itch: seguidores | 10 | NAO_OBSERVAVEL | — | — | SEM_LEITURA | — |\n"
    "| itch: downloads | 100 | 47 | 53 | 4.08 | EM_CURSO | +3 |\n"
    "\n> **Sem retorno em 17 dias:** Instagram: seguidores (0 medido(s), nada a mais desde 13/10).\n"))
apontar(placar=_placar)
_ig = d.ignorancias()
ok("meta sem leitura aparece como ignorância",
   any("itch: seguidores" in i["pergunta"] for i in _ig), _ig)
ok("a ignorância explica que ausência de leitura não é zero",
   any("não é zero" in i["porque"] for i in _ig))
ok("'sem retorno em N dias' vira recusa do dono, com o número",
   any("17 dias" in i["numero"] and "recusa" in i["porque"] + i["decisao"] or
       ("17 dias" in i["numero"] and "escolha de vida" in i["porque"]) for i in d.recusadas()))

# ---------- 6. veto do dono é recusa herdada, com data ----------
_nunca = escrever("nunca.json", json.dumps({
    "nunca_publicar": ["toque-rapido"],
    "motivo": "criação que não deu certo", "pedido_em": "2026-10-26"}))
apontar(nunca=_nunca)
_rec = d.recusadas()
ok("veto do dono entra como recusa", any("toque-rapido" in i["decisao"] for i in _rec))
ok("o veto carrega a data do pedido", any("2026-10-26" in i["numero"] for i in _rec))

# ---------- 7. formato com zero repetido vira decisão de parar ----------
_plano = escrever("plano.json", json.dumps({
    "meta_em_risco": {"meta": "itch: downloads", "falta": 54.0, "por_dia": 3.38},
    "formatos_a_evitar": [{"formato": "comentário em post alheio", "zeros": 90,
                           "total": 217, "pct": 41.5}]}))
apontar(plano=_plano)
_dec = d.decididas()
ok("a meta mais atrasada vira prioridade, com a conta por dia",
   any("itch: downloads" in i["numero"] and "3.38" in i["numero"] for i in _dec), _dec)
ok("formato que devolve zero repetido vira decisão de parar",
   any("zero" in i["decisao"] and "41.5" in i["numero"] for i in _dec), _dec)

# ---------- 8. saída: markdown, átomo e idempotência ----------
d.PLANO, d.APRENDIZADO = os.path.join(RAIZ, "posts", "plano-do-dia.json"), os.path.join(RAIZ, "posts", "aprendizado.json")
d.PLACAR, d.NUNCA = os.path.join(RAIZ, "posts", "placar-metas.md"), os.path.join(RAIZ, "posts", "nunca-publicar.json")
_livro = d.livro()
_md = d.markdown(_livro)
ok("o markdown tem as três seções com contagem",
   all(t in _md for t in ("O que a casa decide sozinha", "O que a casa se recusa a decidir",
                          "O que a casa não sabe")))
ok("o markdown repete a lei: decisão sem número não entra", "Decisão sem número não entra" in _md)
_saida_json = os.path.join(tmp, "d.json")
_saida_md = os.path.join(tmp, "d.md")
_antigo_json, _antigo_md = d.SAIDA_JSON, d.SAIDA_MD
d.SAIDA_JSON, d.SAIDA_MD = _saida_json, _saida_md
_captura = io.StringIO()
_stdout = sys.stdout
sys.stdout = _captura
try:
    d.main([])
finally:
    sys.stdout = _stdout
d.SAIDA_JSON, d.SAIDA_MD = _antigo_json, _antigo_md
ok("grava posts/decisoes.json e posts/decisoes.md",
   os.path.exists(_saida_json) and os.path.exists(_saida_md))
ok("escrita atômica (nenhum .tmp sobrou)",
   not os.path.exists(_saida_json + ".tmp") and not os.path.exists(_saida_md + ".tmp"))
ok("o json gravado é legível e tem contagem",
   json.load(open(_saida_json, encoding="utf-8")).get("contagem", {}).get("decididas") is not None)
ok("idempotente fora o carimbo de hora",
   {k: v for k, v in d.livro().items() if k != "quando"} ==
   {k: v for k, v in json.load(open(_saida_json, encoding="utf-8")).items() if k != "quando"})
ok("o resumo impresso mostra as três contagens", "ignorâncias declaradas" in _captura.getvalue())

print()
if FALHAS:
    print("%d de %d verificações do livro de decisões FALHARAM" % (len(FALHAS), len(TOTAL)))
    sys.exit(1)
print("%d/%d verificações do livro de decisões passaram" % (len(TOTAL), len(TOTAL)))
