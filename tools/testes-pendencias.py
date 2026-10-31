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
ok("existe um item sobre o que a página do itch realmente abre", _pagina is not None)
ok("ele não conta como pendência do dono",
   "itch-pagina-abre-build" not in rel["pendentes_em"], rel["pendentes_em"])
ok("a medida dele cita o upload antigo que a página abre",
   "19268311" in _pagina["medido"], _pagina["medido"])
ok("a medida dele diz que o upload NÃO tem o selo", "NÃO tem o selo" in _pagina["medido"],
   _pagina["medido"])
ok("ele cita a página pública do jogo como caminho que chega ao jogador",
   any("site da casa" in c or "YouTube" in c for c in _pagina["coberto_em"]),
   _pagina["coberto_em"])
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

# ---- o build no itch deixa de ser pendência FANTASMA quando há build com prova
# MEDIDO (31/10/2026): o item ficava "esperando o dono" para sempre porque a única medida era
# "a página respondeu 200" — verdade mesmo sem build nenhum. Com o build 2257110 no ar, o
# relatório continuava pedindo ao dono o que já estava feito.
import tempfile as _tf, shutil as _sh
_tmp = _tf.mkdtemp()
_orig_json = pend.os.path.join(pend.RAIZ, "posts", "itch-builds.json")
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

print("\n%d/%d verificações do medidor de pendências passaram" % (len(certos), len(certos) + len(falhas)))
sys.exit(0 if not falhas else 1)
