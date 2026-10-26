#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do controle da pagina do itch. Nenhum teste toca a rede."""
import importlib.util
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("navegador", os.path.join(RAIZ, "tools", "itch-navegador.py"))
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)

certos = [0]
falhas = [0]


def ok(nome, cond, det=""):
    if cond:
        certos[0] += 1; print("OK " + nome)
    else:
        falhas[0] += 1; print("FALHOU " + nome + (" - " + str(det)[:200] if det else ""))


# ---------------------------------------------------------------- cookie nunca vaza
ok("resumo do cookie nao mostra valor", "segredo123" not in n.resumir_cookie("itchio=segredo123; cf=xyz"))
ok("resumo mostra os nomes dos cookies", "itchio" in n.resumir_cookie("itchio=segredo123; cf=xyz"))
ok("cookie ausente e dito como ausente", n.resumir_cookie("") == "ausente")

# ---------------------------------------------------------------- formulario
PAGINA = """
<form method="post" action="/dashboard/game/1/edit">
 <input type="hidden" name="csrf_token" value="tok123">
 <input type="text" name="title" value="Ceifalume">
 <input type="text" name="short_text" value="Fazenda noturna">
 <textarea name="description">Texto &amp; mais texto</textarea>
 <select name="genre"><option value="sim">Simulation</option><option value="act" selected>Action</option></select>
 <input type="checkbox" name="p_android" value="on" checked>
 <input type="checkbox" name="p_web" value="on">
 <input type="submit" name="salvar" value="Save">
</form>
"""
c = n.campos_do_form(PAGINA)
ok("le input de texto", c.get("title") == "Ceifalume", c.get("title"))
ok("le csrf_token", c.get("csrf_token") == "tok123")
ok("le textarea com entidade desescapada", c.get("description") == "Texto & mais texto", c.get("description"))
ok("le select pela opcao selecionada", c.get("genre") == "act", c.get("genre"))
ok("checkbox marcado entra", c.get("p_android") == "on")
ok("checkbox vazio nao entra", "p_web" not in c)
ok("botao de submit nao entra como campo", "salvar" not in c)

# ---------------------------------------------------------------- envio preserva o resto
envio, aplicados = n.montar_envio(c, {"titulo": "Ceifalume 2"})
ok("troca o campo pedido", envio["title"] == "Ceifalume 2")
ok("preserva descricao e csrf", envio["description"] == "Texto & mais texto" and envio["csrf_token"] == "tok123")
ok("reporta o que aplicou", aplicados == ["titulo"])
_v, _a = n.montar_envio(c, {"campo_que_nao_existe": "x"})
ok("campo desconhecido nao vira escrita", _a == [])

# ---------------------------------------------------------------- palavra obrigatoria
ok_escr, msg_escr, back = n.aplicar("/x", {"titulo": "y"}, "cookie", get=lambda u, ck, timeout=40: (PAGINA, None),
                                    post=lambda *a, **k: (None, None, "nao devia chamar"), confirmacao="")
ok("sem a palavra EDITAR nao escreve", ok_escr is False and "EDITAR" in msg_escr, msg_escr)
ok("e nao chama o POST", back is None)

# ---------------------------------------------------------------- escrita feliz
chamadas = {}


def post_falso(url, cookie, dados, timeout=60):
    chamadas["url"] = url
    chamadas["dados"] = dados
    return "https://itch.io/dashboard/game/1/edit", "<html>salvo</html>", None


ok_e, msg_e, backup = n.aplicar("/dashboard/game/1/edit", {"titulo": "Novo", "resumo": "Novo resumo"},
                                "cookie", get=lambda u, ck, timeout=40: (PAGINA, None),
                                post=post_falso, confirmacao="EDITAR")
ok("com EDITAR escreve", ok_e is True, msg_e)
ok("o envio leva o formulario inteiro", chamadas["dados"]["description"] == "Texto & mais texto")
ok("o envio leva os campos novos", chamadas["dados"]["title"] == "Novo" and chamadas["dados"]["short_text"] == "Novo resumo")
ok("backup guarda o valor ANTERIOR", backup["titulo"] == "Ceifalume", backup)
ok("backup e um dicionario com os campos mapeados", "descricao" in backup)

# ---------------------------------------------------------------- falhas nao fingem
ok_f, msg_f, _ = n.aplicar("/x", {"titulo": "y"}, "cookie",
                           get=lambda u, ck, timeout=40: ("<form><input name='title' value='a'></form>", None),
                           post=post_falso, confirmacao="EDITAR")
ok("formulario sem csrf nao escreve", ok_f is False and "csrf" in msg_f, msg_f)
ok_g, msg_g, _ = n.aplicar("/x", {"titulo": "y"}, "cookie",
                           get=lambda u, ck, timeout=40: (None, "HTTP 403"), post=post_falso, confirmacao="EDITAR")
ok("erro de leitura nao vira escrita", ok_g is False and "403" in msg_g, msg_g)
ok_h, msg_h, _ = n.aplicar("/x", {"titulo": "y"}, "cookie",
                           get=lambda u, ck, timeout=40: (PAGINA, None),
                           post=lambda u, ck, d, timeout=60: ("https://itch.io/login", "x", None),
                           confirmacao="EDITAR")
ok("redirecionar para login = sessao caiu", ok_h is False and "caiu" in msg_h, msg_h)

# ---------------------------------------------------------------- sessao
ok_s, msg_s = n.sessao_ok("")
ok("sem cookie, sessao invalida", ok_s is False and "ITCH_COOKIE" in msg_s, msg_s)
ok_s2, _ = n.sessao_ok("ck", get=lambda u, ck, timeout=40: ("<html id='dashboard'>oi</html>", None))
ok("dashboard com o conteudo certo = sessao valida", ok_s2 is True)
ok_s3, msg_s3 = n.sessao_ok("ck", get=lambda u, ck, timeout=40: (None, "sessao recusada: o itch redirecionou para o login"))
ok("redirect para login = sessao invalida", ok_s3 is False)

# ---------------------------------------------------------------- conferencia na publica
PUB = "<h1>Ceifalume</h1><p>Fazenda noturna</p>"
achados, erro = n.conferir_na_publica("rebocl-brank", "ceifalume", {"titulo": "Ceifalume", "resumo": "Fazenda noturna"},
                                      get=lambda u, ck, timeout=40: (PUB, None))
ok("confere o que aparece na pagina publica", achados == {"titulo": True, "resumo": True}, achados)
falta, _ = n.conferir_na_publica("rebocl-brank", "ceifalume", {"titulo": "Nao existe"},
                                 get=lambda u, ck, timeout=40: (PUB, None))
ok("e detecta o que NAO aparece", falta == {"titulo": False}, falta)

# ---------------------------------------------------------------- backup em disco
tmp = tempfile.mkdtemp()
gravado = {}
n.gravar_backup(os.path.join(tmp, "posts", "backup-itch.json"), {"titulo": "antigo"},
                escrever=lambda c, t: gravado.setdefault("texto", t))
ok("backup serializa em json", '"titulo": "antigo"' in gravado["texto"])

# ---------------------------------------------------------------- o codigo nao embute cookie
fonte = open(os.path.join(RAIZ, "tools", "itch-navegador.py"), encoding="utf-8").read()
ok("o codigo le o cookie do ambiente", 'os.environ.get("ITCH_COOKIE"' in fonte)
ok("o codigo nao contem cookie literal", "itchio=" not in fonte)

# ------------------------------------------------- descoberta do endereco de edicao
# (o caminho que eu tinha chutado — /dashboard/game/5017404/edit — devolveu 404 no navegador
#  do dono; nada de chutar formato: com a sessao o /dashboard lista o link verdadeiro)
# medido no navegador do dono em 26/10: o editor de verdade e https://itch.io/game/edit/<id>
PAINEL = """
<a href="/dashboard/game/5017404/edit">Edit</a>
<a href="/dashboard/game/5017404/analytics">Analytics</a>
<a href="/dashboard/game/999/edit">outro jogo</a>
<a href="/game/edit/5017404">Edit game</a>
"""
lista = n.candidatos_de_edicao(PAINEL, 5017404)
ok("prefere o formato real /game/edit/<id>", lista[0] == "/game/edit/5017404", lista)
ok("acha o link de edicao no dashboard", "/dashboard/game/5017404/edit" in lista, lista)
ok("nao pega o jogo de outro id", "/dashboard/game/999/edit" not in lista, lista)
ok("o primeiro candidato e o editor", lista[0] == "/game/edit/5017404", lista)
vazio = n.candidatos_de_edicao("", 5017404)
ok("sem dashboard cai nos formatos conhecidos",
   "/dashboard/game/5017404/edit" in vazio and "/dashboard/game/5017404" in vazio, vazio)
ok("o formato real vem primeiro mesmo sem dashboard", vazio[0] == "/game/edit/5017404", vazio)


def get_com_csrf(url, cookie, timeout=40):
    if url.endswith("/dashboard"):
        return PAINEL, None
    if url.endswith("/game/edit/5017404"):
        return '<form><input name="csrf_token" value="x"></form>', None
    return "<html>sem formulario</html>", None


caminho, tentativas = n.descobrir_edicao("c=1", 5017404, get=get_com_csrf)
ok("descobrir usa o primeiro candidato que tem csrf",
   caminho == "/game/edit/5017404", (caminho, tentativas))
ok("descobrir registra o que tentou",
   any("OK (tem csrf_token)" in x for x in tentativas), tentativas)
sem_form = n.descobrir_edicao("c=1", 5017404, get=lambda u, c, timeout=40: ("<html>404</html>", None))
ok("descobrir recusa pagina sem formulario", sem_form[0] is None, sem_form)
ok("descobrir explica por que recusou",
   all("sem formulario" in x or x.startswith("dashboard") for x in sem_form[1]), sem_form[1])


def get_dashboard_caido(url, cookie, timeout=40):
    if url.endswith("/dashboard"):
        return None, "sessao recusada"
    return ('<form><input name="csrf_token" value="x"></form>', None)


caido = n.descobrir_edicao("c=1", 5017404, get=get_dashboard_caido)
ok("descobrir reporta a falha do dashboard e segue",
   caido[0] == "/game/edit/5017404" and caido[1][0].startswith("dashboard: sessao recusada"), caido)

# ------------------------------------------- 403 da Cloudflare != sessao invalida
# (medido no runner em 26/10: /dashboard devolve 403 para TODA combinacao, inclusive sem cookie)
def get_bloqueado(url, cookie, timeout=40):
    return None, n.BLOQUEIO


ok("403 vira bloqueio, nao 'sessao invalida'",
   n.sessao_ok("c=1", get=get_bloqueado) == (None, n.BLOQUEIO))
ok("bloqueio nao e lido como False (nao acusa sessao ruim)",
   n.sessao_ok("c=1", get=get_bloqueado)[0] is None)
ok("sessao invalida de verdade continua False",
   n.sessao_ok("c=1", get=lambda u, c, timeout=40: (None, "sessao recusada: o itch redirecionou para o login"))[0] is False)
ok("sem cookie continua False",
   n.sessao_ok("", get=get_bloqueado)[0] is False)
ok("o texto do bloqueio diz que nao e a sessao", "nao e a sessao" in n.BLOQUEIO, n.BLOQUEIO)

print("\n%d/%d testes do controle do itch passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
