#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desenha a CAPA do vídeo — uma por vídeo, com o que aquele vídeo mostra.

POR QUE EXISTE (06/11/2026). Os três vídeos do dia subiram com o MESMO primeiro quadro: mesmo
enquadramento, mesmo "Dia 1", mesma faixa. No grid do YouTube um anula o outro — e o print está
no mostruário. Capa é a única parte do vídeo que o espectador vê ANTES de decidir; repetir capa
é repetir o vídeo.

O que a capa leva:
  · o quadro do próprio vídeo (não um template);
  · o ângulo em uma frase curta (o texto que o redator escolheu para aquele vídeo);
  · os NÚMEROS daquela partida (mudas, colheitas, minutos) — o que só aquele vídeo tem;
  · a assinatura da cena, que é o que prova que a capa não é a de outro vídeo.

Regra de legibilidade: fonte grande, contorno escuro (o jogo é uma fazenda noturna: fundo escuro
e claro no mesmo quadro) e faixa opaca embaixo. Medido por contraste, não por gosto.
"""
import argparse
import hashlib
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

LARGURA, ALTURA = 1280, 720
MARGEM = 56
FONTE_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTE_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
COR_TEXTO = (255, 255, 255)
COR_DESTAQUE = (255, 214, 92)
COR_SOMBRA = (0, 0, 0)


def fonte(caminho, tamanho):
    try:
        return ImageFont.truetype(caminho, tamanho)
    except OSError:
        return ImageFont.load_default()


def quadro_de_entrada(caminho):
    """O quadro do vídeo, recortado para 16:9 sem esticar (recorte central)."""
    im = Image.open(caminho).convert("RGB")
    alvo = LARGURA / ALTURA
    l, a = im.size
    if l / a > alvo:
        novo_l = int(a * alvo)
        im = im.crop(((l - novo_l) // 2, 0, (l + novo_l) // 2, a))
    else:
        novo_a = int(l / alvo)
        im = im.crop((0, (a - novo_a) // 2, l, (a + novo_a) // 2))
    return im.resize((LARGURA, ALTURA), Image.LANCZOS)


def escurecer(im, fracao=0.52):
    """Escurece a parte de baixo: o texto precisa de fundo previsível sobre cena clara."""
    base = im.convert("RGBA")
    véu = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(véu)
    alto = int(ALTURA * fracao)
    for i in range(alto):
        y = ALTURA - alto + i
        alfa = int(232 * (i / float(alto)) ** 0.7)
        d.line([(0, y), (LARGURA, y)], fill=(4, 6, 12, alfa))
    return Image.alpha_composite(base, véu).convert("RGB")


def veu_do_texto(im, altura=252, forca=0.90):
    """Bloco escuro atrás do título — mais forte que o escurecer().

    POR QUE (06/11/2026, medido nas capas dos vídeos antigos): os vídeos antigos do CEIFALUME têm
    legenda BURNADA no rodapé ("COMO JOGAR: 1) toque no botão..."), e o título novo caía em cima
    dela: duas letras brancas brigando no mesmo lugar. Este véu cobre a faixa e o título volta a
    ser a única coisa legível ali. Não apaga o quadro: a cena continua atrás, 10% visível.
    """
    base = im.convert("RGBA")
    véu = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(véu)
    alt = min(int(altura), ALTURA)
    for i in range(alt):
        y = ALTURA - alt + i
        # primeiro 25% do bloco entra rápido (tapa a legenda antiga), o resto fica cheio
        alfa = int(255 * forca * min(1.0, (i / float(alt)) / 0.25))
        d.line([(0, y), (LARGURA, y)], fill=(4, 6, 12, alfa))
    return Image.alpha_composite(base, véu).convert("RGB")


def veu_do_topo(im, altura=132):
    """Véu leve no topo: a assinatura e a marca leem sobre qualquer cena (o jogo é claro à
    esquerda — o painel do Dia 1 — e escuro à direita)."""
    base = im.convert("RGBA")
    véu = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(véu)
    for y in range(altura):
        alfa = int(150 * (1 - y / float(altura)) ** 0.8)
        d.line([(0, y), (LARGURA, y)], fill=(4, 6, 12, alfa))
    return Image.alpha_composite(base, véu).convert("RGB")


def com_contorno(d, xy, texto, f, cor=COR_TEXTO, contorno=3):
    x, y = xy
    for dx in range(-contorno, contorno + 1):
        for dy in range(-contorno, contorno + 1):
            if dx or dy:
                d.text((x + dx, y + dy), texto, font=f, fill=COR_SOMBRA)
    d.text((x, y), texto, font=f, fill=cor)


def quebrar(d, texto, f, largura_max, maximo_linhas=3):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if d.textlength(teste, font=f) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    if len(linhas) > maximo_linhas:
        linhas = linhas[:maximo_linhas]
        while d.textlength(linhas[-1] + "…", font=f) > largura_max:
            linhas[-1] = linhas[-1].rsplit(" ", 1)[0]
        linhas[-1] += "…"
    return linhas


def desenhar(entrada, saida, titulo, numeros="", assinatura="", marca="reboclbrank-max.github.io/site"):
    """Desenha a capa e devolve o resumo do que foi desenhado (para o log e para o teste)."""
    titulo = " ".join((titulo or "").split())
    if not titulo:
        raise ValueError("capa sem título: capa sem título é template, e template é o defeito")
    im = veu_do_texto(veu_do_topo(escurecer(quadro_de_entrada(entrada))))
    d = ImageDraw.Draw(im)

    f_kicker = fonte(FONTE_BOLD, 30)
    if assinatura:
        com_contorno(d, (MARGEM, 34), "PARTIDA " + assinatura.upper(), f_kicker, COR_DESTAQUE, 2)
    if marca:
        larg = d.textlength(marca, font=fonte(FONTE_NORMAL, 24))
        com_contorno(d, (LARGURA - MARGEM - larg, 38), marca, fonte(FONTE_NORMAL, 24),
                     (226, 226, 226), 2)

    # O bloco de texto vive no terço de baixo, com o véu por trás: fonte grande o bastante para
    # ler no celular (62 px em 720p) e nunca em cima dos números.
    f_titulo = fonte(FONTE_BOLD, 62)
    linhas = quebrar(d, titulo, f_titulo, LARGURA - 2 * MARGEM, 3)
    altura_bloco = len(linhas) * 72
    altura_numeros = 54 if numeros else 0
    y = ALTURA - MARGEM - altura_bloco - altura_numeros
    for linha in linhas:
        com_contorno(d, (MARGEM, y), linha, f_titulo, COR_TEXTO, 3)
        y += 72

    if numeros:
        f_num = fonte(FONTE_BOLD, 36)
        com_contorno(d, (MARGEM, ALTURA - MARGEM - 44), numeros, f_num, COR_DESTAQUE, 3)

    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    im.save(saida, "PNG")
    bruto = open(saida, "rb").read()
    return {"saida": saida, "titulo": titulo, "linhas": len(linhas), "numeros": numeros,
            "veu_do_texto": True,
            "assinatura": assinatura, "sha256": hashlib.sha256(bruto).hexdigest()[:16],
            "bytes": len(bruto)}


def main(argv):
    ap = argparse.ArgumentParser(description="capa única por vídeo")
    ap.add_argument("--quadro", required=True, help="quadro do próprio vídeo (PNG)")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--titulo", required=True, help="o ângulo daquele vídeo, em uma frase")
    ap.add_argument("--numeros", default="", help="mudas, colheitas, minutos daquela partida")
    ap.add_argument("--assinatura", default="", help="assinatura da cena (tools/cena.py)")
    a = ap.parse_args(argv[1:])
    r = desenhar(a.quadro, a.saida, a.titulo, a.numeros, a.assinatura)
    print("capa: %s · %d linha(s) · %d bytes · sha %s"
          % (r["saida"], r["linhas"], r["bytes"], r["sha256"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
