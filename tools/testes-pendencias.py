#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testa o medidor de pendências — sem rede, com páginas de mentira.

O que ele protege:
  * o detector reconhece o post do vídeo na página pública de devlog (e não reconhece quando
    ele não está lá — falso positivo faria a casa achar que publicou);
  * "feito" nunca é deduzido de página vazia ou de erro HTTP;
  * o aviso ao dono sai uma vez por mudança de estado, não todo dia;
  * nada do relatório carrega cookie, chave ou segredo.
"""
import importlib.util
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("pend", os.path.join(RAIZ, "tools", "pendencias-do-dono.py"))
pend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pend)

# A SUÍTE NÃO ESCREVE NA CASA (06/11/2026): o módulo grava pendencias-do-dono.json/.md e lê o
# registro do itch. Rodando contra os caminhos de produção, cada execução reescrevia dois
# arquivos do repositório e reescrevia o itch-builds.json (com "restaura no fim", que falha se o
# teste estourar no meio). Agora tudo aponta para cópias descartáveis.
import tempfile as _temp
_BANCADA = _temp.mkdtemp(prefix="pendencias-")
pend.SAIDA_JSON = os.path.join(_BANCADA, "pendencias-do-dono.json")
pend.SAIDA_MD = os.path.join(_BANCADA, "pendencias-do-dono.md")
pend.CAMINHO_BUILDS = os.path.join(_BANCADA, "itch-builds.json")
import shutil as _shutil
_origem_builds = os.path.join(RAIZ, "posts", "itch-builds.json")
if os.path.exists(_origem_builds):
    _shutil.copy(_origem_builds, pend.CAMINHO_BUILDS)

certos, falhas = [], []


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos.append(nome)
        print("OK  " + nome)
    else:
        falhas.append((nome, detalhe))
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe else ""))


# Página no formato REAL medido em 30/10 (a estrutura de <a class="title"> do itch).
PAGINA_SEM_POST = """<ul id="blog_post_list_1" class="blog_post_list_widget base_widget"><li>
<div><a href="https://rebocl-brank.itch.io/ceifalume/devlog/1675714/1-semana-de-ceifalume"
class="title">1 semana de Ceifalume: o que vem na 0.2 (e eu quero sua opinião)</a></div></li>
<li><div><a href="https://rebocl-brank.itch.io/ceifalume/devlog/1660000/01-no-ar"
class="title">0.1 no ar: a fazenda não dorme</a></div></li></ul>"""

PAGINA_COM_POST = PAGINA_SEM_POST.replace(
    "<li>",
    '<li><div><a href="https://rebocl-brank.itch.io/ceifalume/devlog/1690000/ceifalume-gameplay" '
    'class="title">O CEIFALUME jogando sozinho: 2 minutos de gameplay</a></div>'
    '<div>assistir: https://youtu.be/GuE7af6dYo8</div></li><li>', 1)

ok("reconhece o post do vídeo pela página pública", pend.devlog_do_video_saiu(PAGINA_COM_POST))
ok("NÃO reconhece quando o post não está lá", not pend.devlog_do_video_saiu(PAGINA_SEM_POST))
ok("página vazia não vira 'publicado'", not pend.devlog_do_video_saiu(""))
ok("HTML de erro não vira 'publicado'", not pend.devlog_do_video_saiu("<h1>403 Forbidden</h1>"))
ok("lista os títulos dos posts que já existem",
   pend.posts_visiveis(PAGINA_SEM_POST) == ["1 semana de Ceifalume: o que vem na 0.2 (e eu quero sua opinião)",
                                            "0.1 no ar: a fazenda não dorme"],
   pend.posts_visiveis(PAGINA_SEM_POST))
ok("o link do vídeo sozinho já basta como marca",
   pend.devlog_do_video_saiu("<p>veja https://youtu.be/GuE7af6dYo8</p>"))
ok("marca em caixa alta também conta",
   pend.devlog_do_video_saiu("<p>GU E7AF6DYO8</p>") or pend.devlog_do_video_saiu("<p>gue7af6dyo8</p>"))

# ---- o relatório (sem rede: as funções de busca são trocadas)
_original = pend.buscar
pend.buscar = lambda url, timeout=30: (200, PAGINA_SEM_POST if "devlog" in url else "<html>jogo</html>")
rel = pend.montar({"pendentes_em": []})
pend.buscar = _original

ok("o relatório lista os itens", len(rel["itens"]) >= 2, len(rel["itens"]))
ok("com o post ausente, o devlog fica visível e NÃO como feito",
   any(i["id"] == "itch-devlog-gameplay" and i["estado"] != "feito" for i in rel["itens"]))
ok("o YouTube aparece como feito",
   any(i["id"] == "youtube-gameplay" and i["estado"] == "feito" for i in rel["itens"]))

# REGRA NOVA (31/10/2026): pendência é o que o dono PODE resolver. O devlog do itch não é: o
# painel dá 403 (Cloudflare) para IP de datacenter e a API oficial não tem endpoint de devlog
# (docs/sondagens/ITCH-DEVLOG-SEM-CAMINHO-AUTOMATICO.json). Pedir o impossível todo dia é o
# jeito mais rápido de o dono parar de ler o aviso.
_devlog = [i for i in rel["itens"] if i["id"] == "itch-devlog-gameplay"][0]
ok("o devlog sem caminho automático não conta como pendência do dono",
   "itch-devlog-gameplay" not in rel["pendentes_em"], rel["pendentes_em"])
ok("ele também não se esconde: aparece na lista de sem caminho automático",
   "itch-devlog-gameplay" in rel["sem_caminho_automatico_em"], rel["sem_caminho_automatico_em"])
ok("o item sem caminho diz onde o conteúdo chega ao jogador",
   len(_devlog.get("coberto_em") or []) >= 2, _devlog.get("coberto_em"))
ok("o item sem caminho cita a sondagem que provou isso",
   os.path.exists(os.path.join(pend.RAIZ, _devlog.get("sondagem") or "")),
   _devlog.get("sondagem"))
ok("a medida do devlog cita o 403 do Cloudflare e a falta de endpoint na API",
   "403" in _devlog["medido"] and "API" in _devlog["medido"], _devlog["medido"])
ok("nenhum item é ao mesmo tempo pendente e sem caminho",
   not (set(rel["pendentes_em"]) & set(rel["sem_caminho_automatico_em"])))
ok("o dono não fica com tarefa nenhuma nesta medição", rel["pendentes_em"] == [],
   rel["pendentes_em"])

# O item que só existe porque medimos a PÁGINA do itch (não o log do butler).
_pagina = [i for i in rel["itens"] if i["id"] == "itch-pagina-abre-build"][0]
ok("existe um item sobre o que a página do itch realmente entrega", _pagina is not None)
ok("ele não conta como pendência do dono",
   "itch-pagina-abre-build" not in rel["pendentes_em"], rel["pendentes_em"])
ok("com a conferência por sha256 mostrando conteúdo igual, o item é FEITO",
   _pagina["estado"] == "feito", _pagina["estado"])
ok("a medida dele mostra arquivo por arquivo (IGUAL/DIFERENTE)",
   "IGUAL" in _pagina["medido"] and "DIFERENTE" in _pagina["medido"], _pagina["medido"])
ok("a medida dele diz que o jogo que o jogador recebe é o do repositório",
   "é o do repositório" in _pagina["medido"], _pagina["medido"])
ok("a medida dele cita o GIF da descrição como caminho do vídeo",
   "GIF da descrição" in _pagina["medido"], _pagina["medido"])

# e se a conferência disser o contrário, o item volta a ser limitação medida (não tarefa)
import json as _json
# a cópia da bancada, não o registro da casa (o módulo lê pend.CAMINHO_BUILDS)
_caminho_builds = pend.CAMINHO_BUILDS
_guardado_builds = open(_caminho_builds, encoding="utf-8").read()
try:
    _d = _json.loads(_guardado_builds)
    _d["builds"][0]["conferencia_do_servido"]["jogo_igual_ao_repo"] = False
    open(_caminho_builds, "w", encoding="utf-8").write(_json.dumps(_d))
    _rel_dif = pend.montar()
    _item_dif = [i for i in _rel_dif["itens"] if i["id"] == "itch-pagina-abre-build"][0]
    ok("se o servido divergir do repositório, o item vira limitação medida (não tarefa)",
       _item_dif["estado"] == "sem caminho automático"
       and "itch-pagina-abre-build" not in _rel_dif["pendentes_em"], _item_dif["estado"])
finally:
    open(_caminho_builds, "w", encoding="utf-8").write(_guardado_builds)
ok("quando o servido é igual, ele cita a conferência e o GIF como prova/caminho",
   ("sha256" in _pagina["medido"] or "IGUAL" in _pagina["medido"])
   and "GIF da descrição" in _pagina["medido"], _pagina["medido"])
_cobertura_devlog = " ".join(_devlog.get("coberto_em") or [])
ok("a cobertura do devlog não mente dizendo que o build do canal chega ao jogador",
   "build no ar (2257110)" not in _cobertura_devlog, _cobertura_devlog)

# o aviso continua sendo sobre MUDANÇA de pendência de verdade
_sem_mudanca = pend.montar({"pendentes_em": rel["pendentes_em"]})
ok("NÃO avisa quando o estado é o mesmo", _sem_mudanca["mudou_desde_o_ultimo"] is False)
_com_pendencia = pend.montar({"pendentes_em": ["itch-devlog-gameplay"]})
ok("avisa quando a lista de pendências do dono muda de verdade",
   _com_pendencia["mudou_desde_o_ultimo"] is True)

# ---- quando o dono publicar, o medidor percebe sozinho
pend.buscar = lambda url, timeout=30: (200, PAGINA_COM_POST if "devlog" in url else "<html>jogo</html>")
rel_feito = pend.montar({"pendentes_em": rel["pendentes_em"]})
pend.buscar = _original
ok("com o post no ar, o item vira feito (sem ninguém avisar)",
   any(i["id"] == "itch-devlog-gameplay" and i["estado"] == "feito" for i in rel_feito["itens"]))

_texto_aviso = pend.texto_do_aviso(rel)
ok("o aviso mostra só o que falta", "itch-devlog-gameplay" not in _texto_aviso)
ok("o aviso tem o link público do devlog", pend.DEVLOG_PUBLICO in _texto_aviso)
ok("o aviso não carrega segredo nem cookie",
   not any(p in _texto_aviso.lower() for p in ("cookie", "itcg", "token", "bearer")))

# ---- o relatório gravado é JSON válido e não vaza credencial
pend.escrever(rel)
_salvo = json.load(open(pend.SAIDA_JSON, encoding="utf-8"))
ok("o relatório é JSON válido com itens", isinstance(_salvo.get("itens"), list) and len(_salvo["itens"]) >= 2)
ok("o relatório não contém cookie nem chave",
   not any(p in json.dumps(_salvo).lower() for p in ("itch_cookie", "itcg", "api_key", "bearer")))
ok("o .md foi escrito", os.path.getsize(pend.SAIDA_MD) > 200)

# ---- O RELATÓRIO ABRE COM O ESTADO DA CASA (07/11/2026)
# O dono pediu que o chat mostre o que a casa já sabe: quantos vídeos, quantas capas de quantas,
# o tamanho e a idade da fila. Isso não pode depender de abrir seis JSON à mão.
_md = open(pend.SAIDA_MD, encoding="utf-8").read()
ok("o relatório tem a seção Estado da casa", "## Estado da casa" in _md,
   _md[_md.find("## Estado da casa"):][:80])
ok("o estado da casa diz quantos vídeos foram publicados", "Vídeos publicados:" in _md)
ok("o estado da casa diz a cobertura de capas", "Capas da casa:" in _md)
ok("o estado da casa diz o tamanho da fila", "Fila:" in _md,
   [l for l in _md.splitlines() if l.startswith("- Fila:")])
# ---- canais desligados aparecem uma vez, com motivo (07/11/2026) ---------------------------
ok("o relatório tem a seção dos canais desligados", "## Canais desligados por decisão" in _md,
   _md[_md.find("## Canais"):][:80])
ok("os três canais desligados estão nomeados",
   all(nome in _md for nome in ("telegram", "mastodon", "discord")),
   [n for n in ("telegram", "mastodon", "discord") if n not in _md])
ok("cada canal desligado leva o motivo junto", _md.count("decisão de 07/11/2026") >= 3,
   _md.count("decisão de 07/11/2026"))

ok("o estado da casa vem antes das pendências",
   _md.find("## Estado da casa") < _md.find("| item | estado | como |"),
   (_md.find("## Estado da casa"), _md.find("| item | estado | como |")))

# ---- o build no itch deixa de ser pendência FANTASMA quando há build com prova
# MEDIDO (31/10/2026): o item ficava "esperando o dono" para sempre porque a única medida era
# "a página respondeu 200" — verdade mesmo sem build nenhum. Com o build 2257110 no ar, o
# relatório continuava pedindo ao dono o que já estava feito.
import tempfile as _tf, shutil as _sh
_tmp = _tf.mkdtemp()
_orig_json = pend.CAMINHO_BUILDS        # já é a cópia descartável montada no topo
_guardado = open(_orig_json, encoding="utf-8").read() if os.path.exists(_orig_json) else None
try:
    with open(_orig_json, "w", encoding="utf-8") as f:
        json.dump({"builds": [{"slug": "ceifalume", "build": "2257110",
                               "versao": "2026.10.31-0046",
                               "link": "https://rebocl-brank.itch.io/ceifalume",
                               "prova": "push run 41151936756; status run 41152028164 IGUAL"}]}, f)
    _rel_com = pend.montar()
    _item = [i for i in _rel_com["itens"] if i["id"] == "itch-build-selo"][0]
    ok("com build e prova no registro, o item do build é FEITO", _item["estado"] == "feito",
       _item["estado"])
    ok("a medida do build cita o número do build", "2257110" in _item["medido"], _item["medido"])
    ok("a medida do build cita a prova (run do push)", "41151936756" in _item["medido"],
       _item["medido"])
    with open(_orig_json, "w", encoding="utf-8") as f:
        json.dump({"builds": [{"slug": "ceifalume", "build": "", "prova": ""}]}, f)
    _rel_sem = pend.montar()
    _item2 = [i for i in _rel_sem["itens"] if i["id"] == "itch-build-selo"][0]
    ok("build sem id nem prova NÃO vira feito", _item2["estado"] != "feito", _item2["estado"])
    with open(_orig_json, "w", encoding="utf-8") as f:
        json.dump({"builds": [{"slug": "ceifalume", "build": "2257110", "prova": ""}]}, f)
    ok("build com id mas SEM prova também não vira feito",
       [i for i in pend.montar()["itens"] if i["id"] == "itch-build-selo"][0]["estado"] != "feito")
finally:
    if _guardado is None:
        os.remove(_orig_json)
    else:
        open(_orig_json, "w", encoding="utf-8").write(_guardado)
    _sh.rmtree(_tmp, ignore_errors=True)

# ------------------------------------------------------------------ a agenda medida aparece
# (07/11/2026) O relatório diário passa a abrir com a cadência medida: o cron pede 63 disparos
# por dia e o GitHub entregou 14 na semana. É a primeira coisa que explica um dia parado.
import tempfile as _tempfile

_salvo_md = pend.SAIDA_MD
_pasta_cad = _tempfile.mkdtemp(prefix="pend-cadencia-")
pend.SAIDA_MD = os.path.join(_pasta_cad, "pendencias.md")
_cad_path = os.path.join(RAIZ, "posts", "cadencia.json")
_cad_antes = open(_cad_path, encoding="utf-8").read() if os.path.exists(_cad_path) else None
try:
    with open(_cad_path, "w", encoding="utf-8") as f:
        json.dump({"medido_em": "2026-11-07", "janela_dias": 7,
                   "total_esperado_por_dia": 63, "total_medido_por_dia": 14.02,
                   "linhas": [{"workflow": "marketing-24h", "esperado_por_dia": 45,
                               "medido_por_dia": 1.86, "entrega_pct": 4.1},
                              {"workflow": "medir-itch", "esperado_por_dia": 1,
                               "medido_por_dia": 0.86, "entrega_pct": 86.0}],
                   "corrente": {"veredito": "ATRASADA: 2 pulso(s) não saíram desde 07/11 09:00",
                                "pulsos_perdidos": 2,
                                "buracos": [{"desde": "a", "ate": "b", "pulsos_perdidos": 2}]}}, f)
    pend.escrever(pend.montar())
    _texto_cad = open(pend.SAIDA_MD, encoding="utf-8").read()
    ok("o relatório diz o que o cron pede", "o cron pede **63**" in _texto_cad,
       _texto_cad[:200])
    ok("o relatório diz o que o GitHub entregou", "entregou **14.02/dia**" in _texto_cad)
    ok("o relatório nomeia a pior entrega com número",
       "marketing-24h 4.1%" in _texto_cad,
       [l for l in _texto_cad.splitlines() if "Agenda" in l])
    ok("a entrega melhor não é chamada de pior", "medir-itch 86.0%" not in _texto_cad,
       [l for l in _texto_cad.splitlines() if "Agenda" in l])
    _linha_corrente = [l for l in _texto_cad.splitlines() if l.startswith("- Corrente:")]
    ok("o relatório diz se a corrente está entregando", _linha_corrente
       and "ATRASADA" in _linha_corrente[0], _linha_corrente)
    ok("o relatório diz quantos pulsos devidos não saíram",
       _linha_corrente and "2 pulso(s)" in _linha_corrente[0], _linha_corrente)
    ok("o relatório diz quantos buracos houve em 24h",
       _linha_corrente and "1 buraco(s)" in _linha_corrente[0], _linha_corrente)
    ok("o relatório diz quando é o PRÓXIMO pulso (em dia hoje não garante amanhã)",
       _linha_corrente and "próximo pulso" in _linha_corrente[0], _linha_corrente)
    ok("o próximo pulso vem com dia e hora, não com 'em breve'",
       _linha_corrente and __import__("re").search(r"próximo pulso \d\d/\d\d \d\d:\d\d",
                                                  _linha_corrente[0]) is not None,
       _linha_corrente)
    # A ORIGINALIDADE NO RELATÓRIO (07/11/2026): o dono pediu coisas únicas; o relatório passa a
    # dizer quantas, com data. Repetição é o que a casa mais errou (40x o mesmo texto em 9 dias).
    _uni_path = os.path.join(RAIZ, "posts", "unicidade.json")
    _uni_antes = open(_uni_path, encoding="utf-8").read() if os.path.exists(_uni_path) else None
    try:
        with open(_uni_path, "w", encoding="utf-8") as f:
            json.dump({"medido_em": "2026-11-07", "posts": 109, "dias_com_post": 24,
                       "media_por_dia": 4.54,
                       "veredito": "últimos 7 dias: 10 post(s), todos textos diferentes · "
                                   "média 4.54/dia · o último dia com repetição foi 2026-10-25"}, f)
        pend.escrever(pend.montar())
        _texto_uni = open(pend.SAIDA_MD, encoding="utf-8").read()
        _linha_uni = [l for l in _texto_uni.splitlines() if l.startswith("- Originalidade:")]
        ok("o relatório diz quantos posts diferentes a casa publicou", _linha_uni
           and "todos textos diferentes" in _linha_uni[0], _linha_uni)
        ok("o relatório diz a data do último dia com repetição",
           _linha_uni and "2026-10-25" in _linha_uni[0], _linha_uni)
        with open(_uni_path, "w", encoding="utf-8") as f:
            json.dump({"medido_em": "2026-11-07", "posts": 12, "media_por_dia": 1.2,
                       "veredito": "REPETIÇÃO nos últimos 7 dias: 12 post(s), 8 texto(s) "
                                   "único(s), 4 repetido(s)"}, f)
        pend.escrever(pend.montar())
        _texto_rep = open(pend.SAIDA_MD, encoding="utf-8").read()
        _linha_pauta = [l for l in _texto_uni.splitlines() if l.startswith("- Pauta:")]
        ok("o relatório diz quantos pares assunto+ângulo estão livres",
           _linha_pauta and "par(es) assunto+ângulo livre(s)" in _linha_pauta[0], _linha_pauta)
        ok("a pauta vem com número, não com 'há material'",
           _linha_pauta and __import__("re").search(r"\d+ par\(es\)", _linha_pauta[0]) is not None,
           _linha_pauta)
        ok("o relatório diz se o redator monta pauta AGORA (o que importa)",
           _linha_pauta and "o redator monta pauta:" in _linha_pauta[0], _linha_pauta)
        ok("a linha não promete '3,8 dias' — a rotação de pares não é fim de linha",
           _linha_pauta and "dia(s) no teto" not in _linha_pauta[0], _linha_pauta)
        ok("repetição medida aparece no relatório como REPETIÇÃO, não como estilo",
           any("REPETIÇÃO" in l and l.startswith("- Originalidade:")
               for l in _texto_rep.splitlines()),
           [l for l in _texto_rep.splitlines() if "Originalidade" in l])
    finally:
        if _uni_antes is None:
            if os.path.exists(_uni_path):
                os.unlink(_uni_path)
        else:
            with open(_uni_path, "w", encoding="utf-8") as f:
                f.write(_uni_antes)

    # corrente em dia: a linha muda de tom, e o relatório não fica mudo quando está tudo bem
    with open(_cad_path, "w", encoding="utf-8") as f:
        json.dump({"medido_em": "2026-11-07", "janela_dias": 7,
                   "total_esperado_por_dia": 63, "total_medido_por_dia": 40.0,
                   "linhas": [{"workflow": "marketing-24h", "esperado_por_dia": 45,
                               "medido_por_dia": 39.0, "entrega_pct": 86.7}],
                   "corrente": {"veredito": "em dia (último pulso há 6 min)",
                                              "pulsos_perdidos": 0, "buracos": []}}, f)
    pend.escrever(pend.montar())
    _texto_ok = open(pend.SAIDA_MD, encoding="utf-8").read()
    ok("corrente em dia é dita como em dia, sem inventar problema",
       "Corrente: em dia" in _texto_ok and "ATRASADA" not in _texto_ok,
       [l for l in _texto_ok.splitlines() if "Corrente" in l])
finally:
    if _cad_antes is None:
        if os.path.exists(_cad_path):
            os.unlink(_cad_path)
    else:
        with open(_cad_path, "w", encoding="utf-8") as f:
            f.write(_cad_antes)
    pend.SAIDA_MD = _salvo_md

print("\n%d/%d verificações do medidor de pendências passaram" % (len(certos), len(certos) + len(falhas)))
sys.exit(0 if not falhas else 1)
