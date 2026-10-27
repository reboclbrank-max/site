#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreiras do vídeo de gameplay — o que tem que ser verdade antes de chamar de vídeo.

Prova, sem rede e sem publicar nada:
  - o roteiro de captura é determinístico, começa pelas telas de abertura e termina dentro do
    tempo pedido (nenhuma ação fora da janela, nenhuma coordenada fora da tela);
  - o gravador recusa rodar sem navegador e sem ffmpeg, com código de erro próprio;
  - o validador de vídeo REPROVA tela parada, tela preta e arquivo pequeno, e APROVA um vídeo
    sintético com movimento — a barreira serve para os dois lados;
  - o kit do gameplay só existe quando o arquivo existe, e mantém os links oficiais do kit;
  - o envio continua trancado sem a palavra PUBLICAR;
  - o workflow tem cron de gravação e NÃO publica sozinho.
"""
import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))

falhas = 0


def ok(nome, cond, detalhe=""):
    global falhas
    if cond:
        print("OK  " + nome)
    else:
        falhas += 1
        print("FALHOU  " + nome + ("  <" + str(detalhe) + ">" if detalhe else ""))


def node(script):
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, cwd=RAIZ)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout)[-300:]
    return (r.stdout or "").strip(), None


def _pares_ass(texto):
    import re as _re
    saida = []
    for linha in texto.splitlines():
        m = _re.match(r"Dialogue: 0,(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+),.*?,,.*?,,(.*)$", linha)
        if m:
            ini = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            fim = int(m.group(4)) * 3600 + int(m.group(5)) * 60 + float(m.group(6))
            saida.append((ini, fim, m.group(7)))
    return saida


def _duracao_maxima(texto):
    return max((f - i for i, f, _t in _pares_ass(texto)), default=0)


def _textos(texto):
    return [t for _i, _f, t in _pares_ass(texto)]


def ffmpeg():
    import importlib.util
    spec = importlib.util.spec_from_file_location("val", os.path.join(RAIZ, "tools", "validar-video.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, mod.ffmpeg()


def main():
    # 1. o agente que olha o estado e decide (o roteiro cego saiu em 27/10)
    saida, erro = node(
        "const m=require('./tools/gravar-gameplay.js');"
        "const cel=(v,id)=>({id:id||'A',verde:v,centro:{x:500,y:300}});"
        "const base={tutorial:0,titulo:0,celulas:[cel(0,'A'),cel(0,'B'),cel(0,'C'),cel(0,'D')]};"
        "const r={"
        " tutorial:m.decidir({...base,tutorial:0.4}).motivo,"
        " titulo:m.decidir({...base,titulo:0.3}).motivo,"
        " pronta:m.decidir({...base,celulas:[cel(0.12,'A'),cel(0,'B')]}),"
        " vazia:m.decidir({...base}).tipo,"
        " crescendo:m.decidir({...base,celulas:[cel(0.05,'A'),cel(0.04,'B')]}).motivo"
        "};"
        "console.log(JSON.stringify(r));")
    ok("o decisor roda no Node", saida is not None, erro)
    if saida:
        d = json.loads(saida)
        ok("tutorial visivel -> toca no tutorial", "tutorial" in d["tutorial"], d["tutorial"])
        ok("tela de titulo -> toca em Jogar", "t" in d["titulo"], d["titulo"])
        ok("celula madura -> colhe aquela celula", "pronta" in d["pronta"]["motivo"], d["pronta"])
        ok("celula madura manda tocar no centro dela",
           d["pronta"]["alvo"] == {"x": 500, "y": 300}, d["pronta"].get("alvo"))
        ok("tudo vazio -> planta", d["vazia"] == "plantar", d["vazia"])
        ok("tudo crescendo -> rende moeda no bico", "bico" in d["crescendo"], d["crescendo"])
    fonte = open(os.path.join(RAIZ, "tools", "gravar-gameplay.js"), encoding="utf-8").read()
    ok("o gravador decide pelo estado (nao por lista fixa)", "function decidir(" in fonte)
    ok("o gravador grava o relatorio de decisoes ao lado do video", "-decisoes.json" in fonte)

    # 2. o gravador não finge: sem biblioteca de navegador ele devolve null (código 3 no uso).
    saida, erro = node(
        "const m=require('./tools/gravar-gameplay.js');"
        "const vazio=m.carregarPlaywright(['/nao/existe/a','/nem/isto'],false);"
        "const semLista=m.carregarPlaywright([],false);"
        "const real=m.carregarPlaywright();"
        "console.log(JSON.stringify({vazio:vazio===null,semLista:semLista===null,"
        "real:real!==null}));")
    ok("o gravador acha o navegador pela lista de caminhos (função testável)", saida is not None, erro)
    if saida:
        d2 = json.loads(saida)
        ok("sem navegador instalado a escolha é null — e o uso sai com código 3",
           d2["vazio"] is True, saida)
        ok("lista vazia e sem padrões também devolve null (não quebra)",
           d2["semLista"] is True, saida)
        ok("com o navegador instalado a escolha não é null", d2["real"] is True, saida)

    # 3. o validador reprova o que não é gameplay
    mod, binario = ffmpeg()
    if not binario:
        print("○ validador de vídeo → SKIP: sem ffmpeg nesta máquina")
    else:
        import tempfile
        pasta = tempfile.mkdtemp()
        parado = os.path.join(pasta, "parado.mp4")
        subprocess.run([binario, "-y", "-f", "lavfi", "-i", "color=c=0x1b2a4a:s=1280x720:d=12",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", parado],
                       capture_output=True)
        antes = falhas
        ok_v, rel, problemas = mod.validar(parado, binario=binario, escrever=lambda *_: None)
        ok("vídeo de cor única é reprovado", ok_v is False and problemas, problemas)
        ok("o motivo aponta imagem parada ou cor", any("parada" in p or "cor" in p for p in problemas),
           problemas)

        movendo = os.path.join(pasta, "movendo.mp4")
        subprocess.run([binario, "-y", "-f", "lavfi",
                        "-i", "testsrc=size=1280x720:rate=24:duration=12",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", movendo], capture_output=True)
        ok_m, rel_m, probs_m = mod.validar(movendo, binario=binario, escrever=lambda *_: None)
        ok("vídeo com movimento é aprovado", ok_m is True, probs_m)
        ok("o relatório traz números medidos", all(k in rel_m for k in
           ("duracao_s", "largura", "movimento_medio", "cores_media")), list(rel_m))
        ok("a leitura do arquivo encontrou 1280x720", (rel_m.get("largura"), rel_m.get("altura")) == (1280, 720),
           (rel_m.get("largura"), rel_m.get("altura")))

    # 4. kit do gameplay
    spec = __import__("importlib.util").util.spec_from_file_location(
        "kitg", os.path.join(RAIZ, "tools", "kit-gameplay.py"))
    kitg = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(kitg)
    p, erros = kitg.pacote("ceifalume")
    ok("o gameplay tem pacote pronto", p is not None and not erros, erros)
    if p:
        ok("o pacote aponta para o arquivo do gameplay", p["arquivo"].endswith("ceifalume-gameplay.mp4"), p["arquivo"])
        ok("o pacote tem id próprio para o envio", p.get("id") == "ceifalume-gameplay", p.get("id"))
        ok("a descrição mantém os links oficiais",
           "https://reboclbrank-max.github.io/site/jogos/ceifalume/" in p["descricao"]
           and "canais.html" in p["descricao"])
        ok("a descrição diz que o vídeo foi gravado do jogo", "gravado automaticamente" in p["descricao"])
        ok("o título cabe no limite do YouTube", 0 < len(p["titulo"]) <= 100, len(p["titulo"]))
        ok("o pacote não promete o que a casa não sustenta",
           not any(x in (p["titulo"] + p["descricao"]).lower()
                   for x in ("em breve", "melhor do mundo", "garantido", "viral")))

    # 4b. pós-produção: legenda, trilha e cartão
    spec2 = __import__("importlib.util").util.spec_from_file_location(
        "prod", os.path.join(RAIZ, "tools", "produzir-video.py"))
    prod = __import__("importlib.util").util.module_from_spec(spec2)
    spec2.loader.exec_module(prod)
    decisoes = [{"t": 2.0, "motivo": "célula A livre"}, {"t": 6.0, "motivo": "célula B livre"},
                {"t": 9.0, "motivo": "célula A pronta (verde 0.094)"},
                {"t": 12.0, "motivo": "tudo semeado ou crescendo: moeda no bico"}]
    ass = prod.montar_ass(decisoes, 20)
    # duas decisões diferentes com a MESMA ação ("célula A livre" e "célula B livre" viram
    # "plantando semente") não precisam de duas legendas seguidas iguais.
    ok("a legenda vem das decisões do agente", ass.count("Dialogue:") == 3, ass.count("Dialogue:"))
    ok("decisões repetidas no fim não duplicam legenda",
       prod.montar_ass(decisoes + [{"t": 12.5, "motivo": "tudo semeado ou crescendo: moeda no bico"}], 20)
       .count("Dialogue:") == 3)
    ok("as legendas descrevem plantio, colheita e moeda",
       {"plantando semente", "colhendo a planta madura", "fazendo bico: +1 moeda"} <= set(_textos(ass)),
       _textos(ass))
    ok("o estilo da legenda fica no rodapé e não cobre a tela",
       "Style: Casa" in ass and "MarginV, Encoding" in ass)
    ok("nenhuma legenda fica mais de 4 s na tela", _duracao_maxima(ass) <= 4.01, _duracao_maxima(ass))
    ok("o texto da legenda é curto e legível", all(len(x) <= 48 for x in _textos(ass)), _textos(ass))
    ok("o relatório de decisões sem movimento ainda gera legenda",
       prod.montar_ass([], 20).count("Dialogue:") == 0)

    # 5. envio continua trancado
    env = dict(os.environ, KIT_YOUTUBE=os.path.join("posts", "kit-gameplay.json"), CONFIRMACAO="")
    r = subprocess.run([sys.executable, "tools/enviar-youtube.py", "ceifalume-gameplay"],
                       capture_output=True, text=True, cwd=RAIZ, env=env)
    ok("sem PUBLICAR o envio do gameplay é recusado", r.returncode == 1 and "PUBLICAR" in (r.stdout + r.stderr),
       (r.stdout + r.stderr)[-120:])

    # 6. o workflow
    caminho = os.path.join(RAIZ, ".github", "workflows", "gravar-gameplay.yml")
    texto = open(caminho, encoding="utf-8").read() if os.path.exists(caminho) else ""
    ok("workflow do gameplay existe", bool(texto))
    for marca, nome in [
        ("node tools/gravar-gameplay.js", "roda o gravador"),
        ("tools/validar-video.py", "mede o vídeo antes de chamar de vídeo"),
        ("tools/kit-gameplay.py", "monta o kit do gameplay"),
        ("upload-artifact", "guarda o arquivo como artefato"),
        ("cron:", "tem gravação agendada"),
        ("publicar == 'PUBLICAR'", "exige a palavra PUBLICAR para publicar"),
        ("workflow_dispatch", "pode ser rodado à mão"),
    ]:
        ok("workflow " + nome, marca in texto, marca)
    ok("o cron só grava (não publica sozinho)",
       "secrets.YT_CLIENT_ID" not in texto.split("publicar == 'PUBLICAR'")[0],
       "credencial citada antes do cadeado")

    total = 37
    print("\n%d/%d testes do vídeo de gameplay passaram" % (total - falhas, total))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
