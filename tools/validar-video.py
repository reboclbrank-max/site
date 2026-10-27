#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validador do vídeo de gameplay — decide se o arquivo tem JOGO na imagem.

POR QUE EXISTE (27/10/2026): a casa conseguiu gravar, pela primeira vez, o jogo rodando num
navegador sem tela (Chromium + WebGL por software). O risco seguinte é o oposto: entregar
"vídeo" que é tela preta, tela de carregamento parada ou splash do estúdio por 45 segundos.
Nada disso é gameplay, e a casa não pode chamar isso de gameplay.

O que este script mede, sem depender de biblioteca externa (só ffmpeg):
  - duração, resolução e taxa de quadros reais (lidos do próprio arquivo);
  - brilho médio de cada amostra (tela preta tem brilho ~0 e variância ~0);
  - variedade de cor (quantas cores distintas aparecem: jogo tem centenas);
  - movimento (diferença média entre amostras consecutivas) e o maior trecho congelado;
  - se o arquivo tem o mínimo de bytes que vídeo real ocupa.

Saída: relatório em texto e código 0 só quando o vídeo passa em tudo. Cada checagem imprime
o número medido — nunca "ok" sem número.
"""
import os
import struct
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# limites da casa — conservadores de propósito
MIN_DURACAO = 8.0          # segundos
MIN_LARGURA = 640
MIN_ALTURA = 360
MIN_FPS = 12.0
MAX_FRACO_PRETO = 0.20     # até 20% das amostras podem ser escuras (transições)
MIN_CORES = 60             # cores distintas numa amostra (jogo real passa fácil)
MIN_MOVIMENTO = 1.2        # diferença média (0-255) entre amostras seguidas
MAX_CONGELADO = 0.60       # fração máxima do vídeo parada

LARGURA_AMOSTRA = 160
ALTURA_AMOSTRA = 90
FPS_AMOSTRA = 2.0


def ffmpeg(explicito=None):
    """Caminho do ffmpeg: argumento, variável de ambiente, PATH, ou o do imageio-ffmpeg."""
    candidatos = [explicito, os.environ.get("FFMPEG_PATH")]
    for c in candidatos:
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
    """(duração, largura, altura, fps) lidos do cabeçalho do próprio arquivo."""
    r = subprocess.run([binario, "-hide_banner", "-i", arquivo], capture_output=True, text=True)
    texto = (r.stderr or "") + (r.stdout or "")
    dur = fps = None
    largura = altura = None
    m = texto.replace(" ", "")
    import re
    d = re.search(r"Duration:(\d+):(\d+):(\d+\.?\d*)", m)
    if d:
        dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    # a linha do stream traz "... , 1280x720 [SAR 1:1 DAR 16:9], 24 fps" — o espaço
    # depois da vírgula é o motivo de o padrão exigir \s*.
    v = re.search(r"Video:.*,\s*(\d{2,5})x(\d{2,5})", texto)
    if v:
        largura, altura = int(v.group(1)), int(v.group(2))
    f = re.search(r"([\d.]+)\s*fps", texto)
    if f:
        fps = float(f.group(1))
    return dur, largura, altura, fps


def amostras(binario, arquivo):
    """Lista de quadros rgb24 pequenos — a matéria-prima das medições."""
    cmd = [binario, "-v", "error", "-i", arquivo, "-vf",
           "fps=%s,scale=%d:%d" % (FPS_AMOSTRA, LARGURA_AMOSTRA, ALTURA_AMOSTRA),
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        return []
    bruto = r.stdout
    tamanho = LARGURA_AMOSTRA * ALTURA_AMOSTRA * 3
    return [bruto[i:i + tamanho] for i in range(0, len(bruto) - tamanho + 1, tamanho)]


def estatisticas(quadros):
    """Por quadro: brilho médio, cores distintas, e a diferença para o quadro anterior."""
    dados = []
    anterior = None
    for q in quadros:
        total = len(q)
        pix = struct.unpack("%dB" % total, q)
        # amostra 1 pixel a cada 9 para não pesar (mesmo resultado a olho)
        pontos = pix[0::9]
        brilho = sum(pontos) / float(len(pontos))
        cores = len(set((pix[i] << 16) | (pix[i + 1] << 8) | pix[i + 2]
                        for i in range(0, total - 2, 3 * 7)))
        diferenca = None
        if anterior is not None:
            # diferença média absoluta, em passos de 3 pixels
            soma = 0
            n = 0
            for i in range(0, total - 2, 9):
                soma += abs(q[i] - anterior[i])
                n += 1
            diferenca = soma / float(n)
        dados.append({"brilho": brilho, "cores": cores, "diferenca": diferenca})
        anterior = q
    return dados


def maior_congelado(dados, limite=0.6):
    """Maior trecho (em segundos) em que nada se move."""
    maior = atual = 0
    for d in dados:
        if d["diferenca"] is not None and d["diferenca"] < limite:
            atual += 1
            maior = max(maior, atual)
        else:
            atual = 0
    return maior / FPS_AMOSTRA


def validar(caminho, binario=None, escrever=print):
    """Roda tudo. Devolve (ok, relatorio_dict, lista_de_problemas)."""
    problemas = []
    rel = {"arquivo": caminho}
    if not os.path.exists(caminho):
        return False, rel, ["arquivo não existe"]
    tamanho = os.path.getsize(caminho)
    rel["bytes"] = tamanho
    if tamanho < 100_000:
        problemas.append("arquivo pequeno demais (%d B): vídeo real tem mais" % tamanho)

    binario = binario or ffmpeg()
    if not binario:
        return False, rel, ["sem ffmpeg para medir o vídeo"]

    dur, largura, altura, fps = metadados(binario, caminho)
    rel.update({"duracao_s": dur, "largura": largura, "altura": altura, "fps": fps})
    if not dur:
        problemas.append("não consegui ler a duração (arquivo corrompido?)")
    elif dur < MIN_DURACAO:
        problemas.append("curto demais: %.1f s (mínimo %s)" % (dur, MIN_DURACAO))
    if not largura or largura < MIN_LARGURA or not altura or altura < MIN_ALTURA:
        problemas.append("resolução baixa: %sx%s (mínimo %dx%d)"
                         % (largura, altura, MIN_LARGURA, MIN_ALTURA))
    if fps and fps < MIN_FPS:
        problemas.append("taxa de quadros baixa: %s fps" % fps)

    quadros = amostras(binario, caminho)
    rel["amostras"] = len(quadros)
    if len(quadros) < 4:
        problemas.append("poucas amostras para julgar (%d)" % len(quadros))
        return False, rel, problemas

    dados = estatisticas(quadros)
    brilhos = [d["brilho"] for d in dados]
    cores = [d["cores"] for d in dados]
    difs = [d["diferenca"] for d in dados if d["diferenca"] is not None]
    pretos = sum(1 for b in brilhos if b < 8.0) / float(len(brilhos))
    movimento = sum(difs) / float(len(difs)) if difs else 0.0
    cores_media = sum(cores) / float(len(cores))
    congelado = maior_congelado(dados)

    rel.update({
        "brilho_medio": round(sum(brilhos) / len(brilhos), 2),
        "fracao_escura": round(pretos, 3),
        "cores_media": round(cores_media, 1),
        "movimento_medio": round(movimento, 2),
        "maior_congelado_s": round(congelado, 1),
    })

    if pretos > MAX_FRACO_PRETO:
        problemas.append("%.0f%% das amostras estão escuras (tela preta não é gameplay)"
                         % (pretos * 100))
    if cores_media < MIN_CORES:
        problemas.append("pouca variedade de cor (%.0f cores): parece tela vazia, não jogo"
                         % cores_media)
    if movimento < MIN_MOVIMENTO:
        problemas.append("imagem quase parada (movimento %.2f): não há gameplay em curso"
                         % movimento)
    if congelado > MAX_CONGELADO * (dur or 1):
        problemas.append("trecho congelado de %.1f s" % congelado)

    escrever("vídeo: %s" % os.path.basename(caminho))
    escrever("  %s · %sx%s · %s fps · %d amostras"
             % ("%.1f s" % dur if dur else "duração ?", largura, altura,
                ("%.0f" % fps) if fps else "?", len(quadros)))
    escrever("  brilho médio %.1f (escuro em %.0f%% das amostras) · %.0f cores · "
             "movimento %.2f · maior trecho parado %.1f s"
             % (rel["brilho_medio"], pretos * 100, cores_media, movimento, congelado))
    for p in problemas:
        escrever("  ✘ " + p)
    if not problemas:
        escrever("  ✔ o arquivo tem imagem em movimento de verdade")
    return (not problemas), rel, problemas


def main(argv):
    alvo = argv[0] if argv else os.path.join(RAIZ, "media", "gameplay",
                                            "ceifalume-gameplay.mp4")
    ok, _rel, problemas = validar(alvo)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
