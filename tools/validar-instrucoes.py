#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede se as INSTRUÇÕES DE COMO JOGAR estão na tela do primeiro ao último quadro.

Requisito do dono, palavra por palavra: "no vídeo as instruções de como jogar não saem da tela
em momento algum". Isso não se garante escrevendo no relatório — se mede no arquivo final:

  para cada amostra do vídeo (1 por segundo, ~160x90 RGB):
    1. a faixa do rodapé está escura e opaca (brilho médio baixo e variância baixa);
    2. há texto claro dentro dela (fração de pixels claros acima de um mínimo);
    3. a faixa é a MESMA em todo o vídeo (a assinatura de brilho não muda além do ruído) — se
       alguém cortar a faixa no meio, o número cai e o script reprova.

Saída: um número por checagem e código 0 só se TODAS as amostras passarem. Vídeo sem faixa,
faixa que some no meio ou texto apagado reprovam aqui — antes de ir para o YouTube.
"""
import os
import subprocess
import sys

LARGURA_AMOSTRA = 160
ALTURA_AMOSTRA = 90
FPS_AMOSTRA = 1.0

# Faixa de 92 px num quadro de 720 = 12,8% do rodapé.
FRACAO_RODAPE = 0.13
MAX_BRILHO_RODAPE = 88.0      # fundo escuro (0-255)
MIN_BRILHO_TEXTO = 120.0      # o texto tem de ser claro
MIN_FRACAO_CLAROS = 0.012     # ao menos 1,2% de pixels claros na faixa (texto de verdade)
MAX_DESVIO_ASSINATURA = 26.0  # a faixa não pode mudar de cara no meio do vídeo


def ffmpeg():
    for c in [os.environ.get("FFMPEG_PATH")]:
        if c and os.path.exists(c):
            return c
    try:
        if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0:
            return "ffmpeg"
    except FileNotFoundError:
        pass
    try:
        saida = subprocess.run([sys.executable, "-c",
                                "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                               capture_output=True, text=True)
        caminho = (saida.stdout or "").strip()
        if saida.returncode == 0 and caminho and os.path.exists(caminho):
            return caminho
    except Exception:  # noqa: BLE001
        pass
    return None


def quadros(binario, arquivo):
    cmd = [binario, "-v", "error", "-i", arquivo, "-vf",
           "fps=%s,scale=%d:%d" % (FPS_AMOSTRA, LARGURA_AMOSTRA, ALTURA_AMOSTRA),
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        return []
    dados = r.stdout
    tamanho = LARGURA_AMOSTRA * ALTURA_AMOSTRA * 3
    return [dados[i:i + tamanho] for i in range(0, len(dados) - tamanho + 1, tamanho)]


def medir_rodape(quadro):
    """(brilho médio da faixa, fração de pixels claros, assinatura da faixa)."""
    inicio = int(ALTURA_AMOSTRA * (1 - FRACAO_RODAPE))
    total = claros = 0
    soma = 0.0
    assinatura = []
    for y in range(inicio, ALTURA_AMOSTRA):
        linha_soma = 0
        for x in range(LARGURA_AMOSTRA):
            i = (y * LARGURA_AMOSTRA + x) * 3
            r, g, b = quadro[i], quadro[i + 1], quadro[i + 2]
            brilho = 0.2126 * r + 0.7152 * g + 0.0722 * b
            soma += brilho
            total += 1
            if brilho > 150:
                claros += 1
            linha_soma += brilho
        assinatura.append(linha_soma / LARGURA_AMOSTRA)
    return soma / total, claros / total, assinatura


def main(argv):
    if not argv:
        print("uso: python3 tools/validar-instrucoes.py <video.mp4>")
        return 2
    arquivo = argv[0]
    if not os.path.exists(arquivo):
        print("✘ arquivo não existe: " + arquivo)
        return 2
    binario = ffmpeg()
    if not binario:
        print("✘ sem ffmpeg")
        return 2
    amostras = quadros(binario, arquivo)
    if not amostras:
        print("✘ não consegui ler quadro nenhum")
        return 2

    medidas = [medir_rodape(q) for q in amostras]
    brilhos = [m[0] for m in medidas]
    fracoes = [m[1] for m in medidas]
    referencia = medidas[0][2]
    desvios = []
    for m in medidas[1:]:
        d = sum(abs(a - b) for a, b in zip(m[2], referencia)) / len(referencia)
        desvios.append(d)

    problemas = []
    sem_faixa = [i for i, b in enumerate(brilhos) if b > MAX_BRILHO_RODAPE]
    sem_texto = [i for i, f in enumerate(fracoes) if f < MIN_FRACAO_CLAROS]
    if sem_faixa:
        problemas.append("%d de %d amostras com rodapé claro (faixa ausente), primeiro em %ds"
                         % (len(sem_faixa), len(brilhos), sem_faixa[0]))
    if sem_texto:
        problemas.append("%d de %d amostras sem texto claro na faixa, primeira em %ds"
                         % (len(sem_texto), len(brilhos), sem_texto[0]))
    pior = max(desvios) if desvios else 0.0
    if pior > MAX_DESVIO_ASSINATURA:
        i = desvios.index(pior)
        problemas.append("a faixa muda de cara no meio do vídeo (desvio %.1f em %ds, limite %.1f)"
                         % (pior, i + 1, MAX_DESVIO_ASSINATURA))

    print("amostras: %d (1 por segundo)" % len(amostras))
    print("rodapé escuro: brilho máx %.1f (limite %.1f) · mínimo %.1f" % (max(brilhos), MAX_BRILHO_RODAPE, min(brilhos)))
    print("texto claro: fração mínima %.3f (mínimo %.3f) · média %.3f"
          % (min(fracoes), MIN_FRACAO_CLAROS, sum(fracoes) / len(fracoes)))
    print("faixa estável: desvio máximo %.1f (limite %.1f)" % (pior, MAX_DESVIO_ASSINATURA))
    if problemas:
        for p in problemas:
            print("✘ " + p)
        return 1
    print("✔ instruções presentes e estáveis em todas as %d amostras" % len(amostras))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
