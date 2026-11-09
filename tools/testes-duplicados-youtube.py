#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira offline do ajuste de vídeos repetidos — sem rede, sem token, sem canal.

O que este teste cerca:
  * sem a palavra certa NADA acontece (e a palavra de apagar não serve para privar);
  * o script só mexe nos ids escritos: id estranho, repetido ou ausente é recusado;
  * a chamada de privar manda SOMENTE `privacyStatus` — título, descrição e tags não mudam;
  * vídeo que já estava privado não é tocado de novo;
  * sem consentimento (refresh token) não sai requisição nenhuma;
  * o workflow não tem cron e não pede permissão de escrita no repositório.
"""
import importlib.util
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


dupl = carrega("duplicados_youtube", "duplicados-youtube.py")

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + detalhe if detalhe else ""))


ID = "f5kQFOQs0To"

# ---- confirmação ----
ok("privar sem a palavra não passa",
   dupl.exigir_ambiente("privar", "", ID) != [], "deveria recusar vazio")
ok("privar com a palavra de apagar não passa",
   dupl.exigir_ambiente("privar", "APAGAR", ID) != [], "palavra cruzada tem de ser recusada")
ok("apagar com a palavra de privar não passa",
   dupl.exigir_ambiente("apagar", "PRIVAR", ID) != [], "palavra cruzada tem de ser recusada")
ok("privar com PRIVAR passa", dupl.exigir_ambiente("privar", "PRIVAR", ID) == [])
ok("apagar com APAGAR passa", dupl.exigir_ambiente("apagar", " apagar ", ID) == [])
ok("ação desconhecida é recusada", dupl.exigir_ambiente("tornar-publico", "PRIVAR", ID) != [])

# ---- ids ----
ok("lista vazia é recusada", dupl.validar_ids([]) != [])
ok("id com caractere estranho é recusado", dupl.validar_ids(["abc/def"]) != [])
ok("id repetido é recusado", dupl.validar_ids([ID, ID]) != [])
ok("separar aceita vírgula, espaço e ponto e vírgula",
   dupl.separar_ids(" a1b2c3d4 , e5f6g7h8;i9j0k1l2 ") == ["a1b2c3d4", "e5f6g7h8", "i9j0k1l2"])

# ---- decisão por vídeo ----
PUBLICO = {"id": ID, "status": {"privacyStatus": "public"}, "snippet": {"title": "CEIFALUME"}}
PRIVADO = {"id": ID, "status": {"privacyStatus": "private"}, "snippet": {"title": "CEIFALUME"}}
ok("vídeo público com ação privar vira privar", dupl.decisao(PUBLICO, "privar")[0] == "privar")
ok("vídeo já privado não é tocado de novo", dupl.decisao(PRIVADO, "privar")[0] == "nada")
ok("vídeo que não está na conta é recusado", dupl.decisao(None, "privar")[0] == "recusar")
ok("vídeo privado ainda pode ser apagado", dupl.decisao(PRIVADO, "apagar")[0] == "apagar")

# ---- o corpo do privar não toca em texto ----
corpo = dupl.corpo_privado(ID)
ok("o corpo leva só o id e o privacyStatus",
   corpo == {"id": ID, "status": {"privacyStatus": "private"}}, str(corpo))
ok("nada de snippet no corpo", "snippet" not in corpo)
ok("a chamada usa part=status", "/videos?part=status" in open(
    os.path.join(RAIZ, "tools", "duplicados-youtube.py"), encoding="utf-8").read())

# ---- sem consentimento, sem requisição ----
chamadas = []
original = dupl.pedir
dupl.pedir = lambda *a, **k: chamadas.append((a, k)) or (200, "{}")
os.environ.pop("YT_REFRESH_TOKEN", None)
os.environ["ACAO"] = "privar"
os.environ["IDS"] = ID
os.environ["CONFIRMACAO"] = "PRIVAR"
try:
    saida = dupl.main()
finally:
    dupl.pedir = original
    for chave in ("ACAO", "IDS", "CONFIRMACAO"):
        os.environ.pop(chave, None)
ok("sem refresh token sai com erro e nenhuma requisição", saida == 1 and chamadas == [],
   "saida=%s chamadas=%d" % (saida, len(chamadas)))

# ---- o workflow não publica sozinho ----
caminho_workflow = os.path.join(RAIZ, ".github", "workflows", "duplicados-youtube.yml")
texto_workflow = open(caminho_workflow, encoding="utf-8").read() if os.path.exists(caminho_workflow) else ""
ok("existe workflow próprio para o ajuste", bool(texto_workflow))
ok("o workflow não tem cron", "schedule:" not in texto_workflow)
ok("o workflow exige ids, ação e confirmação",
   all(chave in texto_workflow for chave in ("ids:", "acao:", "confirmacao:")))
ok("o workflow não pede escrita no repositório", "contents: read" in texto_workflow)

print("%d/%d contratos do ajuste de vídeos repetidos passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
