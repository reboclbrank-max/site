#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desenha a faixa de instruções que fica no rodapé do vídeo do gameplay.

Por que PIL e não drawtext: o ffmpeg deste ambiente e o do runner não têm drawtext (medido em
27/10/2026 — só libass). Desenhar o PNG aqui e sobrepor com `overlay` funciona em qualquer build
e deixa o texto com a mesma cara em qualquer máquina.

Regra de legibilidade (medida, não achismo): fundo quase opaco (alfa 216/255) e fonte com
contorno escuro. Sobre a cena clara do dia e sobre a cena escura da noite o contraste do texto
fica acima de 4.5:1, que é o mínimo do WCAG AA para texto normal.
"""
import argparse
import textwrap

from PIL import Image, ImageDraw, ImageFont

FONTE_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTE_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

ALFA_FUNDO = 216       # 0-255: alto o bastante para o texto ler sobre o jogo
COR_FUNDO = (10, 14, 22)
COR_TEXTO = (255, 255, 255)
COR_DESTAQUE = (255, 214, 92)


def fonte(caminho, tamanho):
    try:
        return ImageFont.truetype(caminho, tamanho)
    except OSError:
        return ImageFont.load_default()


def quebrar(texto, desenho, f, largura_max):
    """Quebra em linhas que cabem na largura, preservando palavras."""
    palavras = texto.split()
    linhas, atual = [], ""
    for palavra in palavras:
        teste = (atual + " " + palavra).strip()
        if desenho.textlength(teste, font=f) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--saida", required=True)
    p.add_argument("--largura", type=int, default=1280)
    p.add_argument("--altura", type=int, default=150)
    p.add_argument("--fonte", type=int, default=28)
    p.add_argument("--linha", action="append", default=[])
    a = p.parse_args()

    linhas = a.linha or ["COMO JOGAR: escolha a semente, plante no campo, faça um bico e colha."]
    fundo = Image.new("RGBA", (a.largura, a.altura), COR_FUNDO + (ALFA_FUNDO,))
    desenho = ImageDraw.Draw(fundo)
    desenho.rectangle([0, 0, a.largura, 2], fill=COR_DESTAQUE + (255,))

    margem = 14
    util = a.largura - 2 * margem

    # Ajuste automático: diminui a fonte até TODAS as linhas caberem na faixa. Se nem no menor
    # tamanho couber, o desenho falha — faixa cortada no meio seria instrução pela metade.
    tamanho = a.fonte
    while tamanho >= 12:
        f1 = fonte(FONTE_BOLD, tamanho)
        f2 = fonte(FONTE_NORMAL, max(12, tamanho - 7))
        blocos = []
        for indice, texto in enumerate(linhas):
            f = f1 if indice == 0 else f2
            blocos.append((f, quebrar(texto, desenho, f, util)))
        altura_total = sum(len(b[1]) * (b[0].size + 5) for b in blocos)
        if altura_total <= a.altura - 8:
            break
        tamanho -= 1
    if altura_total > a.altura - 4:
        raise SystemExit("faixa pequena demais para o texto: %d px" % altura_total)

    y = max(4, (a.altura - altura_total) // 2)
    for indice, (f, quebradas) in enumerate(blocos):
        cor = COR_TEXTO if indice == 0 else (225, 233, 243)
        for linha in quebradas:
            # contorno escuro: garante leitura mesmo se o fundo falhar
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                desenho.text((margem + dx, y + dy), linha, font=f, fill=(0, 0, 0, 255))
            desenho.text((margem, y), linha, font=f, fill=cor + (255,))
            y += f.size + 5

    fundo.save(a.saida, "PNG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
