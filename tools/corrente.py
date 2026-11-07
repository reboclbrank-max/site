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
PULSO_EVENTO = "pulso"         # `repository_dispatch` que acorda o `marketing-24h`
# AS DIÁRIAS QUE A CORRENTE GARANTE (07/11/2026). O cron também falha nas diárias: medido na
# semana, 86% de entrega — e `medir-o-dia`, a régua da casa, recebeu ZERO. A corrente passa a
# conferir, na hora de preferência de cada uma, se ela já rodou hoje; se não rodou, dispara.
#
# SÓ O QUE MEDE, NUNCA O QUE ESCREVE: `administrar-itch` e `administrar-youtube` exigem a
# palavra de confirmação no gatilho manual — e a corrente não digita palavra de ninguém. Elas
# ficam de fora de propósito, e há contrato para isso.
# A GRAÇA DE UMA PASSADA (07/11/2026): a corrente não atropela o cron. Se a diária é das 9h, a
# conferência só cobra a partir das 9h20 — dá uma passada inteira para o cron fazer o trabalho
# dele. Sem isso, a corrente dispararia junto com o cron e a casa rodaria a mesma diária duas vezes.
GRACA_MINUTOS = 20
DIARIAS_GARANTIDAS = (("medir-o-dia", 9), ("ler-comentarios", 9), ("pendencias-do-dono", 9),
                      ("vigia-sessao-itch", 9), ("medir-itch", 10))
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


def _post(url, corpo, token):
    """POST na API do GitHub. Devolve o status; erro de HTTP é levantado com o motivo."""
    dados = json.dumps(corpo).encode()
    req = urllib.request.Request(url, data=dados, method="POST",
                                 headers={"Authorization": "Bearer " + token,
                                          "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def disparar(workflow, token, repo=REPO, ref="main"):
    """Dispara um workflow pelo `workflow_dispatch` (usado para a própria corrente).

    Só serve para workflow cujo `workflow_dispatch` não exija entrada obrigatória: o pulso
    `marketing-24h` exige a palavra PUBLICAR, e mandar essa palavra daqui seria a automação
    digitando autorização de gente. Para o pulso existe `disparar_pulso`.
    """
    url = "https://api.github.com/repos/%s/actions/workflows/%s.yml/dispatches" % (repo, workflow)
    status = _post(url, {"ref": ref}, token)
    if status not in (201, 204):
        raise RuntimeError("dispatch de %s devolveu HTTP %s" % (workflow, status))
    return True


def disparar_pulso(token, repo=REPO, evento=PULSO_EVENTO):
    """Acorda o pulso por `repository_dispatch` — o caminho que não pede palavra de ninguém.

    O pulso roda as mesmas barreiras e o mesmo portão do pulso agendado: a corrente não decide
    nada, só toca o relógio no horário que o cron prometia e não cumpria.
    """
    url = "https://api.github.com/repos/%s/dispatches" % repo
    status = _post(url, {"event_type": evento}, token)
    if status not in (201, 204):
        raise RuntimeError("pulso devolveu HTTP %s" % status)
    return True


def ler_runs(workflow, token, repo=REPO, por_pagina=10):
    """Runs recentes de um workflow (só o suficiente para saber se rodou hoje)."""
    url = ("https://api.github.com/repos/%s/actions/workflows/%s.yml/runs?per_page=%d"
           % (repo, workflow, por_pagina))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token,
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get("workflow_runs") or []


def _dia_local(instante):
    return instante.astimezone(FUSO).date()


def rodaram_hoje(agora, ler_runs_fn=None, token=None, diarias=DIARIAS_GARANTIDAS):
    """{nome: True/False} — rodou hoje? E {nome: motivo} para o que não deu para ler.

    "Não consegui ler" não é "não rodou": disparar no escuro duplicaria run, e dizer que rodou
    seria inventar. O que não foi lido fica de fora deste ciclo, com o motivo anotado.
    """
    ler_runs_fn = ler_runs_fn or (lambda wf: ler_runs(wf, token))
    hoje, rodaram, sem_leitura = _dia_local(agora), {}, {}
    for nome, _hora in diarias:
        try:
            runs = ler_runs_fn(nome)
        except Exception as erro:  # noqa: BLE001 — rede ruim não vira "não rodou"
            sem_leitura[nome] = str(erro)[:90]
            continue
        rodaram[nome] = any(
            _dia_local(datetime.datetime.fromisoformat(str(r.get("created_at") or "")
                                                       .replace("Z", "+00:00"))) == hoje
            for r in runs if r.get("created_at"))
    return rodaram, sem_leitura


def diarias_faltando(agora, rodaram, horas=None, diarias=DIARIAS_GARANTIDAS):
    """Quais diárias já passaram da hora de preferência e ainda não rodaram hoje."""
    horas = set(horas_de_pulso() if horas is None else horas)
    local = agora.astimezone(FUSO)
    if local.hour not in horas:
        return []
    # SÓ DISPARA O QUE FOI LIDO E NÃO RODOU (`is False`). Chave ausente quer dizer "não deu para
    # ler", e disparar no escuro duplicaria run; dizer que rodou seria inventar.
    minutos_agora = local.hour * 60 + local.minute
    return [nome for nome, hora in diarias
            if minutos_agora >= hora * 60 + GRACA_MINUTOS and rodaram.get(nome) is False]


def garantir(agora, token=None, disparar_fn=None, ler_runs_fn=None, horas=None,
             diarias=DIARIAS_GARANTIDAS):
    """Dispara as diárias que faltam. Devolve {'dispares': [...], 'sem_leitura': {...}}."""
    disparar_fn = disparar_fn or (lambda wf: disparar(wf, token))
    rodaram, sem_leitura = rodaram_hoje(agora, ler_runs_fn=ler_runs_fn, token=token,
                                        diarias=diarias)
    faltando = diarias_faltando(agora, rodaram, horas=horas, diarias=diarias)
    for nome in faltando:
        disparar_fn(nome)
    return {"dispares": faltando, "sem_leitura": sem_leitura}


def esperar(segundos, dormir=time.sleep):
    segundos = max(0, min(int(segundos), int(ESPERA_MAXIMA.total_seconds())))
    dormir(segundos)
    return segundos


def ciclo(agora_fn=None, pulso_fn=None, si_fn=None, dormir=time.sleep, token=None,
          parado_fn=None, garantir_fn=None):
    """Um passo da corrente: espera, acorda o pulso, marca a si mesma. Devolve o que fez."""
    agora_fn = agora_fn or (lambda: datetime.datetime.now(datetime.timezone.utc))
    # DOIS CAMINHOS DIFERENTES, DE PROPÓSITO: o pulso vai por `repository_dispatch` (não pede
    # palavra de ninguém); a corrente se reagenda por `workflow_dispatch`, que é o único jeito
    # de um workflow disparar a si mesmo.
    pulso_fn = pulso_fn or (lambda: disparar_pulso(token))
    si_fn = si_fn or (lambda: disparar("corrente", token))
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
    pulso_fn()
    # AS DIÁRIAS QUE O CRON DEIXOU PASSAR (07/11/2026): na hora de cada uma, se ela não rodou
    # hoje, a corrente dispara. Só as que medem — ver DIARIAS_GARANTIDAS.
    diarias = {"dispares": [], "sem_leitura": {}}
    if garantir_fn is not None:
        try:
            diarias = garantir_fn(alvo) or diarias
        except Exception as erro:  # noqa: BLE001 — diária perdida não derruba a corrente
            diarias = {"dispares": [], "sem_leitura": {"_": str(erro)[:90]}}
    si_fn()
    return {"acao": "disparou", "em": alvo.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "esperou_s": esperados, "motivo": motivo(alvo, abre, fecha),
            "diarias": diarias["dispares"], "sem_leitura": diarias["sem_leitura"]}


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
        feito = ciclo(token=token,
                      garantir_fn=lambda instante: garantir(instante, token=token))
    except Exception as erro:  # noqa: BLE001 — falha de disparo não pode virar "disparei"
        print("corrente interrompida: %s — o cron do workflow reinicia depois" % str(erro)[:160])
        return 3
    print("corrente: %s · %s" % (feito["acao"], feito.get("motivo") or feito.get("em")))
    if feito.get("diarias"):
        print("diárias que o cron deixou passar, disparadas agora: " + ", ".join(feito["diarias"]))
    # nome de variável NÃO pode ser `motivo`: dentro de `main` isso sombreia a função `motivo()`
    # usada no ensaio logo acima (mesmo defeito do `_t` que já mordeu noutra suíte).
    for nome, por_que in (feito.get("sem_leitura") or {}).items():
        print("diária não conferida (%s): %s — não disparei às cegas" % (nome, por_que))
    return 0 if feito["acao"] in ("parou", "disparou", "parar") else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
