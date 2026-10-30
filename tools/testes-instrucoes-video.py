#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do vídeo com instruções fixas na tela (rodada 111).

O que se prova aqui, com ffmpeg de verdade e vídeos sintéticos pequenos (2 s):

  1. vídeo COM a faixa de instruções passa no validador;
  2. vídeo SEM faixa reprova (senão o validador não vale nada);
  3. vídeo em que a faixa SOME no meio reprova (é o caso real do vídeo anterior da casa:
     as instruções apareciam só no tutorial do começo e depois saíam da tela);
  4. vídeo com faixa ilegível (texto apagado) reprova;
  5. o desenhista recusa faixa pequena demais para o texto, em vez de cortar a instrução no meio.

Nada aqui toca a rede: os vídeos são gerados com lavfi (cor sólida) no diretório temporário.
"""
import os
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def rodar(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    binario = ffmpeg()
    if not binario:
        print("SKIP: sem ffmpeg neste ambiente")
        return 2
    if shutil.which("node") is None:
        print("SKIP: sem node neste ambiente")
        return 2
    temporario = tempfile.mkdtemp(prefix="testes-instrucoes-")
    jogo = os.path.join(temporario, "jogo.mp4")
    # 3 s de "jogo" sintético: cor sólida que se mexe (não é o ponto do teste, mas evita
    # qualquer atalho do validador que dependa de imagem parada).
    r = rodar([binario, "-y", "-hide_banner", "-loglevel", "error",
               "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=12:duration=3",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", jogo])
    assert r.returncode == 0, "não gerei o vídeo sintético: " + (r.stderr or "")[-200:]

    falhas = []

    def ok(nome, condicao, detalhe=""):
        if condicao:
            print("✔ " + nome)
        else:
            print("✘ " + nome + (" → " + detalhe if detalhe else ""))
            falhas.append(nome)

    # ---------- 1 e 2: validador aceita quem tem faixa e reprova quem não tem ----------
    sem_faixa = rodar([sys.executable, os.path.join(RAIZ, "tools", "validar-instrucoes.py"), jogo])
    ok("vídeo sem faixa de instruções reprova", sem_faixa.returncode == 1,
       "código " + str(sem_faixa.returncode))

    com_faixa = os.path.join(temporario, "com-faixa.mp4")
    r = rodar(["node", os.path.join(RAIZ, "tools", "legenda-guia.js"),
               "--entrada", jogo, "--saida", com_faixa, "--sem-trilha"])
    ok("legenda-guia produz o vídeo com a faixa", r.returncode == 0 and os.path.exists(com_faixa),
       (r.stderr or r.stdout or "")[-200:])
    if os.path.exists(com_faixa):
        medida = rodar([sys.executable, os.path.join(RAIZ, "tools", "validar-instrucoes.py"), com_faixa])
        ok("vídeo com a faixa passa no validador", medida.returncode == 0,
           (medida.stdout or "")[-300:])

    # ---------- 3: faixa que some no meio reprova ----------
    if os.path.exists(com_faixa):
        cortado = os.path.join(temporario, "faixa-some.mp4")
        # 1,5 s com faixa + 1,5 s sem faixa: exatamente o defeito do vídeo antigo da casa
        r = rodar([binario, "-y", "-hide_banner", "-loglevel", "error",
                   "-i", com_faixa, "-i", jogo, "-filter_complex",
                   "[0:v]trim=0:1.5,setpts=PTS-STARTPTS[a];[1:v]trim=0:1.5,setpts=PTS-STARTPTS[b];"
                   "[a][b]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264",
                   "-pix_fmt", "yuv420p", cortado])
        if r.returncode == 0:
            medida = rodar([sys.executable, os.path.join(RAIZ, "tools", "validar-instrucoes.py"), cortado])
            ok("vídeo em que a faixa some no meio reprova", medida.returncode == 1,
               (medida.stdout or "")[-300:])
        else:
            ok("vídeo em que a faixa some no meio reprova", False, "não montei o caso: " + (r.stderr or "")[-150:])

    # ---------- 4: faixa ilegível reprova ----------
    if os.path.exists(com_faixa):
        ilegivel = os.path.join(temporario, "faixa-ilegivel.mp4")
        # escurece o rodapé até apagar o texto (mantém a faixa, mata a leitura)
        r = rodar([binario, "-y", "-hide_banner", "-loglevel", "error", "-i", com_faixa,
                   "-vf", "drawbox=x=0:y=ih-150:w=iw:h=150:color=black@1:t=fill",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", ilegivel])
        if r.returncode == 0:
            medida = rodar([sys.executable, os.path.join(RAIZ, "tools", "validar-instrucoes.py"), ilegivel])
            ok("faixa com texto apagado reprova", medida.returncode == 1, (medida.stdout or "")[-250:])
        else:
            ok("faixa com texto apagado reprova", False, "não montei o caso: " + (r.stderr or "")[-150:])

    # ---------- 5: desenhista recusa faixa pequena demais ----------
    pequena = os.path.join(temporario, "faixa-pequena.png")
    r = rodar([sys.executable, os.path.join(RAIZ, "tools", "desenhar-faixa.py"),
               "--saida", pequena, "--largura", "640", "--altura", "8",
               "--linha", "COMO JOGAR: escolha a semente, plante no campo, faça um bico, colha e venda."])
    ok("faixa pequena demais é recusada, em vez de cortar a instrução", r.returncode != 0,
       "o desenhista aceitou uma faixa de 8 px")

    shutil.rmtree(temporario, ignore_errors=True)
    if falhas:
        print("\n%d contrato(s) falharam" % len(falhas))
        return 1
    print("\n5 contratos das instruções no vídeo passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
