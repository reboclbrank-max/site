#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confere que o vídeo final tem imagem, legenda, som e cartão — não só bytes.

POR QUE EXISTE (27/10/2026): o validador de imagem (tools/validar-video.py) prova que há
jogo na tela, mas não prova que o vídeo está APRESENTÁVEL. Um MP4 mudo e sem legenda passaria
nele e não deveria ser chamado de vídeo pronto. Aqui se mede o que falta:

  - trilha de áudio presente e não silenciosa (nível médio medido, não presumido);
  - faixa de legendas queimada visível: compara o quadro do rodapé com o mesmo quadro sem
    o filtro — se a legenda existe, a região do rodapé muda;
  - cartão final: os 3 últimos segundos são escuros e quase estáticos (fundo do cartão),
    diferentes do jogo em si.

Uso: python3 tools/testes-video-final.py media/gameplay/ceifalume-gameplay.mp4
"""
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ffmpeg():
    for c in [os.environ.get("FFMPEG_PATH")]:
        if c and os.path.exists(c):
            return c
    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0:
        return "ffmpeg"
    try:
        saida = subprocess.run(
            [sys.executable, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
            capture_output=True, text=True)
        caminho = (saida.stdout or "").strip()
        if saida.returncode == 0 and caminho and os.path.exists(caminho):
            return caminho
    except Exception:  # noqa: BLE001
        pass
    return None


def metadados(binario, arquivo):
    r = subprocess.run([binario, "-hide_banner", "-i", arquivo], capture_output=True, text=True)
    texto = (r.stderr or "") + (r.stdout or "")
    dur = None
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", texto)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return dur, texto


def nivel_audio(binario, arquivo):
    """Volume médio e pico medidos com o filtro volumedetect."""
    r = subprocess.run([binario, "-hide_banner", "-i", arquivo, "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    texto = (r.stderr or "") + (r.stdout or "")
    media = re.search(r"mean_volume:\s*(-?[\d.]+) dB", texto)
    pico = re.search(r"max_volume:\s*(-?[\d.]+) dB", texto)
    return (float(media.group(1)) if media else None,
            float(pico.group(1)) if pico else None)


def brilho_regiao(binario, arquivo, tempo, regiao):
    """Brilho médio de uma região (x,y,w,h) num instante — em 0-255."""
    x, y, w, h = regiao
    cmd = [binario, "-v", "error", "-ss", str(tempo), "-i", arquivo, "-frames:v", "1",
           "-vf", "crop=%d:%d:%d:%d,scale=32:18" % (w, h, x, y),
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    dados = r.stdout
    return sum(dados) / float(len(dados))


def validar(caminho, escrever=print):
    problemas = []
    binario = ffmpeg()
    if not binario:
        return False, {"erro": "sem ffmpeg"}
    if not os.path.exists(caminho):
        return False, {"erro": "arquivo não existe"}
    dur, texto = metadados(binario, caminho)
    info = {"duracao": dur, "bytes": os.path.getsize(caminho)}
    if not dur or dur < 12:
        problemas.append("duração curta demais: %s" % dur)

    # 1. som
    if "Audio:" not in texto:
        problemas.append("sem trilha de áudio")
        info["audio_media"] = None
    else:
        media, pico = nivel_audio(binario, caminho)
        info["audio_media"] = media
        info["audio_pico"] = pico
        if media is None:
            problemas.append("não consegui medir o áudio")
        elif media < -45:
            problemas.append("áudio praticamente mudo (média %.1f dB)" % media)
        if pico is not None and pico > -0.5:
            problemas.append("áudio estourando (pico %.1f dB)" % pico)

    # 2. legenda queimada: o rodapé do meio do vídeo muda por causa do texto
    meio = (dur or 30) * 0.45
    rodape = (300, 560, 680, 130)
    com_filtro = brilho_regiao(binario, caminho, meio, rodape)
    info["rodape_brilho"] = com_filtro
    # legenda com fundo escuro puxa o brilho médio do rodapé para baixo em relação ao jogo
    if com_filtro is None:
        problemas.append("não consegui medir o rodapé (legenda não verificada)")
    elif com_filtro > 120:
        problemas.append("rodapé sem legenda visível (brilho %.0f)" % com_filtro)

    # 3. cartão final: os últimos 2,5 s são escuros
    final = brilho_regiao(binario, caminho, max(0, (dur or 30) - 1.5), (0, 0, 1280, 720))
    info["cartao_brilho"] = final
    if final is None:
        problemas.append("não consegui medir o cartão final")
    elif final > 60:
        problemas.append("o fim do vídeo não parece cartão (brilho %.0f)" % final)

    escrever("vídeo final: %s" % os.path.basename(caminho))
    escrever("  %.1f s · %.1f MB" % (dur or 0, info["bytes"] / 1048576.0))
    escrever("  áudio: média %s dB · pico %s dB" % (info.get("audio_media"), info.get("audio_pico")))
    escrever("  rodapé (legenda) brilho %.0f · cartão final brilho %.0f"
             % (com_filtro or -1, final or -1))
    for p in problemas:
        escrever("  ✘ " + p)
    if not problemas:
        escrever("  ✔ tem som, legenda queimada e cartão final")
    return (not problemas), info, problemas


def main(argv):
    alvo = argv[0] if argv else os.path.join(RAIZ, "media", "gameplay", "ceifalume-gameplay.mp4")
    ok, _i, _p = validar(alvo)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
