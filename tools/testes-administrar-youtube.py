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
ok("e diz exatamente o que falta", any("falta consentimento" in l for l in linhas), linhas)
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

# ------------------------------------------------------------------ token revogado é dito, não escondido
def _renovar_revogado(ci, cs, r):
    return None, "renovação recusada: invalid_grant"


_linhas_r, _ok_r = adm.estado({"YT_REFRESH_TOKEN": "r", "YT_CLIENT_ID": "i", "YT_CLIENT_SECRET": "s"},
                             renovar=_renovar_revogado, get=GetFalso({}))
ok("token revogado gera alerta explícito com o que fazer",
   any("ALERTA" in l and "autorizar-youtube" in l for l in _linhas_r), _linhas_r)

# ------------------------------------------------------------------ prova só com API key
_gk = GetFalso({"key=": {"items": [{"snippet": {"title": "Canal do dono"}, "statistics":
                                     {"subscriberCount": "24", "videoCount": "5", "viewCount": "900"}}]}})
linhas_k, ok_k = adm.estado_por_chave({"YT_API_KEY": "k", "YT_CHANNEL_ID": "UC1"}, get=_gk)
ok("API key sozinha prova o canal", ok_k and "Canal do dono" in linhas_k[0], linhas_k)
ok("a prova por API key mostra números reais", "24 inscritos" in linhas_k[0], linhas_k)
sem_chave, ok_sem = adm.estado_por_chave({}, get=_gk)
ok("sem chave, a prova não finge", ok_sem is False and "sem API key" in sem_chave[0], sem_chave)
_erro = GetFalso({"key=": {}})
_erro.__call__ = lambda url, token, metodo="GET", corpo=None, timeout=45: (None, "HTTP 400: API key not valid")
linhas_e, ok_e = adm.estado_por_chave({"YT_API_KEY": "k", "YT_CHANNEL_ID": "UC1"}, get=_erro)
ok("chave inválida aparece como chave inválida", ok_e is False and "não leu o canal" in linhas_e[0], linhas_e)


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

# ------------------------------------------------------------------ estado medido
_e = os.path.join(RAIZ, "ESTADO-AGORA.md")
ok("o retrato do estado existe", os.path.exists(_e))
if os.path.exists(_e):
    _t = " ".join(open(_e, encoding="utf-8").read().split())
    ok("o retrato registra o prazo ilimitado medido", "ILIMITADO" in _t and "refresh_token_expires_in" in _t)
    ok("o retrato não contém valor de segredo", "1//0" not in _t and "GOCSPX-" not in _t and "AIza" not in _t)
    ok("o retrato declara o que continua fora do alcance", "fora do alcance" in _t)

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

# ------------------------------------------------------------------ sem token não estoura
ok("requisição sem token não monta 'Bearer None'",
   adm._requisicao("https://exemplo.invalido/x?key=k", None)[0] is None)


class GetExplode:
    def __call__(self, *a, **k):
        raise TypeError("Bearer None")


linhas_x, ok_x = adm.estado_por_chave({"YT_API_KEY": "k", "YT_CHANNEL_ID": "UC1"}, get=GetExplode())
ok("exceção na leitura vira linha de log, não pilha de erro",
   ok_x is False and "falhou" in linhas_x[0] and "TypeError" in linhas_x[0], linhas_x)

print("\n%d/%d testes do administrador do YouTube passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
