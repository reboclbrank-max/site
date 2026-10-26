#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controle da pagina do itch.io por sessao — o que a API nao oferece.

Medido em 26/10: a API do itch e so de leitura e o butler so sobe build. Para editar a pagina
(texto, tags, capa) o unico caminho e agir como o navegador do dono. Isso e possivel porque
/dashboard NAO e desafiado pelo Cloudflare (so /login e):

   itch.io/          -> 200 sem desafio
   itch.io/login     -> 403 desafio Cloudflare   <- por isso o LOGIN nao se automatiza
   itch.io/dashboard -> 302 sem cookie / 200 com cookie

Regras de seguranca:
  * o cookie vive em segredo (ITCH_COOKIE), nunca em arquivo, nunca em log;
  * o modo padrao e LER; escrever exige a palavra EDITAR;
  * antes de escrever, devolve backup dos valores atuais;
  * depois de escrever, RELE a pagina publica e confere — sem isso nao e prova.
"""
import html as html_mod
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://itch.io"
PALAVRA = "EDITAR"
AGENTE = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

MAPA = {
    "title": "titulo",
    "short_text": "resumo",
    "description": "descricao",
    "genre": "genero",
    "tags": "tags",
    "min_price": "preco",
    "classification": "classificacao",
}


def cabecalhos(cookie):
    if not cookie:
        return {}
    return {"Cookie": cookie, "User-Agent": AGENTE, "Accept-Language": "pt-BR,pt;q=0.9"}


def resumir_cookie(cookie):
    if not cookie:
        return "ausente"
    nomes = sorted({p.split("=")[0].strip() for p in cookie.split(";") if "=" in p})
    return "%d cookie(s): %s - %d caracteres" % (len(nomes), ", ".join(nomes), len(cookie))


def candidatos_de_edicao(pagina_dashboard, id_jogo):
    """Le os links do /dashboard e devolve os caminhos de edicao do jogo, do mais provavel ao menos.

    Nada de chutar formato: o itch nao documenta o endereco do editor e o caminho devolve 404
    para quem nao tem sessao. Com a sessao, o /dashboard lista o jogo e o link verdadeiro vem nele.
    """
    achados = []
    for href in re.findall(r'href="([^"]+)"', pagina_dashboard or ""):
        limpo = html_mod.unescape(href).strip()
        if not limpo.startswith("/"):
            continue
        caminho = limpo.split("?")[0].split("#")[0]
        if not caminho.startswith("/dashboard/game/"):
            continue
        if str(id_jogo) and str(id_jogo) not in caminho:
            continue
        if caminho not in achados:
            achados.append(caminho)
    achados.sort(key=lambda c: (0 if c.rstrip("/").endswith("/edit") else 1, len(c)))
    for extra in ("/dashboard/game/%s/edit" % id_jogo, "/dashboard/game/%s" % id_jogo):
        if extra not in achados:
            achados.append(extra)
    return achados


def descobrir_edicao(cookie, id_jogo, get=None):
    """Devolve (caminho_valido, tentativas). A validacao e dura: precisa ter csrf_token."""
    get = get or _get
    painel, erro = buscar("/dashboard", cookie, get=get)
    tentativas = []
    if erro:
        tentativas.append("dashboard: " + erro)
        lista = candidatos_de_edicao("", id_jogo)
    else:
        lista = candidatos_de_edicao(painel, id_jogo)
        tentativas.append("dashboard: %d candidato(s) -> %s" % (len(lista), ", ".join(lista[:6])))
    for caminho in lista:
        pagina, erro2 = buscar(caminho, cookie, get=get)
        if erro2:
            tentativas.append("%s: %s" % (caminho, erro2))
            continue
        if "csrf_token" not in (pagina or ""):
            tentativas.append("%s: respondeu sem formulario de edicao" % caminho)
            continue
        tentativas.append("%s: OK (tem csrf_token)" % caminho)
        return caminho, tentativas
    return None, tentativas


def buscar(caminho, cookie, get=None, timeout=40):
    get = get or _get
    return get(BASE + caminho, cookie, timeout=timeout)


def _get(url, cookie, timeout=40):
    req = urllib.request.Request(url, headers=cabecalhos(cookie))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            final = r.geturl()
            texto = r.read().decode("utf-8", "replace")
            if "/login" in final:
                return None, "sessao recusada: o itch redirecionou para o login"
            return texto, None
    except urllib.error.HTTPError as e:
        return None, "HTTP %d" % e.code
    except Exception as e:
        return None, str(e)[:120]


def _post(url, cookie, dados, timeout=60):
    corpo = urllib.parse.urlencode(dados, doseq=True).encode()
    req = urllib.request.Request(url, data=corpo, method="POST", headers=dict(
        cabecalhos(cookie), **{"Content-Type": "application/x-www-form-urlencoded"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.geturl(), r.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        return None, None, "HTTP %d: %s" % (e.code, (e.read().decode() or "")[:200])
    except Exception as e:
        return None, None, str(e)[:150]


def sessao_ok(cookie, get=None):
    if not cookie:
        return False, "sem cookie (segredo ITCH_COOKIE)"
    pagina, erro = buscar("/dashboard", cookie, get=get)
    if erro:
        return False, erro
    if "dashboard" not in (pagina or "").lower():
        return False, "respondeu 200 mas nao parece o painel (sessao parcial?)"
    return True, "sessao valida"


def _atributo(tag, nome):
    m = re.search(r'\b%s="([^"]*)"' % re.escape(nome), tag or "", re.I)
    return html_mod.unescape(m.group(1)) if m else ""


def campos_do_form(pagina):
    campos = {}
    for tag in re.findall(r"<input\b[^>]*>", pagina or "", re.I):
        nome = _atributo(tag, "name")
        if not nome:
            continue
        tipo = (_atributo(tag, "type") or "text").lower()
        if tipo in ("checkbox", "radio"):
            if re.search(r"\bchecked\b", tag, re.I):
                campos[nome] = _atributo(tag, "value") or "on"
            continue
        if tipo in ("submit", "button", "file"):
            continue
        campos[nome] = _atributo(tag, "value") or ""
    for m in re.finditer(r"<textarea\b([^>]*)>(.*?)</textarea>", pagina or "", re.I | re.S):
        nome = _atributo(m.group(1), "name")
        if nome:
            campos[nome] = html_mod.unescape(m.group(2))
    for m in re.finditer(r"<select\b([^>]*)>(.*?)</select>", pagina or "", re.I | re.S):
        nome = _atributo(m.group(1), "name")
        if not nome:
            continue
        # a marca 'selected' pode vir antes OU depois de value= no mesmo <option>
        escolhido = ""
        for tag in re.findall(r"<option\b[^>]*>", m.group(2), re.I):
            if re.search(r"\bselected\b", tag, re.I):
                escolhido = _atributo(tag, "value")
                break
        campos[nome] = escolhido
    return campos


def ler(caminho_edicao, cookie, get=None):
    pagina, erro = buscar(caminho_edicao, cookie, get=get)
    if erro:
        return None, erro
    campos = campos_do_form(pagina)
    estado = {rotulo: campos.get(campo) for campo, rotulo in MAPA.items() if campo in campos}
    estado["_campos_do_itch"] = sorted(campos.keys())
    return estado, None


def montar_envio(campos_atuais, mudancas):
    """Parte do formulario INTEIRO e troca so o que veio: o itch regrava tudo no POST."""
    envio = dict(campos_atuais)
    aplicados = []
    for campo, rotulo in MAPA.items():
        if rotulo in mudancas:
            envio[campo] = mudancas[rotulo]
            aplicados.append(rotulo)
    return envio, aplicados


def aplicar(caminho_edicao, mudancas, cookie, get=None, post=None, confirmacao=""):
    if confirmacao != PALAVRA:
        return False, "recusado: escrever exige a palavra " + PALAVRA, None
    pagina, erro = buscar(caminho_edicao, cookie, get=get)
    if erro:
        return False, erro, None
    atual = campos_do_form(pagina)
    if "csrf_token" not in atual:
        return False, "formulario sem csrf_token — pagina mudou; nada foi escrito", None
    backup = {rotulo: atual.get(campo) for campo, rotulo in MAPA.items() if campo in atual}
    envio, aplicados = montar_envio(atual, mudancas)
    if not aplicados:
        return False, "nenhum campo reconhecido em " + ", ".join(mudancas), backup
    post = post or _post
    destino, corpo, erro2 = post(BASE + caminho_edicao, cookie, envio)
    if erro2:
        return False, erro2, backup
    if "/login" in (destino or ""):
        return False, "sessao caiu durante o envio", backup
    return True, "enviado: " + ", ".join(aplicados), backup


def conferir_na_publica(usuario, slug, esperado, get=None, cookie=None):
    pagina, erro = buscar("/%s/%s" % (usuario, slug), cookie or "", get=get)
    if erro:
        return None, erro
    achados = {}
    for rotulo, valor in esperado.items():
        if valor is None:
            continue
        achados[rotulo] = str(valor)[:60] in html_mod.unescape(pagina or "")
    return achados, None


def gravar_backup(caminho_backup, backup, escrever=None):
    escrever = escrever or _escrever
    escrever(caminho_backup, json.dumps(backup, ensure_ascii=False, indent=2) + "\n")
    return caminho_backup


def _escrever(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def main(argv):
    cookie = os.environ.get("ITCH_COOKIE", "")
    print("cookie: " + resumir_cookie(cookie))
    ok, msg = sessao_ok(cookie)
    print(("OK " if ok else "FALHOU ") + "sessao: " + msg)
    if not ok:
        return 1
    alvo = os.environ.get("ITCH_EDICAO", "")
    if not alvo:
        print("- ITCH_EDICAO nao definido (ex.: /dashboard/game/123/edit) - so testei a sessao")
        return 0
    estado, erro = ler(alvo, cookie)
    if erro:
        print("FALHOU leitura da pagina de edicao: " + erro)
        return 1
    print("campos do itch: " + ", ".join(estado["_campos_do_itch"]))
    for rotulo in MAPA.values():
        if rotulo in estado:
            valor = estado[rotulo]
            print("  %s = %s" % (rotulo, (str(valor)[:70] + "...") if valor and len(str(valor)) > 70 else valor))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
