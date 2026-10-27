#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pós-produção do gameplay: legenda queimada, trilha sintetizada e cartão final.

POR QUE EXISTE (27/10/2026): a captura crua era honesta, mas não era vídeo apresentável —
sem legenda, sem áudio, sem assinatura. Este script pega o MP4 cru + o relatório de decisões
que o gravador escreve (`*-decisoes.json`) e entrega o vídeo final:

  1. **legendas** — uma linha por decisão do agente ("planta nabo", "colhe e vende",
     "rende moeda no bico"), com tempo tirado do próprio relatório. Nada é inventado;
     o que aparece na legenda é o que o agente decidiu e fez.
  2. **trilha** — sintetizada aqui mesmo com o ffmpeg (pad de três notas, volume baixo).
     É música gerada por procedimento, não música licenciada; a descrição do vídeo diz isso.
  3. **cartão final** — 3 s com o endereço do jogo, para quem chega no fim saber onde jogar.

Ferramentas: só ffmpeg (com libass/libfreetype). Se faltar alguma, o script falha dizendo
qual — nunca entrega vídeo mudo sem legenda chamando isso de "pronto".
"""
import json
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# texto curto e verdadeiro para cada tipo de ação registrada pelo agente
LEGENDAS = [
    (r"^tutorial", "abrindo o jogo"),
    (r"^tela de t", "abrindo o jogo"),
    (r"^c[eé]lula (\w) livre$", "plantando semente"),
    (r"^c[eé]lula (\w) pronta", "colhendo a planta madura"),
    (r"bico", "fazendo bico: +1 moeda"),
    (r"vender", "vendendo a colheita"),
]


def ffmpeg(explicito=None):
    for c in [explicito, os.environ.get("FFMPEG_PATH")]:
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


def duracao(binario, arquivo):
    r = subprocess.run([binario, "-hide_banner", "-i", arquivo], capture_output=True, text=True)
    texto = (r.stderr or "") + (r.stdout or "")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", texto)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def texto_da_decisao(motivo):
    for padrao, texto in LEGENDAS:
        if re.search(padrao, motivo or "", re.I):
            return texto
    return (motivo or "")[:48]


ESTILO_ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Casa,DejaVu Sans,34,&H00E8E6E1,&H00E8E6E1,&H00101010,&H99000000,0,0,0,0,100,100,0.5,0,3,10,0,2,60,60,28,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_tempo(segundos):
    s = max(0.0, float(segundos))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return "%d:%02d:%05.2f" % (h, m, s % 60)


def montar_ass(decisoes, duracao_total):
    """Legendas com estilo da casa (fundo escuro, rodapé) — o estilo padrão do libass cobre
    metade da tela e esconde o jogo, que é justamente o que o vídeo precisa mostrar."""
    vistos = []
    for d in decisoes:
        texto = texto_da_decisao(d.get("motivo"))
        if vistos and vistos[-1][1] == texto:
            continue
        vistos.append((d.get("t", 0), texto))
    linhas = []
    for i, (t, texto) in enumerate(vistos):
        proximo = vistos[i + 1][0] if i + 1 < len(vistos) else duracao_total
        fim = min(proximo, t + 4)              # nada de legenda parada 11 s
        fim = max(fim, min(t + 1.2, proximo))
        linhas.append("Dialogue: 0,%s,%s,Casa,,0,0,0,,%s"
                      % (_ass_tempo(t), _ass_tempo(fim), texto.replace("{", "").replace("}", "")))
    return ESTILO_ASS + "\n".join(linhas) + "\n"


def montar_srt(decisoes, duracao_total):
    """SRT para quem quiser legenda desligável (o vídeo final usa ASS, este fica de extra)."""
    blocos = []
    vistos = []
    for d in decisoes:
        texto = texto_da_decisao(d.get("motivo"))
        if vistos and vistos[-1][1] == texto:
            continue
        vistos.append((d.get("t", 0), texto))
    for i, (t, texto) in enumerate(vistos):
        proximo = vistos[i + 1][0] if i + 1 < len(vistos) else duracao_total
        fim = min(proximo, t + 4)
        fim = max(fim, min(t + 1.2, proximo))
        blocos.append("%d\n%s --> %s\n%s\n" % (i + 1, _srt_tempo(t), _srt_tempo(fim), texto))
    return "\n".join(blocos)


def _srt_tempo(segundos):
    s = max(0.0, float(segundos))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    resto = s % 60
    return ("%02d:%02d:%06.3f" % (h, m, resto)).replace(".", ",")


def gerar_trilha(binario, destino, segundos):
    """Pad de três notas (Lá menor) com respiração lenta. Volume baixo de propósito."""
    filtro = ("aevalsrc=0.055*sin(2*PI*220*t)+0.04*sin(2*PI*261.63*t)"
              "+0.03*sin(2*PI*329.63*t)+0.02*sin(2*PI*110*t):s=44100:d=%s,"
              "tremolo=f=0.15:d=0.25,volume=0.6" % (segundos + 0.5))
    r = subprocess.run([binario, "-y", "-f", "lavfi", "-i", filtro,
                        "-c:a", "aac", "-b:a", "96k", destino], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "")[-300:]


def cartao_final(binario, destino, segundos, titulo, linha2, raiz=RAIZ):
    """3 s de cartão final.

    O ffmpeg deste ambiente NÃO tem drawtext (medido em 27/10: só libass/subtitles). Então o
    cartão é desenhado no navegador (tools/cartao-final.js) e aqui vira vídeo com -loop 1.
    Se o navegador não existir, devolve falha — o vídeo continua, sem cartão.
    """
    png = os.path.join(os.path.dirname(destino), "cartao.png")
    node = subprocess.run(["node", os.path.join(raiz, "tools", "cartao-final.js"),
                           "--saida", png, "--titulo", titulo, "--linha2", linha2],
                          capture_output=True, text=True)
    if node.returncode != 0 or not os.path.exists(png):
        return False, (node.stderr or node.stdout or "cartão não gerado")[-300:]
    r = subprocess.run([binario, "-y", "-loop", "1", "-t", str(segundos), "-i", png,
                        "-vf", "scale=1280:720,format=yuv420p", "-r", "24",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", destino],
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "")[-300:]


def produzir(cru, decisoes_json, saida, binario=None, escrever=print):
    """Devolve (ok, informacoes, problemas)."""
    binario = binario or ffmpeg()
    problemas = []
    info = {}
    if not binario:
        return False, info, ["sem ffmpeg"]
    if not os.path.exists(cru):
        return False, info, ["vídeo cru não existe: " + cru]
    if not os.path.exists(decisoes_json):
        return False, info, ["relatório de decisões não existe: " + decisoes_json]

    rel = json.load(open(decisoes_json, encoding="utf-8"))
    decisoes = rel.get("decisoes") or []
    dur = duracao(binario, cru)
    info["duracao_cru"] = dur
    if not dur:
        return False, info, ["não consegui ler a duração do cru"]

    pasta = os.path.dirname(os.path.abspath(saida)) or "."
    os.makedirs(pasta, exist_ok=True)
    ass = os.path.join(pasta, "legendas.ass")
    srt = os.path.join(pasta, "legendas.srt")
    trilha = os.path.join(pasta, "trilha.m4a")
    cartao = os.path.join(pasta, "cartao.mp4")

    conteudo_ass = montar_ass(decisoes, dur)
    with open(ass, "w", encoding="utf-8") as f:
        f.write(conteudo_ass)
    with open(srt, "w", encoding="utf-8") as f:
        f.write(montar_srt(decisoes, dur))
    info["legendas"] = conteudo_ass.count("Dialogue:")
    if not info["legendas"]:
        problemas.append("nenhuma legenda gerada (relatório sem decisões)")

    ok_trilha, erro = gerar_trilha(binario, trilha, dur)
    if not ok_trilha:
        problemas.append("trilha falhou: " + erro[-160:])
    ok_cartao, erro = cartao_final(binario, cartao, 3, "CEIFALUME",
                                   "reboclbrank-max.github.io/site/")
    if not ok_cartao:
        problemas.append("cartão final falhou: " + erro[-160:])

    # legenda queimada + trilha + cartão final, num passo
    lista = os.path.join(pasta, "partes.txt")
    with open(lista, "w", encoding="utf-8") as f:
        f.write("file '" + os.path.abspath(cru) + "'\n")
        if ok_cartao:
            f.write("file '" + os.path.abspath(cartao) + "'\n")
    filtro = ("ass='" + ass.replace("\\", "/").replace(":", r"\:") + "',"
              "scale=1280:720:flags=lanczos")
    comando = [binario, "-y", "-f", "concat", "-safe", "0", "-i", lista]
    if ok_trilha:
        comando += ["-i", trilha]
    comando += ["-vf", filtro, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if ok_trilha:
        comando += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k",
                    "-shortest"]
    comando += [saida]
    r = subprocess.run(comando, capture_output=True, text=True)
    if r.returncode != 0:
        return False, info, problemas + ["montagem falhou: " + (r.stderr or "")[-300:]]

    info["duracao_final"] = duracao(binario, saida)
    info["bytes"] = os.path.getsize(saida) if os.path.exists(saida) else 0
    escrever("vídeo final: %s" % os.path.basename(saida))
    escrever("  %s s · %.1f MB · %d legendas · trilha: %s · cartão: %s"
             % ("%.1f" % (info["duracao_final"] or 0), info["bytes"] / 1048576.0,
                info["legendas"], "sim" if ok_trilha else "NÃO", "sim" if ok_cartao else "NÃO"))
    for p in problemas:
        escrever("  ✘ " + p)
    return (not problemas), info, problemas


def main(argv):
    cru = argv[0] if argv else os.path.join(RAIZ, "media", "gameplay", "ceifalume-gameplay-cru.mp4")
    rel = argv[1] if len(argv) > 1 else re.sub(r"\.mp4$", "-decisoes.json", cru)
    saida = argv[2] if len(argv) > 2 else os.path.join(RAIZ, "media", "gameplay",
                                                       "ceifalume-gameplay.mp4")
    ok, _info, _problemas = produzir(cru, rel, saida)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
