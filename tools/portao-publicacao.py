#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portão de publicação: a casa só publica o que passa no próprio juízo.

POR QUE EXISTE (06/11/2026). O dono foi direto: "não quero nada automático, quero algo
autônomo — que ele decida o horário perfeito, o post perfeito, o texto perfeito". Automático
é publicar porque deu a hora. Autônomo é poder dizer NÃO.

Este portão é o único lugar que autoriza uma publicação. Ele responde uma pergunta só, com
número na mão:

    "esta publicação é boa o bastante E diferente do que a casa já publicou?"

Se a resposta for não, a casa NÃO publica — e registra o motivo. Recusar é o comportamento
normal, não a exceção.

Regras, todas declaradas e testáveis:

  1. CANAL — itch não recebe publicação automática (não há chave de API para postar; mede-se
     apenas). Instagram exige credencial que a casa não tem: sem ela, recusa declarada.
  2. JANELA — fora da janela do calendário, não publica. Sem calendário, não publica
     (falha fechada: sem janela declarada, nada sai).
  3. NOVIDADE — compara o texto com as últimas publicações do inventário. Parecido demais
     com o que já saiu = repetição, e repetição é recusa.
  4. TÍTULO — não pode repetir título já publicado, nem cair em fórmula genérica
     ("confira", "novidade", "imperdível" sem conteúdo), nem ter tamanho fora da faixa.
  5. JUÍZO — usa a nota do juízo da casa (`juizo.py`) quando houver candidatos; abaixo do
     mínimo, recusa.
  6. SEM HISTÓRICO NÃO HÁ PROVA DE NOVIDADE — mas também não se bloqueia a primeira
     publicação do canal: declara-se "primeira do canal" e segue para as outras regras.

O que este arquivo NÃO faz: escrever texto, escolher tema, falar com a rede. Ele julga.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import unicodedata

# Limiares declarados (não aprendidos): conservadores de propósito.
SEMELHANCA_MAXIMA = 0.62      # acima disso, é repetição
TITULO_SEMELHANCA_MAXIMA = 0.85
TITULO_MIN = 12
TITULO_MAX = 90
NOTA_MINIMA = 0.55
CANAIS_SEM_PUBLICACAO = {
    "itch": "itch não tem chave de API para postar — a casa só mede",
    "instagram": "instagram exige credencial que a casa ainda não tem",
}
CANAIS_CONHECIDOS = {"site", "devlog", "youtube", "instagram", "itch"}
FORMULAS_GENERICAS = (
    "confira agora", "imperdivel", "imperdível", "nao perca", "não perca",
    "novidade quente", "clique aqui", "voce nao vai acreditar", "você não vai acreditar",
)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn").lower()


def _tokens(texto: str) -> set:
    return set(re.findall(r"[a-z0-9]{3,}", _sem_acento(texto)))


def semelhanca(a: str, b: str) -> float:
    """Semelhança de conteúdo por tokens (Jaccard). Zero quando um dos lados é vazio."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def semelhanca_de_texto(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _sem_acento(a), _sem_acento(b)).ratio()


def leitura_do_calendario(calendario: dict | None, agora_local_hora: int) -> tuple[bool, str]:
    if not isinstance(calendario, dict) or "janela" not in calendario:
        return False, "sem calendário: janela não declarada, nada publica"
    janela = calendario.get("janela") or {}
    inicio = int(janela.get("inicio", 0) or 0)
    fim = int(janela.get("fim", 0) or 0)
    if not (inicio <= agora_local_hora < fim):
        return False, "fora da janela (%02dh local, janela %02d-%02dh)" % (agora_local_hora, inicio, fim)
    return True, "dentro da janela (%02dh)" % agora_local_hora


def historico_do_canal(publicacoes: list | None, canal: str) -> list:
    lista = publicacoes if isinstance(publicacoes, list) else []
    return [p for p in lista if isinstance(p, dict) and (p.get("canal") or "").strip().lower() == canal]


def avalia(candidato: dict, *, canal: str, publicacoes: list | None = None,
           calendario: dict | None = None, hora_local: int | None = None,
           nota_juizo: float | None = None) -> dict:
    """Devolve {publica: bool, motivo: str, numeros: {...}}. Nunca lança.

    A ordem das recusas é a ordem do dano: canal impossível, depois janela, depois conteúdo.
    """
    cand = candidato if isinstance(candidato, dict) else {}
    canal = (canal or "").strip().lower()
    numeros: dict = {}

    if canal not in CANAIS_CONHECIDOS:
        return {"publica": False, "motivo": "canal desconhecido: " + (canal or "(vazio)"), "numeros": numeros}
    if canal in CANAIS_SEM_PUBLICACAO:
        return {"publica": False, "motivo": CANAIS_SEM_PUBLICACAO[canal], "numeros": numeros}

    dentro, motivo_janela = leitura_do_calendario(calendario, int(hora_local if hora_local is not None else -1))
    if not dentro:
        return {"publica": False, "motivo": motivo_janela, "numeros": numeros}

    titulo = str(cand.get("titulo") or "").strip()
    texto = str(cand.get("texto") or cand.get("corpo") or "").strip()

    if len(titulo) < TITULO_MIN or len(titulo) > TITULO_MAX:
        return {"publica": False, "numeros": numeros,
                "motivo": "título fora da faixa (%d caracteres, esperado %d-%d)" % (len(titulo), TITULO_MIN, TITULO_MAX)}
    titulo_plano = _sem_acento(titulo)
    for formula in FORMULAS_GENERICAS:
        if _sem_acento(formula) in titulo_plano:
            return {"publica": False, "motivo": "título em fórmula genérica: " + formula, "numeros": numeros}

    recentes = historico_do_canal(publicacoes, canal)
    numeros["historico_do_canal"] = len(recentes)

    for antigo in recentes[:40]:
        titulo_antigo = str(antigo.get("titulo") or "")
        if titulo_antigo.strip() and _sem_acento(titulo_antigo.strip()) == titulo_plano:
            return {"publica": False, "motivo": "título já publicado neste canal: " + titulo_antigo,
                    "numeros": numeros}
        parecido = semelhanca_de_texto(titulo, titulo_antigo)
        if parecido >= TITULO_SEMELHANCA_MAXIMA:
            numeros["titulo_parecido"] = round(parecido, 3)
            return {"publica": False, "numeros": numeros,
                    "motivo": "título quase igual a um já publicado (%.2f)" % parecido}

    pior = 0.0
    pior_titulo = ""
    for antigo in recentes[:40]:
        s = semelhanca(texto, str(antigo.get("texto") or ""))
        if s > pior:
            pior, pior_titulo = s, str(antigo.get("titulo") or "")
    numeros["semelhanca_maxima"] = round(pior, 3)
    if pior >= SEMELHANCA_MAXIMA:
        return {"publica": False, "numeros": numeros,
                "motivo": "texto repetido: %.2f de semelhança com \"%s\"" % (pior, pior_titulo[:60])}

    if nota_juizo is not None:
        numeros["nota_juizo"] = round(float(nota_juizo), 3)
        if float(nota_juizo) < NOTA_MINIMA:
            return {"publica": False, "numeros": numeros,
                    "motivo": "nota do juízo abaixo do mínimo (%.2f < %.2f)" % (float(nota_juizo), NOTA_MINIMA)}

    if not recentes:
        numeros["primeira_do_canal"] = True
    return {"publica": True, "motivo": "passou: janela ok, título próprio, texto novo%s" %
            (" (primeira publicação do canal)" if not recentes else ""), "numeros": numeros}


def registra(decisao: dict, caminho: str) -> None:
    """Registra a decisão em disco (append). Recusa também fica registrada: é prova."""
    registro = {"quando": None, "decisao": decisao}
    linhas = []
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as f:
                linhas = [l for l in f.read().splitlines() if l.strip()]
        except OSError:
            linhas = []
    linhas.append(json.dumps(registro, ensure_ascii=False))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas[-500:]) + "\n")


if __name__ == "__main__":  # pragma: no cover - uso manual
    import sys
    if len(sys.argv) < 2:
        print("uso: portao-publicacao.py <candidato.json> --canal site [--hora 14]")
        raise SystemExit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        cand = json.load(f)
    canal = "site"
    hora = None
    if "--canal" in sys.argv:
        canal = sys.argv[sys.argv.index("--canal") + 1]
    if "--hora" in sys.argv:
        hora = int(sys.argv[sys.argv.index("--hora") + 1])
    cal = None
    if os.path.exists("posts/calendario.json"):
        with open("posts/calendario.json", encoding="utf-8") as f:
            cal = json.load(f)
    pub = None
    if os.path.exists("posts/publicacoes.json"):
        with open("posts/publicacoes.json", encoding="utf-8") as f:
            pub = json.load(f)
    print(json.dumps(avalia(cand, canal=canal, publicacoes=pub, calendario=cal, hora_local=hora),
                     ensure_ascii=False, indent=2))
