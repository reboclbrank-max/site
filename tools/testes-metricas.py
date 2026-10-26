#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do medidor de desempenho — 2026-10-24.

O risco deste tipo de ferramenta é virar enfeite: inventar número, contar post como
resultado, escolher "melhor horário" com quatro amostras ou duplicar o registro a cada
uma das oito execuções diárias. Cada teste abaixo cerca um desses riscos, sem tocar a
rede (a busca HTTP é substituída por dados de teste).
"""
import datetime
import json
import importlib.util
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("metricas", os.path.join(RAIZ, "tools", "metricas.py"))
metricas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metricas)

certos = 0
falhas = 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + detalhe if detalhe else ""))


def post(texto, curtidas=0, reposts=0, respostas=0, quando="2026-10-24T12:00:00.000Z", repost=False):
    item = {
        "post": {
            "uri": "at://x/" + str(abs(hash(texto))),
            "author": {"handle": metricas.ATOR},
            "record": {"text": texto, "createdAt": quando},
            "likeCount": curtidas,
            "repostCount": reposts,
            "replyCount": respostas,
        }
    }
    if repost:
        item["reason"] = {"$type": "app.bsky.feed.defs#reasonRepost"}
    return item


def com_fonte(itens, perfil_dados=None, erro_feed=None, erro_perfil=None):
    """Substitui a leitura de rede por dados de teste."""
    def falso_http(url, tentativas=2):
        if "getProfile" in url:
            return (perfil_dados if perfil_dados is not None else {}, erro_perfil)
        return ({"feed": itens, "cursor": None}, erro_feed) if not erro_feed else (None, erro_feed)
    metricas.http_json = falso_http


# 1. classificação: conteúdo dos jogos vs comentário em post alheio
ok("separa conteúdo dos jogos de comentário em post alheio",
   metricas.classificar("⚽ Sou TÉCNICO — PRANCHETA é manager de futebol") == "promo"
   and metricas.classificar("Nice insight! Love how you use invisible lines") == "comentario")

# 2. engajamento soma curtida, repost e resposta
ok("engajamento soma curtidas, reposts e respostas",
   metricas.engajamento({"likeCount": 2, "repostCount": 1, "replyCount": 3}) == 6)

# 3. repost de terceiro não entra como conteúdo próprio
com_fonte([
    post("⚽ PRANCHETA", curtidas=2),
    post("post de outra pessoa", curtidas=9, repost=True),
])
dados = metricas.analisar()
ok("repost de terceiro não conta como post da casa",
   dados["resumo"]["total"]["posts"] == 1, str(dados["resumo"]["total"]))

# 4. média é por classe, não global
com_fonte([
    post("⚽ PRANCHETA", curtidas=4),
    post("⚽ CEIFALUME", curtidas=2),
    post("Great, I get it! Keep pushing", curtidas=0),
])
dados = metricas.analisar()
ok("média por classe está correta",
   dados["resumo"]["promo"]["media"] == 3.0 and dados["resumo"]["comentario"]["media"] == 0.0,
   str(dados["resumo"]))

# 5. conta a taxa de posts sem nenhum engajamento
com_fonte([post("Great!", curtidas=0), post("Nice!", curtidas=0), post("Ok!", curtidas=1)])
dados = metricas.analisar()
ok("taxa sem engajamento é calculada, não estimada",
   dados["resumo"]["comentario"]["taxa_sem_engajamento"] == 66.7,
   str(dados["resumo"]["comentario"]))

# 6. fonte fora do ar NÃO vira zero
com_fonte([], erro_feed="URLError")
dados = metricas.analisar()
linha = metricas.linha_do_dia(dados)
ok("fonte indisponível aparece como NAO_OBSERVAVEL, nunca como zero",
   "NAO_OBSERVAVEL" in linha and "eng_medio=0" not in linha, linha)

# 7. horário com amostra pequena é declarado ruído
com_fonte([post(f"⚽ PRANCHETA {i}", curtidas=i % 3, quando=f"2026-10-24T{h:02d}:00:00Z") for i, h in enumerate(range(0, 6))])
dados = metricas.analisar()
_, suficiente = metricas.por_hora(dados["posts"])
ok("amostra pequena não sustenta escolher horário", suficiente is False)

# 8. horário com massa suficiente pode concluir
muitos = [post(f"⚽ PRANCHETA {i}", curtidas=i % 5, quando=f"2026-10-24T{h:02d}:00:00Z")
          for h in range(0, 20) for i in range(6)]
com_fonte(muitos)
dados = metricas.analisar()
_, suficiente = metricas.por_hora(dados["posts"])
ok("amostra grande libera a leitura por horário", suficiente is True)

# 9. regravar o mesmo dia não duplica o bloco (o workflow roda 8x/dia)
com_fonte([post("⚽ PRANCHETA", curtidas=3)])
antigo_cwd = os.getcwd()
tmp = tempfile.mkdtemp()
os.chdir(tmp)
try:
    dados = metricas.analisar()
    metricas.SAIDA = "desempenho.md"
    metricas.gravar(dados)
    metricas.gravar(dados)
    metricas.gravar(dados)
    texto = open("desempenho.md", encoding="utf-8").read()
    hoje = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y")
    ok("regravar o mesmo dia não duplica o bloco",
       texto.count("## " + hoje) == 1, f"blocos de hoje: {texto.count('## ' + hoje)}")
finally:
    os.chdir(antigo_cwd)

# 10. não usa token, segredo nem escrita em rede
fonte = open(os.path.join(RAIZ, "tools", "metricas.py"), encoding="utf-8").read()
# O Bluesky continua sendo lido sem credencial; o Instagram usa token do ambiente,
# e o teste garante que ele nunca sai do cabeçalho HTTP (nem em log, nem em arquivo).
trecho_publico = fonte.split("def http_json_autorizado")[0]
ok("medição pública do Bluesky não manda Authorization",
   "Authorization" not in trecho_publico, "credencial vazou para o caminho público")
ok("token do Instagram vem do ambiente, nunca literal no código",
   'os.environ.get("IG_TOKEN")' in fonte and "ghp_" not in fonte
   and all(t not in fonte for t in ("IGAA", "Bearer IG", "ATATT")))
ok("nenhum print grava token nem cabeçalho",
   not any("print(" in l and ("token" in l or "Authorization" in l) for l in fonte.splitlines()))
ok("não publica nada (nenhum POST, nenhum createRecord)",
   "method=\"POST\"" not in fonte and "createRecord" not in fonte)

# 11. o registro diário traz os dois tipos e o total, sem inventar
com_fonte([post("⚽ PRANCHETA", curtidas=2), post("Nice!", curtidas=0)],
          perfil_dados={"followersCount": 34, "followsCount": 10, "postsCount": 338})
dados = metricas.analisar()
linha = metricas.linha_do_dia(dados)
ok("linha do dia tem seguidores, posts, média e os dois tipos",
   all(t in linha for t in ("bsky_seguidores=34", "posts_proprios=2", "eng_medio=", "promo:", "comentario:")), linha)

# 12. conversa: quem respondeu ao conteúdo da casa e quem ficou sem resposta
def com_threads(respostas_por_uri, erro_thread=None):
    """Fonte falsa: feed genérico + thread descrita caso a caso."""
    def falso(url, tentativas=2):
        if "getProfile" in url:
            return ({"followersCount": 34, "followsCount": 10, "postsCount": 338}, None)
        if "getPostThread" in url:
            uri = url.split("uri=")[1].split("&")[0]
            if erro_thread:
                return (None, erro_thread)
            return ({"thread": {"replies": [
                {"post": {"author": {"handle": a}}} for a in respostas_por_uri.get(uri, [])
            ]}}, None)
        return ({"feed": [], "cursor": None}, None)
    metricas.http_json = falso


def meu(uri, classe_texto, respostas=1):
    return {"uri": uri, "classe": metricas.classificar(classe_texto), "respostas": respostas}


# dois posts de conteúdo próprio: um com resposta de fã, outro já atendido pela casa
com_threads({
    "at://promo-sem-resposta": ["fa.novo"],
    "at://promo-atendido": ["fa.antigo", metricas.ATOR],
})
conv = metricas.interacao([meu("at://promo-sem-resposta", "⚽ PRANCHETA"),
                           meu("at://promo-atendido", "🌙 CEIFALUME")])
ok("resposta ao conteúdo da casa sem retorno vira pendência",
   conv["por_classe"]["promo"]["pendentes"] == 1, str(conv["por_classe"]["promo"]))
ok("resposta já atendida não conta como pendente",
   conv["por_classe"]["promo"]["respondidas"] == 1, str(conv["por_classe"]["promo"]))

# 13. retribuição em post alheio não é fila de resposta
com_threads({"at://comentario": ["autor.do.post"]})
conv = metricas.interacao([meu("at://comentario", "que jogo bonito")])
ok("agradecimento em post alheio não entra como pendência de resposta",
   conv["por_classe"]["promo"]["pendentes"] == 0 and conv["por_classe"]["comentario"]["respostas"] == 1,
   str(conv["por_classe"]))

# 14. thread ilegível não vira zero: vira NAO_OBSERVAVEL
com_threads({}, erro_thread="URLError")
conv = metricas.interacao([meu("at://x", "⚽ PRANCHETA")])
ok("thread fora do ar = fonte_ok False (não zero)",
   conv["fonte_ok"] is False and conv["posts_checados"] == 0, str(conv))
com_fonte([post("⚽ PRANCHETA", respostas=3)])
metricas.interacao = lambda posts, max_threads=40: {"posts_checados": 0, "por_classe": {},
                                                    "respostas_recebidas": 0, "respondidas": 0,
                                                    "pendentes": 0, "fonte_ok": False, "erro": "URLError"}
dados = metricas.analisar()
ok("linha do dia marca interacao=NAO_OBSERVAVEL quando a thread falha",
   "interacao=NAO_OBSERVAVEL" in metricas.linha_do_dia(dados), metricas.linha_do_dia(dados))

# 15. placar de metas: alvo, falta e ausência de leitura
import tempfile as _tf
metas_teste = {
    "ig_30_dias": {"inicio": "2026-10-13", "posts": 30, "seguidores": 50},
    "bsky_30_dias": {"seguidores": 50},
    "yt_30_dias": {"inscritos": 40, "shorts": 4},
}
with _tf.TemporaryDirectory() as d:
    caminho = os.path.join(d, "metas.json")
    json.dump(metas_teste, open(caminho, "w"))
    linhas, ctx = metricas.placar_metas(
        {"bsky_seguidores": 34, "ig_seguidores": None, "ig_posts": None},
        caminho=caminho, hoje=datetime.date(2026, 10, 24))
b = [l for l in linhas if l["meta"].startswith("Bluesky")][0]
i = [l for l in linhas if l["meta"] == "Instagram: seguidores"][0]
y = [l for l in linhas if l["meta"].startswith("YouTube: inscritos")][0]
ok("placar calcula o que falta para a meta observável", b["observado"] == 34 and b["falta"] == 16, str(b))
ok("meta sem leitura vira SEM_LEITURA, nunca zero",
   i["observado"] is None and i["status"] == "SEM_LEITURA", str(i))
ok("meta de canal sem API não é contada como observada", y["status"] == "SEM_LEITURA", str(y))
ok("placar informa prazo e dias restantes", ctx["dias_restantes"] == 19, str(ctx))
ok("o placar não inventa ritmo quando não há leitura", i["por_dia"] is None, str(i))

# 16. Instagram: contadores e engajamento por formato, sem inventar zero
def com_instagram(contadores, midias=None, erro=None):
    def falso(url, token, tentativas=2):
        if "/media" in url:
            if erro:
                return (None, erro)
            return ({"data": midias or []}, None)
        return (contadores, None)
    metricas.http_json_autorizado = falso


os.environ["IG_TOKEN"] = "valor-de-teste"
os.environ["IG_USER_ID"] = "123"
com_instagram({"followers_count": 0, "media_count": 15},
              [{"like_count": 3, "comments_count": 1, "media_type": "IMAGE"},
               {"like_count": 0, "comments_count": 0, "media_type": "IMAGE"},
               {"like_count": 9, "comments_count": 0, "media_type": "VIDEO"}])
ig, motivo = metricas.observado_instagram()
ok("Instagram: zero seguidores só é zero se a API disser zero",
   ig["seguidores"] == 0 and motivo is None, str(motivo))
ok("Instagram: engajamento separado por formato",
   ig["por_tipo"]["IMAGE"]["media"] == 2.0 and ig["por_tipo"]["VIDEO"]["media"] == 9.0, str(ig["por_tipo"]))
ok("Instagram: conta publicação sem engajamento",
   ig["por_tipo"]["IMAGE"]["zero"] == 1, str(ig["por_tipo"]["IMAGE"]))

com_instagram({"followers_count": 12}, None)
ig, motivo = metricas.observado_instagram()
ok("Instagram: resposta sem os contadores não vira medição", ig is None and "contadores" in motivo, str(motivo))

com_instagram({"followers_count": 5, "media_count": 3}, erro="403")
ig, motivo = metricas.observado_instagram()
ok("Instagram: lista de mídias recusada não zera o engajamento",
   ig["seguidores"] == 5 and "midias_motivo" in ig and "por_tipo" not in ig, str(ig))

os.environ.pop("IG_TOKEN", None)
ig, motivo = metricas.observado_instagram()
ok("Instagram: sem credencial no runtime é NAO_OBSERVAVEL, não zero",
   ig is None and "sem credencial" in motivo, str(motivo))

# 17. itch: duas contas, uma chave cada, sem inventar zero
def com_itch(resposta_por_chave):
    def falso(url, token, tentativas=2):
        return resposta_por_chave.get(token, (None, "403"))
    metricas.http_json_autorizado = falso


com_itch({
    "chave-a": ({"games": [{"title": "Ceifalume", "downloads_count": 44, "views_count": 900, "published": True},
                           {"title": "Rascunho", "downloads_count": 99, "published": False}]}, None),
    "chave-b": ({"games": [{"title": "Prancheta", "downloads_count": 12, "views_count": 200}]}, None),
})
itch, motivo = metricas.observado_itch("chave-a,chave-b")
ok("itch soma as duas contas", itch["downloads"] == 56 and itch["contas_lidas"] == 2, str(motivo))
ok("itch ignora jogo não publicado", all(j["titulo"] != "Rascunho" for j in itch["jogos"]))
ok("itch ordena por download", itch["jogos"][0]["titulo"] == "Ceifalume")

com_itch({})  # todas as chaves recusadas
itch, motivo = metricas.observado_itch("chave-a")
ok("itch com chave recusada é NAO_OBSERVAVEL, não zero", itch is None and "recusada" in motivo, str(motivo))
os.environ.pop("ITCH_API_KEYS", None)
itch, motivo = metricas.observado_itch()
ok("itch sem chave no runtime é NAO_OBSERVAVEL", itch is None and "sem chave" in motivo, motivo)

# 18. YouTube: contadores públicos e contagem de shorts
def com_youtube(canal, playlist=None, videos=None, erro=None):
    def falso(url, tentativas=2):
        if erro:
            return (None, erro)
        if "/channels" in url:
            return (canal, None)
        if "/playlistItems" in url:
            return (playlist if playlist is not None else {}, None)
        return (videos if videos is not None else {}, None)
    metricas.http_json = falso


canal_ok = {"items": [{"statistics": {"subscriberCount": "24", "videoCount": "7", "viewCount": "1500"},
                       "contentDetails": {"relatedPlaylists": {"uploads": "UUxxx"}}}]}
com_youtube(canal_ok,
            {"items": [{"contentDetails": {"videoId": "a"}}, {"contentDetails": {"videoId": "b"}},
                       {"contentDetails": {"videoId": "c"}}]},
            {"items": [{"contentDetails": {"duration": "PT45S"}},
                       {"contentDetails": {"duration": "PT8M"}},
                       {"contentDetails": {"duration": "PT59S"}}]})
yt, motivo = metricas.observado_youtube("chave-yt")
ok("YouTube lê inscritos e vídeos", yt["inscritos"] == 24 and yt["videos"] == 7, str(motivo))
ok("YouTube conta shorts por duração (até 61s)", yt["shorts"] == 2 and yt["videos_conferidos"] == 3, str(yt))

com_youtube({"items": []})
yt, motivo = metricas.observado_youtube("chave-yt")
ok("YouTube sem canal encontrado não vira zero", yt is None and "recusada" in motivo, str(motivo))

com_youtube({"items": [{"statistics": {"hiddenSubscriberCount": True}}]})
yt, motivo = metricas.observado_youtube("chave-yt")
ok("YouTube com inscritos ocultos é NAO_OBSERVAVEL", yt is None and "contadores" in motivo, str(motivo))

com_youtube(canal_ok, erro="quotaExceeded")
yt, motivo = metricas.observado_youtube("chave-yt")
ok("YouTube com erro de cota é NAO_OBSERVAVEL", yt is None and "recusada" in motivo, str(motivo))

os.environ.pop("YT_API_KEY", None)
yt, motivo = metricas.observado_youtube()
ok("YouTube sem chave no runtime é NAO_OBSERVAVEL", yt is None and "sem chave" in motivo, motivo)
ok("a chave do YouTube não é impressa em nenhum caminho",
   not any(("print(" in l and "YT_API_KEY" in l) for l in open(os.path.join(RAIZ, "tools", "metricas.py"), encoding="utf-8").read().splitlines()))

# 19. YouTube: separar o que é da casa do que é de outros jogos
videos_teste = [
    {"titulo": "Ceifalume: a horta acordou à noite", "descricao": "", "views": 230, "likes": 1,
     "comentarios": 0, "segundos": 27, "quando": "2026-10-01"},
    {"titulo": "Prancheta — simulador de futebol", "descricao": "", "views": 4, "likes": 0,
     "comentarios": 0, "segundos": 59, "quando": "2026-09-20"},
    {"titulo": "New game Rumble Knights - idle RPG", "descricao": "", "views": 700, "likes": 9,
     "comentarios": 2, "segundos": 40, "quando": "2026-08-11"},
    {"titulo": "New game Dragon Village Collection", "descricao": "jogo de terceiro", "views": 211,
     "likes": 3, "comentarios": 0, "segundos": 35, "quando": "2026-08-02"},
]
r = metricas.resumo_youtube(videos_teste)
ok("reconhece conteúdo da casa pelo título", r["casa"]["n"] == 2 and r["terceiros"]["n"] == 2, str(r["casa"]))
ok("soma visualizações por grupo", r["casa"]["views"] == 234 and r["terceiros"]["views"] == 911)
ok("calcula a fatia de visualizações da casa", r["casa"]["fatia_views"] == 20.4, str(r["casa"].get("fatia_views")))
ok("lista os melhores da casa em ordem", [m["views"] for m in r["casa"]["melhores"]] == [230, 4])
ok("vídeo sem título não quebra", metricas.resumo_youtube([{"titulo": "", "views": 0}])["terceiros"]["n"] == 1)
ok("canal vazio não vira média zero falsa",
   metricas.resumo_youtube([])["casa"]["media_views"] is None)

# ---- 12. o placar não pode chamar de "sem leitura" o que é lido ---------------------------
# Defeito medido em 25/10/2026: a coluna "fonte" dizia "sem leitura automática" para YouTube e
# itch downloads, que o medidor lia normalmente (45 downloads, 24 inscritos). O dono leu esse
# rótulo e concluiu que não havia leitura. Rótulo errado é medição errada.
_meta_tmp = tempfile.mkdtemp()
_arq_metas = os.path.join(_meta_tmp, "metas.json")
with open(_arq_metas, "w", encoding="utf-8") as f:
    json.dump({"ig_30_dias": {"inicio": "2026-10-13", "posts": 30, "seguidores": 50},
               "yt_30_dias": {"inscritos": 40, "shorts": 4},
               "itch_30_dias": {"downloads": 100, "seguidores": 10},
               "bsky_30_dias": {"seguidores": 50}}, f)
_linhas, _ctx = metricas.placar_metas(observado={"yt_inscritos": 24, "yt_shorts": 5,
                                                 "itch_downloads": 45, "bsky_seguidores": 34,
                                                 "ig_seguidores": 0, "ig_posts": 18},
                                      caminho=_arq_metas)
_por_meta = {l["meta"]: l for l in _linhas}
ok("YouTube inscritos não é rotulado 'sem leitura automática'",
   "sem leitura" not in _por_meta["YouTube: inscritos"]["fonte"].lower(),
   _por_meta["YouTube: inscritos"]["fonte"])
ok("itch downloads não é rotulado 'sem leitura automática'",
   "sem leitura" not in _por_meta["itch: downloads"]["fonte"].lower(),
   _por_meta["itch: downloads"]["fonte"])
ok("itch seguidores declara SEM_API com a data da conferência",
   "SEM_API" in _por_meta["itch: seguidores"]["fonte"] and "25/10/2026" in _por_meta["itch: seguidores"]["fonte"])
ok("o que é lido aparece com número, não com NAO_OBSERVAVEL",
   _por_meta["itch: downloads"]["observado"] == 45 and _por_meta["yt_inscritos"] if False else
   (_por_meta["itch: downloads"]["observado"] == 45 and _por_meta["YouTube: inscritos"]["observado"] == 24))

# ---- 13. o rodapé diz o que é impossível e qual o substituto medido -----------------------
_saida = metricas.gravar_placar(_linhas, _ctx)
_texto_placar = open(_saida, encoding="utf-8").read()
ok("o placar avisa que itch seguidores não tem API", "não publica contagem de seguidores" in _texto_placar)
ok("o placar propõe a troca medida (visitas), sem trocar sozinho", "itch: visitas" in _texto_placar)
ok("o placar não inventa número para a meta impossível",
   "| itch: seguidores | 10 | NAO_OBSERVAVEL |" in _texto_placar)

# ---- 16. o placar mede o RETORNO desde a linha de partida --------------------------------
# "0 seguidores" sozinho não diz nada: pode ser canal parado desde sempre. A coluna nova
# mostra o que andou desde 13/10, e o rodapé nomeia a decisão quando nada andou.
_arq_partida = os.path.join(_meta_tmp, "metas2.json")
with open(_arq_partida, "w", encoding="utf-8") as f:
    json.dump({"ig_30_dias": {"inicio": "2026-10-13", "posts": 30, "seguidores": 50},
               "bsky_30_dias": {"seguidores": 50},
               "itch_30_dias": {"downloads": 100, "seguidores": 10},
               "yt_30_dias": {"inscritos": 40, "shorts": 4},
               "linha_de_partida_13_10": {"ig_seguidores": 0, "bsky_seguidores": 13,
                                          "itch_downloads": 44, "yt_inscritos": 24}}, f)
_obs = {"ig_seguidores": 0, "ig_posts": 18, "bsky_seguidores": 34,
        "itch_downloads": 46, "yt_inscritos": 24, "yt_shorts": 5}
_l2, _c2 = metricas.placar_metas(observado=_obs, caminho=_arq_partida)
_por2 = {l["meta"]: l for l in _l2}
ok("o placar calcula o quanto andou desde a partida", _por2["Bluesky: seguidores"]["delta"] == 21,
   str(_por2["Bluesky: seguidores"].get("delta")))
ok("canal que não moveu tem delta zero", _por2["Instagram: seguidores"]["delta"] == 0)
ok("meta sem leitura não ganha delta inventado", _por2["itch: seguidores"]["delta"] is None)
_c2["dias_decorridos"] = 20  # simula o prazo de duas semanas já vencido
_saida2 = metricas.gravar_placar(_l2, _c2)
_texto2 = open(_saida2, encoding="utf-8").read()
ok("a tabela mostra a coluna 'desde a partida'", "desde a partida" in _texto2)
ok("o placar diz em quantos dias nada voltou", "Sem retorno em" in _texto2, _texto2[-300:])
ok("a decisão de manter ou aposentar é nomeada como do dono",
   "decisão do dono" in _texto2 and "o robô não decide" in _texto2)
# amostra curta NÃO vira veredicto: 2 dias de canal parado é cedo para aposentar nada
_c3 = dict(_c2); _c3["dias_decorridos"] = 10
_saida3 = metricas.gravar_placar(_l2, _c3)
ok("poucos dias não viram veredicto de aposentadoria",
   "Sem retorno em" not in open(_saida3, encoding="utf-8").read())

# ---- 14. o relatório diário do postador usa o MESMO medidor ------------------------------
# Era aqui que nascia o "sem leitura automática": a régua do postador escrevia
# itch_downloads=NAO_OBSERVAVEL e youtube=NAO_OBSERVAVEL à mão.
_fonte_postador = open(os.path.join(RAIZ, "tools", "postador.py"), encoding="utf-8").read()
ok("o postador mede o itch pelo medidor de verdade", "observado_itch()" in _fonte_postador)
ok("o postador mede o YouTube pelo medidor de verdade", "observado_youtube()" in _fonte_postador)
ok("o postador não escreve mais itch/youtube como NAO_OBSERVAVEL fixo",
   '"itch_downloads=NAO_OBSERVAVEL",' not in _fonte_postador
   and '"youtube=NAO_OBSERVAVEL",' not in _fonte_postador)
ok("itch seguidores é declarado SEM_API no relatório diário", "itch_seguidores=SEM_API" in _fonte_postador)

# ---- 15. a régua do dia realmente devolve número (função, não texto) ----------------------
import types
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import postador

_falso = types.SimpleNamespace(
    observado_itch=lambda: ({"downloads": 45, "visitas": 175}, None),
    observado_youtube=lambda: ({"inscritos": 24, "shorts": 5}, None))
_linhas_dia, _lidas = postador.medicoes_de_plataforma(medidor=_falso)
ok("relatório do dia traz o download medido", "itch_downloads=45(api)" in _linhas_dia, str(_linhas_dia))
ok("relatório do dia traz os inscritos medidos", "youtube_inscritos=24(api)" in _linhas_dia, str(_linhas_dia))
ok("relatório do dia conta as leituras reais", _lidas == 2, str(_lidas))
ok("relatório do dia declara itch seguidores como SEM_API", "itch_seguidores=SEM_API" in _linhas_dia)

_sem = types.SimpleNamespace(observado_itch=lambda: (None, "sem chave no runtime"),
                             observado_youtube=lambda: (None, "HTTP 403"))
_linhas_sem, _lidas_sem = postador.medicoes_de_plataforma(medidor=_sem)
ok("sem leitura, o motivo aparece em vez do silêncio",
   "ITCH_API_KEYS" not in str(_linhas_sem) and "sem chave no runtime" in " ".join(_linhas_sem),
   str(_linhas_sem))
ok("sem leitura, nada é contado como lido", _lidas_sem == 0)
ok("medidor quebrado não derruba o ciclo", postador.medicoes_de_plataforma(
    medidor=types.SimpleNamespace(observado_itch=lambda: 1 / 0, observado_youtube=lambda: 1 / 0))[1] == 0)

print("\n%d/%d testes do medidor de desempenho passaram" % (certos, certos + falhas))
raise SystemExit(1 if falhas else 0)
