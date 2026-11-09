#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contenção do marketing, versão 2 — cadência ligada, freios no lugar.

HISTÓRICO, porque isto importa. Na versão 1 (antes de 06/11/2026) este contrato exigia o
oposto: "nenhum publicador tem cron". Ele existia porque a casa publicava por relógio e
repetia — e a trava era desligar o relógio.

Em 06/11/2026 o dono autorizou a cadência ("pode iniciar"). Desligar o relógio deixou de ser
a proteção: a proteção passou a ser o portão (a casa pode dizer NÃO) e o orquestrador (janela,
teto, botão de parar). Então este contrato mudou de pergunta:

    antes: "existe cron?"            depois: "o cron consegue publicar sozinho?"

O que se cobra agora, tudo estático e offline:

  1. SÓ UM PUBLICADOR TEM AGENDA — o `marketing-24h`, que chama o ORQUESTRADOR. O postador
     legado e o bloco contínuo continuam manuais, com confirmação do dono.
  2. O AGENDADO NÃO PUBLICA DIRETO — quem decide é o orquestrador (janela 9-22h, teto
     diário, intervalo mínimo) e quem autoriza é o portão.
  3. O PORTÃO É A ÚLTIMA PALAVRA — se recusa, o ciclo termina sem publicar e registra.
  4. O BOTÃO DE PARAR VALE PARA O CRON — `posts/PARAR` encerra o pulso.
  5. itch NUNCA ENTRA NA AGENDA — a casa só mede (Cloudflare barra IP de datacenter).
  6. TODO PULSO TEM TETO DE TEMPO — runner pendurado não é autonomia, é vazamento.
"""
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
WF = RAIZ / ".github" / "workflows"
resultados = []


def checar(nome, condicao, detalhe=""):
    ok = bool(condicao)
    resultados.append((nome, ok))
    print(("PASS" if ok else "FAIL") + " — " + nome + (("  [" + str(detalhe)[:100] + "]") if detalhe and not ok else ""))


def ler(nome):
    caminho = WF / nome
    return caminho.read_text(encoding="utf-8") if caminho.exists() else ""


def gatilhos(texto):
    if "on:\n" not in texto:
        return ""
    return texto.split("on:\n", 1)[1].split("\npermissions:", 1)[0]


def tem_agenda(texto):
    g = gatilhos(texto)
    return "schedule:" in g and "cron:" in g


# ------------------------------------------------------------------ 1. um publicador só
agendados = [nome for nome in ("marketing-24h.yml", "marketing-continuo.yml", "postagem-diaria.yml")
             if tem_agenda(ler(nome))]
checar("só o orquestrador tem agenda (nada de dois relógios publicando)", agendados == ["marketing-24h.yml"],
      agendados)

for nome in ("postagem-diaria.yml", "marketing-continuo.yml"):
    texto = ler(nome)
    g = gatilhos(texto)
    bloco = re.search(r"^      confirmacao:\n((?:^        .*\n?)*)", g, re.M)
    confirmacao = bloco.group(1) if bloco else ""
    checar(nome + ": continua manual, com confirmação sem default",
           "schedule:" not in g and "required: true" in confirmacao and "default:" not in confirmacao)
    checar(nome + ": exige o dono e a palavra PUBLICAR",
           "github.actor == 'reboclbrank-max' && inputs.confirmacao == 'PUBLICAR'" in texto)

# ------------------------------------------------------------------ 2. o agendado decide pelo orquestrador
wf24 = ler("marketing-24h.yml")
checar("a agenda roda o orquestrador, não um publicador direto", "python3 tools/orquestrador.py" in wf24)
checar("a agenda só vale no main", "github.ref == 'refs/heads/main'" in wf24)
checar("o pulso manual continua exigindo o dono e a palavra",
      "github.actor == 'reboclbrank-max' && inputs.confirmacao == 'PUBLICAR'" in wf24)
checar("a agenda não roda dois pulsos ao mesmo tempo", "concurrency:" in wf24 and "cancel-in-progress" in wf24)

orq = (RAIZ / "tools" / "orquestrador.py").read_text(encoding="utf-8")
checar("o orquestrador checa a janela antes de publicar", "def pode_publicar" in orq and "janela" in orq)
checar("o orquestrador tem intervalo mínimo entre publicações", "INTERVALO_PUBLICACAO" in orq)
checar("o orquestrador respeita o teto diário", "teto" in orq.lower())
checar("o orquestrador registra cada pulso (pulso atrasado não duplica post)",
      "historico" in orq and "gravar_estado" in orq)

# ------------------------------------------------------------------ 3. o portão é a última palavra
postador = (RAIZ / "tools" / "postador.py").read_text(encoding="utf-8")
checar("o postador pede o texto ao redator", "escolha = ciclo_do_redator()" in postador)
checar("se o portão recusa, o ciclo não publica", "publicacao=RECUSADA" in postador
      and "registra_recusa_do_ciclo(escolha)" in postador)
checar("os canais com credencial passam pelo portão por canal",
      'portao_libera("instagram", mensagem)' in postador and 'portao_libera("threads", mensagem)' in postador)
checar("a fila fixa antiga está desligada por padrão",
      'os.environ.get("RESERVA_DE_FILA") == "1"' in postador)

# ------------------------------------------------------------------ 4. botão de parar
checar("o orquestrador obedece posts/PARAR (inclusive no pulso agendado)",
      "def pediu_para_parar" in orq and "posts/PARAR" in orq)
checar("o bloco contínuo também obedece posts/PARAR",
      "PARAR" in (RAIZ / "tools" / "loop-24h.py").read_text(encoding="utf-8"))

# ------------------------------------------------------------------ 5. itch fora da agenda
checar("itch não é publicado por nenhum agendado: só medição",
      "enviar-itch.py" not in wf24 and "administrar-itch.py" not in wf24
      and "publicar-devlog-itch.js" not in wf24)
calendario = json.loads((RAIZ / "posts" / "calendario.json").read_text(encoding="utf-8"))
checar("a janela de publicação está declarada no calendário",
      isinstance(calendario.get("janela"), dict) and calendario["janela"].get("fim", 0) > calendario["janela"].get("inicio", 0))
checar("o teto diário está declarado e é finito",
      isinstance(calendario.get("teto_diario"), int) and 0 < calendario["teto_diario"] <= 10,
      calendario.get("teto_diario"))

# ------------------------------------------------------------------ 6. todo pulso tem teto de tempo
checar("todo publicador tem timeout", all(
    "timeout-minutes:" in ler(nome)
    for nome in ("marketing-24h.yml", "marketing-continuo.yml", "postagem-diaria.yml")))

falhas = [nome for nome, ok in resultados if not ok]
print("\n%d/%d contratos de contenção do marketing passaram" % (len(resultados) - len(falhas), len(resultados)))
if falhas:
    raise SystemExit("Falhas: " + "; ".join(falhas))
