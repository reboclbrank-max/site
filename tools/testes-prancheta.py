#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do roteiro do PRANCHETA (sem rede e sem navegador)."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
total = 0
falhas = []


def ok(nome, cond, detalhe=""):
    global total
    total += 1
    if cond:
        print("OK  " + nome)
    else:
        falhas.append(nome)
        print("FALHOU  " + nome + ("  <" + str(detalhe) + ">" if detalhe else ""))


fonte = open(os.path.join(RAIZ, "tools", "gravar-prancheta.js"), encoding="utf-8").read()

ok("o roteiro jogado é o do PRANCHETA (jogo certo)", "prancheta" in fonte.lower()
   and "rebocl-brank.itch.io/prancheta" in fonte)
ok("o build é descoberto na página do itch (o id muda a cada versão)",
   "html-classic.itch.zone" in fonte and "descobrirBuild" in fonte)
ok("há endereço de reserva se a descoberta falhar", "BUILD_RESERVA" in fonte)
ok("confere cada passo POR IMAGEM (mudança de tela), não por tempo",
   "diferenca(" in fonte and "mudanca" in fonte)
ok("falha quando menos de 4 passos essenciais mudam a tela",
   "essenciais < 4" in fonte and "return 8" in fonte)
ok("grava relatório de decisões ao lado do vídeo", "-decisoes.json" in fonte)
ok("a partida tem roteiro próprio (instrução, seguir, velocidade, pular)",
   all(x in fonte for x in ("instrucao:", "seguir:", "velocidadeRapida:", "pularParaFim:")))

# A descoberta do build é testada com Node (o módulo não roda o fluxo quando importado).
import subprocess
teste = (
    "const m=require('./tools/gravar-prancheta.js');"
    "const html='<iframe src=\"https://html-classic.itch.zone/html/999/index.html?v=1&amp;x=2\">';"
    "const achado=m.descobrirBuild('http://x', () => html);"
    "const reserva=m.descobrirBuild('http://x', () => { throw new Error('sem rede'); });"
    "console.log(JSON.stringify({achado,reserva}));"
)
r = subprocess.run(["node", "-e", teste], cwd=RAIZ, capture_output=True, text=True)
valido = r.returncode == 0 and r.stdout.strip()
dados = {}
if valido:
    import json as _json
    dados = _json.loads(r.stdout.strip())
ok("descobrirBuild acha o iframe do itch",
   dados.get("achado") == "https://html-classic.itch.zone/html/999/index.html?v=1&x=2",
   dados.get("achado") or (r.stderr or "")[:120])
ok("sem rede cai no endereço de reserva em vez de quebrar",
   str(dados.get("reserva", "")).startswith("https://html-classic.itch.zone/html/"),
   dados.get("reserva"))

for nome, trecho in (
    ("legenda para o menu do PRANCHETA", "abrindo o jogo"),
    ("legenda para a prancheta tática", "abrindo a prancheta tática"),
    ("legenda para a partida", "começando a partida"),
):
    prod = open(os.path.join(RAIZ, "tools", "produzir-video.py"), encoding="utf-8").read()
    ok(nome, trecho in prod)

wf = open(os.path.join(RAIZ, ".github", "workflows", "gravar-prancheta.yml"),
          encoding="utf-8").read()
ok("existe workflow próprio do PRANCHETA", "gravar-prancheta" in wf)
ok("o workflow roda o roteiro medido", "tools/gravar-prancheta.js" in wf)
ok("o workflow mede o vídeo antes de guardar",
   "validar-video.py" in wf and wf.index("validar-video.py") < wf.index("upload-artifact"))
ok("o envio ao YouTube continua atrás da palavra PUBLICAR",
   "publicar == 'PUBLICAR'" in wf)
# ATÉ 06/11/2026 este contrato cobrava que "enviar-youtube" NÃO aparecesse no workflow — e o
# campo PUBLICAR existia sem nenhum passo de envio: promessa falsa com contrato verde em cima.
# O contrato certo é: o agendamento não publica, e o envio só roda com a palavra PUBLICAR.
ok("o envio ao YouTube existe e depende da palavra PUBLICAR",
   "enviar-youtube.py prancheta-gameplay" in wf and "publicar == 'PUBLICAR'" in wf)
envio = wf[wf.index("enviar-youtube.py prancheta-gameplay"):]
ok("o envio está atrás de uma condição de PUBLICAR (nunca no agendamento)",
   "if: ${{ github.event.inputs.publicar == 'PUBLICAR' }}" in
   wf[max(0, wf.index("enviar-youtube.py prancheta-gameplay") - 900):])
ok("o resumo do run não promete envio que não acontece",
   "STATUS_PUBLICACAO" in wf and "Envia ao YouTube (só com a palavra PUBLICAR)" in wf)

# ---- rotação da cena do PRANCHETA (06/11/2026) ---------------------------------------------
import importlib.util
_spec = importlib.util.spec_from_file_location("cena", os.path.join(RAIZ, "tools", "cena.py"))
cena = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cena)

ok("o PRANCHETA tem estratégias próprias na rotação",
   set(cena.JOGOS) == {"ceifalume", "prancheta"} and len(cena.ORDEM_PRANCHETA) >= 3,
   cena.ORDEM_PRANCHETA)
ok("cada estratégia do PRANCHETA diz o que muda na tela",
   all(e.get("porque") and e.get("instrucao") in ("pressionar", "seguir")
       for e in cena.ESTRATEGIAS_PRANCHETA.values()))
ok("a rotação do PRANCHETA não repete a última estratégia",
   all(cena.proxima({"partidas": [{"jogo": "prancheta", "estrategia": e}]}, "prancheta") != e
       for e in cena.ORDEM_PRANCHETA))
ok("a rotação do CEIFALUME não é afetada pela do PRANCHETA",
   cena.proxima({"partidas": [{"jogo": "prancheta", "estrategia": "posse_normal"}]},
                "ceifalume") == cena.ORDEM[0])

_rel = {"jogo": "prancheta", "decisoes": [{"t": 1.0, "acao": "a"}, {"t": 4.0, "acao": "b"}],
        "toques_partida": 7, "passos_confirmados": 6}
ok("o registro guarda a marca do jogo", cena.registrar(_rel, "posse_normal", {"partidas": []},
                                                      jogo="prancheta")[0] is True)
_mem = {"partidas": []}
_ok1, _m1, _a1 = cena.registrar(_rel, "posse_normal", _mem, jogo="prancheta")
_ok2, _m2, _a2 = cena.registrar(_rel, "posse_normal", _mem, jogo="prancheta")
ok("partida repetida do PRANCHETA não entra duas vezes",
   _ok1 is True and _ok2 is False and "repetida" in _m2, _m2)
ok("estratégia diferente dá assinatura diferente",
   cena.registrar(_rel, "contra_ataque", {"partidas": []}, jogo="prancheta")[2] != _a1)

ok("o workflow escolhe a cena pelo cena.py e passa ao gravador",
   "cena.py proxima --jogo prancheta" in wf and "--estrategia \"$ESTRATEGIA\"" in wf)
ok("o workflow registra a partida e falha se ela repetir",
   "cena.py registrar --jogo prancheta" in wf and "partida repetida" in wf)
ok("o workflow desenha capa do quadro do próprio vídeo",
   "desenhar-capa.py" in wf and "prancheta-cru-quadro.png" in wf)
ok("a capa usa a prancheta tática quando ela existe (e não o placar final)",
   "prancheta-prancheta.png" in wf and wf.index("prancheta-prancheta.png")
   < wf.index("prancheta-cru-quadro.png"))
ok("o workflow monta o pacote de envio do PRANCHETA",
   "prancheta-para-video.py" in wf and "prancheta-gameplay" in wf)

# ---- o PRANCHETA vira pacote de vídeo (título, descrição, capa) ------------------------------
import json
import tempfile
_spec2 = importlib.util.spec_from_file_location(
    "prancheta_para_video", os.path.join(RAIZ, "tools", "prancheta-para-video.py"))
ppv = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(ppv)

REL = {"jogo": "prancheta", "estrategia": "pressao_rapida", "passos_confirmados": 6,
       "toques_partida": 11,
       "decisoes": [{"t": 1.0, "acao": "nova carreira", "ok": True},
                    {"t": 2.5, "acao": "aceitar convite", "ok": True},
                    {"t": 4.0, "acao": "abrir a prancheta", "ok": True}]}
pac = ppv.montar_pacote(REL, "pressao_rapida", "abc123def456")
ok("o pacote do PRANCHETA tem id, arquivo e capa próprios",
   pac["id"] == "prancheta-gameplay" and pac["arquivo"].endswith(".mp4") and pac["capa"])
ok("o título diz a estratégia daquela gravação (não é molde)",
   pac["titulo"] != ppv.TITULOS["posse_normal"] and "11 toques" in pac["titulo"], pac["titulo"])
ok("a descrição carrega fonte, número e link",
   "Fonte: posts/cenas.json" in pac["descricao"] and "11 toques" in pac["descricao"]
   and "http" in pac["descricao"])
_ju = importlib.util.spec_from_file_location("juizo", os.path.join(RAIZ, "tools", "juizo.py"))
juizo = importlib.util.module_from_spec(_ju)
_ju.loader.exec_module(juizo)
_nota, _ = juizo.nota_descricao(pac["descricao"])
ok("a descrição passa a régua de descrição", _nota >= juizo.NOTA_MINIMA_DESCRICAO, _nota)
ok("número que não está no relatório não aparece no texto",
   "13 colheitas" not in pac["descricao"] and "8 horas" not in pac["descricao"])

_tmp = tempfile.mkdtemp(prefix="kit-prancheta-")
_kit = os.path.join(_tmp, "kit-gameplay.json")
with open(_kit, "w", encoding="utf-8") as _f:
    json.dump({"pacotes": [{"id": "ceifalume-gameplay", "titulo": "CEIFALUME"}]}, _f)
ppv.gravar_pacote(pac, _kit)
_dados = json.load(open(_kit, encoding="utf-8"))
ok("o pacote do PRANCHETA entra no kit sem apagar o do CEIFALUME",
   {p["id"] for p in _dados["pacotes"]} == {"ceifalume-gameplay", "prancheta-gameplay"},
   [p["id"] for p in _dados["pacotes"]])
ppv.gravar_pacote(pac, _kit)
ok("gravar o mesmo pacote duas vezes não duplica",
   len(json.load(open(_kit, encoding="utf-8"))["pacotes"]) == 2)
_sem_rel = ppv.main(["x", "--relatorio", os.path.join(_tmp, "nao-existe.json"), "--sem-kit"])
ok("sem relatório da gravação o tool falha com motivo (não inventa texto)", _sem_rel == 2)

print("\n%d/%d testes do roteiro do PRANCHETA passaram" % (total - len(falhas), total))
sys.exit(1 if falhas else 0)
