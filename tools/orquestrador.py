#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orquestrador 24h do marketing da casa.

Roda em pulsos (o workflow dispara a cada ~15 min). Em cada pulso decide UMA ação,
por prioridade, e registra o que fez em `posts/orquestrador.json`.

Por que um orquestrador e não "o postador rodando sempre":
  - o postador sabe publicar, mas não sabe decidir prioridade, nem medir, nem aprender;
  - sem estado, o cron atrasado duplicaria post (o pulso de 15 min encontraria o de 2h);
  - aqui a decisão vira DADO (estado no repositório), auditável e testável offline.

Prioridade de cada pulso (a primeira que couber vence):
  1. MEDIR      — se passaram 6h da última medição
  2. PESQUISAR  — se é hora da pesquisa diária (03h local) e ela não foi feita hoje
  3. APRENDER   — se é hora do aprendizado diário (04h local) e ele não foi feito hoje
  4. PUBLICAR   — se está na janela, sob teto diário e passaram 2h do último ciclo
  5. DORMIR     — nada a fazer: registra o pulso e sai (não inventa trabalho)

Nunca publica fora da janela, nunca passa do teto, nunca repete a mesma ação no mesmo dia
quando ela é diária.
"""
import datetime
import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO = os.path.join(RAIZ, "posts", "orquestrador.json")
CALENDARIO = os.path.join(RAIZ, "posts", "calendario.json")
LOG = os.path.join(RAIZ, "posts", "log.md")

INTERVALO_PUBLICACAO = datetime.timedelta(hours=2)
INTERVALO_MEDICAO = datetime.timedelta(hours=6)


# ----------------------------------------------------------------- utilidades de tempo
def agora_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def local(agora=None, fuso="America/Fortaleza"):
    agora = agora or agora_utc()
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=datetime.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return agora.astimezone(ZoneInfo(fuso))
    except Exception:
        return agora.astimezone(datetime.timezone(datetime.timedelta(hours=-3)))


def iso(momento):
    return momento.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ler_iso(texto):
    if not texto:
        return None
    try:
        base = texto.replace("Z", "+00:00")
        momento = datetime.datetime.fromisoformat(base)
        return momento if momento.tzinfo else momento.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


# ----------------------------------------------------------------- estado e calendário
def estado_vazio():
    return {
        "_o_que_e": "memoria do orquestrador 24h: o que ja foi feito e quando",
        "versao": 1,
        "ultima_publicacao": None,
        "ultima_medicao": None,
        "ultima_pesquisa": None,
        "ultima_aprendizagem": None,
        "pulsos": 0,
        "historico": [],
    }


def carregar_estado(caminho=ESTADO):
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        return estado_vazio()
    base = estado_vazio()
    base.update(dados or {})
    return base


def gravar_estado(dados, caminho=ESTADO):
    dados["historico"] = (dados.get("historico") or [])[-40:]
    pasta = os.path.dirname(caminho)
    if pasta and not os.path.isdir(pasta):
        os.makedirs(pasta, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")


def ler_calendario(caminho=CALENDARIO):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def pode_publicar(agora, calendario):
    """(pode, motivo) — janela e teto, lidos do calendário. Sem calendário, 24h (legado)."""
    if not calendario or "janela" not in calendario:
        return True, "sem calendario: janela nao aplicada"
    j = calendario["janela"]
    hora = local(agora, j.get("fuso", "America/Fortaleza")).hour
    inicio, fim = int(j.get("inicio", 0)), int(j.get("fim", 24))
    if not (inicio <= hora < fim):
        return False, "fora da janela (%02dh local)" % hora
    teto = int(calendario.get("teto_diario", 0) or 0)
    if teto:
        hoje = local(agora, j.get("fuso", "America/Fortaleza")).strftime("%d/%m/%Y")
        feitos = 0
        try:
            with open(LOG, encoding="utf-8") as f:
                feitos = sum(1 for linha in f if linha.startswith("## " + hoje))
        except Exception:
            feitos = 0
        # o pulso do orquestrador também conta; usa o maior entre log e estado do dia
        registrado = (calendario.get("_ciclos_no_dia") or {}).get(hoje, 0)
        feitos = max(feitos, int(registrado))
        if feitos >= teto:
            return False, "teto diario atingido (%d de %d)" % (feitos, teto)
        return True, "janela ok (%02dh) · ciclos hoje %d/%d" % (hora, feitos, teto)
    return True, "janela ok (%02dh) · sem teto" % hora


def ja_feito_hoje(momento_iso, agora, fuso):
    momento = ler_iso(momento_iso)
    if not momento:
        return False
    return momento.astimezone(local(agora, fuso).tzinfo).date() == local(agora, fuso).date()


# ----------------------------------------------------------------- decisão
def decidir(agora=None, estado=None, calendario=None):
    """Devolve (acao, motivo). Puro: não executa nada — por isso é testável."""
    agora = agora or agora_utc()
    estado = estado if estado is not None else carregar_estado()
    calendario = calendario if calendario is not None else ler_calendario()
    fuso = (calendario or {}).get("janela", {}).get("fuso", "America/Fortaleza")
    hora_local = local(agora, fuso).hour

    ultima_medicao = ler_iso(estado.get("ultima_medicao"))
    if not ultima_medicao or (agora - ultima_medicao) >= INTERVALO_MEDICAO:
        return "medir", "medição vencida (intervalo de %dh)" % (INTERVALO_MEDICAO.total_seconds() / 3600)

    if 3 <= hora_local < 4 and not ja_feito_hoje(estado.get("ultima_pesquisa"), agora, fuso):
        return "pesquisar", "janela diária de pesquisa (03h local)"

    if 4 <= hora_local < 5 and not ja_feito_hoje(estado.get("ultima_aprendizagem"), agora, fuso):
        return "aprender", "janela diária de aprendizado (04h local)"

    pode, motivo = pode_publicar(agora, calendario)
    if not pode:
        return "dormir", motivo

    ultima = ler_iso(estado.get("ultima_publicacao"))
    if ultima and (agora - ultima) < INTERVALO_PUBLICACAO:
        faltam = INTERVALO_PUBLICACAO - (agora - ultima)
        return "dormir", "publicou há %.0f min (mínimo %dh)" % (
            (agora - ultima).total_seconds() / 60, INTERVALO_PUBLICACAO.total_seconds() / 3600)

    return "publicar", motivo


# ----------------------------------------------------------------- execução
def rodar(comando, cwd=RAIZ, timeout=600):
    try:
        r = subprocess.run(comando, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        saida = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode, saida[-600:]
    except Exception as e:
        return 1, str(e)[:200]


def executar(acao, agora=None, rodar_fn=None):
    """Executa a ação decidida. `rodar_fn` é injetável para o teste rodar offline."""
    rodar_fn = rodar_fn or rodar
    if acao == "publicar":
        return rodar_fn([sys.executable, "tools/postador.py"])
    if acao == "medir":
        return rodar_fn([sys.executable, "tools/metricas.py", "--json"])
    if acao == "pesquisar":
        # a pesquisa usa o mesmo motor do postador no modo que só planeja (sem publicar)
        return rodar_fn([sys.executable, "tools/pesquisar-oportunidade.py"])
    if acao == "aprender":
        return rodar_fn([sys.executable, "tools/aprender-horario.py"])
    return 0, "nada a fazer (%s)" % acao


def main(argv):
    seco = "--seco" in argv          # decide e registra, mas não executa
    agora = agora_utc()
    estado = carregar_estado()
    calendario = ler_calendario()
    acao, motivo = decidir(agora, estado, calendario)

    print("pulso %s · ação: %s · %s" % (iso(agora), acao, motivo))
    codigo, saida = (0, "modo seco") if seco else executar(acao, agora)
    print(saida)

    estado["pulsos"] = int(estado.get("pulsos", 0)) + 1
    if acao == "publicar" and codigo == 0:
        estado["ultima_publicacao"] = iso(agora)
        fuso = (calendario or {}).get("janela", {}).get("fuso", "America/Fortaleza")
        hoje = local(agora, fuso).strftime("%d/%m/%Y")
        contagem = calendario.setdefault("_ciclos_no_dia", {}) if isinstance(calendario, dict) else None
        if contagem is not None:
            contagem[hoje] = int(contagem.get(hoje, 0)) + 1
            gravar_calendario(calendario)
    elif acao == "medir" and codigo == 0:
        estado["ultima_medicao"] = iso(agora)
    elif acao == "pesquisar" and codigo == 0:
        estado["ultima_pesquisa"] = iso(agora)
    elif acao == "aprender" and codigo == 0:
        estado["ultima_aprendizagem"] = iso(agora)

    estado["historico"].append({"quando": iso(agora), "acao": acao, "motivo": motivo,
                                "codigo": codigo, "saida": saida[:200]})
    gravar_estado(estado)
    print("registrado: pulsos=%d" % estado["pulsos"])
    return 0 if codigo == 0 else 1


def gravar_calendario(dados, caminho=CALENDARIO):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
