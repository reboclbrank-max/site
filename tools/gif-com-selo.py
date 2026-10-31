#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Põe o selo do gameplay na imagem que a página do itch MOSTRA ao jogador.

POR QUE EXISTE (31/10/2026): o itch não deixa automatizar nada da página — nem o texto, nem o
upload que o jogo abre, nem o devlog (o painel responde 403 do Cloudflare para IP de datacenter,
e a API oficial não tem endpoint para isso). Mas a descrição do jogo, escrita meses atrás, começa
com uma imagem hospedada NO NOSSO domínio:

    <img src="https://reboclbrank-max.github.io/site/media/ceifalume/gif-jogo-ceifalume-640x360.gif">

Ou seja: essa imagem é servida por nós e aparece para quem visita o jogo no itch (medido em
31/10/2026: ela está na página pública). Trocar o CONTEÚDO dela é o único caminho automático que
existe para o vídeo do gameplay chegar a quem está no itch. Então o GIF passa a levar, no canto,
o endereço do vídeo.

Duas regras que o código respeita:
  * o endereço do vídeo NÃO é digitado aqui — vem do selo do próprio build
    (`ceifalume/index.html`, `id="rb-gameplay"`), que é a única fonte da verdade;
  * o arquivo é servido para gente de verdade, então não pode inchar. O primeiro caminho é o
    ffmpeg (paleta de 128 cores: o GIF NOVO ficou MENOR que o original, 2,41 MB contra 3,05 MB).
    O Pillow fica como reserva e SE RECUSA a gravar se o resultado passar de 2× o original —
    reserva que estraga a página não é reserva.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIF = os.path.join(RAIZ, "media", "ceifalume", "gif-jogo-ceifalume-640x360.gif")
# A FONTE intocada (o GIF original, guardado no repositório). Carimbar sempre daqui é o que
# impede o defeito medido em 31/10/2026: rodar o script duas vezes carimbava um GIF já carimbado
# e cada rodada perdia qualidade (2,91 MB → 2,29 MB → 2,16 MB). Gerar de fonte fixa é
# idempotente: duas rodadas seguidas dão o mesmo arquivo.
INDEX = os.path.join(RAIZ, "ceifalume", "index.html")
FONTES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
LIMITE_DE_CRESCIMENTO = 2.0   # o arquivo servido não pode dobrar de peso
PISO_DO_TETO = 200 * 1024     # abaixo disso o peso é irrelevante para a página (toy/teste)
ROTULO = "▶ gameplay: %s"


def link_do_selo(index=None):
    """O endereço do vídeo, lido do selo do build (não de uma constante que envelhece)."""
    texto = index if index is not None else open(INDEX, encoding="utf-8").read()
    achado = re.search(r'id="rb-gameplay"[^>]*href="(https://youtu\.be/[A-Za-z0-9_-]+)"', texto)
    if not achado:
        achado = re.search(r'href="(https://youtu\.be/[A-Za-z0-9_-]+)"[^>]*id="rb-gameplay"', texto)
    return achado.group(1) if achado else ""


def rotulo_do_selo(link):
    """Texto curto e legível no canto: o suficiente para achar o vídeo sem cobrir o jogo."""
    return ROTULO % (link or "").replace("https://", "")


def fonte(tamanho):
    for caminho in FONTES:
        if os.path.exists(caminho):
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default()


def carimbar_frame(frame, rotulo, escala=0.9):
    """Desenha a faixa no canto inferior direito. Devolve o frame em RGB."""
    base = frame.convert("RGB") if frame.mode != "RGB" else frame.copy()
    largura, altura = base.size
    faixa = Image.new("RGBA", base.size, (0, 0, 0, 0))
    desenho = ImageDraw.Draw(faixa)
    letra = fonte(max(10, int(round(15 * escala))))
    margem = max(6, int(round(8 * escala)))
    caixa = desenho.textbbox((0, 0), rotulo, font=letra)
    largura_texto = caixa[2] - caixa[0]
    altura_texto = caixa[3] - caixa[1]
    x1 = largura - margem
    y1 = altura - margem
    x0 = x1 - largura_texto - 2 * margem
    y0 = y1 - altura_texto - 2 * margem
    desenho.rounded_rectangle([x0, y0, x1, y1], radius=max(4, int(6 * escala)),
                              fill=(12, 10, 8, 205), outline=(240, 217, 122, 230), width=1)
    desenho.text((x0 + margem, y0 + margem - caixa[1]), rotulo, font=letra,
                 fill=(240, 217, 122, 255))
    return Image.alpha_composite(base.convert("RGBA"), faixa).convert("RGB")


def achar_ffmpeg():
    """PATH primeiro, depois FFMPEG_PATH, depois o binário do imageio-ffmpeg (gratuito, já usado
    nesta casa). Sem nenhum dos três, o selo ainda sai — pelo Pillow, com teto de tamanho."""
    caminho = shutil.which("ffmpeg")
    if caminho:
        return caminho
    if os.environ.get("FFMPEG_PATH") and os.path.exists(os.environ["FFMPEG_PATH"]):
        return os.environ["FFMPEG_PATH"]
    try:
        import imageio_ffmpeg  # noqa: PLC0415
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def _gravar_com_ffmpeg(quadros, destino, ffmpeg, fps):
    """Grava em arquivo .gif de verdade: o ffmpeg escolhe o muxer pela EXTENSÃO (com .tmp ele
    recusa — medido em 31/10/2026: "Error initializing the muxer")."""
    with tempfile.TemporaryDirectory() as pasta:
        for indice, quadro in enumerate(quadros):
            quadro.save(os.path.join(pasta, "f%04d.png" % indice))
        paleta = "split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=3"
        r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps),
                            "-i", os.path.join(pasta, "f%04d.png"), "-vf", paleta,
                            "-loop", "0", destino], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(destino):
            return False, (r.stderr or "ffmpeg não gravou")[-300:]
        return True, ""


def fonte_intocada():
    """O GIF original, se estiver guardado ao lado do servido."""
    candidato = GIF.replace(".gif", "-fonte.gif")
    return candidato if os.path.exists(candidato) else GIF


def carimbar_gif(origem=None, destino=None, link=None, escala=0.9, ffmpeg=None):
    origem = origem or fonte_intocada()
    # destino é o GIF SERVIDO, nunca a origem: com `destino = origem` o script carimbava a fonte
    # e a segunda rodada carimbava o carimbo (medido em 31/10/2026 — 2,91 MB → 2,29 → 2,16 MB).
    destino = destino or GIF
    link = link if link is not None else link_do_selo()
    if not link:
        return False, "não achei o endereço do vídeo no selo do build (ceifalume/index.html)"
    rotulo = rotulo_do_selo(link)
    imagem = Image.open(origem)
    largura, altura = imagem.size
    duracao = imagem.info.get("duration") or 100
    quadros = []
    for indice in range(getattr(imagem, "n_frames", 1)):
        imagem.seek(indice)
        quadros.append(carimbar_frame(imagem.copy(), rotulo, escala=escala))
    bytes_antes = os.path.getsize(origem)
    fps = max(1, int(round(1000.0 / duracao)))
    caminho_ffmpeg = ffmpeg if ffmpeg is not None else achar_ffmpeg()
    # .gif de verdade no temporário: ffmpeg (e o Pillow, que também olha o nome) precisam da
    # extensão certa. A troca final continua atômica (os.replace).
    # o temporário mora AO LADO do destino: /tmp pode estar em outro sistema de arquivos e
    # os.replace entre discos falha ("Invalid cross-device link", medido em 31/10/2026).
    pasta_temp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(destino)))
    temporario = os.path.join(pasta_temp, "saida.gif")

    via = "pillow"
    if caminho_ffmpeg:
        ok, erro = _gravar_com_ffmpeg(quadros, temporario, caminho_ffmpeg, fps)
        if ok:
            via = "ffmpeg"
        else:
            print("aviso: ffmpeg falhou (%s) — caindo no Pillow" % erro[:120])

    if via == "pillow":
        # O Pillow grava GIF sem paleta ótima: 140 quadros viram ~16 MB (medido). Como o arquivo
        # é servido para visitantes, aqui ele só é aceito se não inchar a página.
        quadros[0].save(temporario, format="GIF", save_all=True, append_images=quadros[1:],
                        duration=duracao, loop=0, optimize=True, disposal=2)
    # O teto vale para QUALQUER caminho: o que importa é o arquivo servido ao visitante.
    teto = max(bytes_antes * LIMITE_DE_CRESCIMENTO, PISO_DO_TETO)
    if os.path.getsize(temporario) > teto:
        candidato = os.path.getsize(temporario)
        shutil.rmtree(pasta_temp, ignore_errors=True)
        return False, ("o GIF sairia com %.2f MB (teto de %.2f MB, %.0fx o original de %.2f MB) "
                       "— recusado para não pesar a página do itch"
                       % (candidato / 1048576.0, teto / 1048576.0, LIMITE_DE_CRESCIMENTO,
                          bytes_antes / 1048576.0))
    os.replace(temporario, destino)
    shutil.rmtree(pasta_temp, ignore_errors=True)
    return True, {"bytes": os.path.getsize(destino), "bytes_antes": bytes_antes,
                  "origem": os.path.basename(origem),
                  "frames": len(quadros), "tamanho": (largura, altura),
                  "link": link, "rotulo": rotulo, "via": via, "duracao_ms": duracao}


def main(argv):
    escala = float(argv[0]) if argv else 0.9
    ok, resultado = carimbar_gif(escala=escala)
    if not ok:
        print("✗ " + resultado)
        return 1
    print("✓ GIF carimbado (%s) a partir de %s: %s — %d quadros, %dx%d, %.2f MB (fonte %.2f MB), vídeo %s" % (
        resultado["via"], resultado["origem"], os.path.relpath(GIF, RAIZ), resultado["frames"],
        resultado["tamanho"][0], resultado["tamanho"][1],
        resultado["bytes"] / 1048576.0, resultado["bytes_antes"] / 1048576.0,
        resultado["link"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
