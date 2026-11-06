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

  0. CREDENCIAL — canal sem credencial viva não publica; a recusa diz qual falta.
     itch não recebe publicação automática em nenhuma hipótese (não há chave de API para
     postar; mede-se apenas).
  1. JANELA — fora da janela do calendário, não publica. Sem calendário, não publica
     (falha fechada: sem janela declarada, nada sai).
  2. TÍTULO — faixa de tamanho, nada de fórmula genérica ("confira", "imperdível"...).
  3. UM ASSUNTO — o post não pode falar dos dois jogos. Medido em 06/11/2026: quatro posts
     seguidos repetiram "PRANCHETA ... CEIFALUME ... dois jogos, um dev solo". Enquanto o
     pedido ao motor trazia os dois jogos, o texto saía com a mesma estrutura. Post de dois
     jogos é a assinatura da repetição, e por isso virou recusa explícita.
  4. FORMA — mesma forma de texto (mesmo tipo de abertura, mesmo esqueleto de frases, mesmo
     número de hashtags) para o mesmo jogo = repetição, mesmo com palavras diferentes.
     Trocar adjetivo não é novidade.
  5. NOVIDADE — compara título e texto com as últimas publicações do canal. Parecido demais
     com o que já saiu = repetição, e repetição é recusa.
  6. JUÍZO — usa a nota do juízo da casa (`juizo.py`) quando houver candidatos; abaixo do
     mínimo, recusa.
  7. SEM HISTÓRICO NÃO HÁ PROVA DE NOVIDADE — mas também não se bloqueia a primeira
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
JANELA_DE_FORMA = 12          # quantas publicações recentes entram na comparação de forma

# Canais que a casa conhece. Publicação só acontece nos que têm caminho de envio.
CANAIS_CONHECIDOS = {
    "site", "devlog", "youtube", "instagram", "itch",
    "threads", "bluesky", "mastodon", "telegram",
}
CANAIS_SEM_PUBLICACAO = {
    "itch": "itch não tem chave de API para postar — a casa só mede",
}
# Canais que exigem credencial viva declarada pelo chamador.
CANAIS_COM_CREDENCIAL = {
    "instagram": "IG_TOKEN + IG_USER_ID",
    "threads": "THREADS_TOKEN + THREADS_USER_ID",
    "bluesky": "BSKY_HANDLE + BSKY_APP_PASSWORD",
    "mastodon": "MASTODON_URL + MASTODON_TOKEN",
    "telegram": "TELEGRAM_TOKEN + TELEGRAM_CHAT",
}

# Jogos da casa — usados na regra "um assunto por post".
JOGOS = ("prancheta", "ceifalume")

# MECÂNICA QUE OS JOGOS NÃO TÊM. Medido em 06/11/2026: com o pedido novo, um motor de texto
# livre respondeu "Ceifalume travou no pathfinding dos inimigos; a IA ignora paredes". O
# Ceifalume é fazenda idle — não tem inimigo, nem perseguição, nem parede. Fato inventado em
# post da casa é o pior defeito possível: quebra a confiança que o post existe para construir.
TERMOS_INVENTADOS = (
    "inimigo", "inimigos", "pathfinding", "boss", "chefe final", "combate", "batalha",
    "power-up", "power up", "loot", "battle pass", "temporada de passe", "loja de itens",
    "multiplayer online", "pvp", "servidor online",
)

# CONTRADIÇÃO COM FATO CONFERIDO. Medido em 06/11/2026: o motor escreveu "Ceifalume ainda não
# salva o progresso" — e o jogo salva sozinho desde a 0.1. A lista é curta de propósito: são as
# contradições que a casa JÁ VIU o motor inventar. Cada linha diz qual fato a frase nega, para
# poder ser conferida. Quando aparecer outra, entra aqui com a data.
CONTRADICOES = (
    ("ceifalume", "não salva", "o save é automático (jogos/ceifalume/index.html)"),
    ("ceifalume", "nao salva", "o save é automático (jogos/ceifalume/index.html)"),
    ("ceifalume", "não tem save", "o save é automático (jogos/ceifalume/index.html)"),
    ("ceifalume", "não cresce com o jogo fechado", "as plantações crescem até 8 h com o jogo fechado"),
    ("prancheta", "não tem troca", "são até 5 trocas por partida (jogos/prancheta/index.html)"),
    ("prancheta", "não salva", "o save é local, no aparelho (jogos/prancheta/index.html)"),
)

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


def jogos_citados(texto: str, jogos=JOGOS) -> set:
    """Quais jogos da casa o texto nomeia. Vazio quando não nomeia nenhum."""
    plano = _sem_acento(texto)
    return {j for j in jogos if _sem_acento(j) in plano}


# ------------------------------------------------------------------ forma do texto
def forma(texto: str) -> dict:
    """Retrato estrutural do texto — o que faz dois posts "parecerem o mesmo".

    Medido em 06/11/2026 nos quatro posts repetidos: as palavras mudavam, a FORMA não —
    abertura com rótulo e dois pontos, dois blocos de jogo, fecho de assinatura, duas
    hashtags. Comparar só palavras (Jaccard) deixava isso passar com 0.5 de semelhança.
    """
    t = " ".join(str(texto or "").split())
    plano = _sem_acento(t)
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", t) if f.strip()]
    abertura = plano.split()[:2]
    if plano.lstrip().startswith("?") or not plano:
        tipo_abertura = "vazio"
    elif ":" in t[:40]:
        tipo_abertura = "rotulo"
    elif re.match(r"^[^\w\s]", t):
        tipo_abertura = "emoji"
    elif plano.rstrip().endswith("?"):
        tipo_abertura = "pergunta"
    elif frases and plano.startswith(("voce", "vc")):
        tipo_abertura = "voce"
    else:
        tipo_abertura = "frase"
    esqueleto = []
    for f in frases:
        pf = _sem_acento(f)
        if pf.endswith("?"):
            esqueleto.append("pergunta")
        elif ":" in f[:40]:
            esqueleto.append("rotulo")
        elif re.match(r"^\d+[.)]", f):
            esqueleto.append("passo")
        elif any(p in pf for p in ("gratis", "jogue", "baixe", "acesse", "siga")):
            esqueleto.append("convite")
        else:
            esqueleto.append("frase")
    hashtags = len(re.findall(r"(?<!\w)#\w+", t, re.UNICODE))
    return {
        "abertura": " ".join(abertura),
        "tipo_abertura": tipo_abertura,
        "frases": len(frases),
        "esqueleto": tuple(esqueleto[:6]),
        "hashtags": hashtags,
        "emoji_no_inicio": bool(t) and not t[0].isalnum(),
    }


def forma_distintiva(f: dict) -> bool:
    """Só uma forma com marca própria pode acusar repetição.

    Uma frase solta, sem rótulo e sem hashtag, combina com quase tudo — acusar repetição por
    isso seria ruído, não critério. A forma conta quando tem estrutura reconhecível: dois ou
    mais blocos, ou abertura com rótulo, ou hashtag.
    """
    if not isinstance(f, dict):
        return False
    return (len(f.get("esqueleto") or ()) >= 2
            or f.get("tipo_abertura") == "rotulo"
            or int(f.get("hashtags") or 0) >= 1)


def mesma_forma(a: dict, b: dict) -> bool:
    """Mesma forma = abertura, esqueleto de frases e hashtags iguais — e forma com marca."""
    if not (forma_distintiva(a) and forma_distintiva(b)):
        return False
    return (a.get("tipo_abertura") == b.get("tipo_abertura")
            and a.get("esqueleto") == b.get("esqueleto")
            and a.get("hashtags") == b.get("hashtags"))


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
    """Publicações do canal, do mais novo para o mais antigo.

    CONTRATO DE ORDEM: `publicacoes` chega ordenada do mais novo para o mais antigo — é o que
    `recentes[:40]` pressupõe. Lista em ordem cronológica faz o portão comparar com o começo
    da história e deixar passar repetição (defeito encontrado em 06/11/2026). Quem chama é
    quem ordena (`redator._recente_primeiro`).
    """
    lista = publicacoes if isinstance(publicacoes, list) else []
    return [p for p in lista if isinstance(p, dict) and (p.get("canal") or "").strip().lower() == canal]


def avalia(candidato: dict, *, canal: str, publicacoes: list | None = None,
           calendario: dict | None = None, hora_local: int | None = None,
           nota_juizo: float | None = None, credencial_disponivel: bool = False,
           nota_minima: float | None = None, jogos=JOGOS) -> dict:
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
    if canal in CANAIS_COM_CREDENCIAL and not credencial_disponivel:
        return {"publica": False, "numeros": numeros,
                "motivo": "%s exige credencial que esta execução não tem (%s)"
                          % (canal, CANAIS_COM_CREDENCIAL[canal])}

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

    plano_texto = _sem_acento(texto)
    for termo in TERMOS_INVENTADOS:
        if _sem_acento(termo) in plano_texto:
            return {"publica": False, "numeros": numeros,
                    "motivo": "mecânica que os jogos da casa não têm: \"%s\" (fato inventado)" % termo}

    citados = jogos_citados(texto, jogos)
    numeros["jogos_citados"] = sorted(citados)
    for jogo, trecho, fato in CONTRADICOES:
        if jogo in citados and _sem_acento(trecho) in plano_texto:
            return {"publica": False, "numeros": numeros,
                    "motivo": "contradiz fato conferido: \"%s\" — %s" % (trecho, fato)}
    if len(citados) > 1:
        return {"publica": False, "numeros": numeros,
                "motivo": "fala de %d jogos ao mesmo tempo (%s): um assunto por post"
                          % (len(citados), ", ".join(sorted(citados)))}

    recentes = historico_do_canal(publicacoes, canal)
    numeros["historico_do_canal"] = len(recentes)

    minha_forma = forma(texto)
    for antigo in recentes[:JANELA_DE_FORMA]:
        texto_antigo = str(antigo.get("texto") or "")
        if jogos_citados(texto_antigo, jogos) != citados:
            continue  # forma só se compara dentro do mesmo assunto
        if mesma_forma(minha_forma, antigo.get("forma") if isinstance(antigo.get("forma"), dict) else forma(texto_antigo)):
            return {"publica": False, "numeros": numeros,
                    "motivo": "mesma forma de um post recente do canal (abertura %s, %d frases, %d hashtags): %s"
                              % (minha_forma["tipo_abertura"], minha_forma["frases"],
                                 minha_forma["hashtags"], str(antigo.get("titulo") or "")[:50])}

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

    # Texto igual, mesmo com palavras novas, não passa — nunca. A janela de 40 comparação por
    # semelhança não cobre a história inteira; repetição EXATA não tem idade que a desculpe.
    alvo = _sem_acento(" ".join(texto.split()))
    for antigo in recentes[:500]:
        anterior = _sem_acento(" ".join(str(antigo.get("texto") or "").split()))
        if anterior and anterior == alvo:
            return {"publica": False, "numeros": numeros,
                    "motivo": "texto repetido: exatamente igual a um já publicado neste canal: \"%s\""
                              % str(antigo.get("titulo") or "")[:50]}

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
        minimo = NOTA_MINIMA if nota_minima is None else float(nota_minima)
        numeros["nota_juizo"] = round(float(nota_juizo), 3)
        numeros["nota_minima"] = minimo
        if float(nota_juizo) < minimo:
            return {"publica": False, "numeros": numeros,
                    "motivo": "nota do juízo abaixo do mínimo (%.2f < %.2f)" % (float(nota_juizo), minimo)}

    if not recentes:
        numeros["primeira_do_canal"] = True
    return {"publica": True, "motivo": "passou: janela ok, título próprio, um assunto, forma nova, texto novo%s" %
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
        print("uso: portao-publicacao.py <candidato.json> --canal site [--hora 14] [--credencial]")
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
    print(json.dumps(avalia(cand, canal=canal, publicacoes=pub, calendario=cal, hora_local=hora,
                            credencial_disponivel="--credencial" in sys.argv),
                     ensure_ascii=False, indent=2))
