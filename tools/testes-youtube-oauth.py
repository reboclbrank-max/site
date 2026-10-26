#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do OAuth e do envio do YouTube — offline, sem rede e sem segredo.

O que este teste cerca:
  * o fluxo de autorização não imprime token em log nenhum;
  * `authorization_pending` (dono ainda não aprovou) NÃO é tratado como falha;
  * envio sem a palavra PUBLICAR não acontece;
  * kit inválido/arquivo ausente não viram upload;
  * nenhum dos dois workflows tem cron: nada publica sozinho.
"""
import importlib.util
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


oauth = carrega("youtube_oauth", "youtube_oauth.py")
envio = carrega("enviar_youtube", "enviar-youtube.py")

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + detalhe if detalhe else ""))


# ---------------------------------------------------------------- escopo e sigilo
ok("pede o escopo de administração (cobre envio e edição num consentimento só)",
   oauth.ESCOPO == "https://www.googleapis.com/auth/youtube", oauth.ESCOPO)
ok("o escopo pedido não é 'force-ssl' (esse é o mínimo que não serve para playlist+upload combinados)",
   "force-ssl" not in oauth.ESCOPO)
ok("resumo de segredo mostra no máximo 4 caracteres",
   "AB12" in oauth.resumo_de_segredo("AB12xyz1234")
   and "xyz1234" not in oauth.resumo_de_segredo("AB12xyz1234"))
ok("resumo de segredo não devolve o valor",
   "segredo" not in oauth.resumo_de_segredo("xyzw-segredo-longo"))

fonte_oauth = open(os.path.join(RAIZ, "tools", "youtube_oauth.py"), encoding="utf-8").read()
ok("nenhum print de token no módulo de OAuth",
   "print(dados" not in fonte_oauth and "print(token" not in fonte_oauth and "print(refresh" not in fonte_oauth)

# ---------------------------------------------------------------- fluxo de dispositivo
def post_falso(respostas):
    """Simula o Google: devolve respostas na ordem e registra as chamadas."""
    chamadas, fila = [], list(respostas)

    def _post(url, dados, timeout=45, cabecalhos=None):
        chamadas.append((url, dict(dados)))
        return fila.pop(0) if fila else ({"error": "vazio"}, 400)
    _post.chamadas = chamadas
    return _post


_falso = post_falso([({"device_code": "DC", "user_code": "ABCD-EFGH",
                       "verification_url": "https://google.com/device",
                       "expires_in": 1800, "interval": 5}, 200)])
codigo, erro = oauth.pedir_codigo("client-123", post=_falso)
ok("pedir código devolve device_code e user_code", not erro and codigo["user_code"] == "ABCD-EFGH", str(erro))
ok("pedir código manda o escopo de envio",
   _falso.chamadas[0][1].get("scope") == oauth.ESCOPO, str(_falso.chamadas[0][1]))
ok("pedir código sem client_id não explode", oauth.pedir_codigo("", post=_falso)[1] is not None)

_espera = post_falso([({"error": "authorization_pending"}, 428),
                      ({"error": "authorization_pending"}, 428),
                      ({"refresh_token": "REFRESH-SECRETO", "access_token": "A"}, 200)])
dormiu = []
dados, erro = oauth.trocar_token("c", "s", "DC", post=_espera, tentativas=3, dormir=dormiu.append)
ok("dono ainda não aprovou não é falha: espera e tenta de novo",
   erro is None and dados.get("refresh_token") == "REFRESH-SECRETO", str(erro))
ok("a espera entre tentativas acontece de verdade", len(dormiu) == 2, str(dormiu))

_expirado = post_falso([({"error": "expired_token"}, 400)])
ok("código expirado devolve erro claro",
   oauth.trocar_token("c", "s", "DC", post=_expirado, tentativas=1, dormir=lambda *_: None)[1] is not None)

_renova = post_falso([({"access_token": "AT-CURTO", "expires_in": 3599}, 200)])
token, erro = oauth.renovar("c", "s", "REFRESH", post=_renova)
ok("renovação troca refresh por access token", token == "AT-CURTO" and not erro, str(erro))
ok("renovação sem refresh_token devolve erro", oauth.renovar("c", "s", "", post=_renova)[1] is not None)

# gravar segredo: nunca imprime valor, e falha de chave pública é tratada
_gravado = {}


def get_falso(url, pat):
    return {"key": "chave-publica-b64", "key_id": "1"}, None


def put_falso(url, pat, dados):
    _gravado["url"] = url
    _gravado["dados"] = dados
    return True, None


gravou, msg = oauth.gravar_segredo("reboclbrank-max/site", "YT_REFRESH_TOKEN", "TOKEN-BEM-SECRETO",
                               "pat", get=get_falso, put=put_falso,
                               selar=lambda chave, valor: "SELADO")
ok_gravou = bool(gravou) and _gravado["dados"]["encrypted_value"] == "SELADO"
ok("segredo é selado antes de subir", ok_gravou, str(_gravado.get("dados")))
ok("a mensagem de sucesso não contém o valor do segredo", "TOKEN-BEM-SECRETO" not in msg, msg)
ok("gravar segredo sem PAT falha em vez de fingir sucesso",
   oauth.gravar_segredo("r", "N", "V", "", get=get_falso, put=put_falso)[0] is False)

# ---------------------------------------------------------------- envio: trava e kit
ok("envio sem a palavra PUBLICAR não acontece", envio.executar("prancheta", "", raiz=RAIZ)[0] is False)
ok("palavra errada também não publica", envio.executar("prancheta", "sim", raiz=RAIZ)[0] is False)
ok("a trava é avaliada antes de qualquer rede",
   "faltou a confirmação" in envio.executar("prancheta", "", raiz=RAIZ)[1])

_dados = envio.carregar_kit(os.path.join(RAIZ, "posts", "kit-youtube.json"))
_pac = envio.pacote_do_kit(_dados, "ceifalume")
ok("o kit tem pacote do ceifalume", _pac is not None)
ok("metadados vêm do kit, sem texto novo",
   envio.metadados(_pac)["snippet"]["title"] == _pac["titulo"]
   and envio.metadados(_pac)["snippet"]["description"] == _pac["descricao"])
ok("categoria é Gaming e o vídeo não é 'para crianças'",
   envio.metadados(_pac)["snippet"]["categoryId"] == "20"
   and envio.metadados(_pac)["status"]["selfDeclaredMadeForKids"] is False)
ok("vídeo do kit passa na validação do próprio kit",
   envio.validar_antes(_pac, raiz=RAIZ, validador=envio._validador_do_kit()) == [])
_pac_ruim = dict(_pac)
_pac_ruim["titulo"] = "o melhor do mundo"
ok("título com promessa vazia é barrado antes do upload",
   envio.validar_antes(_pac_ruim, raiz=RAIZ, validador=envio._validador_do_kit()) != [])
_pac_ausente = dict(_pac)
_pac_ausente["arquivo"] = "media/nao-existe.mp4"
ok("arquivo ausente é barrado antes do upload",
   any("ausente" in e for e in envio.validar_antes(_pac_ausente, raiz=RAIZ, validador=lambda p: [])))

# ---------------------------------------------------------------- execução falsa completa
def _renovar_falso(cid, csec, ref):
    return "AT", None


def _iniciar_falso(token, meta, tamanho):
    ok_url = token == "AT" and meta["snippet"]["title"] == _pac["titulo"] and tamanho > 0
    return ("https://upload.example/sessao", None) if ok_url else (None, "metadados errados")


def _enviar_falso(url, caminho):
    return ({"id": "VIDEO123"}, None) if os.path.exists(caminho) else (None, "arquivo sumiu")


os.environ.update({"YT_CLIENT_ID": "c", "YT_CLIENT_SECRET": "s", "YT_REFRESH_TOKEN": "r"})
ok_upload, msg_upload = envio.executar("ceifalume", "PUBLICAR", raiz=RAIZ, renovar=_renovar_falso,
                                       iniciar=_iniciar_falso, enviar=_enviar_falso,
                                       escrever=lambda *_: None)
ok("com PUBLICAR e kit válido, o envio completa", ok_upload and "youtu.be/VIDEO123" in msg_upload, msg_upload)
for chave in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
    os.environ.pop(chave, None)

# ---------------------------------------------------------------- nenhum workflow publica sozinho
for wf in ("enviar-youtube.yml", "autorizar-youtube.yml"):
    caminho = os.path.join(RAIZ, ".github", "workflows", wf)
    texto = open(caminho, encoding="utf-8").read()
    ok(f"{wf} não tem cron (nada publica sozinho)", "schedule:" not in texto)
    ok(f"{wf} só roda por workflow_dispatch", "workflow_dispatch:" in texto)
_envio_wf = open(os.path.join(RAIZ, ".github", "workflows", "enviar-youtube.yml"), encoding="utf-8").read()
ok("o workflow de envio exige a confirmação do dono", "confirmacao" in _envio_wf)
ok("o workflow de envio roda as barreiras antes de tocar a rede",
   _envio_wf.index("testes-youtube-oauth.py") < _envio_wf.index("enviar-youtube.py"))
ok("o workflow de envio não recebe segredo de escrita em rede",
   "contents: write" not in _envio_wf)

print("\n%d/%d testes do OAuth e do envio do YouTube passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
