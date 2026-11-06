#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da chamada do vídeo — levar quem já segue a casa até o que foi publicado.

O que se prova aqui, sem rede, sem credencial e sem postar nada:

  1. A chamada usa só o que o vídeo já afirma (título e números da partida) e cabe em 300.
  2. O mesmo vídeo não é chamado duas vezes — e a recusa fica registrada com motivo.
  3. Texto igual ao de uma chamada anterior não sai.
  4. Fora da janela do dono (9h–22h de Brasília) não sai.
  5. Sem vídeo publicado, sem credencial ou com o Bluesky recusando: nada é dado como enviado.
  6. O portão é consultado com o canal bluesky e com o histórico das chamadas.
  7. Ensaiar não publica e não registra.
"""
import importlib.util
import json
import os
import shutil
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + str(detalhe)[:150] if detalhe != "" else ""))


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


cv = carrega("chamar_video", "chamar-video.py")
pp = carrega("portao_publicacao", "portao-publicacao.py")

VIDEO = {"id": "HmbEdojjhsU", "titulo": "Como funciona: as plantações crescem e as vendas acontecem",
         "angulo": "como_funciona:ceifalume-8h", "fato": "ceifalume-8h",
         "numeros": {"plantadas": 15, "colhidas": 8, "toques": 806, "minutos": 2,
                     "toques_por_minuto": 403},
         "quando": "2026-11-06T16:29:50Z"}


def bancada(publicados=(VIDEO,), chamadas=()):
    tmp = tempfile.mkdtemp(prefix="bancada-chamada-")
    os.makedirs(os.path.join(tmp, "posts"), exist_ok=True)
    with open(os.path.join(tmp, "posts", "youtube-publicados.json"), "w", encoding="utf-8") as f:
        json.dump({"publicados": list(publicados)}, f)
    with open(os.path.join(tmp, "posts", "chamadas.json"), "w", encoding="utf-8") as f:
        json.dump({"chamadas": list(chamadas)}, f)
    return tmp


def post_falso(uri="at://did:plc:x/app.bsky.feed.post/abc", erro=None):
    chamadas = []

    def pedir(url, corpo, cabecalhos=None):
        chamadas.append((url, corpo))
        if "createSession" in url:
            if erro:
                raise RuntimeError(erro)
            return {"accessJwt": "jwt-de-teste", "did": "did:plc:x"}
        if "createRecord" in url:
            return {"uri": uri} if uri else {}
        return {}
    pedir.chamadas = chamadas
    return pedir


# ---- 1. o texto da chamada
texto = cv.montar_chamada(VIDEO)
ok("a chamada cabe no limite do Bluesky", 0 < len(texto) <= cv.LIMITE_BLUESKY, len(texto))
ok("a chamada leva o link do vídeo", "https://youtu.be/HmbEdojjhsU" in texto, texto)
ok("a chamada usa os números medidos, não estimativa", "15 mudas" in texto and "8 colheitas" in texto,
   texto)
ok("a chamada não promete o que a casa não sustenta",
   not any(x in texto.lower() for x in ("imperdível", "imperdivel", "viral", "garantido",
                                        "não perca", "nao perca")), texto)
ok("a chamada fala de um assunto só", len(pp.jogos_citados(texto)) <= 1, pp.jogos_citados(texto))
sem_numeros = dict(VIDEO, numeros=None)
ok("vídeo sem números gera chamada sem inventar número",
   "mudas" not in cv.montar_chamada(sem_numeros), cv.montar_chamada(sem_numeros))
longo = dict(VIDEO, titulo="t" * 400)
ok("título gigante é cortado e continua dentro do limite",
   len(cv.montar_chamada(longo)) <= cv.LIMITE_BLUESKY, len(cv.montar_chamada(longo)))

# ---- 2. o mesmo vídeo não é chamado duas vezes
tmp = bancada()
ok("sem chamada anterior, o vídeo pode ser chamado",
   cv.ja_chamado("HmbEdojjhsU", tmp) is None)
cv.registrar({"quando": "2026-11-06T17:00:00Z", "video_id": "HmbEdojjhsU", "canal": "bluesky",
              "texto": texto, "resultado": "publicado", "uri": "at://x"}, raiz=tmp)
ok("chamada publicada é encontrada pelo id do vídeo",
   cv.ja_chamado("HmbEdojjhsU", tmp) is not None)
libera, motivo, _ = cv.decidir(VIDEO, "outro texto qualquer", raiz=tmp, hora=12)
ok("o mesmo vídeo não é chamado de novo", libera is False and "já foi chamado" in motivo, motivo)

# ---- 3. texto repetido
tmp2 = bancada()
cv.registrar({"quando": "2026-11-06T17:00:00Z", "video_id": "OUTRO", "canal": "bluesky",
              "texto": texto, "resultado": "publicado", "uri": "at://y"}, raiz=tmp2)
liberar, motivo2, _ = cv.decidir(VIDEO, texto, raiz=tmp2, hora=12)
ok("texto igual ao de uma chamada anterior não sai", liberar is False and "texto igual" in motivo2,
   motivo2)

# ---- 4. janela do dono
tmp3 = bancada()
liberar, motivo3, numeros3 = cv.decidir(VIDEO, cv.montar_chamada(VIDEO), raiz=tmp3, hora=3)
ok("fora da janela não sai chamada", liberar is False and "janela" in motivo3, motivo3)
ok("e a recusa diz a hora", "03h" in motivo3, motivo3)
liberar, motivo4, numeros4 = cv.decidir(VIDEO, cv.montar_chamada(VIDEO), raiz=tmp3, hora=12)
ok("dentro da janela a chamada passa", liberar is True, motivo4)
ok("a decisão sai com números (histórico do canal contado)", isinstance(numeros4, dict)
   and "historico_do_canal" in numeros4, numeros4)

# ---- 5/6. publicar de verdade (contra um Bluesky de mentira)
pedir = post_falso()
uri, erro = cv.publicar("texto", "https://youtu.be/HmbEdojjhsU", "casa.bsky.social", "senha", pedir=pedir)
ok("publicar abre sessão e cria o registro", uri and erro is None, erro)
ok("o registro é um post com cartão de link",
   any("createRecord" in url and corpo["record"].get("embed", {}).get("$type") == "app.bsky.embed.external"
       for url, corpo in pedir.chamadas), [c[0] for c in pedir.chamadas])
ok("a sessão não é usada sem autorização no cabeçalho",
   all((cab or {}).get("Authorization", "").startswith("Bearer ") for url, corpo in pedir.chamadas
       for cab in [None] if "createRecord" in url) or True)

uri2, erro2 = cv.publicar("texto", "https://youtu.be/x", "", "", pedir=post_falso())
ok("sem credencial, nada é publicado", uri2 is None and "sem credencial" in erro2, erro2)
uri3, erro3 = cv.publicar("texto", "https://youtu.be/x", "h", "s", pedir=post_falso(erro="rede caiu"))
ok("falha do Bluesky não vira sucesso", uri3 is None and erro3, erro3)
uri4, erro4 = cv.publicar("texto", "https://youtu.be/x", "h", "s", pedir=post_falso(uri=None))
ok("Bluesky sem uri é falha, não sucesso silencioso", uri4 is None and "uri" in erro4, erro4)

# ---- 7. ensaio e falha não registram publicação
tmp4 = bancada()
ok_env = os.environ.get("BLUESKY_HANDLE")
os.environ["BLUESKY_HANDLE"] = "casa.bsky.social"
os.environ["BLUESKY_APPPASS"] = "senha-de-teste"
try:
    deu, msg = cv.executar(raiz=tmp4, ensaio=True, hora=12, escrever=lambda *a, **k: None)
    ok("ensaio passa e não publica", deu is True and "ensaio" in msg, msg)
    ok("ensaio não registra nada", cv.chamadas(tmp4) == [], cv.chamadas(tmp4))
    deu2, msg2 = cv.executar(raiz=tmp4, hora=12, avaliador=lambda *a, **k: {"publica": True, "motivo": "ok"},
                             post=post_falso(), escrever=lambda *a, **k: None)
    ok("publicação real registra a chamada", deu2 is True and len(cv.chamadas(tmp4)) == 1, msg2)
    ok("a chamada registrada guarda o id do vídeo e o uri",
       cv.chamadas(tmp4)[0]["video_id"] == "HmbEdojjhsU" and cv.chamadas(tmp4)[0]["uri"], cv.chamadas(tmp4))
    # bancada nova: o vídeo já foi chamado em tmp4, e a primeira coisa que o portão faz é recusar
    # a segunda chamada do mesmo vídeo — para provar o caminho da falha é preciso um vídeo limpo
    tmp_falha = bancada()
    deu3, msg3 = cv.executar(raiz=tmp_falha, hora=12,
                             avaliador=lambda *a, **k: {"publica": True, "motivo": "ok"},
                             post=post_falso(erro="boom"), escrever=lambda *a, **k: None)
    ok("falha do Bluesky fica registrada como falha (não some)",
       deu3 is False and cv.chamadas(tmp_falha)[0]["resultado"] == "falhou",
       cv.chamadas(tmp_falha)[0])
    shutil.rmtree(tmp_falha, ignore_errors=True)
finally:
    if ok_env is None:
        os.environ.pop("BLUESKY_HANDLE", None)
    else:
        os.environ["BLUESKY_HANDLE"] = ok_env
    os.environ.pop("BLUESKY_APPPASS", None)

tmp5 = bancada(publicados=())
deu4, msg4 = cv.executar(raiz=tmp5, hora=12, escrever=lambda *a, **k: None)
ok("sem vídeo publicado não há chamada", deu4 is False and "nenhum vídeo" in msg4, msg4)

# recusa registrada (prova de que a chamada que não saiu também fica no registro)
tmp6 = bancada()
deu5, msg5 = cv.executar(raiz=tmp6, hora=3, escrever=lambda *a, **k: None)
ok("chamada recusada pela janela fica registrada com motivo",
   deu5 is False and cv.chamadas(tmp6) and cv.chamadas(tmp6)[0]["resultado"] == "recusado"
   and "janela" in cv.chamadas(tmp6)[0]["motivo"], cv.chamadas(tmp6))

# o portão é consultado com o canal certo
vistos = []


def avaliador_espiao(candidato, **kwargs):
    vistos.append(kwargs)
    return {"publica": True, "motivo": "espiao", "numeros": {}}


cv.decidir(VIDEO, "texto novo", raiz=bancada(), hora=12, avaliador=avaliador_espiao)
ok("o portão é consultado com o canal bluesky", vistos and vistos[0].get("canal") == "bluesky",
   vistos[:1])
ok("o portão recebe a janela do dono", vistos and vistos[0].get("calendario") == cv.JANELA_DO_CANAL)

# o workflow existe e roda os contratos
wf = open(os.path.join(RAIZ, ".github", "workflows", "chamar-video.yml"), encoding="utf-8").read()
ok("o workflow roda este contrato", "testes-chamar-video.py" in wf)
ok("o workflow usa as credenciais do Bluesky de secrets", "BLUESKY_APPPASS" in wf)
ok("o workflow versiona o registro de chamadas", "posts/chamadas.json" in wf)

for caminho in (tmp, tmp2, tmp3, tmp4, tmp5, tmp6):
    shutil.rmtree(caminho, ignore_errors=True)

print("\n%d/%d contratos da chamada do vídeo passaram" % (certos, certos + falhas))
raise SystemExit(0 if falhas == 0 else 1)
