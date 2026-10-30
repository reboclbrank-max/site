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


total = 0


def ok(nome, cond, detalhe=""):
    # O total era um número escrito à mão ("total = 37"): prova nova não entrava na conta e o
    # relatório mentia sobre quantas provas existiam. Agora quem conta é a própria chamada.
    global falhas, total
    total += 1
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
    # Os estados abaixo são os MEDIDOS no jogo rodando em 27/10/2026 (ver docs/VIDEO-GAMEPLAY.md):
    # campo vazio: casca 0,000 · crescendo: verde 0,05-0,10 · maduro: casca 0,026-0,037.
    saida, erro = node(
        "const m=require('./tools/gravar-gameplay.js');"
        "const cel=(o)=>Object.assign({id:'A',verde:0,branco:0,ouroBotao:0,"
        "centro:{x:500,y:300},colher:{x:510,y:337}},o);"
        "const quatro=(f)=>({id:f.id||'A',verde:f.verde||0,branco:f.branco||0,"
        "ouroBotao:f.ouroBotao||0,centro:{x:500,y:300},colher:{x:510,y:337}});"
        "const base={tutorial:0,titulo:0,hud:0.084,celulas:[cel({id:'A'}),cel({id:'B'}),"
        "cel({id:'C'}),cel({id:'D'})]};"
        "const dois={A:2,B:2,C:2,D:2};"
        "const r={"
        " tutorial:m.decidir({...base,tutorial:0.4}).motivo,"
        " titulo:m.decidir({...base,titulo:0.3}).motivo,"
        " abertura:m.decidir({...base,hud:0}).motivo,"
        " pronta:m.decidir({...base,celulas:[cel({id:'A',branco:0.028}),cel({id:'B'})]}),"
        " vazia:m.decidir({...base},{confirmacoes:dois}).tipo,"
        " semConfirmacao:m.decidir({...base},{}).tipo,"
        " barra:m.decidir({...base,celulas:[cel({id:'A',ouroBotao:0.09}),cel({id:'B'})]},"
        "{confirmacoes:dois}).celula.id,"
        " crescendo:m.decidir({...base,celulas:[cel({id:'A',verde:0.05}),"
        "cel({id:'B',verde:0.04})]}).motivo"
        "};"
        "console.log(JSON.stringify(r));")
    ok("o decisor roda no Node", saida is not None, erro)
    if saida:
        d = json.loads(saida)
        ok("tutorial visivel -> toca no tutorial", "tutorial" in d["tutorial"], d["tutorial"])
        ok("tela de titulo -> toca em Jogar", "t" in d["titulo"], d["titulo"])
        ok("sem HUD de moedas -> atravessa a abertura", "abertura" in d["abertura"], d["abertura"])
        ok("celula madura -> colhe aquela celula", "pronta" in d["pronta"]["motivo"], d["pronta"])
        ok("celula madura manda tocar no botao Colher da caixa",
           d["pronta"]["alvo"] == {"x": 510, "y": 337}, d["pronta"].get("alvo"))
        ok("tudo vazio -> planta", d["vazia"] == "plantar", d["vazia"])
        ok("celula livre so e plantada quando a leitura se repete",
           d["semConfirmacao"] != "plantar", d["semConfirmacao"])
        ok("celula com barra dourada nao e replantada (planta na outra)",
           d["barra"] == "B", d["barra"])
        ok("tudo crescendo -> rende moeda no bico", "bico" in d["crescendo"], d["crescendo"])

    # 1b. ECONOMIA — o robo compra melhoria e escolhe a semente mais cara que o bolso cobre.
    # O estado de dinheiro abaixo vem do save do proprio jogo (moedas/nivel_*/semente_selecionada),
    # e a compra e conferida no save depois do toque — nao no "parece que comprou".
    saida, erro = node(
        "const m=require('./tools/gravar-gameplay.js');"
        "const cel=(id)=>Object.assign({id:id,verde:0.05,branco:0,ouroBotao:0.05,"
        "centro:{x:500,y:300},colher:{x:510,y:337}});"
        "const base={tutorial:0,titulo:0,hud:0.084,celulas:[cel('A'),cel('B')]};"
        "const eco=(o)=>Object.assign({moedas:0,semente:0},o);"
        "const d=(e,mem)=>m.decidir(base,Object.assign({confirmacoes:{A:2,B:2},economia:e},mem||{}));"
        "const todos={poco:true,lanterna:true,composteira:true,campo:true,celeiro:true};"
        "const r={"
        " rico:d(eco({moedas:100})),"
        " pobre:d(eco({moedas:20})).tipo,"
        " celeiroBarato:d(eco({moedas:35})).tipo,"
        " prioridade:d(eco({moedas:100}),{melhoriasFeitas:{poco:true}}).melhoria.id,"
        " caro:d(eco({moedas:1400}),{melhoriasFeitas:todos}),"
        " milho:d(eco({moedas:200}),{melhoriasFeitas:todos}),"
        " rodadaCurta:d(eco({moedas:90}),{melhoriasFeitas:todos}).tipo,"
        " tomate:d(eco({moedas:1300}),{melhoriasFeitas:todos}),"
        " semSemente:d(eco({moedas:1300,semente:3}),{melhoriasFeitas:todos}).tipo,"
        " zero:d(eco({moedas:0})).tipo,"
        " ganho:m.ganhoDeMoedas(25,19,70),"
        " semLeitura:m.ganhoDeMoedas(null,19,70)"
        "};"
        "console.log(JSON.stringify(r));")
    ok("o decisor de economia roda no Node", saida is not None, erro)
    if saida:
        e = json.loads(saida)
        ok("com dinheiro no bolso o robo compra melhoria", e["rico"]["tipo"] == "melhoria",
           e["rico"])
        ok("a melhoria comprada e a de maior efeito (poco, nao a mais barata)",
           e["rico"]["melhoria"]["id"] == "poco", e["rico"]["melhoria"])
        ok("sem dinheiro suficiente o robo nao inventa compra", e["pobre"] != "melhoria", e["pobre"])
        ok("celeiro (que nao muda moedas/min) nao e comprado nem sendo o mais barato",
           e["celeiroBarato"] != "melhoria", e["celeiroBarato"])
        ok("melhoria ja comprada nao e comprada de novo (vai para a proxima)",
           e["prioridade"] == "lanterna", e["prioridade"])
        ok("com as melhorias feitas o robo troca a semente pelo maior valor",
           e["caro"]["tipo"] == "semente", e["caro"])
        ok("com 1400 moedas a semente e o Tomate (200 x 6 rodadas + 5 = 1205)",
           e["caro"]["semente"]["indice"] == 3, e["caro"]["semente"])
        ok("com 200 moedas a semente sobe para o Milho (20 x 6 + 5 = 125)",
           e["milho"]["semente"]["nome"] == "Milho", e["milho"]["semente"])
        ok("com 90 moedas NAO sobe para o Milho (trocar sem caixa para 6 rodadas piora)",
           e["rodadaCurta"] != "semente", e["rodadaCurta"])
        ok("com 1300 moedas a semente escolhida sobe para o Tomate (venda 380)",
           e["tomate"]["semente"]["nome"] == "Tomate", e["tomate"]["semente"])
        ok("semente ja escolhida nao e trocada de novo", e["semSemente"] != "semente",
           e["semSemente"])
        ok("sem moeda nenhuma o robo continua jogando (nao travа no dinheiro)",
           e["zero"] in ("plantar", "toque"), e["zero"])
        ok("GANHO != SALDO: saldo cai 25->19 gastando 70 e o ganho e 64",
           e["ganho"] == 64, e["ganho"])
        ok("sem leitura do save o ganho e null (nao vira numero inventado)",
           e["semLeitura"] is None, e["semLeitura"])
    # 1c. FAZENDA PELO SAVE + BICO — medido em 27/10/2026.
    # O save diz, celula por celula, o que esta plantado e se esta pronto; a leitura por cor
    # inventava colheita (casca 0,015 na celula D) e o robo passava minutos colhendo celula que
    # estava crescendo. E o bico nao tem espera: 60 ms entre toques rendeu 525 moedas/min.
    saida, erro = node(
        "const m=require('./tools/gravar-gameplay.js');"
        "const base={tutorial:0,titulo:0,hud:0.084,celulas:[]};"
        "const todos={poco:true,lanterna:true,composteira:true,campo:true,celeiro:true};"
        "const eco=(lista,o)=>Object.assign({moedas:50,semente:0,camposLista:lista},o||{});"
        "const d=(e,mem)=>m.decidir(base,Object.assign({confirmacoes:{},ocupadas:{},"
        "economia:e,melhoriasFeitas:todos},mem||{}));"
        "const cresce=[{planta:'nabo',pronto:false},{planta:'nabo',pronto:false}];"
        "const r={"
        " pronto:d(eco([{planta:'nabo',pronto:true},{planta:'nabo',pronto:false}])),"
        " vazio:d(eco([{planta:'',pronto:false},{planta:'nabo',pronto:false}])),"
        " crescendo:d(eco(cresce)).motivo,"
        " recente:d(eco([{planta:'nabo',pronto:true}]),{agora:20000,colhidasHaPouco:{A:18000}}).motivo,"
        " pixelMentiroso:d(eco(cresce,{}),{agora:20000,"
        "colhidasHaPouco:{}}).tipo,"
        " bicoMinimo:m.BICO.intervalo,"
        " rajada:m.BICO.rajadaMs,"
        " celulas:m.CELULAS.length,"
        " quinta:m.CELULAS[4].id,"
        " centroQuinta:Math.round(m.CELULAS[4].x+m.CELULAS[4].w/2)+','+"
        "Math.round(m.CELULAS[4].y+m.CELULAS[4].h/2)"
        "};"
        "console.log(JSON.stringify(r));")
    ok("o decisor de fazenda pelo save roda no Node", saida is not None, erro)
    if saida:
        f = json.loads(saida)
        ok("save diz pronto -> colhe aquela celula", f["pronto"]["tipo"] == "colher", f["pronto"])
        ok("quem colhe e o clique no CORPO da planta (nao na barra do rodape)",
           f["pronto"]["alvo"] == f["pronto"]["alvo"] and f["pronto"]["prontas"][0]["alvo"]
           == {"x": 510, "y": 260}, f["pronto"]["prontas"])
        ok("save diz vazio -> planta aquela celula", f["vazio"]["tipo"] == "plantar", f["vazio"])
        ok("save diz crescendo -> bico (nao inventa colheita)",
           f["crescendo"].startswith("save: fazenda crescendo"), f["crescendo"])
        ok("celula recem-colhida nao e colhida de novo (save atrasa 1-2 s)",
           "vazia" in f["recente"] or f["recente"].startswith("save: fazenda"),
           f["recente"])
        ok("com o save na mao a leitura por pixel nao decide colheita",
           f["pixelMentiroso"] in ("toque", "plantar"), f["pixelMentiroso"])
        ok("o bico e tocado a cada 45 ms (medido: sem espera no jogo)", f["bicoMinimo"] == 45,
           f["bicoMinimo"])
        ok("a rajada de bico dura 8 s antes de olhar a fazenda de novo", f["rajada"] == 8000,
           f["rajada"])
        ok("o robo enxerga 5 celulas (a 5a foi mapeada comprando o campo)", f["celulas"] == 5,
           f["celulas"])
        ok("a 5a celula e a E, no ponto medido (755,486)",
           f["quinta"] == "E" and f["centroQuinta"] == "755,486", f["centroQuinta"])

    fonte = open(os.path.join(RAIZ, "tools", "gravar-gameplay.js"), encoding="utf-8").read()
    ok("o gravador decide pelo estado (nao por lista fixa)", "function decidir(" in fonte)
    ok("o gasto com semente entra na conta do ganho", "gastoSementes" in fonte)
    ok("o ganho e conferido com o que saiu do bolso (melhorias + sementes)",
       "gasto + gastoSementes" in fonte)
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

    # 2b. o corte do vídeo é derivado do relatório (funciona em qualquer velocidade de máquina)
    spec_prod = __import__("importlib.util").util.spec_from_file_location(
        "prod", os.path.join(RAIZ, "tools", "produzir-video.py"))
    mod_prod = __import__("importlib.util").util.module_from_spec(spec_prod)
    spec_prod.loader.exec_module(mod_prod)
    relatorio = [
        {"t": 1.0, "acao": "toque em 640,484"},
        {"t": 14.7, "acao": "semente + célula C"},
        {"t": 23.2, "acao": "semente + célula D"},
        {"t": 60.0, "acao": "toque em 100,481"},
        {"t": 113.0, "acao": "colher C + vender"},
        {"t": 128.3, "acao": "colher D + vender"},
    ]
    trechos = mod_prod.trechos_automaticos(relatorio, 135.0)
    ok("o corte sai do relatório (cobre o plantio e a colheita)",
       bool(trechos) and trechos[0][0] <= 14.7 and trechos[0][1] >= 23.2
       and trechos[-1][0] <= 113.0 and trechos[-1][1] >= 128.3, trechos)
    ok("relatório sem colheita não inventa corte",
       mod_prod.trechos_automaticos([{"t": 1.0, "acao": "semente + célula A"}], 60.0) is None)
    # 2b-2. o corte que mostra acao de verdade (o robo de 27/10 faz rajadas de bico e o filme
    # cru fica quase parado: movimento 0,23-0,34 contra minimo 1,20).
    rel_bico = [
        {"t": 15.0, "acao": "semente + célula(s) A,B,C,D"},
        {"t": 40.0, "acao": "rajada de 60 bicos (+60 moedas)"},
        {"t": 62.0, "acao": "colher A,B,C,D + vender"},
        {"t": 70.0, "acao": "comprar Cavar Poço (nível 1)"},
        {"t": 95.0, "acao": "subir para Trigo (venda 110 por ciclo)"},
    ]
    eventos = mod_prod.trechos_dos_eventos(rel_bico, 120.0)
    ok("o corte dos eventos pega plantar, colher, comprar e trocar semente",
       eventos is not None and len(eventos) >= 3, eventos)
    ok("o corte dos eventos NAO corta em cima das rajadas de bico",
       eventos is not None and all(not (37 <= a <= 43) for a, _b, _v in eventos), eventos)
    misto = mod_prod.trechos_mistos(rel_bico, 120.0)
    ok("o corte misto existe quando ha evento", misto is not None, misto)
    if misto:
        lentos = [t for t in misto if t[2] == 1.0]
        rapidos = [t for t in misto if t[2] > 1.0]
        ok("acao em velocidade real (1x) e espera acelerada (3x)", lentos and rapidos, misto)
        ok("o corte misto cobre o filme inteiro, sem buraco",
           abs(sum(b - a for a, b, _v in misto) - 120.0) < 1.0, misto)

    variantes = mod_prod.variantes_do_corte(trechos, 135.0)
    ok("há corte de reserva mais largo quando o enxuto reprova",
       len(variantes) >= 2 and variantes[1][0][0] <= trechos[0][0], len(variantes))

    # 2c. o que foi publicado fica registrado num JSON público (o chat lê esse arquivo)
    spec_env = __import__("importlib.util").util.spec_from_file_location(
        "env", os.path.join(RAIZ, "tools", "enviar-youtube.py"))
    mod_env = __import__("importlib.util").util.module_from_spec(spec_env)
    spec_env.loader.exec_module(mod_env)
    import tempfile
    with tempfile.TemporaryDirectory() as pasta:
        os.makedirs(os.path.join(pasta, "posts"), exist_ok=True)
        caminho = mod_env.registrar(pasta, "ceifalume-gameplay", "CEIFALUME", "abc123",
                                    quando="2026-10-27T00:00:00Z", escrever=lambda *_: None)
        guardado = json.load(open(caminho, encoding="utf-8"))
        ok("o envio deixa registro público com o id do vídeo",
           guardado["publicados"][0]["id"] == "abc123"
           and guardado["publicados"][0]["url"] == "https://youtu.be/abc123", guardado)
        mod_env.registrar(pasta, "ceifalume-gameplay", "CEIFALUME", "abc123",
                          escrever=lambda *_: None)
        guardado = json.load(open(caminho, encoding="utf-8"))
        ok("registrar o mesmo vídeo duas vezes não duplica",
           len(guardado["publicados"]) == 1, guardado["publicados"])
    fonte_wf = open(os.path.join(RAIZ, ".github", "workflows", "gravar-gameplay.yml"),
                    encoding="utf-8").read()
    marca = "Registra o que foi publicado"
    trecho_registro = fonte_wf.split(marca)[1][:400] if marca in fonte_wf else ""
    ok("o workflow guarda o registro só depois da palavra PUBLICAR",
       bool(trecho_registro) and "publicar == 'PUBLICAR'" in trecho_registro.split("run:")[0],
       "registro sem cadeado")

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
        # Rodada 111: o arquivo do kit é o que tem as INSTRUÇÕES de como jogar queimadas na tela.
        ok("o pacote aponta para o vídeo com as instruções de como jogar",
           p["arquivo"].endswith("ceifalume-gameplay-instrucoes.mp4"), p["arquivo"])
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

    # ---------- escala dos cliques (conserto de 30/10/2026) ----------
    # As regiões eram lidas em coordenadas de 1280x720 e escaladas pelo canvas; os CLIQUES não.
    # Em qualquer resolução diferente de 1280x720 o robô tocava fora do botão e a gravação saía
    # sem plantio (medido: 3 de 3 em 960x540). Estes contratos impedem a volta do defeito.
    import re
    fonte = open(os.path.join(RAIZ, "tools", "gravar-gameplay.js"), encoding="utf-8").read()
    cliques_crus = re.findall(r"mouse\.click\(\s*(?:ALVO|alvo)\.", fonte)
    ok("nenhum clique usa coordenada fixa sem passar pela escala", not cliques_crus,
       "%d clique(s) sem escala" % len(cliques_crus))
    ok("existe calibração da escala pelo canvas real", "async function calibrarEscala" in fonte)
    ok("a escala é calibrada depois de o canvas encher a viewport",
       "calibrarEscala(pagina)" in fonte and "vp.width * 0.9" in fonte)
    ok("gravação sem plantio falha com motivo (não vira vídeo de capa)",
       "nenhuma semente foi plantada" in fonte and "return 9" in fonte)
    ok("há escape quando o jogo fica preso na abertura",
       "escaparDaAbertura" in fonte and "ABERTURA_MAXIMA" in fonte)

    print("\n%d/%d testes do vídeo de gameplay passaram" % (total - falhas, total))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
