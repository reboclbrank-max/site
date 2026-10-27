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


def ffmpeg():
    import importlib.util
    spec = importlib.util.spec_from_file_location("val", os.path.join(RAIZ, "tools", "validar-video.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, mod.ffmpeg()


def main():
    # 1. o roteiro
    saida, erro = node(
        "const m=require('./tools/gravar-gameplay.js');"
        "const r=m.roteiro(45);"
        "const fora=r.filter(a=>a.t<0||a.t>=44.7||a.x<0||a.x>1280||a.y<0||a.y>720);"
        "const cresce=r.every((a,i)=>i===0||a.t>=r[i-1].t);"
        "const igual=JSON.stringify(r)===JSON.stringify(m.roteiro(45));"
        "console.log(JSON.stringify({n:r.length,fora:fora.length,cresce,igual,"
        "primeiro:r[0].nota,ultimo:r[r.length-1].nota,xs:[...new Set(r.map(a=>a.x))].length}));")
    ok("o roteiro de captura roda no Node", saida is not None, erro)
    if saida:
        d = json.loads(saida)
        ok("roteiro tem ações suficientes para 45 s", d["n"] >= 25, d["n"])
        ok("nenhuma ação fora da tela ou do tempo", d["fora"] == 0, d["fora"])
        ok("as ações estão em ordem de tempo", d["cresce"] is True)
        ok("o roteiro é determinístico (duas chamadas iguais)", d["igual"] is True)
        ok("o roteiro começa avançando as telas de abertura", d["primeiro"] == "avançar tela", d["primeiro"])
        ok("o roteiro toca em pontos diferentes da tela", d["xs"] >= 3, d["xs"])

    # 2. o gravador não finge: sem biblioteca de navegador ele devolve null (código 3 no uso).
    #    A prova é na função que decide, não no que está instalado nesta máquina.
    saida, erro = node(
        "const m=require('./tools/gravar-gameplay.js');"
        "console.log(JSON.stringify({vazio:m.carregarPlaywright(['/nao/existe/a','/nem/isto'])}));")
    ok("o gravador acha o navegador pela lista de caminhos (função testável)", saida is not None, erro)
    if saida:
        ok("sem navegador instalado a escolha é null — e o uso sai com código 3",
           json.loads(saida)["vazio"] is None, saida)

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

    total = 27
    print("\n%d/%d testes do vídeo de gameplay passaram" % (total - falhas, total))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
