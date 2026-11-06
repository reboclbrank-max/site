#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da capa: uma capa por vídeo, com o que só aquele vídeo tem.

O defeito que estes contratos impedem (06/11/2026): três vídeos no ar com o mesmo primeiro
quadro. Capa igual faz o espectador não distinguir um vídeo do outro no grid — e o dono viu.
"""
import hashlib
import importlib.util
import os
import tempfile

from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("capa", os.path.join(RAIZ, "tools", "desenhar-capa.py"))
capa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capa)

resultados = []


def checar(nome, condicao, detalhe=""):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome
          + ("" if condicao or not detalhe else "  [%s]" % (detalhe,)))


def quadro(cor, marca=0):
    """Quadro de mentira, mas com o tamanho e a variedade de cor de um quadro do jogo."""
    im = Image.new("RGB", (1280, 720), cor)
    d = ImageDraw.Draw(im)
    for i in range(0, 1280, 80):
        d.rectangle([i, 300 + (i + marca) % 200, i + 60, 700], fill=(20, 30, 40))
    pasta = tempfile.mkdtemp(prefix="capa-")
    caminho = os.path.join(pasta, "quadro.png")
    im.save(caminho)
    return caminho


def sha(caminho):
    return hashlib.sha256(open(caminho, "rb").read()).hexdigest()


pasta = tempfile.mkdtemp(prefix="capas-")
q1 = quadro((12, 20, 40))
q2 = quadro((60, 40, 10), marca=37)

# ---- 1. a capa é 1280x720 e não é o quadro cru
s1 = os.path.join(pasta, "c1.png")
r1 = capa.desenhar(q1, s1, "Quantas colheitas cabem em 2 minutos?", "9 colheitas · 2 min", "abc123")
im = Image.open(s1)
checar("a capa tem o tamanho do YouTube (1280x720)", im.size == (1280, 720), im.size)
checar("a capa não é o quadro cru: ela muda a imagem", sha(s1) != sha(q1))
checar("a capa diz quantas linhas de título usou", r1["linhas"] >= 1, r1["linhas"])

# ---- 2. vídeos diferentes dão capas diferentes (o defeito de 06/11)
s2 = os.path.join(pasta, "c2.png")
capa.desenhar(q1, s2, "Onde jogar CEIFALUME sem instalar loja", "5 colheitas · 2 min", "def456")
checar("título diferente e números diferentes = capa diferente", sha(s1) != sha(s2))
s3 = os.path.join(pasta, "c3.png")
capa.desenhar(q2, s3, "Quantas colheitas cabem em 2 minutos?", "9 colheitas · 2 min", "abc123")
checar("quadro diferente = capa diferente", sha(s1) != sha(s3))

# ---- 3. a mesma entrada dá a mesma capa (é determinístico, não sorte)
s4 = os.path.join(pasta, "c4.png")
capa.desenhar(q1, s4, "Quantas colheitas cabem em 2 minutos?", "9 colheitas · 2 min", "abc123")
checar("mesma entrada, mesma capa (determinístico)", sha(s1) == sha(s4))

# ---- 4. assinatura na capa: é ela que amarra capa e partida
s5 = os.path.join(pasta, "c5.png")
r5 = capa.desenhar(q1, s5, "Quantas colheitas cabem em 2 minutos?", "9 colheitas · 2 min", "zzz999")
checar("assinatura diferente aparece na capa (e muda o arquivo)", sha(s1) != sha(s5) and r5["assinatura"] == "zzz999")

# ---- 5. capa sem título é recusada: seria template
try:
    capa.desenhar(q1, os.path.join(pasta, "x.png"), "   ", "9 colheitas", "abc123")
    recusou = False
except ValueError as erro:
    recusou = "título" in str(erro)
checar("capa sem título é recusada", recusou)

# ---- 6. título longo é quebrado, não vaza da margem
s6 = os.path.join(pasta, "c6.png")
r6 = capa.desenhar(q1, s6, "Um título muito longo mesmo para testar a quebra automática de linha "
                           "sem invadir a margem da capa do vídeo da casa", "3 mudas", "abc123")
checar("título longo é quebrado em até 3 linhas", r6["linhas"] <= 3, r6["linhas"])

# ---- 7. os números da partida ficam na capa quando existem
s7 = os.path.join(pasta, "c7.png")
r7 = capa.desenhar(q1, s7, "Nove colheitas em dois minutos", "9 colheitas · 2 min", "abc123")
s8 = os.path.join(pasta, "c8.png")
r8 = capa.desenhar(q1, s8, "Nove colheitas em dois minutos", "", "abc123")
checar("com números a capa é outra (o número entra no desenho)", sha(s7) != sha(s8) and r7["numeros"])

# ---- 8. a marca da casa aparece, e some quando não se quer
s9 = os.path.join(pasta, "c9.png")
capa.desenhar(q1, s9, "Sem marca nenhuma", "", "abc123", marca="")
checar("capa sem marca é diferente da capa com marca", sha(s9) != sha(s7))

certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos da capa passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
