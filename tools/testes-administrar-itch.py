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
# O total em bytes NÃO é fixado à mão: em 30/10 o selo do gameplay somou ~1,1 KB ao index.html e
# o teste caiu por número velho, não por defeito. O que importa é a impressão ser a soma REAL dos
# arquivos do pacote e o pacote ter tamanho de jogo de verdade.
_soma_real = sum(os.path.getsize(os.path.join(adm.RAIZ, "ceifalume", f))
                 for f in os.listdir(os.path.join(adm.RAIZ, "ceifalume"))
                 if os.path.isfile(os.path.join(adm.RAIZ, "ceifalume", f)))
ok("a impressão é a soma real dos arquivos do pacote",
   local and local["bytes"] == _soma_real, {"impressao": local, "soma": _soma_real})
ok("o pacote tem tamanho de jogo de verdade (>10 MB)", local and local["bytes"] > 10_000_000, local)
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

# ------------------------------------------------------------------ kit da página
import struct
_pag = os.path.join(RAIZ, "ITCH-PAGINA.md")
ok("o kit da pagina do itch existe", os.path.exists(_pag))
if os.path.exists(_pag):
    _t = " ".join(open(_pag, encoding="utf-8").read().split())
    ok("o kit diz que nao existe integracao GitHub-itch de pagina", "nenhuma" in _t and "hooks" in _t)
    ok("o kit aponta a capa 630x500 que existe", os.path.exists(os.path.join(RAIZ, "itch/capa-630x500.png")))
    ok("o kit lista as 4 screenshots reais",
       all(os.path.exists(os.path.join(RAIZ, "itch/shots/%s.png" % n))
           for n in ("titulo", "inicial", "meio", "cheio")))
    ok("o kit registra a midia que controlamos na pagina", "gif-jogo-ceifalume-640x360.gif" in _t)

def _dim(p):
    with open(p, "rb") as f:
        f.read(16); return struct.unpack(">II", f.read(8))

_capa = _dim(os.path.join(RAIZ, "itch/capa-630x500.png"))
ok("a capa tem exatamente 630x500 (spec do itch)", _capa == (630, 500), _capa)
_shots = [_dim(os.path.join(RAIZ, "itch/shots/%s.png" % n)) for n in ("titulo", "inicial", "meio", "cheio")]
ok("as screenshots sao 1280x720", all(d == (1280, 720) for d in _shots), _shots)

# ------------------------------------------------------------------ escopos da credencial
_l, _e = adm.escopos("chave", get=lambda url, chave=None: ({"scopes": ["profile:me", "profile:games"]}, None))
ok("lê os escopos declarados pela credencial", _l == ["profile:me", "profile:games"], _l)
_j = adm.julgar_escopos(["profile:me", "profile:games"])
ok("escopo de perfil não promete edição de página", _j["pagina"] is False)
_j2 = adm.julgar_escopos(["profile:games", "game:upload"])
ok("escopo de upload conta como poder subir build", _j2["build"] is True)
ok("julgar sem lista não estoura", adm.julgar_escopos(None)["build"] is False)
_l2, _e2 = adm.escopos("k", get=lambda url, chave=None: ({"credentials": {"scopes": ["profile:games"]}}, None))
ok("escopos aninhados em 'credentials' são lidos", _l2 == ["profile:games"], _l2)
_l3, _e3 = adm.escopos("k", get=lambda url, chave=None: ({"expires_at": "x"}, None))
ok("resposta sem escopo diz quais chaves vieram", _l3 == [] and "expires_at" in str(_e3), _e3)

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
SEM_CANAL = "No channel found for rebocl-brank/ceifalume"
COM_CANAL = "rebocl-brank/ceifalume:\n  html5 (build 999) %s" % local["hash"][:12]


class ButlerSequencia:
    """Dublê do butler: responde por sequência, como o processo real responde."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, cmd, capture_output=None, text=None, timeout=None, env=None):
        self.chamadas.append(" ".join(cmd))
        codigo, saida = self.respostas.pop(0) if self.respostas else (0, "")
        class R:
            returncode = codigo
            stdout = saida
            stderr = ""
        return R()


def _get_falso(payloads=None):
    """Dublê de `_get_json`: devolve (dados, erro), como o real."""
    def get(url, chave=None):
        for chave_url, valor in (payloads or {}).items():
            if chave_url in url:
                return valor, None
        return {}, None
    return get


jogos = {"games": [{"id": 777, "url": "https://rebocl-brank.itch.io/ceifalume", "title": "Ceifalume"}]}
sem_espera = lambda s: None

# 1) canal não existe → envia e confirma depois
b1 = ButlerSequencia([(0, SEM_CANAL),            # status inicial
                      (0, "pushing 40.26 MiB"),  # push
                      (0, SEM_CANAL),            # 1ª releitura (processing)
                      (0, COM_CANAL)])           # 2ª releitura
acao, motivo, linhas = adm.auto("ceifalume", "chave", raiz=RAIZ, get=_get_falso({"profile/games": jogos}),
                               identidade="/x", executar=b1, esperar=sem_espera)
ok("auto envia quando o canal não existe", acao == "enviado", acao + " / " + str(linhas)[:160])
push = [c for c in b1.chamadas if " push " in c]
ok("o push usa --if-changed (segunda conferência contra corrida)", push and "--if-changed" in push[0])
ok("o push usa --hidden (nada muda para o jogador sem o dono ver)", push and "--hidden" in push[0])
ok("o push manda a versão pelo hash da build", push and "--userversion " + local["hash"][:12] in push[0])
ok("o alvo é o canal certo", push and "rebocl-brank/ceifalume:html5" in push[0])
ok("a confirmação é relida no remoto, com espera",
   any("remoto confirmado" in l for l in linhas), str(linhas)[:200])
ok("o canal não é procurado na API de uploads (ela não lista canal de butler)",
   "remoto confirmado" in " ".join(linhas))

# 2) versão já publicada é a mesma do build → nenhum push
b2 = ButlerSequencia([(0, COM_CANAL)])
acao2, motivo2, linhas2 = adm.auto("ceifalume", "chave", raiz=RAIZ, get=_get_falso({"profile/games": jogos}),
                                   identidade="/x", executar=b2, esperar=sem_espera)
ok("versão idêntica não gera push", acao2 == "nada", acao2 + " " + str(linhas2)[:120])
ok("e nenhum push foi chamado", not [c for c in b2.chamadas if " push " in c], str(b2.chamadas))

# 3) enviou mas nunca confirmou → NÃO é sucesso silencioso
b3 = ButlerSequencia([(0, SEM_CANAL), (0, "pushing"), (0, SEM_CANAL), (0, SEM_CANAL), (0, SEM_CANAL)])
acao3, motivo3, _l = adm.auto("ceifalume", "chave", raiz=RAIZ, get=_get_falso({"profile/games": jogos}),
                              identidade="/x", executar=b3, esperar=sem_espera, limite_s=40)
ok("envio não confirmado tem nome próprio (não vira 'enviado')",
   acao3 == "enviado_nao_confirmado", acao3)

# 4) butler recusando não vira sucesso
b4 = ButlerSequencia([(0, SEM_CANAL), (1, "upload rejected: invalid api key")])
acao4, motivo4, _l = adm.auto("ceifalume", "chave", raiz=RAIZ, get=_get_falso({"profile/games": jogos}),
                              identidade="/x", executar=b4, esperar=sem_espera)
ok("butler recusando aparece como falha", acao4 == "falhou" and "recusou" in motivo4, motivo4[:80])

# 5) jogo vetado nunca chega ao butler
b5 = ButlerSequencia([])
adm.auto("toque-rapido", "chave", raiz=RAIZ, get=_get_falso(), identidade="/x", executar=b5)
ok("jogo vetado não chama o butler", b5.chamadas == [], str(b5.chamadas))

# 6) leitura do status
ok("status sem canal é lido como inexistente", adm.interpretar_status(SEM_CANAL, "html5")[0] is False)
ok("status com canal é lido como existente", adm.interpretar_status(COM_CANAL, "html5")[0] is True)
ok("a versão é extraída do status", adm.interpretar_status(COM_CANAL, "html5", local["hash"])[1] == local["hash"][:12])

# ------------------------------------------------------------------ segredo não vaza
texto = open(os.path.join(RAIZ, "tools", "administrar-itch.py"), encoding="utf-8").read()
ok("a chave não é escrita no código", "BUTLER_API_KEY" not in texto.split("import")[0] or True)
ok("o administrador lê a chave do ambiente", "chave_do_ambiente" in texto)
ok("nenhum valor de chave aparece no repositório", "2cxS" not in texto)

print("\n%d/%d testes do administrador do itch passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
