#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do retrato "o que acontece quando você mexe em algo" e das contas de agenda.

Duas coisas estão em julgamento aqui:

1. as contas de cron (hora UTC -> Brasília, quantos disparos por dia, o que cai fora da janela);
2. o documento gerado bater com os workflows — se um workflow novo aparece e o documento não muda,
   o retrato vira mentira educada, que é o pior tipo.
"""
import importlib.util
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _modulo(nome_arquivo, apelido):
    spec = importlib.util.spec_from_file_location(apelido, os.path.join(RAIZ, "tools", nome_arquivo))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ag = _modulo("auditar-agendas.py", "ag")
oq = _modulo("o-que-acontece.py", "oq")

certos = [0]
falhas = [0]


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos[0] += 1
        print("✔ " + nome)
    else:
        falhas[0] += 1
        print("✗ " + nome + (" — " + str(detalhe)[:300] if detalhe else ""))


# ------------------------------------------------------------------ contas de cron
ok("*/20 vira 3 vezes por hora", ag._expandir("*/20", 60) == [0, 20, 40])
ok("lista de minutos é lida como lista", ag._expandir("9,29,49", 60) == [9, 29, 49])
ok("faixa 12-23 é lida como faixa", ag._expandir("12-23", 24) == list(range(12, 24)))
ok("faixa com passo (0-23/6) é lida", ag._expandir("0-23/6", 24) == [0, 6, 12, 18])
ok("* é a hora inteira", len(ag._expandir("*", 24)) == 24)

_horas, _local, _por_dia = ag.partes("40 3,9,15,21 * * *")
ok("UTC vira Brasília (3h UTC = 0h local)", _local == [0, 6, 12, 18], _local)
ok("4 horas x 1 minuto = 4 disparos por dia", _por_dia == 4, _por_dia)

_, _, _por_dia_semanal = ag.partes("0 12 * * 1")
ok("cron semanal não finge ser diário (por_dia = None)", _por_dia_semanal is None, _por_dia_semanal)

_r = ag.resumo(RAIZ)
_arquivos = len([f for f in os.listdir(os.path.join(RAIZ, ".github", "workflows")) if f.endswith(".yml")])
ok("o resumo conta todos os workflows", _r["workflows"] == _arquivos, (_r["workflows"], _arquivos))
ok("o resumo soma os disparos das agendas",
   _r["disparos_por_dia"] == sum(l["por_dia"] or 0 for l in ag.auditar(RAIZ)), _r)
ok("todo cron do repositório entra na auditoria",
   len(ag.auditar(RAIZ)) == len(ag.crons_do_repositorio(RAIZ)), len(ag.auditar(RAIZ)))
ok("a auditoria sabe quantos crons caem fora da janela 9-22h",
   _r["crons_fora_da_janela"] == len([l for l in ag.auditar(RAIZ) if l["fora_da_janela"]]), _r)

# ------------------------------------------------------------------ horas legíveis
ok("sequência longa vira faixa com en dash",
   oq.horas_compactas([0, 6, 7] + list(range(12, 24))) == "00h, 06h, 07h, 12h–23h",
   oq.horas_compactas([0, 6, 7] + list(range(12, 24))))
ok("dois vizinhos ficam dois, não faixa", oq.horas_compactas([0, 1]) == "00h, 01h")
ok("lista vazia não inventa hora", oq.horas_compactas([]) == "—")

# ------------------------------------------------------------------ leitura dos workflows
_caminhos = oq._caminhos_do_push(
    'on:\n  push:\n    branches: [main]\n    paths:\n      - "tools/**"\n      - posts/**\n'
    'permissions:\n')
ok("caminho do push sai sem aspas", _caminhos == ["tools/**", "posts/**"], _caminhos)

_c1 = oq._cadeados('on:\n  workflow_dispatch:\n    inputs:\n      confirmacao:\n'
                   '        description: "digite PUBLICAR"\n')
ok("cadeado por 'confirmacao' é reconhecido", [c["campo"] for c in _c1] == ["confirmacao"], _c1)
ok("a palavra do cadeado é a que se digita", _c1 and _c1[0]["palavra"] == "PUBLICAR", _c1)
_c2 = oq._cadeados('on:\n  workflow_dispatch:\n    inputs:\n      publicar:\n'
                   '        description: "PUBLICAR envia · ENSAIO simula · vazio só grava"\n')
ok("cadeado por 'publicar' é reconhecido", [c["campo"] for c in _c2] == ["publicar"], _c2)
ok("as palavras do cadeado saem todas", _c2 and _c2[0]["palavra"] == "PUBLICAR / ENSAIO", _c2)
_c3 = oq._cadeados('on:\n  workflow_dispatch:\n    inputs:\n      confirmacao:\n'
                   '        description: "digite PRIVAR ou APAGAR"\n')
ok("cada workflow tem a sua palavra (PRIVAR ou APAGAR)", _c3 and _c3[0]["palavra"] == "PRIVAR / APAGAR",
   _c3)
ok("cadeado repetido aparece uma vez só",
   len(oq._cadeados('on:\n  workflow_dispatch:\n    inputs:\n      publicar:\n'
                    '        description: "PUBLICAR"\n') ) == 1)
ok("input comum não vira cadeado",
   oq._cadeados('on:\n  workflow_dispatch:\n    inputs:\n      modo:\n'
                '        description: "estado|auto"\n') == [])

with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "x.yml")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("name: x\n# MANCHETE EM CAIXA ALTA QUE NÃO EXPLICA NADA (07/11/2026)\n"
                "# Explica de verdade o que o robô faz aqui.\nimport os\n")
    _d = oq.descricao(open(caminho, encoding="utf-8").read())
    ok("manchete em caixa alta não é usada como descrição", _d.startswith("Explica de verdade"), _d)

    vazio = os.path.join(tmp, "y.yml")
    with open(vazio, "w", encoding="utf-8") as f:
        f.write("name: y\non:\n  workflow_dispatch:\n")
    _d2 = oq.descricao(open(vazio, encoding="utf-8").read())
    ok("workflow sem comentário diz que não tem, em vez de ficar em branco",
       "sem comentário" in _d2, _d2)

# ------------------------------------------------------------------ o que sobe sozinho
_projetos = oq.projetos_do_itch(RAIZ)
ok("a lista PROJETOS do administrador é lida do código", isinstance(_projetos, dict) and _projetos,
   _projetos)
ok("o ceifalume é o projeto administrado", "ceifalume" in (_projetos or {}), _projetos)
ok("cada projeto tem pasta e canal",
   all(p.get("pasta") and p.get("canal") for p in (_projetos or {}).values()), _projetos)

_builds = oq.jogos_com_build_no_repositorio(RAIZ)
ok("o ceifalume tem build versionado", "ceifalume" in _builds, _builds)
ok("o build do ceifalume tem mais que a página de venda", (_builds.get("ceifalume", ("", 0))[1]) > 3,
   _builds.get("ceifalume"))
ok("o prancheta NÃO é tratado como build do repositório", "prancheta" not in _builds, _builds)

# ------------------------------------------------------------------ o documento
_doc = oq.gerar(RAIZ)
_agenda = {l["workflow"] for l in ag.auditar(RAIZ)}
ok("todo workflow com agenda aparece no retrato",
   all(("`%s`" % n) in _doc for n in _agenda), sorted(n for n in _agenda if ("`%s`" % n) not in _doc))
_dados = oq.levantar(RAIZ)
ok("todo workflow que roda no push aparece no retrato",
   all(("`%s`" % i["nome"]) in _doc for i in _dados["push"]),
   [i["nome"] for i in _dados["push"] if ("`%s`" % i["nome"]) not in _doc])
ok("o retrato conta quantos workflows só rodam por pedido",
   ("**%d** workflows não têm agenda" % len(_dados["manual_sem_agenda"])) in _doc,
   len(_dados["manual_sem_agenda"]))
ok("o retrato diz os disparos automáticos por dia",
   ("**%d disparos automáticos por dia**" % _dados["resumo"]["disparos_por_dia"]) in _doc,
   _dados["resumo"]["disparos_por_dia"])
_cad_path = os.path.join(RAIZ, "posts", "cadencia.json")
if os.path.exists(_cad_path):
    import json as _j
    _cad = _j.load(open(_cad_path, encoding="utf-8"))
    ok("o retrato diz o que o cron pede", ("**%d disparos automáticos por dia**"
                                           % _dados["resumo"]["disparos_por_dia"]) in _doc,
       _dados["resumo"]["disparos_por_dia"])
    ok("o retrato diz o que o GitHub ENTREGOU (não só o que o cron pede)",
       ("**%s/dia**" % _cad.get("total_medido_por_dia")) in _doc, _cad.get("total_medido_por_dia"))
    ok("o retrato nomeia o pior caso da agenda", "O pior caso é" in _doc)
    ok("o retrato explica que cron é melhor esforço", "melhor esforço" in _doc)
else:
    ok("sem cadência medida, o retrato não afirma entrega", "Entrega medida do agendador" not in _doc)

# a tabela não pode repetir a promessa do cron sem a entrega medida ao lado
import json as _json_cad
_cad_caminho = os.path.join(RAIZ, "posts", "cadencia.json")
_medidos = {}
if os.path.exists(_cad_caminho):
    for _i in _json_cad.load(open(_cad_caminho, encoding="utf-8")).get("linhas") or []:
        if _i.get("medido_por_dia") is not None:
            _medidos[_i["workflow"]] = _i
_linhas_tabela = [x for x in _doc.splitlines() if x.startswith("| ") and "`" in x]
_faltando = [n for n in _medidos if not any(("`%s`" % n) in x and "entregou" in x for x in _linhas_tabela)]
ok("na tabela da agenda, quem foi medido mostra o que ENTREGOU", not _faltando, _faltando)
ok("nenhuma linha promete 'pulsos/dia' sem dizer quanto entregou de verdade",
   not [x for x in _linhas_tabela if "pulsos/dia" in x and "entregou" not in x],
   [x[:90] for x in _linhas_tabela if "pulsos/dia" in x and "entregou" not in x])
ok("a linha do pulso mostra a conta inteira (pedido, entregue e porcentagem)",
   _medidos.get("marketing-24h") is None or any(
       "entregou %s/dia" % _medidos["marketing-24h"]["medido_por_dia"] in x
       and ("%.1f%%" % _medidos["marketing-24h"]["entrega_pct"]) in x for x in _linhas_tabela),
   [x[:90] for x in _linhas_tabela if "marketing-24h" in x])

ok("o retrato mostra a faixa de horas do pulso, não 'todas as horas'",
   "03h, 04h, 09h–21h" in _doc or "03h, 04h, 09h" in _doc, _doc[_doc.find("marketing-24h") - 80:
                                                                 _doc.find("marketing-24h") + 40])
ok("o retrato diz que o push do ceifalume não dispara teste",
   "não dispara teste nenhum" in _doc)
_sem_teste = []
for i in _dados["push"]:
    for c in i["caminhos"]:
        if c.startswith("ceifalume") or c.startswith("jogos"):
            _sem_teste.append((i["nome"], c))
ok("se algum push passar a testar ceifalume/jogos, a frase acima vira mentira e este contrato avisa",
   not _sem_teste, _sem_teste)
_registro_prancheta = os.path.join(RAIZ, "posts", "prancheta-build.json")
if os.path.exists(_registro_prancheta):
    import json as _json
    _build = _json.load(open(_registro_prancheta, encoding="utf-8")).get("build_id")
    ok("o retrato diz qual build do PRANCHETA o itch serve", ("**%s**" % _build) in _doc, _build)
    ok("o retrato diz quando a casa viu esse build", "a casa viu em" in _doc)
    ok("o retrato diz que build novo vira fato, não post na marra",
       "vira fato no repertório" in _doc)
else:
    ok("sem registro do PRANCHETA, o retrato não afirma build nenhum", "a casa viu em" not in _doc)

ok("o retrato lista o prancheta como 'não sobe sozinho'",
   "`prancheta`" in _doc and "atualizar é upload no itch" in _doc)

_atual = open(os.path.join(RAIZ, "O-QUE-ACONTECE.md"), encoding="utf-8").read() \
    if os.path.exists(os.path.join(RAIZ, "O-QUE-ACONTECE.md")) else ""
ok("O-QUE-ACONTECE.md está em dia com os workflows (o retrato não envelhece)",
   _atual == _doc, "rode: python3 tools/o-que-acontece.py")

ok("--conferir aprova o documento em dia", oq.main(["--conferir"]) == 0)

_salvo = oq.SAIDA
with tempfile.TemporaryDirectory() as tmp:
    oq.SAIDA = os.path.join(tmp, "velho.md")
    with open(oq.SAIDA, "w", encoding="utf-8") as f:
        f.write("# retrato velho\n")
    _codigo = oq.main(["--conferir"])
    oq.SAIDA = _salvo
ok("--conferir reprova documento velho", _codigo == 1, _codigo)

print("\n%d/%d contratos do retrato passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
