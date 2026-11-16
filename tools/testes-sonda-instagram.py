#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da sonda do Instagram: provar sem publicar e sem vazar token.

A sonda fala com o servidor da Meta; aqui ela fala com um servidor de mentira. O que se prova
é o que depende da casa: a ordem dos passos, a parada antes do publish, a máscara do token e o
que significa cada resposta — inclusive as ruins.
"""
import os
import importlib.util
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sonda", RAIZ / "tools" / "sonda-instagram.py")
sonda_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sonda_mod)

resultados = []


def checar(nome, condicao, detalhe=""):
    ok = bool(condicao)
    resultados.append((nome, ok))
    print(("PASS" if ok else "FAIL") + " — " + nome + (("  [" + str(detalhe)[:120] + "]") if detalhe and not ok else ""))


fonte = (RAIZ / "tools" / "sonda-instagram.py").read_text(encoding="utf-8")
checar("a sonda não monta endpoint de publicação", "/media_publish" not in fonte)
checar("a parada antes do publish está declarada no código", "NÃO é feita" in fonte)
checar("a sonda mascara o token", "def mascara(" in fonte and "valor[:4]" in fonte)

TOKEN = "IGAAsegredo-de-teste-1234567890"


def http_feliz(metodo, url, dados=None):
    if url.endswith("/media"):
        assert dados and dados.get("image_url") and dados.get("access_token")
        return {"id": "container-1"},  # noqa: E501  (dublê devolve dict simples)
    if "/media" in url:
        return {"id": "container-1"}
    if "content_publishing_limit" in url:
        return {"data": [{"quota_usage": 3, "config": {"quota_total": 50}}]}
    if "/me?" in url:
        return {"id": "178414", "username": "reboclbrank", "account_type": "MEDIA_CREATOR",
                "media_count": 37}
    return {"status_code": "FINISHED"}


CHAMADAS = []


def http_feliz_registrando(metodo, url, dados=None):
    CHAMADAS.append((metodo, url.split("?")[0]))
    if url.endswith("/media") and metodo == "POST":
        return {"id": "container-1"}
    if "content_publishing_limit" in url:
        return {"data": [{"quota_usage": 3, "config": {"quota_total": 50}}]}
    if "/me?" in url:
        return {"id": "178414", "username": "reboclbrank", "account_type": "MEDIA_CREATOR",
                "media_count": 37}
    return {"status_code": "FINISHED"}


r = sonda_mod.sonda(token=TOKEN, ig_user_id="178414", http=http_feliz_registrando,
                    pausa=lambda s: None)
checar("caminho inteiro: conclusão é de prova", r["conclusao"].startswith("CAMINHO_INTEIRO_PROVADO"), r["conclusao"])
checar("identidade traz usuário e contagem de posts",
      r["passos"]["identidade"]["username"] == "reboclbrank" and r["passos"]["identidade"]["posts"] == 37)
checar("permissão traz a quota de publicação", r["passos"]["permissao"]["quota_usada"] == 3)
checar("container fica FINISHED", r["passos"]["caminho"]["status_code"] == "FINISHED")
checar("nenhum passo toca /media_publish", not any("media_publish" in u for _, u in CHAMADAS),
      [u for _, u in CHAMADAS])
checar("o token aparece mascarado no relatório", TOKEN not in str(r) and "IGAA…" in r["token"], r["token"])


def http_sem_permissao(metodo, url, dados=None):
    if "/me?" in url:
        return {"id": "1", "username": "reboclbrank", "account_type": "PESSOAL", "media_count": 37}
    raise RuntimeError("HTTP 403 · (#10) Application does not have permission (código 10)")


r = sonda_mod.sonda(token=TOKEN, ig_user_id="1", http=http_sem_permissao, pausa=lambda s: None)
checar("token que só lê é declarado sem permissão de publicar",
      r["conclusao"].startswith("SEM_PERMISSAO_DE_PUBLICAR"), r["conclusao"])
checar("e nem tenta criar container nesse caso", "caminho" not in r["passos"])


def http_token_ruim(metodo, url, dados=None):
    raise RuntimeError("HTTP 401 · (#190) Invalid OAuth access token (código 190)")


r = sonda_mod.sonda(token=TOKEN, ig_user_id="1", http=http_token_ruim, pausa=lambda s: None)
checar("token inválido é declarado na cara", r["conclusao"].startswith("TOKEN_INVALIDO"), r["conclusao"])

r = sonda_mod.sonda(token="", ig_user_id="", http=http_token_ruim, pausa=lambda s: None)
checar("sem credencial a sonda não inventa resultado",
      r["conclusao"].startswith("SEM_CREDENCIAL"), r["conclusao"])


def http_container_erro(metodo, url, dados=None):
    if "/me?" in url:
        return {"id": "1", "username": "reboclbrank", "media_count": 37}
    if "content_publishing_limit" in url:
        return {"data": [{"quota_usage": 0}]}
    if url.endswith("/media"):
        return {"id": "c2"}
    return {"status_code": "ERROR", "status": "media fetch failed"}


r = sonda_mod.sonda(token=TOKEN, ig_user_id="1", http=http_container_erro, pausa=lambda s: None)
checar("container com erro é declarado, não escondido",
      r["conclusao"].startswith("CONTAINER_COM_ERRO"), r["conclusao"])

# ---- 16/11/2026: o bug do access_token em GET -------------------------------------------
# publicar-instagram.py passou 11 runs vermelhos porque mandava o access_token no CORPO de um
# GET. A Graph API ignora corpo em GET, responde HTTP 400 código 100 ("Object with ID ...
# does not exist") e o container morria órfão. Estes contratos travam a regressão nos DOIS
# módulos: token em GET vai na QUERY STRING, token em POST pode ir no corpo.
import importlib.util as _ilu

_spec_pub = _ilu.spec_from_file_location(
    "publicar_mod", str(RAIZ / "tools" / "publicar-instagram.py"))
pub_mod = _ilu.module_from_spec(_spec_pub)
_spec_pub.loader.exec_module(pub_mod)

_pedidos = []


class _Resp:
    def __init__(self, corpo):
        self._c = corpo

    def read(self):
        return self._c

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Req:
    # Captura o que o http() REAL monta: é aqui, e só aqui, que se vê se o token foi para a
    # query string (GET) ou para o corpo (POST).
    def __init__(self, url, data=None, headers=None, method=None):
        self.url, self.data, self.method = url, data, method
        _pedidos.append(self)


def _urlopen(req, timeout=60):
    if "/media_publish" in req.url:
        return _Resp(b'{"id":"m1"}')
    if req.url.rstrip("/").endswith("/media"):
        return _Resp(b'{"id":"c1"}')
    return _Resp(b'{"status_code":"FINISHED"}')


_orig_req, _orig_open = pub_mod.urllib.request.Request, pub_mod.urllib.request.urlopen
pub_mod.urllib.request.Request = _Req
pub_mod.urllib.request.urlopen = _urlopen
try:
    # sem http_fn: publicar() usa o http() de verdade do módulo
    pub_mod.publicar(token="T" * 20, ig_user_id="1784", image_url="http://x/y.png",
                     caption="teste", publicar_de_verdade=True,
                     pausa=lambda s: None, tentativas=1, intervalo=0)
finally:
    pub_mod.urllib.request.Request = _orig_req
    pub_mod.urllib.request.urlopen = _orig_open

_gets = [r for r in _pedidos if "fields=status_code" in r.url]
checar("o publicador manda o token na URL no GET de estado",
       bool(_gets) and all("access_token=" in r.url for r in _gets),
       [r.url for r in _gets])
checar("o publicador não manda corpo no GET de estado",
       bool(_gets) and all(r.data is None for r in _gets),
       [r.data for r in _gets])
_publicacao = [r for r in _pedidos if "/media_publish" in r.url]
checar("o media_publish recebe o creation_id e publica",
       bool(_publicacao) and b"creation_id" in (_publicacao[0].data or b""),
       [(r.url, r.data) for r in _publicacao])

checar("o GET de estado pede status_code e status",
       any("fields=status_code,status" in r.url for r in _gets), [r.url for r in _gets])


certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos da sonda do Instagram passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
