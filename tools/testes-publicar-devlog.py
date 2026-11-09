#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testa o publicador de devlog sem proxy — o caminho que hoje existe e o que não existe.

Trava o que deixaria a casa tentar por caminho torto:
  * sem ITCH_PROXY ele RECUSA publicar (código 3) em vez de tentar de datacenter;
  * sem a palavra PUBLICAR ele recusa (código 2);
  * sem sessão ele recusa (código 2);
  * nunca imprime o cookie, nunca aceita proxy público embutido no código;
  * o texto publicado vem do arquivo testado do favorito (mesma coisa que o dono usa).
"""
import json
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RAIZ, "tools", "publicar-devlog-itch.js")
FONTE = open(SCRIPT, encoding="utf-8").read()

certos, falhas = [], []


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos.append(nome)
        print("OK  " + nome)
    else:
        falhas.append((nome, detalhe))
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe else ""))


def rodar(args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in
           ("ITCH_PROXY", "ITCH_COOKIE", "CONFIRMACAO")}
    env.update(env_extra or {})
    return subprocess.run(["node", SCRIPT] + args, capture_output=True, text=True,
                          env=env, timeout=120, cwd=RAIZ)


r = rodar(["--publicar"], {"ITCH_COOKIE": "itchio=abc", "CONFIRMACAO": "PUBLICAR"})
ok("sem ITCH_PROXY recusa publicar (código 3)", r.returncode == 3, r.returncode)
ok("e diz por que, citando a medida", "403" in r.stdout and "desafio" in r.stdout, r.stdout[:120])
ok("e aponta o caminho que existe (favorito de 1 clique)", "bookmarklet" in r.stdout)

r2 = rodar(["--publicar"], {"ITCH_COOKIE": "itchio=abc", "ITCH_PROXY": "http://127.0.0.1:9"})
ok("sem a palavra PUBLICAR recusa (código 2)", r2.returncode == 2, r2.returncode)
ok("e diz que publicar é decisão", "PUBLICAR" in r2.stdout)

r3 = rodar(["--publicar"], {"CONFIRMACAO": "PUBLICAR", "ITCH_PROXY": "http://127.0.0.1:9"})
ok("sem sessão recusa (código 2)", r3.returncode == 2, r3.returncode)

# A ordem das travas importa: sessão -> palavra -> proxy. Assim nunca tenta rede sem proxy.
ok("a trava do proxy vem antes de qualquer acesso ao painel",
   FONTE.index("if (!proxy)") < FONTE.index("chromium.launch"), "ordem invertida")

ok("nunca imprime o cookie", "console.log(cookie" not in FONTE and "${cookie}" not in FONTE)
ok("não tem proxy público embutido no código",
   not re.search(r"(free-proxy|proxyscrape|openproxy|residential-proxy)", FONTE, re.I))
ok("não tenta burlar o desafio (sem serviço de captcha)",
   not re.search(r"(2captcha|anticaptcha|deathbycaptcha|turnstile-solver)", FONTE, re.I))
ok("publica com o MESMO código do favorito do dono",
   "devlog-gameplay-bookmarklet.txt" in FONTE and "pagina.evaluate(favorito)" in FONTE)
ok("confirma o resultado na página pública (não confia no próprio POST)",
   "DEVLOG_PUBLICO" in FONTE and "estadoPublico()" in FONTE)

_txt = json.load(open(os.path.join(RAIZ, "posts", "devlog-itch-gameplay.json"), encoding="utf-8"))
ok("o texto do devlog existe e tem título e corpo", bool(_txt.get("titulo")) and bool(_txt.get("corpo")))
ok("o texto cita o vídeo publicado", "GuE7af6dYo8" in _txt.get("corpo", ""))

# modo verificação: só leitura pública, funciona sem proxy e sem sessão
r4 = rodar([])
ok("modo verificação funciona sem proxy, sem sessão e sem palavra",
   r4.returncode in (0, 1) and "devlog público" in r4.stdout, (r4.returncode, r4.stdout[:120]))

print("\n%d/%d verificações do publicador de devlog passaram" % (len(certos), len(certos) + len(falhas)))
sys.exit(0 if not falhas else 1)
