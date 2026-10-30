#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Juízo: o gosto da casa — critérios, escolha entre opções e revisão do próprio texto.

POR QUE EXISTE (30/10/2026). Até aqui o robô não ESCOLHIA: pegava o primeiro texto que passava
no crivo. Isso não é critério, é ordem de chegada. O dono pediu "mente humana": dentro do que é
honesto, isso significa quatro coisas concretas — e nenhuma delas é fingir sentimento:

  1. CRITÉRIO DECLARADO — cada traço que a casa valoriza está escrito, com peso e origem
     ("medido" quando veio do feed real, "declarado" quando é escolha da casa).
  2. APRENDER O GOSTO COM O RESULTADO — quando há engajamento medido por post
     (`posts/feed-medido.json`), cada traço é comparado com/sem e só vira peso quando a
     amostra passa e a diferença supera o desvio. Ruído não vira gosto (mesma lei do horário).
  3. ESCOLHER ENTRE OPÇÕES — vários candidatos, pontuados, com justificativa registrada:
     "escolhi o 2º porque tem pergunta e fecha em 167 caracteres".
  4. REVISAR A SI MESMO — reler o que escreveu e TIRAR o excesso (hashtag a mais, espaço
     duplo, sobra no fim). A revisão nunca inventa conteúdo: só corta.

O que este arquivo NÃO faz, e não vai fingir: sentir, ter opinião sobre gosto alheio, ou decidir
o que é "bonito". Tudo o que ele afirma tem número ou está marcado como escolha declarada.
"""
import datetime
import importlib.util
import json
import os
import re
import statistics
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = os.path.join(RAIZ, "posts", "feed-medido.json")
PERFIL_SAIDA = os.path.join(RAIZ, "posts", "perfil-de-gosto.json")
MEMORIA = os.path.join(RAIZ, "posts", "memoria-de-gosto.json")
LIMITE_TEXTO = 220

# Amostra mínima de cada lado (com/sem traço) para um traço virar peso medido.
AMOSTRA_MINIMA = 15

# Mesma régua do crivo do postador: o post tem de citar a casa ou um jogo dela.
JOGOS = ("prancheta", "ceifalume", "rebocl", "fazenda", "manager", "futebol")


# ------------------------------------------------------------------ traços
def tracos(texto):
    """Traços observáveis do texto. Nada de opinião: cada um é verificável por leitura."""
    t = " ".join(str(texto or "").split())
    baixo = t.lower()
    hashtags = re.findall(r"(?<!\w)#\w+", t, re.UNICODE)
    primeiro = t[:2]
    return {
        "tem_pergunta": "?" in t,
        "pergunta_no_fim": t.rstrip().endswith("?"),
        "emoji_no_inicio": bool(primeiro) and not primeiro[0].isalnum(),
        "cita_jogo": any(j in baixo for j in JOGOS),
        "chamada": any(c in baixo for c in ("grátis", "gratis", "navegador", "conta pra mim",
                                            "comenta", "jogue", "acompanhe", "no apk")),
        "hashtag_1_ou_2": 1 <= len(hashtags) <= 2,
        "sem_hashtag": len(hashtags) == 0,
        "tamanho_ideal": 120 <= len(t) <= 200,
        "tem_numero": bool(re.search(r"\d", t)),
        "tem_link": bool(re.search(r"https?://|www\.", baixo)),
    }


# Peso declarado quando NÃO existe medição por post. Cada linha é uma decisão da casa,
# escrita aqui para poder ser discutida e revista — não um número mágico escondido.
PESOS_DECLARADOS = {
    "tem_pergunta": +1,
    "pergunta_no_fim": +1,
    "emoji_no_inicio": 0,
    "cita_jogo": +2,      # sem o nome do jogo o post não é da casa
    "chamada": +1,
    "hashtag_1_ou_2": +1,
    "sem_hashtag": 0,
    "tamanho_ideal": +1,
    "tem_numero": +1,
    "tem_link": -1,       # link no corpo cansa no menor canal (o destino entra depois)
}


# ------------------------------------------------------------------ aprender o gosto
def ler_feed(caminho=None):
    try:
        with open(caminho or FEED, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return []
    itens = dados.get("posts") if isinstance(dados, dict) else dados
    if not isinstance(itens, list):
        return []
    limpos = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        texto = item.get("texto")
        eng = item.get("engajamento")
        if texto is None or eng is None:
            continue
        try:
            limpos.append({"texto": str(texto), "engajamento": float(eng)})
        except (TypeError, ValueError):
            continue
    return limpos


def aprender(feed=None, amostra_minima=AMOSTRA_MINIMA):
    """Para cada traço: média com e sem ele. Só vira peso medido com amostra e sinal claros."""
    feed = feed if feed is not None else ler_feed()
    resultado = {}
    for nome in PESOS_DECLARADOS:
        com = [p["engajamento"] for p in feed if tracos(p["texto"]).get(nome)]
        sem = [p["engajamento"] for p in feed if not tracos(p["texto"]).get(nome)]
        item = {
            "com": {"n": len(com), "media": round(statistics.fmean(com), 2) if com else None},
            "sem": {"n": len(sem), "media": round(statistics.fmean(sem), 2) if sem else None},
            "medido": False,
            "direcao": None,
            "base": "declarado",
            "peso": PESOS_DECLARADOS[nome],
        }
        if len(com) >= amostra_minima and len(sem) >= amostra_minima:
            valores = com + sem
            desvio = statistics.pstdev(valores) if len(valores) > 1 else 0.0
            ganho = statistics.fmean(com) - statistics.fmean(sem)
            if abs(ganho) > desvio:
                item.update({"medido": True, "base": "medido",
                             "direcao": 1 if ganho > 0 else -1,
                             "peso": 1 if ganho > 0 else -1,
                             "ganho": round(ganho, 2), "desvio": round(desvio, 2)})
            else:
                item["porque"] = ("amostra ok, mas a diferença (%.2f) está dentro do desvio "
                                  "(%.2f): não vira gosto" % (ganho, desvio))
        else:
            item["porque"] = ("amostra insuficiente: %d com / %d sem (mínimo %d de cada)"
                              % (len(com), len(sem), amostra_minima))
        resultado[nome] = item
    return resultado


def perfil(feed=None):
    aprendido = aprender(feed)
    pesos = {k: v["peso"] for k, v in aprendido.items()}
    medidos = [k for k, v in aprendido.items() if v["medido"]]
    return {
        "quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_lei": "traço só pesa quando a amostra passa e a diferença supera o desvio; "
                "o resto fica marcado como escolha declarada, não como gosto aprendido.",
        "pesos": pesos,
        "tracos": aprendido,
        "medidos": medidos,
        "declarados": [k for k in aprendido if k not in medidos],
        "amostra": len(feed if feed is not None else ler_feed()),
    }


# ------------------------------------------------------------------ escolher
def pontuar(texto, pesos=None):
    """(pontuação, detalhe) — soma dos pesos dos traços presentes, com o que contribuiu."""
    pesos = pesos or PESOS_DECLARADOS
    presentes = tracos(texto)
    total = 0
    contribuicoes = []
    for nome, tem in presentes.items():
        peso = int(pesos.get(nome, 0))
        if not tem:
            continue
        total += peso
        if peso:
            contribuicoes.append(((1 if peso > 0 else -1), nome, abs(peso)))
    contribuicoes.sort(key=lambda c: (-c[0], -c[2], c[1]))
    return total, contribuicoes


def _assinatura(texto):
    t = re.sub(r"[^0-9a-z]+", " ", str(texto or "").lower())
    return " ".join(t.split())[:60]


def escolher(candidatos, pesos=None, validador=None, ultimo_texto=""):
    """Escolhe o melhor candidato — e diz por quê. Devolve (texto, justificativa, ranking).

    Empate: prefere quem ABRE diferente do último post (variedade é parte do critério humano:
    dois dias com a mesma abertura cansam antes do conteúdo).
    """
    aberturas = len(candidatos or [])
    validos = []
    for i, c in enumerate(candidatos or []):
        texto = " ".join(str(c or "").split())
        if not texto:
            continue
        if validador is not None and not validador(texto):
            continue
        validos.append((i, texto))
    if not validos:
        return None, "nenhum candidato passou no crivo", {"candidatos": aberturas, "validos": 0}

    vistos = set()
    unicos = []
    for i, texto in validos:
        chave = _assinatura(texto)
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append((i, texto))

    abertura_ultimo = _assinatura(ultimo_texto)[:3]
    ranking = []
    for i, texto in unicos:
        pontos, contrib = pontuar(texto, pesos)
        variedade = 1 if abertura_ultimo and _assinatura(texto)[:3] != abertura_ultimo else 0
        ranking.append({"ordem": i + 1, "texto": texto, "pontos": pontos + variedade,
                        "pontos_base": pontos, "variedade": variedade,
                        "contribuicoes": contrib[:4], "tamanho": len(texto)})
    ranking.sort(key=lambda r: (-r["pontos"], r["tamanho"] < 120, r["ordem"]))
    melhor = ranking[0]
    razoes = []
    for sinal, nome, _peso in melhor["contribuicoes"]:
        if sinal > 0 and len(razoes) < 3:
            razoes.append(nome.replace("_", " "))
        elif sinal < 0 and len(razoes) < 3:
            razoes.append("menos " + nome.replace("_", " "))
    justificativa = "escolhi o %dº de %d (%d válidos): %s · %d caracteres%s" % (
        melhor["ordem"], aberturas, len(unicos),
        ", ".join(razoes) if razoes else "sem traço forte",
        melhor["tamanho"],
        " · abre diferente do último post" if melhor["variedade"] else "")
    return melhor["texto"], justificativa, {"candidatos": aberturas, "validos": len(unicos),
                                            "ranking": ranking}


# ------------------------------------------------------------------ revisar a si mesmo
def revisar(texto, limite=LIMITE_TEXTO):
    """Tira excesso e devolve (texto, mudanças). Nunca cria conteúdo — só corta.

    Revisar inventando frase seria escrever outro post e chamar de revisão. A casa não faz isso.
    """
    original = str(texto or "")
    t = " ".join(original.split())
    mudancas = []
    if t != original:
        mudancas.append("espaços/quebras normalizados")
    hashtags = re.findall(r"(?<!\w)#\w+", t, re.UNICODE)
    if len(hashtags) > 2:
        for extra in hashtags[2:]:
            t = re.sub(r"\s*" + re.escape(extra), "", t, count=1)
        mudancas.append("removidas %d hashtag(s) além de 2" % (len(hashtags) - 2))
    if re.search(r"https?://|www\.", t, re.I):
        mudancas.append("ATENÇÃO: tem link no corpo (o destino entra depois)")
    if len(t) > limite:
        corte = t[:limite]
        if " " in corte:
            corte = corte[:corte.rfind(" ")]
        t = corte.rstrip(" ,.;:—-·")
        mudancas.append("cortado de %d para %d caracteres" % (len(original.strip()), len(t)))
    t = t.strip(" ·—-")
    if t != t.strip():
        mudancas.append("sobra removida do fim")
    return t, mudancas


# ------------------------------------------------------------------ memória e resultado
def ler_memoria(caminho=None):
    try:
        with open(caminho or MEMORIA, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return {"escolhas": []}
    if not isinstance(dados, dict) or not isinstance(dados.get("escolhas"), list):
        return {"escolhas": []}
    return dados


def registrar_escolha(melhor, justificativa, detalhe, revisao=None, caminho=None, quando=None):
    dados = ler_memoria(caminho)
    dados["escolhas"].append({
        "quando": quando or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "texto": str(melhor or "")[:220],
        "justificativa": justificativa,
        "pontos": (detalhe.get("ranking") or [{}])[0].get("pontos") if detalhe.get("ranking") else None,
        "candidatos": detalhe.get("candidatos"),
        "validos": detalhe.get("validos"),
        "revisao": revisao or [],
        "resultado": None,
    })
    dados["escolhas"] = dados["escolhas"][-200:]
    alvo = caminho or MEMORIA
    with open(alvo + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(alvo + ".tmp", alvo)
    return dados


def apurar_resultado(caminho=None, feed=None):
    """Liga cada escolha ao engajamento medido (quando o post já apareceu no feed)."""
    dados = ler_memoria(caminho)
    feed = feed if feed is not None else ler_feed()
    por_assinatura = {}
    for item in feed:
        por_assinatura.setdefault(_assinatura(item["texto"]), item["engajamento"])
    apurados = 0
    for escolha in dados["escolhas"]:
        chave = _assinatura(escolha.get("texto"))
        if chave and chave in por_assinatura and escolha.get("resultado") is None:
            escolha["resultado"] = {"engajamento": por_assinatura[chave], "fonte": "feed-medido.json"}
            apurados += 1
    if apurados:
        with open((caminho or MEMORIA) + ".tmp", "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace((caminho or MEMORIA) + ".tmp", caminho or MEMORIA)
    return apurados, dados


# ------------------------------------------------------------------ CLI
def main(argv):
    feed = ler_feed()
    p = perfil(feed)
    with open(PERFIL_SAIDA + ".tmp", "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(PERFIL_SAIDA + ".tmp", PERFIL_SAIDA)
    apurados, dados = apurar_resultado()
    print("juízo: %d traço(s) com peso medido · %d declarado(s) · amostra do feed: %d"
          % (len(p["medidos"]), len(p["declarados"]), p["amostra"]))
    for nome in p["medidos"]:
        item = p["tracos"][nome]
        print("  medido: %s peso %+d (com %.2f vs sem %.2f, ganho %.2f > desvio %.2f)"
              % (nome, item["peso"], item["com"]["media"], item["sem"]["media"],
                 item["ganho"], item["desvio"]))
    print("escolhas registradas: %d · resultados apurados agora: %d"
          % (len(dados["escolhas"]), apurados))
    if not feed:
        print("sem feed medido: o gosto fica declarado (nenhum peso é inventado)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
