#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do administrador do YouTube. Nenhum teste toca a rede."""
import importlib.util
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("administrar_yt", os.path.join(RAIZ, "tools", "administrar-youtube.py"))
adm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adm)

def renovar_falso(client_id, client_secret, refresh):
    """Dublê do OAuth: a barreira não toca a rede nem precisa de credencial de verdade."""
    if not (client_id and client_secret and refresh):
        return None, "faltam client_id, client_secret ou refresh_token"
    return "token-de-teste", None


certos = [0]
falhas = [0]


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos[0] += 1
        print("✔ " + nome)
    else:
        falhas[0] += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


# ------------------------------------------------------------------ sem consentimento não finge
linhas, feito = adm.estado(ambiente={})
ok("sem refresh_token, o estado não finge sucesso", feito is False, linhas)
ok("e diz exatamente o que falta", "falta consentimento" in linhas[0], linhas)
token, erro = adm.acesso({})
ok("acesso sem token devolve erro explicado", token is None and "consentimento" in erro)
token2, erro2 = adm.acesso({"YT_REFRESH_TOKEN": "x"})
token2, erro2 = adm.acesso({"YT_REFRESH_TOKEN": "x"}, renovar=renovar_falso)
ok("com refresh mas sem client_id, o erro é o do OAuth", token2 is None and "faltam" in erro2, erro2)

# ------------------------------------------------------------------ canal
class GetFalso:
    def __init__(self, respostas):
        self.respostas = respostas
        self.urls = []

    def __call__(self, url, token, metodo="GET", corpo=None, timeout=45):
        self.urls.append(url)
        for chave, valor in self.respostas.items():
            if chave in url:
                return valor, None
        return {}, None


canal_ok = {"items": [{"id": "UC1", "snippet": {"title": "R"}, "statistics": {
    "subscriberCount": "24", "videoCount": "5", "viewCount": "900"}}]}
get1 = GetFalso({"/channels": canal_ok})
c, erro = adm.canal("tok", get=get1)
ok("lê inscritos/vídeos/views do canal", c and (c["inscritos"], c["videos"], c["views"]) == (24, 5, 900), c)
ok("canal vazio vira erro claro", adm.canal("tok", get=GetFalso({"/channels": {"items": []}}))[1] == "a conta não tem canal")

# ------------------------------------------------------------------ divergências de metadado
video = {"id": "v1", "snippet": {"title": "antigo", "description": "velha", "tags": ["a", "b"]},
         "status": {"privacyStatus": "public"}}
ok("título diferente é detectado", "title" in adm.divergencias(video, {"titulo": "novo"}))
ok("descrição diferente é detectada", "description" in adm.divergencias(video, {"descricao": "nova"}))
ok("tags em outra ordem NÃO é divergência",
   adm.divergencias(video, {"tags": ["b", "a"]}) == {}, adm.divergencias(video, {"tags": ["b", "a"]}))
ok("tags diferentes são divergência", "tags" in adm.divergencias(video, {"tags": ["a"]}))
ok("vídeo já igual ao kit não gera nada",
   adm.divergencias(video, {"titulo": "antigo", "descricao": "velha", "tags": ["a", "b"]}) == {})
ok("kit vazio nunca apaga metadado do vídeo", adm.divergencias(video, {}) == {})

# ------------------------------------------------------------------ aplicar metadado
class PutFalso:
    def __init__(self):
        self.corpo = None
        self.metodo = None

    def __call__(self, url, token, metodo="GET", corpo=None, timeout=45):
        self.corpo = corpo
        self.metodo = metodo
        return {"id": "v1"}, None


put = PutFalso()
adm.aplicar_metadados("tok", video, {"title": "novo"}, put=put)
ok("aplicar usa PUT", put.metodo == "PUT", put.metodo)
ok("aplicar preserva descrição e tags que não mudaram",
   put.corpo["snippet"]["description"] == "velha" and put.corpo["snippet"]["tags"] == ["a", "b"], put.corpo)
ok("aplicar manda o id do vídeo", put.corpo["id"] == "v1")

# ------------------------------------------------------------------ auto não cria nem apaga
videos = {"search": {"items": [{"id": {"videoId": "v1"}}]},
          "videos?part=snippet,status": {"items": [video]}}
get2 = GetFalso({"/channels": canal_ok, "search": videos["search"], "videos?part": videos["videos?part=snippet,status"]})
put2 = PutFalso()
linhas2, feito2 = adm.auto(ambiente={"YT_REFRESH_TOKEN": "r", "YT_CLIENT_ID": "i", "YT_CLIENT_SECRET": "s"},
                           get=get2, put=put2, kit={"titulo": "antigo"}, renovar=renovar_falso)
ok("auto com kit igual não chama PUT", put2.corpo is None, str(linhas2))
put3 = PutFalso()
get3 = GetFalso({"/channels": canal_ok, "search": videos["search"], "videos?part": videos["videos?part=snippet,status"]})
linhas3, feito3 = adm.auto(ambiente={"YT_REFRESH_TOKEN": "r", "YT_CLIENT_ID": "i", "YT_CLIENT_SECRET": "s"},
                           get=get3, put=put3, kit={"titulo": "corrigido"}, renovar=renovar_falso)
ok("auto corrige título divergente", put3.corpo and put3.corpo["snippet"]["title"] == "corrigido", str(linhas3))
ok("auto nunca chama upload (videos.insert)", all("upload" not in u for u in get3.urls), str(get3.urls))
ok("auto nunca apaga", "DELETE" not in str(put3.metodo))

# ------------------------------------------------------------------ a trava do Google está documentada
texto = open(os.path.join(RAIZ, "tools", "administrar-youtube.py"), encoding="utf-8").read()
ok("o código avisa da trava de vídeo privado por projeto não auditado",
   "locked as private" in " ".join(texto.split()))
ok("o código não promete publicação que a API pode negar", "não dá para apelar" in texto)

# ------------------------------------------------------------------ guia do dono
_g = os.path.join(RAIZ, "GUIA-YOUTUBE.md")
ok("o guia do YouTube existe", os.path.exists(_g))
if os.path.exists(_g):
    guia = open(_g, encoding="utf-8").read()
    for link in ["console.cloud.google.com/projectcreate",
                 "apis/library/youtube.googleapis.com",
                 "console.cloud.google.com/auth/overview/create",
                 "console.cloud.google.com/auth/audience",
                 "console.cloud.google.com/auth/scopes",
                 "console.cloud.google.com/auth/clients/create",
                 "site/settings/secrets/actions",
                 "actions/workflows/autorizar-youtube.yml",
                 "support.google.com/youtube/contact/yt_api_form"]:
        ok("o guia dá link direto: " + link.split("/")[-1], link in guia)
    # a quebra de linha do markdown não pode esconder a instrução: normaliza antes de procurar
    _g2 = " ".join(guia.split())
    ok("o guia manda publicar o app (senão o token morre em 7 dias)",
       "Publicar app" in _g2 and "7 dias" in _g2)
    ok("o guia pede o tipo de cliente certo (fluxo de dispositivo)",
       "TVs e dispositivos de entrada limitada" in guia)
    ok("o guia usa a política de privacidade que responde 200",
       "reboclbrank-max.github.io/site/privacidade.html" in guia)
    ok("o guia corrige o número de cota antigo", "100 envios por dia" in guia)
    ok("o guia avisa que os segredos não vão pelo chat", "Não me mande esses valores pelo chat" in guia)
    _g3 = " ".join(guia.split())
    ok("o guia diz para NÃO enviar o app para verificação", "não envie para análise" in _g3.lower())
    ok("o guia avisa que logotipo obriga verificação", "Logotipo: deixe vazio" in _g3)
    ok("o guia distingue publicar de verificar", "publicar não é verificar" in _g3)

print("\n%d/%d testes do administrador do YouTube passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
