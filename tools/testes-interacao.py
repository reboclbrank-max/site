#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira da interação: cadência aprovada e escuta de conversa — 2026-10-24.

Dois riscos reais, ambos já observados no repositório:

1. `mestria.json` diz "3 devs/dia" desde 15/10/2026, mas o caçador entendia "3 por
   ciclo" e, com oito ciclos, publicava até 24 comentários por dia. O medidor de
   24/10 mostrou que esse comentário rende 0,85 de engajamento e 42% não recebe nada.
2. A casa nunca leu notificação: 40 respostas recebidas, nenhuma respondida.

Teste offline: não chama rede, não carrega segredo, não publica.
"""
import datetime
import importlib.util
import json
import os
import pathlib
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
espec = importlib.util.spec_from_file_location("postador", RAIZ / "tools" / "postador.py")
postador = importlib.util.module_from_spec(espec)
espec.loader.exec_module(postador)

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


# 1. a cadência aprovada é a que vale, e é por DIA
with tempfile.TemporaryDirectory() as d:
    caminho = os.path.join(d, "mestria.json")
    json.dump({"bluesky": {"interacao": "3 devs/dia, comentário genuíno SEM link"}}, open(caminho, "w"))
    ok("lê a cadência aprovada de interação (3/dia)", postador.limite_interacoes_dia(caminho) == 3,
       str(postador.limite_interacoes_dia(caminho)))
    json.dump({"bluesky": {"interacao": "1 dev/dia"}}, open(caminho, "w"))
    ok("respeita cadência menor se o dono mudar", postador.limite_interacoes_dia(caminho) == 1)
    json.dump({}, open(caminho, "w"))
    ok("sem texto de cadência, cai no padrão conservador",
       postador.limite_interacoes_dia(caminho) == postador.LIMITE_INTERACOES_DIA_PADRAO)
ok("arquivo de mestria ausente não quebra o ciclo",
   postador.limite_interacoes_dia("/caminho/que/nao/existe.json") == postador.LIMITE_INTERACOES_DIA_PADRAO)

# 2. a cota é diária: oito ciclos não podem multiplicar por oito
ok("primeira interação do dia é permitida", postador.vagas_de_interacao("2026-10-24", 3, {}) == 3)
ok("dia já cumprido não permite nova interação",
   postador.vagas_de_interacao("2026-10-24", 3, {"2026-10-24": 3}) == 0)
ok("cota nunca fica negativa",
   postador.vagas_de_interacao("2026-10-24", 3, {"2026-10-24": 9}) == 0)
por_dia_simulado, total_simulado = {}, 0
for _ in range(8):  # oito ciclos do dia, como em produção
    vagas = postador.vagas_de_interacao("2026-10-24", 3, por_dia_simulado)
    feitas = min(vagas, 3)
    por_dia_simulado["2026-10-24"] = por_dia_simulado.get("2026-10-24", 0) + feitas
    total_simulado += feitas
ok("oito ciclos com 3 interações/dia fecham em 3, não em 24", total_simulado == 3,
   "total simulado: %d" % total_simulado)

# 3. registro: formato antigo e novo convivem, dedup não quebra
with tempfile.TemporaryDirectory() as d:
    caminho = os.path.join(d, "interacoes.md")
    open(caminho, "w").write("at://velho/post/1\nat://novo/post/2\t2026-10-24T12:00:00Z\n")
    feitas, por_dia = postador.interacoes_registradas(caminho)
ok("formato antigo continua deduplicando", "at://velho/post/1" in feitas)
ok("formato novo deduplica pelo uri, não pela linha inteira", "at://novo/post/2" in feitas)
ok("conta interação do dia pelo carimbo", por_dia.get("2026-10-24") == 1, str(por_dia))
ok("registro sem arquivo não quebra", postador.interacoes_registradas("/nao/existe.md") == (set(), {}))

# 4. só conversa que a casa abriu pede resposta
DID = "did:plc:casa"
AGORA = datetime.datetime(2026, 10, 24, 12, 0)


def notif(uri, pai, reason="reply", horas_atras=1, autor="did:plc:fa"):
    quando = (AGORA - datetime.timedelta(hours=horas_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"reason": reason, "uri": uri, "cid": "c-" + uri, "indexedAt": quando,
            "author": {"did": autor},
            "record": {"text": "oi", "reply": {"parent": {"uri": pai}}}}


nosso = "at://" + DID + "/app.bsky.feed.post/abc"
lista = [
    notif("at://fa/1", nosso),                                          # resposta ao nosso post
    notif("at://fa/2", "at://outro/app.bsky.feed.post/x"),               # thread alheia
    notif("at://fa/3", nosso, reason="like"),                            # curtida não é conversa
    notif("at://fa/4", nosso, horas_atras=24 * 10),                      # velha demais
    notif("at://fa/5", nosso, autor=DID),                                # a própria casa
    notif("at://fa/6", nosso),                                           # já respondida
]
atencao = postador.respostas_que_pedem_atencao(lista, DID, {"at://fa/6"}, agora=AGORA)
ok("resposta ao conteúdo da casa entra na fila", [n["uri"] for n in atencao] == ["at://fa/1"],
   str([n["uri"] for n in atencao]))
ok("agradecimento em post alheio NÃO vira resposta",
   all(n["uri"] != "at://fa/2" for n in atencao))
ok("curtida não é respondida", all(n["uri"] != "at://fa/3" for n in atencao))
ok("notificação antiga não é respondida", all(n["uri"] != "at://fa/4" for n in atencao))
ok("a casa não responde a si mesma", all(n["uri"] != "at://fa/5" for n in atencao))
ok("conversa já respondida não é respondida de novo", all(n["uri"] != "at://fa/6" for n in atencao))
ok("sem did não há resposta (fail-closed)", postador.respostas_que_pedem_atencao(lista, None) == [])
ok("lista vazia de notificações não quebra", postador.respostas_que_pedem_atencao([], DID) == [])

# 5. o respondedor existe e está limitado
fonte = (RAIZ / "tools" / "postador.py").read_text(encoding="utf-8")
ok("o postador lê notificações (antes: zero leitura)",
   "listNotifications" in fonte and "respondedor de conversa" in fonte)
ok("a resposta passa pelo freio de texto",
   "texto_gerado_seguro(resposta)" in fonte)
ok("a resposta usa a cadência aprovada, não um número solto",
   "limite_interacoes_dia()" in fonte and "vagas_de_interacao(" in fonte)
ok("o caçador não usa mais '3 por ciclo'",
   "if feitas >= 3: break" not in fonte.replace("postador", ""))

# 6. ponte entre redes: existe tema que leva público de onde há gente para onde não há
fonte_temas = fonte
ok("a casa tem temas que divulgam uma rede dentro da outra",
   "bastidores dos jogos" in fonte_temas and "canais oficiais da casa" in fonte_temas)
temas_ponte = ["convide a seguir a conta no Instagram para ver os bastidores dos jogos",
               "convide a seguir a conta no Instagram para acompanhar as artes novas",
               "lembre que o site lista os canais oficiais da casa",
               "convide quem joga no navegador a seguir a conta no Instagram"]
canais = postador.DESTINOS_EDITORIAIS["canais"]
ok("todo tema de ponte roteia para o hub de canais, nunca para URL livre",
   all(postador.destino_editorial("", t) == canais for t in temas_ponte),
   str([postador.destino_editorial("", t) for t in temas_ponte]))

print("\n%d/%d verificações de interação passaram" % (certos, certos + falhas))
raise SystemExit(1 if falhas else 0)
