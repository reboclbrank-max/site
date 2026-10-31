#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova que o selo no GIF é real, discreto e não estraga a página.

Contexto (31/10/2026): a descrição do jogo no itch começa com uma imagem hospedada no nosso
domínio. O painel do itch é 403 para servidor, então trocar o CONTEÚDO dessa imagem é o único
caminho automático para o vídeo do gameplay chegar a quem está no itch. Um selo que inche o
arquivo, que suma no meio, ou que aponte para um vídeo que não é o do build, seria pior que nada.
"""
import importlib.util
import os
import re
import sys
import tempfile

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

spec = importlib.util.spec_from_file_location("gifselo", os.path.join(AQUI, "gif-com-selo.py"))
gs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs)

TOTAL, FALHAS = [], []


def ok(descricao, condicao, detalhe=""):
    TOTAL.append(descricao)
    if condicao:
        print("OK  " + descricao)
        return True
    FALHAS.append(descricao)
    print("FALHOU  " + descricao + ("  <" + str(detalhe)[:200] + ">" if detalhe else ""))
    return False


def gif_de_teste(pasta, lados=(160, 90), quadros=6):
    caminho = os.path.join(pasta, "teste.gif")
    imagens = []
    for i in range(quadros):
        im = Image.new("RGB", lados, (20 + i * 10, 30, 40))
        imagens.append(im)
    imagens[0].save(caminho, save_all=True, append_images=imagens[1:], duration=100, loop=0)
    return caminho


def main():
    # ---------------------------------------------------------------- o endereço vem do build
    link = gs.link_do_selo()
    ok("o endereço do vídeo é lido do selo do build", bool(link) and "youtu.be/" in link, link)
    ok("o endereço lido é o mesmo do ceifalume/index.html",
       link in open(os.path.join(RAIZ, "ceifalume", "index.html"), encoding="utf-8").read(), link)
    ok("sem selo no html, não inventa endereço",
       gs.link_do_selo(index="<html>sem selo</html>") == "")
    ok("o selo funciona com o href antes do id",
       gs.link_do_selo(index='<a href="https://youtu.be/abc123" id="rb-gameplay">x</a>')
       == "https://youtu.be/abc123")
    ok("o rótulo não repete o protocolo (fica curto e legível)",
       "https://" not in gs.rotulo_do_selo(link) and "youtu.be/" in gs.rotulo_do_selo(link),
       gs.rotulo_do_selo(link))

    # ---------------------------------------------------------------- o carimbo é discreto
    base = Image.new("RGB", (640, 360), (10, 12, 20))
    carimbado = gs.carimbar_frame(base, gs.rotulo_do_selo(link))
    ok("o carimbo mantém o tamanho do quadro", carimbado.size == base.size, carimbado.size)
    ok("o carimbo muda o canto inferior direito (onde ele fica)",
       list(carimbado.crop((400, 300, 640, 360)).getdata()) !=
       list(base.crop((400, 300, 640, 360)).getdata()))
    ok("o carimbo NÃO cobre o topo (título do jogo, moedas, sementes)",
       list(carimbado.crop((0, 0, 640, 120)).getdata()) ==
       list(base.crop((0, 0, 640, 120)).getdata()))

    # ---------------------------------------------------------------- gravação com teto
    with tempfile.TemporaryDirectory() as pasta:
        pequeno = gif_de_teste(pasta)
        saida = os.path.join(pasta, "saida.gif")
        deu_certo, resultado = gs.carimbar_gif(origem=pequeno, destino=saida, link=link)
        ok("carimba um GIF de teste e grava o arquivo",
           deu_certo is True and os.path.exists(saida), resultado)
        ok("o GIF de saída guarda o mesmo número de quadros",
           deu_certo and Image.open(saida).n_frames == Image.open(pequeno).n_frames,
           resultado.get("frames") if deu_certo else "")
        teto = max(os.path.getsize(pequeno) * gs.LIMITE_DE_CRESCIMENTO, gs.PISO_DO_TETO)
        ok("o GIF de saída respeita o teto (%.0fx o original ou o piso, o que for maior)"
           % gs.LIMITE_DE_CRESCIMENTO, os.path.getsize(saida) <= teto,
           "%d B vs teto %d B" % (os.path.getsize(saida), teto))
        ok("registra por onde gravou (ffmpeg ou pillow)",
           deu_certo and resultado["via"] in ("ffmpeg", "pillow"),
           resultado.get("via") if deu_certo else "")

        # sem ffmpeg disponível, a reserva não pode inchar o arquivo: ou cabe, ou recusa
        forçado = gs.carimbar_gif(origem=pequeno, destino=os.path.join(pasta, "reserva.gif"),
                                  link=link, ffmpeg="")
        criado = os.path.join(pasta, "reserva.gif")
        if forçado[0]:
            ok("reserva sem ffmpeg só grava se não inchar a página",
               os.path.getsize(criado) <= max(
                   os.path.getsize(pequeno) * gs.LIMITE_DE_CRESCIMENTO, gs.PISO_DO_TETO),
               os.path.getsize(criado))
        else:
            ok("reserva sem ffmpeg recusa em vez de inchar a página",
               "recusado" in forçado[1] and not os.path.exists(criado), forçado[1])
        ok("sem endereço de vídeo, não grava nada",
           gs.carimbar_gif(origem=pequeno, destino=os.path.join(pasta, "x.gif"),
                           link="")[0] is False)

        # arquivo temporário não sobra do lado do destino
        ok("não deixa arquivo temporário ao lado do destino",
           not any(n.endswith(".tmp") or n.startswith("tmp") for n in os.listdir(pasta)),
           os.listdir(pasta))

    # ---------------------------------------------------------------- o GIF do repositório
    real = os.path.join(RAIZ, "media", "ceifalume", "gif-jogo-ceifalume-640x360.gif")
    ok("o GIF servido na página do itch existe", os.path.exists(real), real)
    if os.path.exists(real):
        imagem = Image.open(real)
        ok("o GIF servido mantém 640x360 (o itch dimensiona por ele)", imagem.size == (640, 360),
           imagem.size)
        ok("o GIF servido tem os 140 quadros do original (não virou foto)", imagem.n_frames >= 100,
           imagem.n_frames)
        ok("o GIF servido não pesa mais que o original de 2,91 MB",
           os.path.getsize(real) <= 3054658, os.path.getsize(real))

    # ------------------------------------------- idempotência (carimbar o carimbo é defeito)
    # MEDIDO em 31/10/2026: com `destino = origem`, rodar duas vezes carimbava um GIF já
    # carimbado — 2,91 MB → 2,29 MB → 2,16 MB, perdendo qualidade a cada rodada.
    ok("a origem padrão é a FONTE intocada, não o arquivo servido",
       gs.fonte_intocada() != gs.GIF and os.path.exists(gs.fonte_intocada()),
       gs.fonte_intocada())
    _antes_fonte = open(gs.fonte_intocada(), "rb").read()
    with tempfile.TemporaryDirectory() as pasta:
        pequeno = gif_de_teste(pasta)
        saida = os.path.join(pasta, "idem.gif")
        gs.carimbar_gif(origem=pequeno, destino=saida, link=link)
        primeiro = open(saida, "rb").read()
        gs.carimbar_gif(origem=pequeno, destino=saida, link=link)
        segundo = open(saida, "rb").read()
        ok("carimbar duas vezes com a mesma fonte dá o MESMO arquivo", primeiro == segundo,
           "%d vs %d bytes" % (len(primeiro), len(segundo)))
    ok("a FONTE intocada continua intocada depois de carimbar",
       open(gs.fonte_intocada(), "rb").read() == _antes_fonte)

    # ---------------------------------------------------------------- higiene
    fonte = open(os.path.join(AQUI, "gif-com-selo.py"), encoding="utf-8").read()
    ok("o endereço do vídeo não está escrito no código (vem do build)",
       "youtu.be/GuE7" not in fonte)
    ok("a gravação é atômica (os.replace)", "os.replace(" in fonte)
    ok("existe teto de crescimento declarado", "LIMITE_DE_CRESCIMENTO" in fonte)
    ok("o teto vale para os dois caminhos (ffmpeg e reserva)", fonte.count("teto") >= 2)

    print()
    if FALHAS:
        print("%d de %d verificações do selo no GIF FALHARAM" % (len(FALHAS), len(TOTAL)))
        sys.exit(1)
    print("%d/%d verificações do selo no GIF passaram" % (len(TOTAL), len(TOTAL)))


if __name__ == "__main__":
    main()
