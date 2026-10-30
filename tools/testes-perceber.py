#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do perceber: o olho da casa.

O que este arquivo cobra é o que separa "saber o que fazer" de "seguir o relógio":
necessidade sem número não entra, canal cego é do dono, artefato velho é do robô, e a
fila recebe a tarefa — sem duplicar, sem inventar, sem quebrar o ciclo se a fila falhar.
"""
import datetime
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
    caminho = os.path.join(RAIZ, "tools", "perceber.py")
    spec = importlib.util.spec_from_file_location("perceber", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


p = carregar()
AGORA = datetime.datetime(2026, 10, 30, 12, 0, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------- canais cegos
def log_de(linhas_por_ciclo):
    return [{"quando": "01/10/2026 12:00 UTC", "linhas": l} for l in linhas_por_ciclo]


_cego = [{"telegram": "⚪ falta o segredo TELEGRAM_TOKEN + TELEGRAM_CHAT"}] * 6
_r = p.canais_cegos(lambda n: log_de(_cego)[:n], {"telegram": ["TELEGRAM_TOKEN", "TELEGRAM_CHAT"]})
ok("canal que nunca publicou vira necessidade do DONO", _r and _r[0]["quem"] == "dono", _r)
ok("o porquê traz o número de ciclos e o nome do segredo",
   _r and "6 ciclos" in _r[0]["porque"] and "TELEGRAM_TOKEN + TELEGRAM_CHAT" in _r[0]["porque"], _r)

_redacao = ([{"mastodon": "➖ sem chave ainda"}] * 3
            + [{"mastodon": "⚪ configuracao de publicacao ausente"}] * 3)
_r2 = p.canais_cegos(lambda n: log_de(_redacao)[:n], {"mastodon": ["MASTODON_URL"]})
ok("o reconhecimento não depende da redação antiga ('sem chave', 'configuracao ausente')",
   _r2 and _r2[0]["quem"] == "dono", _r2)

_publica = ([{"bluesky": "✅ postado 200"}] * 5)
ok("canal que publica NÃO vira necessidade",
   p.canais_cegos(lambda n: log_de(_publica)[:n], {"bluesky": ["BLUESKY_HANDLE"]}) == [])
ok("amostra menor que 5 ciclos não acusa canal",
   p.canais_cegos(lambda n: log_de(_cego)[:n], {"telegram": ["TELEGRAM_TOKEN"]}) != []
   and p.canais_cegos(lambda n: log_de(_cego[:3])[:n], {"telegram": ["TELEGRAM_TOKEN"]}) == [])

# ---------------------------------------------------------------- artefatos velhos
tmp = tempfile.mkdtemp(prefix="perceber-")
_raiz_antiga = p.RAIZ
p.RAIZ = tmp
os.makedirs(os.path.join(tmp, "posts"), exist_ok=True)
for caminho, _nome, _tipo in p.ARTEFATOS_VENCIVEIS:
    alvo = os.path.join(tmp, caminho)
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    open(alvo, "w").write("{}")
_velhos = p.artefatos_velhos(AGORA)
ok("arquivo recém-escrito NÃO vira necessidade", _velhos == [], [i["o_que"] for i in _velhos])

_antigo = (AGORA - datetime.timedelta(hours=48)).timestamp()
os.utime(os.path.join(tmp, "posts", "plano-do-dia.json"), (_antigo, _antigo))
_velhos = p.artefatos_velhos(AGORA)
ok("arquivo parado há 48h vira necessidade do ROBÔ",
   len(_velhos) == 1 and _velhos[0]["quem"] == "robô", _velhos)
ok("o porquê mede a idade em horas",
   _velhos and "48 h" in _velhos[0]["porque"], _velhos)
ok("a necessidade velha vira tarefa do tipo que a resolve",
   _velhos and _velhos[0]["tipo_fila"] == "pesquisar", _velhos)

os.remove(os.path.join(tmp, "posts", "aprendizado.json"))
_velhos = p.artefatos_velhos(AGORA)
ok("arquivo ausente também é necessidade (e diz 'ausente')",
   any("ausente" in i["porque"] for i in _velhos), [i["porque"] for i in _velhos])
p.RAIZ = _raiz_antiga

# ---------------------------------------------------------------- metas em risco
_placar = [
    {"meta": "itch: downloads", "alvo": "100", "observado": "47", "falta": "53",
     "por_dia": "4.15", "status": "EM_CURSO"},
    {"meta": "YouTube: shorts", "alvo": "4", "observado": "6", "falta": "0",
     "por_dia": "—", "status": "ATINGIDO"},
    {"meta": "Instagram: seguidores", "alvo": "50", "observado": "0", "falta": "50",
     "por_dia": "0.15", "status": "EM_CURSO"},
]
_r = p.metas_em_risco(_placar, dias_restantes=13)
ok("meta com ritmo alto vira necessidade", len(_r) == 1 and "itch: downloads" in _r[0]["o_que"], _r)
ok("meta batida e meta de ritmo baixo ficam de fora", all("shorts" not in i["o_que"] and
                                                          "Instagram" not in i["o_que"] for i in _r), _r)
ok("o porquê mostra falta, ritmo e prazo",
   _r and "53" in _r[0]["porque"] and "4.15" in _r[0]["porque"] and "13 dias" in _r[0]["porque"], _r)
ok("meta em risco enfileira publicação (é o que empurra número)",
   _r and _r[0]["tipo_fila"] == "publicar", _r)

# ---------------------------------------------------------------- repetição
ok("repetição acima do limite vira necessidade",
   len(p.repeticao_alta({"repeticao_desde_o_conserto": {"pct": 22.0, "ciclos": 9}})) == 1)
ok("repetição dentro do limite não vira nada",
   p.repeticao_alta({"repeticao_desde_o_conserto": {"pct": 4.0, "ciclos": 9}}) == [])
ok("sem medição de repetição, não inventa necessidade", p.repeticao_alta({}) == [])

# ---------------------------------------------------------------- fila travada
ok("tarefa que desistiu vira necessidade de reenfileirar",
   len(p.fila_travada({"tarefas": [{"tipo": "publicar", "estado": "falhou"}]})) == 1)
ok("fila saudável não vira nada", p.fila_travada({"tarefas": [{"tipo": "medir", "estado": "feito"}]}) == [])

# ---------------------------------------------------------------- kit esperando o dono
_r = p.kit_esperando([{"slug": "ceifalume", "quando": "2026-10-29T12:00:00Z"}], AGORA)
ok("vídeo pronto e não publicado vira necessidade do DONO", _r and _r[0]["quem"] == "dono", _r)
ok("o caminho do dono é a palavra PUBLICAR", _r and "PUBLICAR" in _r[0]["como"], _r)
ok("vídeo já publicado (com id) não vira nada", p.kit_esperando([{"slug": "x", "id": "abc"}], AGORA) == [])

# ---------------------------------------------------------------- pendências paradas
_r = p.pendencias_paradas({"quando": "2026-10-20T12:00:00Z",
                           "itens": [{"id": "devlog", "titulo": "devlog no itch",
                                      "estado": "esperando o dono", "como": "1 clique"}]}, AGORA)
ok("pendência parada há mais de 2 dias é lembrada com número",
   _r and "dia(s)" in _r[0]["porque"], _r)
ok("pendência de hoje não vira cobrança",
   p.pendencias_paradas({"quando": "2026-10-30T06:00:00Z",
                         "itens": [{"id": "x", "titulo": "x", "estado": "esperando o dono"}]}, AGORA) == [])
ok("pendência feita nunca vira cobrança",
   p.pendencias_paradas({"quando": "2026-10-01T00:00:00Z",
                         "itens": [{"id": "x", "titulo": "x", "estado": "feito"}]}, AGORA) == [])

# ---------------------------------------------------------------- o livro de verdade
_real = p.perceber(agora=AGORA, enfileirar=False)
ok("o perceber do repositório roda e separa robô × dono",
   isinstance(_real["robo"], list) and isinstance(_real["dono"], list))
ok("toda necessidade tem número no porquê",
   all(any(ch.isdigit() for ch in i["porque"]) for i in _real["robo"] + _real["dono"]),
   [i["porque"] for i in _real["robo"] + _real["dono"] if not any(ch.isdigit() for ch in i["porque"])])
ok("toda necessidade diz quem faz e como verificar",
   all(i["quem"] in ("robô", "dono") and i["como"] and i["verifica"]
       for i in _real["robo"] + _real["dono"]))
ok("os canais cegos aparecem como do dono (com o segredo nomeado)",
   any("segredo" in i["porque"] for i in _real["dono"]), [i["o_que"] for i in _real["dono"]])
ok("nenhuma necessidade se repete (chave única)",
   len({i.get("chave") or i["o_que"] for i in _real["robo"] + _real["dono"]})
   == len(_real["robo"] + _real["dono"]))
ok("a lei está escrita: necessidade sem número não entra",
   "sem número não entra" in _real["_lei"])

# ---------------------------------------------------------------- enfileirar de verdade
_tmp2 = tempfile.mkdtemp(prefix="perceber-fila-")
os.makedirs(os.path.join(_tmp2, "posts"), exist_ok=True)
_fila = p.carregar_fila()                      # carrega do RAIZ real (o módulo é o mesmo)
_fila.ARQUIVO = os.path.join(_tmp2, "posts", "fila-tarefas.json")
_dados = _fila.carregar(_fila.ARQUIVO)
_antes = len(_dados["tarefas"])
_criada = _fila.adicionar(_dados, "publicar", motivo="teste", chave="meta-x")
_fila.gravar(_dados, _fila.ARQUIVO)
ok("a fila aceita a tarefa com a chave da necessidade",
   _criada and _criada["chave"] == "meta-x" and len(_dados["tarefas"]) == _antes + 1)
_dados2 = _fila.carregar(_fila.ARQUIVO)
ok("enfileirar duas vezes não duplica (chave)",
   _fila.adicionar(_dados2, "publicar", motivo="teste", chave="meta-x") is None)

# ---------------------------------------------------------------- markdown e escrita
_md = p.markdown(_real)
ok("o markdown separa robô e dono", "O robô já colocou na fila" in _md and "Espera o dono" in _md)
ok("o markdown diz 'nada pendente' quando não há nada (sem inventar)",
   "Nada pendente" in p.markdown({"quando": "x", "_lei": "l", "robo": [], "dono": [],
                                  "enfileiradas": [], "contagem": {"robo": 0, "dono": 0,
                                                                   "enfileiradas": 0}}))
_js, _mds = os.path.join(_tmp2, "percebido.json"), os.path.join(_tmp2, "percebido.md")
_a1, _a2 = p.SAIDA_JSON, p.SAIDA_MD
p.SAIDA_JSON, p.SAIDA_MD = _js, _mds
_out, sys.stdout = sys.stdout, io.StringIO()
try:
    p.main([])
finally:
    sys.stdout = _out
    p.SAIDA_JSON, p.SAIDA_MD = _a1, _a2
ok("grava percebido.json e .md", os.path.exists(_js) and os.path.exists(_mds))
ok("escrita atômica (sem .tmp)", not os.path.exists(_js + ".tmp") and not os.path.exists(_mds + ".tmp"))
ok("o json gravado tem contagem", "contagem" in json.load(open(_js, encoding="utf-8")))

# ---------------------------------------------------------------- integração com o pulso
_fonte_orq = open(os.path.join(RAIZ, "tools", "orquestrador.py"), encoding="utf-8").read()
ok("o pulso consulta a fila antes do relógio",
   "usar_fila" in _fonte_orq and "if da_fila:" in _fonte_orq)
_fonte_wf = open(os.path.join(RAIZ, ".github", "workflows", "marketing-24h.yml"),
                 encoding="utf-8").read()
ok("o ciclo roda o perceber antes do pulso",
   _fonte_wf.index("tools/perceber.py") < _fonte_wf.index("tools/orquestrador.py"))

print()
if FALHAS:
    print("%d de %d verificações do perceber FALHARAM" % (len(FALHAS), len(TOTAL)))
    sys.exit(1)
print("%d/%d verificações do perceber passaram" % (len(TOTAL), len(TOTAL)))
