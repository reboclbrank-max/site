#!/usr/bin/env python3
"""Retaguarda conservadora da cadência do postador.

O cron do GitHub é best-effort. Este helper é chamado apenas pelos pulsos já
existentes: quando o último ciclo registrado ultrapassa a tolerância e não há
outra execução do mesmo workflow em curso, ele solicita o *mesmo* workflow.
Qualquer fotografia ausente, velha, malformada ou ambígua interrompe a ação.
Não publica, não altera a fila e não lê/escreve credenciais.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

UTC = dt.timezone.utc
JANELA_MAXIMA_SEM_CICLO = dt.timedelta(hours=4)
CABECALHO_CICLO = re.compile(r"^##\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s+UTC)\b")
API_RUNS = (
    "https://api.github.com/repos/reboclbrank-max/site/actions/workflows/"
    "postagem-diaria.yml/runs?per_page=30"
)
API_DISPATCH = (
    "https://api.github.com/repos/reboclbrank-max/site/actions/workflows/"
    "postagem-diaria.yml/dispatches"
)


def ultimo_ciclo_registrado(texto):
    """Devolve a data UTC do último ciclo produtivo no log público, ou None.

    Linhas de teste não contam como ciclo. Um formato inesperado não é
    interpretado como ausência de ciclo: quem chama deve falhar fechado.
    """
    encontrados = []
    for linha in str(texto or "").splitlines():
        if "TESTE" in linha.upper():
            continue
        achado = CABECALHO_CICLO.match(linha)
        if not achado:
            continue
        try:
            encontrados.append(
                dt.datetime.strptime(achado.group(1), "%d/%m/%Y %H:%M UTC").replace(tzinfo=UTC)
            )
        except ValueError:
            return None
    return max(encontrados) if encontrados else None


def normaliza_agora(agora=None):
    agora = agora or dt.datetime.now(UTC)
    if agora.tzinfo is None:
        return agora.replace(tzinfo=UTC)
    return agora.astimezone(UTC)


def decide_retaguarda(texto_log, runs, run_id, agora=None):
    """Escolhe uma única ação sem rede: despachar, preservar ou interromper.

    A consulta precisa conter o próprio pulso e todos os itens precisam ter
    identidade/status bem formados. Uma outra execução ainda não concluída
    bloqueia a retaguarda; ela pode ser o postador real recém-chegado.
    """
    if not run_id or not isinstance(runs, list):
        return "interromper", "fotografia-ausente"

    corrente = None
    itens = []
    for run in runs:
        if not isinstance(run, dict) or run.get("id") is None:
            return "interromper", "fotografia-malformada"
        identificador = str(run["id"])
        status = run.get("status")
        if not isinstance(status, str) or not status:
            return "interromper", "fotografia-malformada"
        itens.append((identificador, status))
        if identificador == str(run_id):
            corrente = status

    if corrente not in {"queued", "in_progress", "pending", "requested", "waiting"}:
        return "interromper", "pulso-nao-confirmado"

    for identificador, status in itens:
        if identificador != str(run_id) and status != "completed":
            return "preservar", "outra-execucao-em-andamento"

    ultimo = ultimo_ciclo_registrado(texto_log)
    if ultimo is None:
        return "interromper", "ultimo-ciclo-nao-confirmado"

    idade = normaliza_agora(agora) - ultimo
    if idade < dt.timedelta(0):
        return "interromper", "relogio-ou-log-inconsistente"
    if idade < JANELA_MAXIMA_SEM_CICLO:
        return "preservar", "ciclo-recente"
    return "despachar", "lacuna-confirmada"


def requisita_json(url, token):
    try:
        pedido = urllib.request.Request(
            url,
            headers={
                "Authorization": "token " + token,
                "Accept": "application/vnd.github+json",
                "User-Agent": "rebocl-retaguarda/1",
            },
        )
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            if resposta.status != 200:
                return None
            corpo = json.loads(resposta.read().decode("utf-8"))
        return corpo if isinstance(corpo, dict) else None
    except Exception:
        return None


def consulta_runs(token):
    fotografia = requisita_json(API_RUNS, token)
    runs = fotografia.get("workflow_runs") if fotografia else None
    return runs if isinstance(runs, list) else None


def despacha_postagem(token):
    try:
        pedido = urllib.request.Request(
            API_DISPATCH,
            data=json.dumps({"ref": "main"}).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": "token " + token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "rebocl-retaguarda/1",
            },
        )
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            return resposta.status == 204
    except Exception:
        return False


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    caminho_log = Path(argv[0]) if argv else Path("posts/log.md")
    token = os.environ.get("GHPAT")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not token or not run_id:
        print("retaguarda: configuração não confirmada; sem despacho")
        return 1

    try:
        texto_log = caminho_log.read_text(encoding="utf-8")
    except Exception:
        print("retaguarda: log público indisponível; sem despacho")
        return 1

    acao, motivo = decide_retaguarda(texto_log, consulta_runs(token), run_id)
    if acao == "despachar":
        if despacha_postagem(token):
            print("retaguarda: lacuna de ciclo confirmada; ciclo existente solicitado")
            return 0
        print("retaguarda: solicitação não confirmada; sem nova tentativa")
        return 1
    if acao == "preservar":
        if motivo == "ciclo-recente":
            print("retaguarda: ciclo recente; preservado")
        else:
            print("retaguarda: execução já observada; preservado")
        return 0

    print("retaguarda: fotografia inconclusiva; sem despacho")
    return 1


if __name__ == "__main__":
    sys.exit(main())
