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
ok("com o post ausente, o devlog fica pendente",
   any(i["id"] == "itch-devlog-gameplay" and i["estado"] != "feito" for i in rel["itens"]))
ok("o YouTube aparece como feito",
   any(i["id"] == "youtube-gameplay" and i["estado"] == "feito" for i in rel["itens"]))
ok("avisa que o estado mudou quando a lista de pendentes muda", rel["mudou_desde_o_ultimo"] is True)
_sem_mudanca = pend.montar({"pendentes_em": rel["pendentes_em"]})
ok("NÃO avisa quando o estado é o mesmo", _sem_mudanca["mudou_desde_o_ultimo"] is False)

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

print("\n%d/%d verificações do medidor de pendências passaram" % (len(certos), len(certos) + len(falhas)))
sys.exit(0 if not falhas else 1)
