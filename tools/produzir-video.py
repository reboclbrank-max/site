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
    # PRANCHETA (o segundo jogo da casa, com roteiro desde 27/10/2026)
    (r"^abrir o menu do jogo$", "abrindo o jogo"),
    (r"^aceitar o convite do clube$", "aceitando o convite do clube"),
    (r"^aplicar a sugestão do staff$", "aplicando a sugestão do staff"),
    (r"^aplicar o microciclo", "montando a semana de treinos"),
    (r"^abrir a prancheta$", "abrindo a prancheta tática"),
    (r"^jogar com o plano", "começando a partida"),
    (r"^dar instrução no intervalo$", "instrução no intervalo"),
    (r"^seguir sem mexer$", "seguindo sem mexer"),
    (r"^acelerar a partida$", "acelerando a partida"),
    (r"^partida em andamento$", "partida em andamento"),
    (r"^pular para o fim", "pulando para o resultado"),
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


def trechos_automaticos(decisoes, duracao):
    """Escolhe os trechos olhando o RELATÓRIO do agente, não números fixos.

    O problema que isto resolve: no runner a captura é mais lenta ou mais rápida que no sandbox,
    então o instante da colheita muda de run para run — um corte com segundos fixos ("106-132")
    funciona numa máquina e corta a colheita fora na outra. O relatório diz exatamente quando o
    agente semeou e quando colheu, então o corte é derivado daí.
    """
    plantar = [float(d.get("t", 0)) for d in decisoes if "semente" in str(d.get("acao") or "")]
    colher = [float(d.get("t", 0)) for d in decisoes if "colher" in str(d.get("acao") or "")]
    if not plantar or not colher:
        return None
    # trecho 1: abertura do jogo + todos os plantios (no máximo 30 s de cauda)
    fim1 = min(duracao, plantar[-1] + 4)
    inicio1 = max(0.0, fim1 - 30)
    # trecho 2: as colheitas e a venda (com folga antes e depois)
    inicio2 = max(0.0, colher[0] - 10)
    fim2 = min(duracao, colher[-1] + 8)
    if fim1 - inicio1 < 4 or fim2 - inicio2 < 4:
        return None
    return [(inicio1, fim1, 1.0), (inicio2, fim2, 1.0)]


def variantes_do_corte(trechos, duracao):
    """Do mais enxuto ao mais largo. Se a medida de movimento reprovar um, tenta o seguinte —
    o que nunca acontece é entregar vídeo parado como se fosse gameplay."""
    if not trechos:
        return []
    candidatos = [trechos]
    largos = [(max(0.0, ini - 6), min(duracao, fim + 6), vel) for ini, fim, vel in trechos]
    candidatos.append(largos)
    tudo = [(max(0.0, trechos[0][0]), min(duracao, trechos[-1][1]), 1.0)]
    candidatos.append(tudo)
    return candidatos


def medir_movimento(binario, arquivo):
    """Usa o mesmo medidor do portão (tools/validar-video.py) — sem conta paralela."""
    import importlib.util
    caminho = os.path.join(RAIZ, "tools", "validar-video.py")
    spec = importlib.util.spec_from_file_location("validar_video", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    quadros = mod.amostras(binario, arquivo)
    dados = mod.estatisticas(quadros)
    difs = [d["diferenca"] for d in dados if d["diferenca"] is not None]
    return (sum(difs) / len(difs)) if difs else 0.0, mod.MIN_MOVIMENTO


def recortar(binario, cru, destino, inicio, fim):
    """Corta um trecho do cru. Existe porque a captura sempre gasta segundos na abertura do
    jogo e, sob gravação, o tempo do jogo anda ~3x mais devagar que o relógio — o trecho de
    espera da plantação fica longo. Recortar é escolher o que mostrar, não maquiar: as decisões
    que sobram são as mesmas, só com o tempo deslocado."""
    comando = [binario, "-y", "-ss", "%.2f" % inicio, "-i", cru]
    if fim:
        comando += ["-t", "%.2f" % max(0.1, fim - inicio)]
    comando += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-an", destino]
    r = subprocess.run(comando, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "")[-300:]


def recortar_trechos(binario, cru, destino, trechos, pasta):
    """Junta vários trechos do cru num só arquivo, na ordem pedida.

    Por que existe: no jogo, entre plantar e colher passam ~30 s de tempo do jogo — e sob
    gravação o relógio do jogo anda quase 3x mais devagar, então a espera ocupa mais de um
    minuto de filme quase parado. O vídeo mostra a ação (plantar, crescer, colher, vender) e o
    trecho de espera é cortado; as decisões do relatório são as mesmas, só com o tempo deslocado.
    """
    pedacos = []
    for i, (ini, fim, velocidade) in enumerate(trechos):
        pedaco = os.path.join(pasta, "trecho-%d.mp4" % i)
        comando = [binario, "-y", "-ss", "%.2f" % ini, "-i", cru,
                   "-t", "%.2f" % max(0.1, fim - ini)]
        if velocidade > 1:
            # espera acelerada: o trecho em que a planta cresce aparece em ritmo x N
            comando += ["-vf", "setpts=PTS/%.3f,fps=24" % velocidade]
        comando += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-an", pedaco]
        r = subprocess.run(comando, capture_output=True, text=True)
        if r.returncode != 0:
            return False, (r.stderr or "")[-300:]
        pedacos.append(pedaco)
    lista = os.path.join(pasta, "trechos.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for pedaco in pedacos:
            f.write("file '" + os.path.abspath(pedaco) + "'\n")
    r = subprocess.run([binario, "-y", "-f", "concat", "-safe", "0", "-i", lista,
                        "-c", "copy", destino], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "")[-300:]


def deslocar(decisoes, trechos):
    """Reescreve o tempo das decisões para a linha do tempo do vídeo cortado."""
    novas = []
    deslocamento = 0.0
    for ini, fim, velocidade in trechos:
        for d in decisoes:
            t = float(d.get("t", 0))
            if ini <= t <= fim:
                novas.append(dict(d, t=round((t - ini) / velocidade + deslocamento, 2)))
        deslocamento += (fim - ini) / velocidade
    novas.sort(key=lambda d: d["t"])
    return novas


def produzir(cru, decisoes_json, saida, binario=None, escrever=print, inicio=0.0, fim=None,
             trechos=None):
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
    if trechos:
        pasta_trechos = os.path.dirname(os.path.abspath(saida)) or "."
        recortado = os.path.join(pasta_trechos, "cru-com-cortes.mp4")
        ok_corte, erro = recortar_trechos(binario, cru, recortado, trechos, pasta_trechos)
        if not ok_corte:
            return False, info, ["recorte falhou: " + erro]
        decisoes = deslocar(decisoes, trechos)
        cru = recortado
    elif inicio or fim:
        recortado = os.path.join(os.path.dirname(os.path.abspath(saida)) or ".", "cru-recortado.mp4")
        ok_corte, erro = recortar(binario, cru, recortado, inicio, fim or 0)
        if not ok_corte:
            return False, info, ["recorte falhou: " + erro]
        decisoes = [dict(d, t=round(float(d.get("t", 0)) - inicio, 2)) for d in decisoes
                    if float(d.get("t", 0)) >= inicio
                    and (not fim or float(d.get("t", 0)) <= fim)]
        cru = recortado
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
    resto = argv[3:]
    inicio = 0.0
    fim = None
    if "--inicio" in resto:
        inicio = float(resto[resto.index("--inicio") + 1])
    if "--fim" in resto:
        fim = float(resto[resto.index("--fim") + 1])
    trechos = None
    if "--trechos" in resto:
        bruto = resto[resto.index("--trechos") + 1]
        trechos = []
        for parte in bruto.split(","):
            faixa, _, vel = parte.partition(":")
            ini, _, fim_t = faixa.partition("-")
            trechos.append((float(ini), float(fim_t), float(vel or 1)))
    if "--trechos-auto" in resto:
        binario = ffmpeg()
        if not binario:
            print("✘ sem ffmpeg")
            return 1
        dur = duracao(binario, cru)
        relatorio = json.load(open(rel, encoding="utf-8"))
        base = trechos_automaticos(relatorio.get("decisoes") or [], dur or 0)
        if not base:
            print("✘ o relatório não tem plantio e colheita: não sei o que cortar")
            return 1
        aprovado = False
        for numero, candidato in enumerate(variantes_do_corte(base, dur or 0), start=1):
            print("corte %d: %s" % (numero, candidato))
            ok, _info, _problemas = produzir(cru, rel, saida, trechos=candidato)
            if not ok:
                return 1
            movimento, minimo = medir_movimento(binario, saida)
            print("  movimento medido: %.2f (mínimo %.2f)" % (movimento, minimo))
            if movimento >= minimo:
                aprovado = True
                break
        if not aprovado:
            print("✘ nenhum corte mostrou ação suficiente: o vídeo NÃO é entregue")
            return 1
        return 0

    ok, _info, _problemas = produzir(cru, rel, saida, inicio=inicio, fim=fim, trechos=trechos)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
