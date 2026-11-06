#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Redator: a invenção do post — pauta, ângulo, texto e a decisão de publicar.

POR QUE EXISTE (06/11/2026). O dono mediu o resultado e o resultado era vergonhoso: 106 posts
sociais em 5 canais e quatro posts seguidos com a MESMA estrutura ("PRANCHETA ... CEIFALUME
... dois jogos, um dev solo brasileiro"). A causa não era preguiça do motor de texto: era o
pedido. O postador mandava ao motor uma lista de fatos dos DOIS jogos, sempre na mesma ordem,
com um tema sorteado por contador e, quando o motor falhava, uma fila fixa de 7 textos. Motor
nenhum inventa variedade quando a pergunta é sempre a mesma.

O que este arquivo faz, em ordem:

  1. PAUTA — decide sobre o que falar: UM assunto (um jogo, o ofício ou a casa) e UM ângulo
     (mecânica por dentro, dica de jogador, número medido, bastidor, cena, convite...).
     Ângulo tem janela de descanso; par (ângulo, assunto) tem janela maior. Não existe
     "tema 27 da lista".
  2. PEDIDO — monta a pergunta ao motor com os fatos DAQUELE assunto, o ângulo e a forma
     exigida (tamanho, hashtag, tipo de abertura). Proíbe citar outro jogo: é a regra que
     mata o "dois jogos, um dev solo".
  3. CANDIDATOS — pede 5 textos de 5 pautas diferentes. Não é o primeiro que chega.
  4. JUÍZO — pontua cada candidato com o gosto da casa (`juizo.py`) e normaliza a nota.
  5. PORTÃO — só publica o que passa no `portao-publicacao.py`. Se nenhum passar, NÃO
     PUBLICA e registra o motivo. Recusar é resultado legítimo, e é o oposto de automático.
  6. MEMÓRIA — grava no `posts/repertorio.json` o que foi dito, com ângulo, assunto, fatos e
     forma, para a próxima pauta não repetir.

Nada aqui toca a rede: o motor de texto é INJETADO (`motor(pedido) -> texto`). Isso permite
provar, offline e sem segredo, que 200 ciclos não repetem — é o que `testes-redator.py` faz.

Hora: a casa só "sabe" a melhor hora quando há amostra que sustente (`posts/aprendizado.json`,
regra de `aprender-horario.py`: 30 por hora e ganho acima de um desvio). Sem isso, a hora é a
janela declarada — e o texto da decisão diz isso com todas as letras, em vez de fingir estudo.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FATOS_PADRAO = os.path.join(RAIZ, "posts", "fatos.json")
REPERTORIO_PADRAO = os.path.join(RAIZ, "posts", "repertorio.json")
APRENDIZADO = os.path.join(RAIZ, "posts", "aprendizado.json")

# Janelas de descanso (declaradas, não aprendidas — não há amostra que sustente estudo).
JANELA_ANGULO = 6      # um ângulo não volta antes de 6 publicações
JANELA_PAR = 20        # o par (ângulo, assunto) não volta antes de 20
CANDIDATOS = 5         # pautas por ciclo: cinco textos para escolher um
LIMITE_DO_PEDIDOO = 540  # `cerebro_com_motivo` corta o pedido em 560 caracteres
NOTA_DE_REFERENCIA = 6.0  # nota de um post sólido no juízo da casa (5 traços positivos)
# Piso do ciclo: um post precisa de pelo menos metade dos traços de um post sólido (3 de 6).
# Abaixo disso não é post ruim de forma pontual — é post sem conteúdo, e a casa não publica.
NOTA_MINIMA_DO_CICLO = 0.5

JOGOS = ("prancheta", "ceifalume")
RODADAS = 2            # quantas levas de 5 textos antes de recusar

# Nome de exibição de cada assunto — o motor precisa saber do que está falando.
ASSUNTOS = {
    "prancheta": "Prancheta (gestão de futebol, navegador e Android)",
    "ceifalume": "Ceifalume (fazenda idle noturna, navegador e Android)",
    "oficio": "o ofício de fazer jogo sozinho",
    "casa": "os canais da casa",
}

# Formatos: (caracteres, hashtags). Rotacionados por posição para os candidatos não saírem
# todos do mesmo tamanho — texto de tamanho fixo é a primeira marca de robô.
FORMATOS = ((140, 0), (200, 1), (180, 1), (160, 0), (220, 2))


# ------------------------------------------------------------------ ângulos
# Cada ângulo é uma PERGUNTA diferente sobre o mesmo jogo. É isto que impede a repetição
# de estrutura: "dica de jogador" e "bastidor de erro" não podem sair com a mesma forma.
ANGULOS = {
    "mecanica_por_dentro": {
        "nome": "mecânica por dentro",
        "classes": ("mecanica",),
        "pedido": "ensine como UMA dessas mecanicas funciona, para quem nunca jogou",
        "forma": "comece com verbo no imperativo, sem emoji, ate 3 frases",
    },
    "dica_de_jogador": {
        "nome": "dica de jogador",
        "classes": ("mecanica", "numero"),
        "pedido": "de uma dica concreta que so quem jogou descobriria",
        "forma": "comece pelo problema do jogador, nao pelo nome do jogo",
    },
    "numero_medido": {
        "nome": "número medido",
        "classes": ("numero",),
        "pedido": "use UM desses numeros como gancho e explique o que ele significa no jogo",
        "forma": "o numero aparece na primeira frase; nada de numero inventado",
    },
    "pergunta_ao_publico": {
        "nome": "pergunta ao público",
        "classes": ("mecanica", "cultura"),
        "pedido": "faca uma pergunta especifica e respondivel sobre o jogo",
        "forma": "a pergunta e a ultima frase; sem hashtag; proibido 'o que voce acha'",
    },
    "bastidor_de_erro": {
        "nome": "bastidor de erro",
        "classes": ("bastidor",),
        "pedido": "conte um detalhe de bastidor do desenvolvimento e o que ele obrigou a muda",
        "forma": "comece pelo fato, sem emoji e sem superlativo",
    },
    "o_que_nao_tem": {
        "nome": "o que não tem",
        "classes": ("cultura", "disponibilidade"),
        "pedido": "diga o que o jogo NAO tem e por que isso foi escolha, sem soar propaganda",
        "forma": "comece pelo que nao tem; nao use a palavra gratis na primeira frase",
    },
    "cena_de_dois_segundos": {
        "nome": "cena de dois segundos",
        "classes": ("mecanica", "cultura"),
        "pedido": "descreva uma cena concreta de 2 segundos de jogo, no presente",
        "forma": "sem lista e sem dois pontos; no maximo 3 frases; nada de nome de recurso",
    },
    "comparacao_honesta": {
        "nome": "comparação honesta",
        "classes": ("disponibilidade", "mecanica"),
        "pedido": "compare duas formas de jogar e diga a desvantagem real de cada uma",
        "forma": "use 'mas' ou 'porem' uma vez; sem emoji",
    },
    "marco_com_data": {
        "nome": "marco com data",
        "classes": ("marco",),
        "pedido": "anuncie um marco real com a data escrita, sem exagero",
        "forma": "a data aparece escrita por extenso numerica; proibido 'finalmente'",
    },
    "convite_a_testar": {
        "nome": "convite a testar",
        "classes": ("mecanica", "disponibilidade"),
        "pedido": "peca testadores dizendo o que o testador ganha e o que a casa ganha",
        "forma": "termine com um convite curto; sem hashtag",
    },
    "tres_passos": {
        "nome": "três passos",
        "classes": ("mecanica", "disponibilidade"),
        "pedido": "liste 3 passos numerados para comecar a jogar agora",
        "forma": "use 1. 2. 3. no comeco das linhas; cada passo e uma acao",
    },
    "ponte_de_canal": {
        "nome": "ponte de canal",
        "classes": ("canal",),
        "pedido": "leve quem le para outro canal da casa, dizendo o que existe la de verdade",
        "forma": "cite o canal pelo nome; sem link no corpo do texto",
    },
    "devlog_aberto": {
        "nome": "devlog aberto",
        "classes": ("bastidor", "mecanica"),
        "pedido": "conte o que esta sendo feito agora e o que ainda nao funciona",
        "forma": "admita um limite do jogo na primeira frase",
    },
    "pergunta_que_ensina": {
        "nome": "pergunta que ensina",
        "classes": ("mecanica", "numero"),
        "pedido": "faca uma pergunta cuja resposta ensina uma tatica do jogo",
        "forma": "comece com uma pergunta em segunda pessoa usando 'você' com acento, e termine com '?'",
    },
}


# ------------------------------------------------------------------ utilidades
def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower()


def _hash(*partes):
    return hashlib.sha256("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()


def _modulo(nome):
    caminho = os.path.join(RAIZ, "tools", nome + ".py")
    spec = importlib.util.spec_from_file_location(nome.replace("-", "_"), caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_porao = {}


def portao():
    if "portao" not in _porao:
        _porao["portao"] = _modulo("portao-publicacao")
    return _porao["portao"]


def juizo():
    """O juízo da casa — opcional: sem ele, a nota é neutra e a decisão diz isso."""
    if "juizo" not in _porao:
        try:
            _porao["juizo"] = _modulo("juizo")
        except Exception:
            _porao["juizo"] = None
    return _porao["juizo"]


def ler_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def gravar_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")


def carregar_fatos(caminho=None):
    dados = ler_json(caminho or FATOS_PADRAO, {})
    itens = dados.get("fatos") if isinstance(dados, dict) else dados
    return [f for f in (itens or []) if isinstance(f, dict) and f.get("afirmacao") and f.get("assunto")]


def carregar_repertorio(caminho=None):
    dados = ler_json(caminho or REPERTORIO_PADRAO, {})
    if not isinstance(dados, dict):
        dados = {}
    dados.setdefault("_o_que_e", "memoria de pauta: o que a casa ja disse, com angulo, assunto e forma")
    dados.setdefault("usos", [])
    dados.setdefault("fatos_de_uma_vez", [])
    return dados


def _iso(agora=None):
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    return agora.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ fatos
def fatos_vencidos(fato, hoje):
    limite = fato.get("validade_dias")
    if not limite or not fato.get("quando"):
        return False
    try:
        quando = datetime.date.fromisoformat(str(fato["quando"])[:10])
        return (hoje - quando).days > int(limite)
    except (ValueError, TypeError):
        return False


def fatos_vivos(fatos, repertorio=None, hoje=None):
    """Fatos que podem ser usados agora: não vencidos e não gastos (os de uma vez só)."""
    hoje = hoje or datetime.date.today()
    gastos = set((repertorio or {}).get("fatos_de_uma_vez") or [])
    vivos = []
    for f in fatos:
        if fatos_vencidos(f, hoje):
            continue
        if f.get("usa_uma_vez") and f.get("id") in gastos:
            continue
        vivos.append(f)
    return vivos


def assuntos_disponiveis(fatos, classes):
    return sorted({f["assunto"] for f in fatos if f.get("classe") in classes})


# ------------------------------------------------------------------ pauta
def _recencia(usos, angulo=None, assunto=None):
    """Quantos usos atrás foi a última vez (0 = o mais recente). None = nunca usado."""
    for distancia, uso in enumerate(reversed(usos)):
        if not isinstance(uso, dict):
            continue
        if angulo is not None and uso.get("angulo") != angulo:
            continue
        if assunto is not None and uso.get("assunto") != assunto:
            continue
        return distancia
    return None


def pautas_possiveis(fatos, repertorio=None, hoje=None):
    """Todas as combinações (ângulo, assunto) válidas agora, já ordenadas por frieza."""
    repertorio = repertorio or {}
    usos = repertorio.get("usos") or []
    vivos = fatos_vivos(fatos, repertorio, hoje)
    pautas = []
    for nome_angulo, angulo in ANGULOS.items():
        recente_angulo = _recencia(usos, angulo=nome_angulo)
        if recente_angulo is not None and recente_angulo < JANELA_ANGULO:
            continue
        for assunto in assuntos_disponiveis(vivos, angulo["classes"]):
            recente_par = _recencia(usos, angulo=nome_angulo, assunto=assunto)
            if recente_par is not None and recente_par < JANELA_PAR:
                continue
            recente_assunto = _recencia(usos, assunto=assunto)
            elegiveis = [f for f in vivos if f["assunto"] == assunto and f.get("classe") in angulo["classes"]]
            if not elegiveis:
                continue
            pautas.append({
                "angulo": nome_angulo,
                "angulo_nome": angulo["nome"],
                "assunto": assunto,
                "fatos": [f["id"] for f in elegiveis],
                "_ordem": (
                    0 if recente_angulo is None else 1,
                    -(recente_angulo if recente_angulo is not None else 10 ** 6),
                    -(recente_assunto if recente_assunto is not None else 10 ** 6),
                    -len(elegiveis),
                    _hash(nome_angulo, assunto),
                ),
            })
    pautas.sort(key=lambda p: p["_ordem"])
    return pautas


def escolher_pautas(fatos, repertorio=None, quantas=CANDIDATOS, hoje=None, excluir_angulos=()):
    """Escolhe as pautas do ciclo: ângulos diferentes e, se der, assuntos diferentes.

    `excluir_angulos` serve à segunda rodada: o que já foi pedido nesta mesma hora não se
    repete dentro do ciclo — variar é o ponto.
    """
    excluir = {a for a in (excluir_angulos or ())}
    possiveis = [p for p in pautas_possiveis(fatos, repertorio, hoje) if p["angulo"] not in excluir]
    escolhidas, assuntos = [], set()
    for pauta in possiveis:
        if pauta["assunto"] in assuntos:
            continue
        escolhidas.append(dict(pauta))
        assuntos.add(pauta["assunto"])
        if len(escolhidas) >= quantas:
            break
    if len(escolhidas) < quantas:  # assunto acabou: aceita repetir assunto, nunca o ângulo
        ja = {p["angulo"] for p in escolhidas}
        for pauta in possiveis:
            if pauta["angulo"] in ja:
                continue
            escolhidas.append(dict(pauta))
            ja.add(pauta["angulo"])
            if len(escolhidas) >= quantas:
                break
    for i, pauta in enumerate(escolhidas):
        pauta["limite"], pauta["hashtags"] = FORMATOS[i % len(FORMATOS)]
        pauta.pop("_ordem", None)
        # Assunto que não é jogo precisa apoiar em UM jogo pelo nome: o gosto da casa cobra
        # que o post cite a casa ou um jogo dela (`juizo.tracos: cita_jogo`). Sem isso, todo
        # post de "ofício" ou "canais" nasceria com nota baixa e nunca sairia.
        if pauta["assunto"] not in JOGOS:
            pauta["jogo_de_apoio"] = JOGOS[int(_hash(pauta["angulo"], pauta["assunto"])[:8], 16) % len(JOGOS)]
    return escolhidas


# ------------------------------------------------------------------ pedido ao motor
def _encurtar(texto, limite):
    """Corta em limite de palavra: pedido cortado no meio de palavra confunde o motor."""
    texto = " ".join(str(texto or "").split())
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    if " " in corte:
        corte = corte[:corte.rfind(" ")]
    return corte.rstrip(" ,.;:—")


def montar_pedido(pauta, fatos, aberturas_proibidas=()):
    """A pergunta ao motor: um assunto, um ângulo, fatos só daquele assunto e a forma exigida.

    O corte em LIMITE_DO_PEDIDOO não é estética: `cerebro_com_motivo` trunca em 560
    caracteres, e pedido truncado no meio é pedido perdido (era o que acontecia).
    """
    angulo = ANGULOS[pauta["angulo"]]
    meus = [f for f in fatos if f.get("id") in (pauta.get("fatos") or [])]
    if not meus:
        meus = [f for f in fatos if f.get("assunto") == pauta["assunto"]]
    # Assunto que não é jogo: prefere fato que não nomeie jogo, para o texto não acabar
    # falando de dois jogos (o portão recusaria).
    def _nomeia_jogo(f):
        plano = _sem_acento(f.get("afirmacao"))
        return any(_sem_acento(j) in plano for j in JOGOS)

    meus.sort(key=lambda f: (pauta["assunto"] not in JOGOS and _nomeia_jogo(f),
                             _hash(pauta["angulo"], f["id"])))
    escolhidos = meus[:2]
    proibidas = [a for a in aberturas_proibidas if a][:2]

    apoio = (" Nao cite outro jogo da casa." if pauta["assunto"] in JOGOS else
             " Cite %s pelo nome, e so ele." % ASSUNTOS.get(pauta.get("jogo_de_apoio"), "").split(" (")[0])

    # Hashtag em português, e do assunto da vez: sugerir #prancheta num post de ceifalume é
    # convidar o motor a falar do outro jogo — que o portão recusa por "dois assuntos".
    TAGS_DO_ASSUNTO = {
        "ceifalume": "use #ceifalume ou #jogobrasileiro",
        "prancheta": "use #prancheta ou #jogobrasileiro",
        "casa": "use #gamedevbr ou #godot",
        "oficio": "use #godot ou #gamedevbr",
    }

    def monta(fatos_usados, angulo_usado, tam_afirmacao):
        corpo = " ".join(_encurtar(f["afirmacao"], tam_afirmacao) for f in fatos_usados)
        pedido = (
            "Posts da casa REBOCL BRANK (dev solo, Brasil). UM post de rede social, ate %d "
            "caracteres, portugues do Brasil. ASSUNTO UNICO: %s. ANGULO: %s. "
            "FATOS (verdade; nao invente numero, data nem mecanica fora deles): %s. FORMA: %s. "
            "%s No maximo %d hashtag(s), em portugues: %s.%s"
            % (pauta.get("limite", 180), ASSUNTOS.get(pauta["assunto"], pauta["assunto"]),
               angulo_usado["pedido"], corpo, angulo_usado["forma"],
               apoio, int(pauta.get("hashtags", 1)), TAGS_DO_ASSUNTO.get(pauta["assunto"], "#godot"),
               (" Nao comece com: " + "; ".join(proibidas) + ".") if proibidas else "")
        )
        return pedido

    # Encolhe em etapas declaradas, sempre com saída: nunca um while que não termina.
    for quantos, tam, reduz_angulo in ((2, 110, False), (1, 110, False), (1, 80, False),
                                       (1, 60, True), (1, 40, True), (0, 40, True)):
        angulo_usado = angulo
        if reduz_angulo:
            angulo_usado = dict(angulo, pedido=_encurtar(angulo["pedido"], 42),
                                forma=_encurtar(angulo["forma"], 36))
        pedido = monta(escolhidos[:quantos], angulo_usado, tam)
        if len(pedido) <= LIMITE_DO_PEDIDOO:
            return pedido
    return pedido[:LIMITE_DO_PEDIDOO]


def limpar_texto(texto, limite=220):
    """Tira o que motor de texto costuma colar: cerca de código, aspas, rótulo, sobra."""
    t = str(texto or "")
    t = re.sub(r"```[a-zA-Z]*", "", t).replace("```", "")
    t = " ".join(t.split())
    t = re.sub(r"^(post|texto|legenda)\s*[:\-]\s*", "", t, flags=re.I)
    t = t.strip().strip('"').strip("“”").strip()
    if len(t) > limite:
        corte = t[:limite]
        fim = max(corte.rfind(". "), corte.rfind("! "), corte.rfind("? "))
        t = (corte[:fim + 1] if fim > 40 else corte.rstrip(" ,.;:—")).strip()
    return t


def titulo_do_texto(texto, assunto):
    """Título = primeira frase. O portão exige 12 a 90 caracteres; abaixo disso, completa."""
    t = " ".join(str(texto or "").split())
    primeira = re.split(r"(?<=[.!?])\s+", t)[0] if t else ""
    primeira = primeira.strip()[:88]
    if len(primeira) < 12:
        primeira = ("%s — %s" % (assunto.capitalize(), t or primeira)).strip()[:88]
    return primeira


# ------------------------------------------------------------------ juízo e hora
def nota_do_texto(texto):
    """(nota 0..1, detalhe). Normaliza a pontuação do juízo pela nota de um post sólido."""
    j = juizo()
    if j is None:
        return None, {"motivo": "juízo indisponível: nota neutra"}
    pontos, contribuicoes = j.pontuar(texto)
    nota = max(0.0, min(1.0, float(pontos) / NOTA_DE_REFERENCIA))
    return round(nota, 3), {"pontos": pontos, "contribuicoes": contribuicoes[:4],
                            "referencia": NOTA_DE_REFERENCIA}


def hora_aprendida(caminho=None):
    """(hora|None, motivo). Só existe hora "sabida" com amostra que sustente."""
    dados = ler_json(caminho or APRENDIZADO, {})
    if not isinstance(dados, dict):
        return None, "sem arquivo de aprendizado: hora não aprendida"
    if not dados.get("confiavel") or dados.get("melhor_hora") is None:
        return None, "hora não aprendida (%s)" % (dados.get("motivo") or "sem prova")
    return int(dados["melhor_hora"]), "hora aprendida com prova: %sh (%s)" % (
        dados["melhor_hora"], dados.get("motivo") or "")


# ------------------------------------------------------------------ ciclo
def ciclo(motor, *, fatos=None, repertorio=None, canal="site", publicacoes=None,
          calendario=None, hora_local=None, quantas=CANDIDATOS, credencial_disponivel=False,
          hoje=None, agora=None, registrar=True, caminho_repertorio=None):
    """Um ciclo completo de invenção + juízo + portão. Nunca publica: devolve a decisão.

    `motor(pedido) -> texto` é injetado. Sem rede aqui, dentro do possível: quem fala com o
    mundo é o motor e quem publica é o postador.
    """
    fatos = fatos if fatos is not None else carregar_fatos()
    repertorio = repertorio if repertorio is not None else carregar_repertorio()
    p = portao()
    publicacoes = _recente_primeiro(publicacoes)
    usos = repertorio.get("usos") or []
    aberturas = [str(u.get("abertura") or "") for u in usos[-3:] if u.get("abertura")]

    pautas, candidatos, recusas, vistos = [], [], [], set()
    tentados = set()
    # DUAS RODADAS: se os 5 primeiros textos não passarem, a casa tenta outros 5 ângulos antes
    # de dizer não. Insistir uma vez é autonomia; insistir para sempre é teimosia — por isso o
    # número é fixo, declarado e o motivo da recusa diz quantos textos foram tentados.
    for _rodada in range(RODADAS):
        novas = escolher_pautas(fatos, repertorio, quantas=quantas, hoje=hoje,
                                excluir_angulos=tentados)
        if not novas:
            break
        pautas.extend(novas)
        tentados.update(p["angulo"] for p in novas)
        candidatos, recusas, vistos, passaram = _pedir(novas, motor, fatos, aberturas, canal,
                                                       publicacoes, calendario, hora_local,
                                                       credencial_disponivel, candidatos,
                                                       recusas, vistos)
        if passaram:
            break

    if not pautas:
        return {"publica": False, "motivo": "nenhuma pauta disponível: todo ângulo e assunto em descanso",
                "candidatos": [], "recusas": [], "pautas": []}

    passaram = [c for c in candidatos if c["decisao"].get("publica")]
    if not passaram:
        return {"publica": False, "motivo": "nenhum dos %d textos passou: %s" % (
            max(len(candidatos), len(recusas)), "; ".join(str(r.get("motivo"))[:70] for r in recusas[:3]) or "sem texto"),
            "candidatos": candidatos, "recusas": recusas, "pautas": pautas}

    passaram.sort(key=lambda c: (-(c["nota"] or 0), len(c["texto"])))
    melhor = passaram[0]
    if registrar:
        registrar_uso(repertorio, melhor, quando=_iso(agora), canal=canal,
                      caminho=caminho_repertorio)
    return {"publica": True,
            "motivo": melhor["decisao"]["motivo"] + " · nota %.2f" % (melhor["nota"] or 0),
            "escolhido": melhor, "candidatos": candidatos, "recusas": recusas, "pautas": pautas,
            "nota": melhor["nota"], "rodadas": (len(pautas) + quantas - 1) // quantas}


def _pedir(pautas, motor, fatos, aberturas, canal, publicacoes, calendario, hora_local,
           credencial_disponivel, candidatos, recusas, vistos):
    """Pede um texto por pauta, julga e passa pelo portão. Devolve o acumulado da rodada."""
    p = portao()
    for pauta in pautas:
        pedido = montar_pedido(pauta, fatos, aberturas)
        try:
            bruto = motor(pedido)
        except Exception as erro:  # motor quebrado não derruba o ciclo
            recusas.append({"pauta": pauta, "motivo": "motor falhou: " + str(erro)[:80]})
            continue
        texto = limpar_texto(bruto, pauta.get("limite", 220))
        if not texto or len(texto) < 40:
            recusas.append({"pauta": pauta, "motivo": "motor não devolveu texto utilizável"})
            continue
        chave = p.forma(texto)["abertura"]
        if chave and chave in vistos:
            recusas.append({"pauta": pauta, "motivo": "candidato com a mesma abertura de outro"})
            continue
        vistos.add(chave)
        titulo = titulo_do_texto(texto, pauta["assunto"])
        nota, detalhe_nota = nota_do_texto(texto)
        decisao = p.avalia({"titulo": titulo, "texto": texto}, canal=canal,
                           publicacoes=publicacoes, calendario=calendario,
                           hora_local=hora_local, nota_juizo=nota,
                           nota_minima=NOTA_MINIMA_DO_CICLO,
                           credencial_disponivel=credencial_disponivel)
        candidatos.append({"pauta": pauta, "texto": texto, "titulo": titulo, "nota": nota,
                           "detalhe_nota": detalhe_nota, "decisao": decisao,
                           "forma": p.forma(texto)})
        if not decisao.get("publica"):
            recusas.append({"pauta": pauta, "motivo": decisao.get("motivo"),
                            "numeros": decisao.get("numeros")})
    return candidatos, recusas, vistos, [c for c in candidatos if c["decisao"].get("publica")]


def registrar_uso(repertorio, candidato, quando=None, canal="site", caminho=None):
    """Grava o que foi dito: ângulo, assunto, fatos, forma e abertura. Memória, não enfeite."""
    pauta = candidato.get("pauta") or {}
    f = candidato.get("forma") or portao().forma(candidato.get("texto"))
    uso = {
        "quando": quando or _iso(),
        "canal": canal,
        "angulo": pauta.get("angulo"),
        "assunto": pauta.get("assunto"),
        "fatos": list(pauta.get("fatos") or []),
        "abertura": f.get("abertura"),
        "tipo_abertura": f.get("tipo_abertura"),
        "esqueleto": list(f.get("esqueleto") or []),
        "hashtags": f.get("hashtags"),
        "nota": candidato.get("nota"),
        "texto": str(candidato.get("texto") or "")[:160],
    }
    repertorio.setdefault("usos", []).append(uso)
    repertorio["usos"] = repertorio["usos"][-500:]
    gastos = repertorio.setdefault("fatos_de_uma_vez", [])
    for fato_id in pauta.get("fatos") or []:
        if fato_id not in gastos:
            gastos.append(fato_id)
    repertorio["ultimo"] = uso
    if caminho:
        gravar_json(caminho, repertorio)
    return uso


def _recente_primeiro(publicacoes):
    """Histórico do portão SEMPRE do mais novo para o mais antigo.

    DEFEITO CORRIGIDO (06/11/2026): o portão compara "as últimas 40 publicações" usando
    `recentes[:40]`. Se quem chama entregar a lista em ordem cronológica (mais antigo
    primeiro), o portão compara com as 40 PRIMEIRAS da história e nunca vê o post de ontem —
    dedupe que não dedupa e repetição que passa. Aqui a ordem é resolvida por data quando
    existe, e a lista é devolvida na ordem que o portão espera.
    """
    lista = [p for p in (publicacoes or []) if isinstance(p, dict)]
    if not lista:
        return []

    def _chave(item):
        quando = str(item.get("quando") or "")
        for formato in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M UTC"):
            try:
                return datetime.datetime.strptime(quando, formato).timestamp()
            except ValueError:
                continue
        return None

    chaves = [_chave(item) for item in lista]
    if all(c is not None for c in chaves):
        # Empate de data (comum: vários posts no mesmo minuto) preserva a ordem recebida —
        # ordenar por data com empate embaralharia a lista e o portão compararia com o post
        # errado. Foi o que aconteceu no primeiro teste deste arquivo.
        ordenado = sorted(enumerate(lista), key=lambda par: (-chaves[par[0]], par[0]))
        return [item for _, item in ordenado]
    return lista


def historico_para_portao(publicacoes_md=None):
    """Converte o arquivo de posts publicados em histórico do portão (com forma medida)."""
    texto = ""
    try:
        with open(publicacoes_md or os.path.join(RAIZ, "posts", "posts-publicados.md"),
                  encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return []
    itens = []
    for bloco in re.split(r"\n## ", texto):
        achado = re.match(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2} UTC)\n(.+)", bloco.strip(), re.S)
        if achado:
            corpo = " ".join(achado.group(2).split())
            itens.append({"canal": "site", "quando": achado.group(1), "texto": corpo[:400],
                          "titulo": corpo.split(".")[0][:88], "forma": portao().forma(corpo)})
    itens.reverse()
    return itens


if __name__ == "__main__":  # pragma: no cover - uso manual
    import sys
    modo = sys.argv[1] if len(sys.argv) > 1 else "--pautas"
    if modo == "--pautas":
        fatos = carregar_fatos()
        rep = carregar_repertorio()
        escolhidas = escolher_pautas(fatos, rep)
        print("pautas do próximo ciclo (%d de %d fatos vivos):" % (len(escolhidas), len(fatos_vivos(fatos, rep))))
        for pauta in escolhidas:
            print(" · %-22s assunto=%-11s limite=%d hashtags=%d fatos=%s"
                  % (pauta["angulo"], pauta["assunto"], pauta["limite"], pauta["hashtags"],
                     ",".join(pauta["fatos"][:3])))
        hora, motivo = hora_aprendida()
        print("hora:", motivo)
        raise SystemExit(0)
    print("uso: redator.py [--pautas]")
    raise SystemExit(2)
