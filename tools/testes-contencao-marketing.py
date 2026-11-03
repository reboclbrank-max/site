#!/usr/bin/env python3
"""Barreira estática e offline: os publicadores antigos não têm agenda nem dispatch implícito."""
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[1]
ALVOS = ("marketing-24h.yml", "marketing-continuo.yml", "postagem-diaria.yml")
resultados = []


def checar(nome, condicao):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome)


for nome in ALVOS:
    texto = (RAIZ / ".github" / "workflows" / nome).read_text(encoding="utf-8")
    gatilhos = texto.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
    checar(nome + ": sem schedule/cron", not re.search(r"^\s+(schedule:|.*cron:)", gatilhos, re.M))
    bloco = re.search(r"^      confirmacao:\n((?:^        .*\n?)*)", gatilhos, re.M)
    confirmacao = bloco.group(1) if bloco else ""
    checar(nome + ": confirmação obrigatória sem default",
           "required: true" in confirmacao and "type: string" in confirmacao
           and "default:" not in confirmacao)
    checar(nome + ": job exige dono e PUBLICAR",
           "github.actor == 'reboclbrank-max' && inputs.confirmacao == 'PUBLICAR'" in texto)

checar("todos os publicadores contidos têm timeout", all(
    "timeout-minutes:" in (RAIZ / ".github" / "workflows" / nome).read_text(encoding="utf-8")
    for nome in ALVOS))

postagem = (RAIZ / ".github" / "workflows" / "postagem-diaria.yml").read_text(encoding="utf-8")
checar("postagem-diaria: retaguarda agendada removida", "\n  acorda:\n" not in postagem)
checar("postagem-diaria: concorrência não depende de evento schedule", "github.event.schedule" not in postagem)

falhas = [nome for nome, ok in resultados if not ok]
print(f"\n{len(resultados) - len(falhas)}/{len(resultados)} contratos PASS")
if falhas:
    raise SystemExit("Falhas: " + "; ".join(falhas))
