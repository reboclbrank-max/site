#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do medidor de desempenho — 2026-10-24.

O risco deste tipo de ferramenta é virar enfeite: inventar número, contar post como
resultado, escolher "melhor horário" com quatro amostras ou duplicar o registro a cada
uma das oito execuções diárias. Cada teste abaixo cerca um desses riscos, sem tocar a
rede (a busca HTTP é substituída por dados de teste).
"""
import datetime
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
ok("mede só o que é público (sem token nem segredo)",
   "Authorization" not in fonte and "secret" not in fonte.lower() and "ghp_" not in fonte)
ok("não publica nada (nenhum POST, nenhum createRecord)",
   "method=\"POST\"" not in fonte and "createRecord" not in fonte)

# 11. o registro diário traz os dois tipos e o total, sem inventar
com_fonte([post("⚽ PRANCHETA", curtidas=2), post("Nice!", curtidas=0)],
          perfil_dados={"followersCount": 34, "followsCount": 10, "postsCount": 338})
dados = metricas.analisar()
linha = metricas.linha_do_dia(dados)
ok("linha do dia tem seguidores, posts, média e os dois tipos",
   all(t in linha for t in ("bsky_seguidores=34", "posts_proprios=2", "eng_medio=", "promo:", "comentario:")), linha)

print("\n%d/%d testes do medidor de desempenho passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
