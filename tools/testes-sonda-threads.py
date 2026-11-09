#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da sonda do Threads: provar sem publicar e sem vazar token.

A sonda fala com o servidor da Meta; aqui ela fala com um servidor de mentira. O que se prova
é o que depende da casa: a ordem dos passos, a parada antes do publish, a máscara do token e o
significado de cada resposta — inclusive as ruins.
"""
import importlib.util
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sonda_threads", RAIZ / "tools" / "sonda-threads.py")
sonda_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sonda_mod)

resultados = []


def checar(nome, condicao, detalhe=""):
    ok = bool(condicao)
    resultados.append((nome, ok))
    print(("PASS" if ok else "FAIL") + " — " + nome + (("  [" + str(detalhe)[:120] + "]") if detalhe and not ok else ""))


fonte = (RAIZ / "tools" / "sonda-threads.py").read_text(encoding="utf-8")
checar("a sonda não monta endpoint de publicação",
      '"/threads_publish"' not in fonte and "'/threads_publish'" not in fonte)
checar("a parada antes do publish está declarada no código", "NÃO é publicado" in fonte
      or "não é chamado aqui" in fonte)
checar("a sonda mascara o token", "def mascara(" in fonte and "valor[:4]" in fonte)
checar("a sonda usa a API do Threads, não a do Instagram",
      "graph.threads.net" in fonte and "graph.instagram.com" not in fonte)

TOKEN = "THsegredo-de-teste-1234567890"
CHAMADAS = []


def http_feliz(metodo, url, dados=None):
    CHAMADAS.append((metodo, url.split("?")[0]))
    if url.endswith("/threads") and metodo == "POST":
        assert dados and dados.get("media_type") == "TEXT" and dados.get("access_token")
        assert dados.get("text")
        return {"id": "container-t1"}
    if "threads_publishing_limit" in url:
        return {"data": [{"quota_usage": 2, "config": {"quota_total": 250}}]}
    if "/me?" in url:
        return {"id": "99", "username": "reboclbrank"}
    return {"status": "FINISHED"}


r = sonda_mod.sonda(token=TOKEN, threads_user_id="99", http=http_feliz, pausa=lambda s: None)
checar("caminho inteiro: conclusão é de prova", r["conclusao"].startswith("CAMINHO_INTEIRO_PROVADO"), r["conclusao"])
checar("identidade traz o usuário", r["passos"]["identidade"]["username"] == "reboclbrank")
checar("permissão traz a quota de publicação", r["passos"]["permissao"]["quota_usada"] == 2)
checar("container fica FINISHED", r["passos"]["caminho"]["status"] == "FINISHED",
      r["passos"]["caminho"])
checar("nenhuma chamada toca o endpoint threads_publish",
      not any(u.rstrip("/").endswith("/threads_publish") for _, u in CHAMADAS),
      [u for _, u in CHAMADAS])
checar("o token aparece mascarado no relatório", TOKEN not in str(r) and "THse…" in r["token"], r["token"])
checar("o container de sonda é de TEXTO (nenhuma mídia da casa é enviada)",
      any(u.endswith("/threads") for _, u in CHAMADAS))


def http_sem_permissao(metodo, url, dados=None):
    if "/me?" in url:
        return {"id": "99", "username": "reboclbrank"}
    raise RuntimeError("HTTP 403 · (#10) Application does not have permission (código 10)")


r = sonda_mod.sonda(token=TOKEN, threads_user_id="99", http=http_sem_permissao, pausa=lambda s: None)
checar("token que só lê é declarado sem permissão de publicar",
      r["conclusao"].startswith("SEM_PERMISSAO_DE_PUBLICAR"), r["conclusao"])
checar("e nem tenta criar container nesse caso", "caminho" not in r["passos"])


def http_token_ruim(metodo, url, dados=None):
    raise RuntimeError("HTTP 401 · (#190) Invalid OAuth access token (código 190)")


r = sonda_mod.sonda(token=TOKEN, threads_user_id="99", http=http_token_ruim, pausa=lambda s: None)
checar("token inválido é declarado na cara", r["conclusao"].startswith("TOKEN_INVALIDO"), r["conclusao"])

r = sonda_mod.sonda(token="", threads_user_id="", http=http_token_ruim, pausa=lambda s: None)
checar("sem credencial a sonda não inventa resultado", r["conclusao"].startswith("SEM_CREDENCIAL"), r["conclusao"])

def http_erro_de_conteudo(metodo, url, dados=None):
    if "/me?" in url:
        return {"id": "99", "username": "reboclbrank"}
    if "threads_publishing_limit" in url:
        return {"data": [{"quota_usage": 0}]}
    if url.endswith("/threads") and metodo == "POST":
        return {"id": "c2"}
    return {"status": "ERROR", "error_message": "text rejected"}


r = sonda_mod.sonda(token=TOKEN, threads_user_id="99", http=http_erro_de_conteudo, pausa=lambda s: None)
checar("container com erro é declarado, não escondido", r["conclusao"].startswith("CONTAINER_COM_ERRO"), r["conclusao"])


def http_publicado(metodo, url, dados=None):
    if "/me?" in url:
        return {"id": "99", "username": "reboclbrank"}
    if "threads_publishing_limit" in url:
        return {"data": [{"quota_usage": 0}]}
    if url.endswith("/threads") and metodo == "POST":
        return {"id": "c3"}
    return {"status": "PUBLISHED"}


r = sonda_mod.sonda(token=TOKEN, threads_user_id="99", http=http_publicado, pausa=lambda s: None)
checar("container que aparece publicado é tratado como anomalia, não como sucesso",
      r["conclusao"].startswith("ATENCAO"), r["conclusao"])

certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos da sonda do Threads passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
