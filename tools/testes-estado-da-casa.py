#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova o `estado-da-casa.py`: o bloco que responde "como está a casa?".

O que se cobra:
  - lê os seis registros e não inventa o que falta (fonte ausente é dita);
  - a fila mostra o tipo, a quantidade e HÁ QUANTO TEMPO a mais velha espera (a fome visível);
  - a cobertura de capas usa o retrato medido, e diz "nenhum sem capa" quando é zero;
  - registro vazio não explode e não vira número falso.
"""
import datetime
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


def _agora_iso():
    """Agora em ISO — a régua é lida como 'medida há X h', então precisa ser recente."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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

    # 1b. prazo vencido tem nome (07/11/2026)
    for _dias, _esperado, _proibido in ((-3, "prazo vencido há 3 dia(s)", "-3 dia(s)"),
                                        (0, "vence hoje", "0 dia(s) restante"),
                                        (5, "5 dia(s) restante(s)", "vencido")):
        with open(os.path.join(tmp, "placar-estado.json"), "w", encoding="utf-8") as f:
            json.dump({"medido_em": _agora_iso(), "dias_restantes": _dias,
                       "prazo": "2026-11-12"}, f)
        _t = est.texto(est.estado())
        ok("régua com %s dia(s): %s" % (_dias, _esperado),
           _esperado in _t and _proibido not in _t, _t.splitlines()[4][:160])

    # 2a. PRANCHETA: o build que está no itch é dito, e sem prometer que sobe por aqui
    with open(os.path.join(tmp, "prancheta-build.json"), "w", encoding="utf-8") as f:
        json.dump({"build_id": "19604665", "medido_em": "2026-11-07T05:38:08Z"}, f)
    _bloco_prancheta = est.texto(est.estado())
    ok("o bloco diz qual build do PRANCHETA está no itch", "build 19604665" in _bloco_prancheta,
       _bloco_prancheta)
    ok("o bloco diz que esse build não sobe por aqui",
       "não sobe por aqui" in _bloco_prancheta, _bloco_prancheta)
    os.unlink(os.path.join(tmp, "prancheta-build.json"))
    ok("sem registro do PRANCHETA, o bloco não inventa linha",
       "PRANCHETA" not in est.texto(est.estado()))

    # 2b. os três números do canal aparecem cada um com nome (e nada de conta que o leitor faça só)
    with open(os.path.join(tmp, "capas-estado.json"), "w", encoding="utf-8") as f:
        json.dump({"no_canal": 169, "sem_capa": 0, "da_casa": 11, "outros_jogos": 158,
                   "com_capa_no_canal": 51, "medido_em": "2026-11-07T01:00:00Z"}, f)
    _bloco_outros = est.texto(est.estado())
    ok("o bloco diz quantos têm capa e quantos citam jogo da casa no título",
       "51 com capa da casa" in _bloco_outros and "11 citam jogo da casa no título" in _bloco_outros,
       _bloco_outros)
    ok("o bloco NÃO chuta 'de outros jogos' (o classificador só olha o título)",
       "outros jogos" not in _bloco_outros, _bloco_outros)
    ok("o bloco diz que nenhum da casa está sem capa",
       "nenhum da casa sem capa" in _bloco_outros, _bloco_outros)
    ok("o bloco não inventa razão para os de outros jogos (nada de 'por regra' sem medir)",
       "por regra" not in _bloco_outros, _bloco_outros)

    # 3. a régua de metas: idade visível, e vencida quando passa de 24 h
    with open(os.path.join(tmp, "placar-estado.json"), "w", encoding="utf-8") as f:
        json.dump({"medido_em": "2026-11-03T06:52:00Z", "dias_restantes": 9, "prazo": "2026-11-12"}, f)
    dados_regua = est.estado()
    ok("o estado carrega quando a régua foi medida", dados_regua["regua_medida_em"] == "2026-11-03T06:52:00Z",
       dados_regua["regua_medida_em"])
    ok("a idade da régua é calculada em horas", dados_regua["regua_horas"] and dados_regua["regua_horas"] > 24,
       dados_regua["regua_horas"])
    _bloco_regua = est.texto(dados_regua)
    ok("a régua velha aparece no bloco", "Régua de metas: medida há" in _bloco_regua, _bloco_regua)
    ok("régua de mais de 24 h é dita VENCIDA", "VENCIDA" in _bloco_regua, _bloco_regua)
    ok("o bloco mostra o prazo e os dias que a régua diz",
       "2026-11-12" in _bloco_regua and "9 dia(s)" in _bloco_regua, _bloco_regua)

    # A régua medida há poucas horas NÃO é vencida: a data é relativa ao agora,
    # não fixa (o CI pode rodar em qualquer dia).
    fresco = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(tmp, "placar-estado.json"), "w", encoding="utf-8") as f:
        json.dump({"medido_em": fresco, "dias_restantes": 5, "prazo": "2026-11-12"}, f)
    ok("régua fresca (2 h atrás) não é chamada de vencida",
       "VENCIDA" not in est.texto(est.estado()), est.texto(est.estado()))

    # 4. título longo cortado em palavra inteira (o número que o dono lê primeiro)
    ok("título curto não é cortado", est._corte("CEIFALUME 0.1") == "CEIFALUME 0.1")
    _longo = est._corte("CEIFALUME 0.1: 8 colheitas, 11 mudas plantadas, e mais um texto enorme aqui")
    ok("título longo termina em palavra inteira", _longo.endswith("…") and " ," not in _longo, _longo)
    _original = "CEIFALUME 0.1: 8 colheitas, 11 mudas plantadas, e mais um texto enorme aqui"
    _sem_reticencias = _longo[:-1]
    _proximo = _original[len(_sem_reticencias):len(_sem_reticencias) + 1]
    # fronteira de palavra: o próximo caractere do original não pode ser letra/número
    ok("o corte é prefixo do original e cai numa fronteira de palavra",
       _original.startswith(_sem_reticencias) and not _proximo.isalnum(),
       (_sem_reticencias, _proximo))
    _cortado = est._corte("a" * 60)
    ok("palavra única gigante não quebra (corta e avisa)", _cortado.endswith("…"), _cortado)

    # 5. capa faltando aparece como falta, não como zero
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
