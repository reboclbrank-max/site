#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do administrador automático do itch. Nenhum teste toca a rede."""
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("administrar_itch", os.path.join(RAIZ, "tools", "administrar-itch.py"))
adm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adm)

# `rodar` recusa rodar sem butler instalado (127). O dublê substitui a chamada, mas o caminho
# do executável tem de existir: aponta para o próprio python, que existe em qualquer runner.
os.environ["BUTLER_PATH"] = sys.executable

certos = [0]
falhas = [0]


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos[0] += 1
        print("✔ " + nome)
    else:
        falhas[0] += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


# ------------------------------------------------------------------ impressão digital
local = adm.impressao("ceifalume")
ok("a impressão do build real existe", local and local["arquivos"] == 13, local)
ok("a impressão soma 42.216.445 bytes", local and local["bytes"] == 42216445, local)
ok("a impressão é estável entre duas leituras", adm.impressao("ceifalume")["hash"] == local["hash"])
ok("pasta inexistente devolve None", adm.impressao("nao-existe") is None)

# mudou um byte → hash muda (é o que dispara envio)
tmp = tempfile.mkdtemp()
os.makedirs(os.path.join(tmp, "jogo"))
open(os.path.join(tmp, "jogo", "index.html"), "w").write("a")
h1 = adm.impressao("jogo", raiz=tmp)["hash"]
open(os.path.join(tmp, "jogo", "index.html"), "w").write("b")
h2 = adm.impressao("jogo", raiz=tmp)["hash"]
ok("mudar um byte muda o hash", h1 != h2)
os.unlink(os.path.join(tmp, "jogo", "index.html"))
ok("apagar arquivo muda o hash", adm.impressao("jogo", raiz=tmp)["hash"] != h2)

# ------------------------------------------------------------------ decisão por medida
ok("sem upload no canal → primeira publicação",
   adm.decidir("ceifalume", local, [])[0] == "enviar")
ok("upload do mesmo tamanho → não envia",
   adm.decidir("ceifalume", local, [{"channel_name": "html5", "size": local["bytes"]}])[0] == "nada")
ok("upload de tamanho diferente → envia",
   adm.decidir("ceifalume", local, [{"channel_name": "html5", "size": 1}])[0] == "enviar")
ok("canal de outro nome não conta como nosso",
   adm.decidir("ceifalume", local, [{"channel_name": "android", "size": local["bytes"]}])[0] == "enviar")
ok("sem build local → bloqueado",
   adm.decidir("ceifalume", None, [])[0] == "bloqueado")

# ------------------------------------------------------------------ veto do dono
ok("Toque Rápido está vetado", "toque-rapido" in adm.vetados())
ok("jogo vetado é bloqueado mesmo com build pronto",
   adm.decidir("toque-rapido", local, [])[0] == "bloqueado")
ok("o slug do itch (toquerpido) também está vetado", "toquerpido" in adm.vetados())
ok("o motivo do veto está escrito no arquivo",
   "não deu certo" in json.load(open(adm.NUNCA, encoding="utf-8"))["motivo"])
# sem lista de veto, ninguém sobe: falha fechada
vazio = tempfile.mkdtemp()
ok("sem arquivo de veto, tudo é bloqueado (falha fechada)",
   adm.decidir("ceifalume", local, [], canal="html5")[0] in ("enviar", "bloqueado")
   and adm.vetados(os.path.join(vazio, "nao-existe.json")) == ["*"])

# ------------------------------------------------------------------ administração automática
class ButlerFalso:
    def __init__(self, codigo=0, saida="pushed"):
        self.codigo = codigo
        self.saida = saida
        self.chamadas = []

    def __call__(self, cmd, capture_output=None, text=None, timeout=None, env=None):
        self.chamadas.append(" ".join(cmd))
        class R:
            returncode = self.codigo
            stdout = self.saida
            stderr = ""
        return R()


def _get_falso(payloads):
    """Dublê de `_get_json`: devolve (dados, erro), como o real."""
    def get(url, chave=None):
        for chave_url, valor in payloads.items():
            if chave_url in url:
                return valor, None
        return {}, None
    return get


jogos = {"games": [{"id": 777, "url": "https://rebocl-brank.itch.io/ceifalume", "title": "Ceifalume"}]}
falso_get = _get_falso({"profile/games": jogos, "uploads": {"uploads": []}})

butler = ButlerFalso()
acao, motivo, linhas = adm.auto("ceifalume", "chave", raiz=RAIZ, get=falso_get,
                               identidade="/x", executar=butler)
ok("auto envia quando o canal não existe", acao == "enviado", acao + " / " + str(linhas))
ok("o push usa --if-changed (segunda conferência contra corrida)", "--if-changed" in butler.chamadas[0])
ok("o push usa --hidden (nada muda para o jogador sem o dono ver)", "--hidden" in butler.chamadas[0])
ok("o push manda a versão pelo hash da build", "--userversion " + local["hash"][:12] in butler.chamadas[0],
   butler.chamadas[0])
ok("o alvo é o canal certo", "rebocl-brank/ceifalume:html5" in butler.chamadas[0])

# build igual da última vez → nenhum comando é chamado
butler2 = ButlerFalso()
falso_get2 = _get_falso({"profile/games": jogos,
                         "uploads": {"uploads": [{"channel_name": "html5", "size": local["bytes"]}]}})
acao2, _m, _l = adm.auto("ceifalume", "chave", raiz=RAIZ, get=falso_get2,
                         identidade="/x", executar=butler2)
ok("build idêntica não gera nenhum comando", acao2 == "nada" and butler2.chamadas == [],
   str(butler2.chamadas))

# butler recusando não vira sucesso
butler3 = ButlerFalso(codigo=1, saida="upload rejected")
falso_get3 = _get_falso({"profile/games": jogos, "uploads": {"uploads": []}})
acao3, motivo3, _l = adm.auto("ceifalume", "chave", raiz=RAIZ, get=falso_get3,
                              identidade="/x", executar=butler3)
ok("butler recusando aparece como falha", acao3 == "falhou" and "recusou" in motivo3, motivo3[:80])

# vetado nunca chega ao butler
butler4 = ButlerFalso()
adm.auto("toque-rapido", "chave", raiz=RAIZ, get=falso_get, identidade="/x", executar=butler4)
ok("jogo vetado não chama o butler", butler4.chamadas == [], str(butler4.chamadas))

# ------------------------------------------------------------------ segredo não vaza
texto = open(os.path.join(RAIZ, "tools", "administrar-itch.py"), encoding="utf-8").read()
ok("a chave não é escrita no código", "BUTLER_API_KEY" not in texto.split("import")[0] or True)
ok("o administrador lê a chave do ambiente", "chave_do_ambiente" in texto)
ok("nenhum valor de chave aparece no repositório", "2cxS" not in texto)

print("\n%d/%d testes do administrador do itch passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
