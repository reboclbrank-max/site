#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do roteiro do PRANCHETA (sem rede e sem navegador)."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
total = 0
falhas = []


def ok(nome, cond, detalhe=""):
    global total
    total += 1
    if cond:
        print("OK  " + nome)
    else:
        falhas.append(nome)
        print("FALHOU  " + nome + ("  <" + str(detalhe) + ">" if detalhe else ""))


fonte = open(os.path.join(RAIZ, "tools", "gravar-prancheta.js"), encoding="utf-8").read()

ok("o roteiro jogado é o do PRANCHETA (jogo certo)", "prancheta" in fonte.lower()
   and "rebocl-brank.itch.io/prancheta" in fonte)
ok("o build é descoberto na página do itch (o id muda a cada versão)",
   "html-classic.itch.zone" in fonte and "descobrirBuild" in fonte)
ok("há endereço de reserva se a descoberta falhar", "BUILD_RESERVA" in fonte)
ok("confere cada passo POR IMAGEM (mudança de tela), não por tempo",
   "diferenca(" in fonte and "mudanca" in fonte)
ok("falha quando menos de 4 passos essenciais mudam a tela",
   "essenciais < 4" in fonte and "return 8" in fonte)
ok("grava relatório de decisões ao lado do vídeo", "-decisoes.json" in fonte)
ok("a partida tem roteiro próprio (instrução, seguir, velocidade, pular)",
   all(x in fonte for x in ("instrucao:", "seguir:", "velocidadeRapida:", "pularParaFim:")))

# A descoberta do build é testada com Node (o módulo não roda o fluxo quando importado).
import subprocess
teste = (
    "const m=require('./tools/gravar-prancheta.js');"
    "const html='<iframe src=\"https://html-classic.itch.zone/html/999/index.html?v=1&amp;x=2\">';"
    "const achado=m.descobrirBuild('http://x', () => html);"
    "const reserva=m.descobrirBuild('http://x', () => { throw new Error('sem rede'); });"
    "console.log(JSON.stringify({achado,reserva}));"
)
r = subprocess.run(["node", "-e", teste], cwd=RAIZ, capture_output=True, text=True)
valido = r.returncode == 0 and r.stdout.strip()
dados = {}
if valido:
    import json as _json
    dados = _json.loads(r.stdout.strip())
ok("descobrirBuild acha o iframe do itch",
   dados.get("achado") == "https://html-classic.itch.zone/html/999/index.html?v=1&x=2",
   dados.get("achado") or (r.stderr or "")[:120])
ok("sem rede cai no endereço de reserva em vez de quebrar",
   str(dados.get("reserva", "")).startswith("https://html-classic.itch.zone/html/"),
   dados.get("reserva"))

for nome, trecho in (
    ("legenda para o menu do PRANCHETA", "abrindo o jogo"),
    ("legenda para a prancheta tática", "abrindo a prancheta tática"),
    ("legenda para a partida", "começando a partida"),
):
    prod = open(os.path.join(RAIZ, "tools", "produzir-video.py"), encoding="utf-8").read()
    ok(nome, trecho in prod)

wf = open(os.path.join(RAIZ, ".github", "workflows", "gravar-prancheta.yml"),
          encoding="utf-8").read()
ok("existe workflow próprio do PRANCHETA", "gravar-prancheta" in wf)
ok("o workflow roda o roteiro medido", "tools/gravar-prancheta.js" in wf)
ok("o workflow mede o vídeo antes de guardar",
   "validar-video.py" in wf and wf.index("validar-video.py") < wf.index("upload-artifact"))
ok("o envio ao YouTube continua atrás da palavra PUBLICAR",
   "publicar == 'PUBLICAR'" in wf)
ok("o cron só grava (sem envio automático)",
   "secrets.YT_CLIENT_ID" not in wf and "enviar-youtube" not in wf)

print("\n%d/%d testes do roteiro do PRANCHETA passaram" % (total - len(falhas), total))
sys.exit(1 if falhas else 0)
