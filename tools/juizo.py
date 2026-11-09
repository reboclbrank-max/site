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
        # ---- traços acrescentados em 06/11/2026, cada um com o defeito que o motivou ----
        # 88 dos 107 posts antigos terminavam sem pontuação (corte seco em ~220 caracteres).
        # hashtag e link no fim são hábito da casa: para medir pontuação, eles saem antes da conta
        "termina_com_pontuacao": bool(re.search(
            r"[.!?…]\s*$",
            re.sub(r"(\s*(#[\wÀ-ÿ]+|https?://\S+))+\s*$", "", t))),
        # 14 posts tinham a mesma estrutura "dois jogos / dois mundos / um dev solo".
        "sem_molde_de_dois_jogos": not re.search(
            r"dois (jogos|mundos|projetos)|um dev solo|duas paix", baixo),
        # o mesmo texto saiu 40 vezes: abertura repetida é o sintoma visível do molde.
        "abertura_propria": not any(baixo.startswith(m) for m in (
            "dois mundos", "dois jogos", "dois projetos", "da tática", "ei!", "🎮 jogou")),
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
    "termina_com_pontuacao": +2,   # frase que termina no meio é o defeito nº 1 da casa
    "sem_molde_de_dois_jogos": +2, # o molde do "dois jogos" é a assinatura da repetição
    "abertura_propria": +1,
}

# ---- RÉGUA DA DESCRIÇÃO DE VÍDEO ------------------------------------------------------------
# A régua de post não serve para descrição: descrição de vídeo DEVE ter link, e não precisa de
# hashtag. Julgar descrição pela régua de post seria medir a coisa errada com número bonito.
# Esta régua foi declarada a partir do que as descrições da casa são (fonte, número, link,
# frase inteira) e o mínimo foi calibrado nas descrições reais de posts/youtube-publicados.json:
# das 4 guardadas, três foram cortadas em "…" (0,727 · 0,364 · 0,364) e a íntegra tira 1,000.
# Com 0,73 a régua recusa as três cortadas e aprova a inteira — é a cicatriz virada em medida.
PESOS_DESCRICAO = {
    "cita_fonte": +2,            # "Fonte: jogos/..." é o que separa descrição de propaganda
    "tem_numero": +2,            # número medido (colheitas, minutos, decisões)
    "tem_link": +1,              # na descrição o link é obrigatório, não defeito
    "sem_corte_seco": +2,        # descrição cortada em "…" é o defeito real de 3 vídeos
    "cita_jogo": +2,
    "sem_clickbait": +1,         # "VOCÊ NÃO VAI ACREDITAR" e afins
    "tamanho_de_descricao": +1,  # entre 80 e 900 caracteres
}
SOMA_DESCRICAO = 11.0
NOTA_MINIMA_DESCRICAO = 0.73


def tracos_descricao(texto):
    t = (texto or "").strip()
    baixo = t.lower()
    return {
        "cita_fonte": bool(re.search(r"fonte:\s*\S+", baixo)),
        "tem_numero": bool(re.search(r"\d", t)),
        "tem_link": bool(re.search(r"https?://|www\.", baixo)),
        # "…" aqui é CORTE, não pausa: as 3 descrições antigas terminam exatamente assim.
        "sem_corte_seco": not t.rstrip().endswith(("…", "...")),
        "cita_jogo": any(n in baixo for n in ("ceifalume", "prancheta", "pelle", "brasa")),
        "sem_clickbait": not re.search(
            r"voce nao vai acreditar|você não vai acreditar|chocante|imperdível|imperdivel", baixo),
        "tamanho_de_descricao": 80 <= len(t) <= 900,
    }


def nota_descricao(texto, pesos=None):
    pesos = pesos or PESOS_DESCRICAO
    tr = tracos_descricao(texto)
    total = sum(pesos.get(n, 0) for n, v in tr.items() if v)
    contrib = [(1, n, pesos.get(n, 0)) for n, v in tr.items() if v]
    valor = max(0.0, min(1.0, total / SOMA_DESCRICAO))
    return round(valor, 3), {"pontos": total, "teto": SOMA_DESCRICAO,
                             "contribuicoes": contrib}


# A MESMA RÉGUA, normalizada em 0..1, e a nota mínima para publicar. O mínimo não é gosto: é a
# MEDIANA do que a casa já publicou antes do conserto (13/10 a 06/11) somada de um passo: 106
# posts do molde dão mediana 0,538 e 75% ficam abaixo de 0,615. Com 0,65 a régua recusa ~78% do
# que a casa publicava antes e aprova os textos escritos depois do conserto (0,692). Calibração
# medida, não escolhida no gosto — e há contrato cobrando os dois lados.
NOTA_MINIMA = 0.65
SOMA_MAXIMA = 10.0     # soma dos pesos positivos declarados (base da normalização)


def nota(texto, pesos=None, soma_maxima=None):
    """(nota 0..1, detalhe). Nota é a régua DECLARADA acima, normalizada — não é opinião.

    O que ela mede: pergunta, jogo citado, chamada, hashtag na medida, tamanho, número,
    pontuação no fim, um assunto só, abertura própria. O que ela NÃO mede: se o texto é
    engraçado, bonito ou verdadeiro — verdade é o portão (fato inventado) que cuida, e graça
    absoluta ninguém mede. Aqui existe uma régua com número, calibrada na história da casa.
    """
    pesos = pesos or PESOS_DECLARADOS
    total, contribuicoes = pontuar(texto, pesos)
    teto = float(soma_maxima or sum(w for w in pesos.values() if w > 0) or SOMA_MAXIMA)
    valor = max(0.0, min(1.0, total / teto)) if teto else 0.0
    return round(valor, 3), {"pontos": total, "teto": teto, "contribuicoes": contribuicoes}


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
def garantir_memoria(caminho=None):
    """Cria o arquivo da memória se ainda não existir — com a lista vazia, não com escolha falsa.

    DEFEITO MEDIDO (31/10/2026): `posts/memoria-de-gosto.json` dava 404 no repositório porque o
    arquivo só nascia no ciclo que PUBLICA, e os ciclos caíam na trava de cadência. Ausência de
    arquivo não é ausência de memória: é memória sem lugar. Agora o lugar existe desde a primeira
    medição e cada escolha só faz acrescentar.
    """
    alvo = caminho or MEMORIA
    if os.path.exists(alvo):
        return False
    with open(alvo + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"_o_que_e": "memória das escolhas de texto: justificativa, candidatos, "
                               "revisão e resultado medido",
                   "escolhas": []}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(alvo + ".tmp", alvo)
    return True


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
    criada = garantir_memoria()
    apurados, dados = apurar_resultado()
    print("juízo: %d traço(s) com peso medido · %d declarado(s) · amostra do feed: %d"
          % (len(p["medidos"]), len(p["declarados"]), p["amostra"]))
    for nome in p["medidos"]:
        item = p["tracos"][nome]
        print("  medido: %s peso %+d (com %.2f vs sem %.2f, ganho %.2f > desvio %.2f)"
              % (nome, item["peso"], item["com"]["media"], item["sem"]["media"],
                 item["ganho"], item["desvio"]))
    if criada:
        print("memória de gosto criada (vazia): %s" % MEMORIA)
    print("escolhas registradas: %d · resultados apurados agora: %d"
          % (len(dados["escolhas"]), apurados))
    if not feed:
        print("sem feed medido: o gosto fica declarado (nenhum peso é inventado)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
