#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrente: dispara o pulso da casa no horário, sem depender do cron do GitHub.

POR QUE EXISTE (07/11/2026, medido): o pulso `marketing-24h` tem cron `*/20 0,6,7,12-23`,
que pede 45 disparos por dia. O GitHub entregou **1,86 por dia** na semana medida (4,1%), e
`medir-o-dia` entregou ZERO. Cron de repositório é melhor esforço: o agendador não promete nada.

Então a casa faz a corrente: um run acorda, espera até o próximo horário de pulso, dispara o
pulso, dispara a si mesmo e dorme de novo. A agenda deixa de ser promessa do GitHub e passa a
ser conta da casa.

Limites, para não virar laço solto:
  - `posts/PARAR` existe -> não dispara nada (a casa inteira respeita esse arquivo);
  - espera máxima de 5h20 (job do GitHub morre em 6h);
  - fora da janela, dorme até 20 minutos antes da abertura (09h de Brasília);
  - cada disparo é registrado no log com hora e motivo; falha de disparo encerra a corrente e
    o cron (que continua lá) reinicia depois.

Uso:
    python3 tools/corrente.py --ensaiar     # mostra os próximos 6 disparos, sem dormir nem chamar API
    python3 tools/corrente.py               # espera, dispara o pulso e a si mesmo
"""
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALENDARIO = os.path.join(RAIZ, "posts", "calendario.json")
PARAR = os.path.join(RAIZ, "posts", "PARAR")
REPO = "reboclbrank-max/site"

FUSO = datetime.timezone(datetime.timedelta(hours=-3))
PASSO_MINUTOS = 20             # o pulso é de 20 em 20 minutos
ESPERA_MAXIMA = datetime.timedelta(hours=5, minutes=20)
MARGEM_DE_ABERTURA = datetime.timedelta(minutes=20)


def janela(caminho_calendario=CALENDARIO):
    """(abre, fecha) em horas locais. Do calendário; sem calendário, 9-22 (o padrão da casa)."""
    try:
        with open(caminho_calendario, encoding="utf-8") as f:
            dados = json.load(f)
        inicio, fim = dados["janela"]["inicio"], dados["janela"]["fim"]
        return int(inicio), int(fim)
    except (OSError, ValueError, KeyError, TypeError):
        return 9, 22


def horas_de_pulso(abre=9, fecha=22, pesquisa=3, aprendizado=4):
    """As horas locais em que o pulso tem o que fazer.

    A janela de publicação, mais as duas janelas de estudo que a casa já declarou (03h pesquisa,
    04h aprendizado). Fora disso o pulso só dormiria — acordá-lo é queimar run para nada.
    """
    return set(range(abre, fecha)) | {pesquisa, aprendizado}


def proximo_disparo(agora, horas=None, passo=PASSO_MINUTOS):
    """O próximo instante de pulso, em UTC — sempre no futuro, alinhado ao passo.

    A primeira versão tentava uma "margem de 20 min antes da abertura"; o ensaio mostrou seis
    vezes o mesmo horário, porque fora da janela ela devolvia o passado. A conta certa é mais
    simples: anda de 20 em 20 minutos a partir de agora e para na primeira hora permitida.
    """
    horas = horas if horas is not None else horas_de_pulso(*janela())
    local = agora.astimezone(FUSO).replace(second=0, microsecond=0)
    resto = local.minute % passo
    alvo = local + datetime.timedelta(minutes=(passo - resto) if resto else passo)
    for _ in range(int(24 * 60 / passo) + 2):
        if alvo.hour in horas:
            return alvo.astimezone(datetime.timezone.utc)
        alvo += datetime.timedelta(minutes=passo)
    raise RuntimeError("nenhum horário de pulso nas próximas 24 h")


def motivo(alvo, abre=9, fecha=22):
    """Por que acordar NAQUELE horário — o log tem de dizer, não só mostrar a hora."""
    local = alvo.astimezone(FUSO)
    if local.hour in (3, 4):
        return "janela de estudo (%dh): pesquisa e aprendizado do dia" % local.hour
    if abre <= local.hour < fecha:
        return "janela aberta: pulso de %d em %d minutos" % (PASSO_MINUTOS, PASSO_MINUTOS)
    return "fora da janela — o pulso vai dormir (não deveria acontecer: a conta mira só a janela)"


def parado(caminho=PARAR):
    return os.path.exists(caminho)


def disparar(workflow, token, repo=REPO, ref="main"):
    """POST de workflow_dispatch. Erro levantado com o motivo — falha não vira 'disparei'."""
    url = ("https://api.github.com/repos/%s/actions/workflows/%s.yml/dispatches"
           % (repo, workflow))
    corpo = json.dumps({"ref": ref}).encode()
    req = urllib.request.Request(url, data=corpo, method="POST",
                                 headers={"Authorization": "Bearer " + token,
                                          "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status not in (201, 204):
            raise RuntimeError("dispatch de %s devolveu HTTP %s" % (workflow, r.status))
    return True


def esperar(segundos, dormir=time.sleep):
    segundos = max(0, min(int(segundos), int(ESPERA_MAXIMA.total_seconds())))
    dormir(segundos)
    return segundos


def ciclo(agora_fn=None, disparar_fn=None, dormir=time.sleep, token=None, parado_fn=None):
    """Um passo da corrente: espera, dispara o pulso, dispara a si mesmo. Devolve o que fez."""
    agora_fn = agora_fn or (lambda: datetime.datetime.now(datetime.timezone.utc))
    disparar_fn = disparar_fn or (lambda wf: disparar(wf, token))
    parado_fn = parado_fn or parado
    if parado_fn():
        return {"acao": "parar", "motivo": "posts/PARAR existe — a casa não faz nada até alguém apagar"}
    abre, fecha = janela()
    agora = agora_fn()
    alvo = proximo_disparo(agora, horas_de_pulso(abre, fecha))
    segundos = (alvo - agora).total_seconds()
    esperados = esperar(segundos, dormir=dormir)
    if parado_fn():
        return {"acao": "parar", "motivo": "posts/PARAR apareceu durante a espera",
                "esperou_s": esperados}
    disparar_fn("marketing-24h")
    disparar_fn("corrente")
    return {"acao": "disparou", "em": alvo.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "esperou_s": esperados, "motivo": motivo(alvo, abre, fecha)}


def main(argv):
    abre, fecha = janela()
    if "--ensaiar" in argv:
        agora = datetime.datetime.now(datetime.timezone.utc)
        print("janela: %dh–%dh (Brasília) · passo de %d min" % (abre, fecha, PASSO_MINUTOS))
        for i in range(6):
            alvo = proximo_disparo(agora, horas_de_pulso(abre, fecha))
            print("  %2d. acorda em %s (%s) — %s" % (
                i + 1, alvo.strftime("%d/%m %H:%MZ"),
                alvo.astimezone(FUSO).strftime("%H:%M BRT"), motivo(alvo, abre, fecha)))
            agora = alvo + datetime.timedelta(seconds=1)
        return 0
    token = os.environ.get("GHPAT") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("sem GHPAT/GITHUB_TOKEN no ambiente — não disparo às cegas")
        return 3
    try:
        feito = ciclo(token=token)
    except Exception as erro:  # noqa: BLE001 — falha de disparo não pode virar "disparei"
        print("corrente interrompida: %s — o cron do workflow reinicia depois" % str(erro)[:160])
        return 3
    print("corrente: %s · %s" % (feito["acao"], feito.get("motivo") or feito.get("em")))
    return 0 if feito["acao"] in ("parou", "disparou", "parar") else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
