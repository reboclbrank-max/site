#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova o `estado-da-casa.py`: o bloco que responde "como está a casa?".

O que se cobra:
  - lê os seis registros e não inventa o que falta (fonte ausente é dita);
  - a fila mostra o tipo, a quantidade e HÁ QUANTO TEMPO a mais velha espera (a fome visível);
  - a cobertura de capas usa o retrato medido, e diz "nenhum sem capa" quando é zero;
  - registro vazio não explode e não vira número falso.
"""
import importlib.util
import json
import os
import shutil
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("estado", os.path.join(RAIZ, "tools", "estado-da-casa.py"))
est = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(est)

res = []


def ok(nome, condicao, dado=None):
    res.append((nome, bool(condicao)))
    print(("OK  " if condicao else "FALHOU  ") + nome + (("  <%s>" % (dado,)) if not condicao and dado is not None else ""))


tmp = tempfile.mkdtemp(prefix="estado-da-casa-")
_original = est.POSTS
est.POSTS = tmp

try:
    # 1. casa sem registro nenhum: não inventa
    vazio = est.estado()
    ok("casa sem registro diz zero vídeos e zero fila",
       vazio["publicados"] == 0 and vazio["fila_pendentes"] == 0, vazio)
    ok("casa sem registro não inventa cobertura de capas",
       vazio["capas_no_canal"] is None and vazio["capas_sem_capa"] is None, vazio)
    texto_vazio = est.texto(vazio)
    ok("o bloco de casa vazia ainda diz o que sabe", "Vídeos publicados: 0" in texto_vazio, texto_vazio)

    # 2. casa com gente dentro
    with open(os.path.join(tmp, "youtube-publicados.json"), "w", encoding="utf-8") as f:
        json.dump({"publicados": [
            {"id": "AAA111bbb22", "titulo": "último vídeo publicado"},
            {"id": "CCC333ddd44", "titulo": "penúltimo"},
        ]}, f)
    with open(os.path.join(tmp, "capas-aplicadas.json"), "w", encoding="utf-8") as f:
        json.dump({"aplicadas": [{"id": "AAA111bbb22"}, {"id": "CCC333ddd44"}, {"id": "EEE555fff66"}]}, f)
    with open(os.path.join(tmp, "capas-estado.json"), "w", encoding="utf-8") as f:
        json.dump({"no_canal": 50, "sem_capa": 0, "medido_em": "2026-11-07T01:00:00Z"}, f)
    with open(os.path.join(tmp, "fila-tarefas.json"), "w", encoding="utf-8") as f:
        json.dump({"tarefas": [
            {"id": "medir-antiga", "tipo": "medir", "estado": "pendente",
             "criada": "2026-11-03T09:33:31Z"},
            {"id": "medir-nova", "tipo": "medir", "estado": "pendente",
             "criada": "2026-11-06T14:37:10Z"},
            {"id": "publicar-1", "tipo": "publicar", "estado": "pendente",
             "criada": "2026-11-06T20:35:27Z"},
            {"id": "ja-feita", "tipo": "medir", "estado": "feito", "criada": "2026-11-01T00:00:00Z"},
        ]}, f)
    with open(os.path.join(tmp, "orquestrador.json"), "w", encoding="utf-8") as f:
        json.dump({"pulsos": 132, "ultima_publicacao": "2026-11-07T00:19:53Z"}, f)

    dados = est.estado()
    ok("conta os vídeos publicados", dados["publicados"] == 2, dados["publicados"])
    ok("diz qual foi o último publicado", dados["ultimo_publicado"] == "AAA111bbb22", dados["ultimo_publicado"])
    ok("conta a fila só pelo que está pendente", dados["fila_pendentes"] == 3, dados["fila_pendentes"])
    ok("separa a fila por tipo", dados["fila_por_tipo"] == {"medir": 2, "publicar": 1}, dados["fila_por_tipo"])
    ok("aponta a tarefa mais velha", dados["fila_mais_velha"] == "medir-antiga", dados["fila_mais_velha"])
    ok("diz há quantas horas a mais velha espera (a fome, visível)",
       dados["fila_mais_velha_horas"] and dados["fila_mais_velha_horas"] > 24,
       dados["fila_mais_velha_horas"])
    ok("lê a cobertura de capas do retrato medido", dados["capas_no_canal"] == 50, dados["capas_no_canal"])

    bloco = est.texto(dados)
    ok("o bloco diz o tamanho do canal medido", "canal com 50 vídeos" in bloco, bloco)
    ok("o bloco diz que nenhum da casa está sem capa", "nenhum da casa sem capa" in bloco, bloco)
    ok("o bloco mostra a fila com tipo e tempo de espera",
       "medir 2" in bloco and "publicar 1" in bloco and "há" in bloco, bloco)
    ok("o bloco mostra os pulsos", "Pulsos: 132" in bloco, bloco)
    ok("o bloco data a medida das capas", "medido em 2026-11-07" in bloco, bloco)

    # 3. capa faltando aparece como falta, não como zero
    with open(os.path.join(tmp, "capas-estado.json"), "w", encoding="utf-8") as f:
        json.dump({"no_canal": 50, "sem_capa": 3, "medido_em": "2026-11-07T01:00:00Z"}, f)
    dados2 = est.estado()
    ok("capa faltando é dita em número", dados2["capas_sem_capa"] == 3, dados2["capas_sem_capa"])
    # NADA DE RAZÃO INVENTADA: o canal tem 169 vídeos e só 51 são da casa. "51 de 169" faria
    # parecer descuido, "169 de 169" seria mentira — o bloco diz os três números com nome.
    ok("capa faltando da casa aparece como falta da casa", "3 da casa sem capa" in est.texto(dados2),
       est.texto(dados2))
    _falso = dict(dados2, capas_no_canal=169, capas_sem_capa=0, capas_aplicadas=51)
    _t = est.texto(_falso)
    ok("o bloco não inventa '169 de 169' quando só 51 têm capa",
       "169 de 169" not in _t and "canal com 169 vídeos" in _t and "51 aplicada" in _t, _t)
    ok("o bloco diz quantos da casa faltam", "3 da casa sem capa" in est.texto(dados2),
       est.texto(dados2))

    # 4. --json é dado cru e legível
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = est.main(["estado-da-casa.py", "--json"])
    saida = json.loads(buf.getvalue())
    ok("--json imprime JSON válido", rc == 0 and isinstance(saida, dict), saida)
    ok("--json traz os mesmos campos do texto",
       {"publicados", "fila_pendentes", "capas_aplicadas"} <= set(saida), list(saida)[:4])
finally:
    est.POSTS = _original
    shutil.rmtree(tmp, ignore_errors=True)

certos = sum(1 for _, c in res if c)
print("\n%d/%d contratos do estado da casa passaram" % (certos, len(res)))
raise SystemExit(0 if certos == len(res) else 1)
