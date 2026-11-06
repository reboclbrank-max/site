#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Redator do vídeo — o texto do gameplay sai de um ÂNGULO declarado e dos fatos da partida.

POR QUE EXISTE (06/11/2026). O canal repetiu o mesmo título de gameplay três vezes
(`f5kQFOQs0To`, `GuE7af6dYo8`, `2qsSknSyeAs`). O portão de forma passou a recusar repetição —
e aí apareceu o outro lado: com o texto do kit sendo um MOLDE, a segunda gravação é recusada
sempre (título 0.94 de semelhança, descrição 1.00 de Jaccard). Freio sem redator é canal parado.

O que este arquivo faz, e o que ele NÃO faz:

  * escolhe um ÂNGULO entre os DECLARADOS abaixo — não há sorteio nem geração livre de texto;
  * escreve só com números MEDIDOS naquela partida (mudas, colheitas, toques, minutos) e com
    fatos do jogo que estão no kit oficial (`tools/kit-youtube.py`);
  * passa o texto pelo MESMO portão dos outros canais (`tools/portao-publicacao.py`, canal
    youtube, janela 9h–22h de Brasília) contra o histórico do canal;
  * recusa quando não há fato para dizer ou quando nenhum ângulo passa — e diz o número e o
    motivo da recusa. Melhor não publicar do que publicar o mesmo de novo.

Ângulo declarado não é enfeite: é o contrato de variedade. Cada um tem abertura, esqueleto de
frases e quantidade de hashtags diferentes, porque é isso que o portão compara quando pergunta
"isto é o mesmo post de novo?".
"""
import importlib.util
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JANELA_DO_CANAL = {"janela": {"inicio": 9, "fim": 22}}
FUSO_DO_CANAL = -3

# Fatos do jogo que o texto pode afirmar — todos vêm do kit oficial, não daqui.
FATOS_DO_KIT = {
    "ceifalume": {
        "mecanica": "plante, colha e negocie à luz da lanterna",
        "atencao": "as plantações crescem por até 8 horas mesmo com o jogo fechado",
        "onde": "grátis no navegador ou no Android, sem conta",
        "motor": "feito com Godot, feito no Brasil",
    },
}


def _modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _kit_gameplay():
    return _modulo("kit_gameplay", "kit-gameplay.py")


def _kit_youtube():
    return _modulo("kit_youtube", "kit-youtube.py")


def _portao():
    return _modulo("portao_publicacao", "portao-publicacao.py")


def hora_local_do_canal(agora=None):
    import datetime
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=datetime.timezone.utc)
    return (agora + datetime.timedelta(hours=FUSO_DO_CANAL)).hour


# ------------------------------------------------------------------ os ângulos declarados
# Cada ângulo é uma forma de contar a MESMA partida. `titulo` e `corpo` recebem os fatos medidos.
# Regras que valem para todos (e que a suíte cobra):
#   - nada de "garantido", "viral", "imperdível", "em breve";
#   - nada de mecânica que o jogo não tem (inimigo, tiro, corrida, chefe);
#   - todo número escrito existe no relatório da partida ou no kit;
#   - a linha de origem e os links oficiais ficam em todos.
ANGULOS = [
    {
        "id": "numeros",
        "hashtags": ["#jogobrasileiro"],
        "titulo": lambda f, j: "%d colheitas em %d min de %s" % (f["colhidas"], f["minutos"], f["nome"]),
        "corpo": lambda f, j: [
            "Em %d minutos de gravação o agente plantou %d mudas e colheu %d, sem esperar parado em nenhum momento."
            % (f["minutos"], f["plantadas"], f["colhidas"]),
            "Cada célula do campo tem o seu próprio tempo de crescimento, e o celeiro guarda o que sobra.",
            "Foram %d toques na tela, cerca de %d por minuto, distribuídos entre semear e colher."
            % (f["toques"], f["toques_por_minuto"]),
        ],
    },
    {
        "id": "pergunta",
        "hashtags": [],
        "titulo": lambda f, j: "Quantas colheitas cabem em %d minutos de %s?" % (f["minutos"], f["nome_curto"]),
        "corpo": lambda f, j: [
            "Quanto cabe em %d minutos de uma fazenda que cresce enquanto você olha para outro lado?"
            % f["minutos"],
            "Nesta partida deu %d colheitas, %d mudas semeadas e %d toques espalhados pelo terreno."
            % (f["colhidas"], f["plantadas"], f["toques"]),
            "A resposta curta é que o limite não é a pressa: é o tempo de cada planta."
        ],
    },
    {
        "id": "rotulo",
        "hashtags": ["#godot", "#jogobrasileiro"],
        "titulo": lambda f, j: "%s: %d toques e %d colheitas na partida de %d min" % (
            f["nome_curto_upper"], f["toques"], f["colhidas"], f["minutos"]),
        "corpo": lambda f, j: [
            "Partida de hoje: %d mudas, %d colheitas e %d toques em %d minutos de tela."
            % (f["plantadas"], f["colhidas"], f["toques"], f["minutos"]),
            "Como se joga: %s; o que sobra da venda fica no celeiro." % j["mecanica"],
            "O jogo em si: %s, %s." % (j["onde"], j["motor"]),
        ],
    },
    {
        "id": "convite",
        "hashtags": ["#jogobrasileiro"],
        "titulo": lambda f, j: "Plante à luz da lanterna: %d mudas em %d min de %s" % (
            f["plantadas"], f["minutos"], f["nome_curto"]),
        "corpo": lambda f, j: [
            "Jogue no navegador e plante à luz da lanterna: nesta gravação saíram %d colheitas de %d mudas."
            % (f["colhidas"], f["plantadas"]),
            "Não precisa instalar nada nem criar conta: abre a página, toca no campo e espera a resposta.",
            "Com o jogo fechado, %s." % j["atencao"],
        ],
    },
    {
        "id": "bastidor",
        "hashtags": ["#godot", "#jogobrasileiro"],
        "titulo": lambda f, j: "Como um agente joga %s sozinho: %d min de gravação" % (
            f["nome_curto"], f["minutos"]),
        "corpo": lambda f, j: [
            "A gravação é do jogo rodando no navegador, capturada por um agente que olha o estado da tela e decide o próximo toque.",
            "Na prática: %d mudas semeadas, %d colheitas e %d toques em %d minutos de partida."
            % (f["plantadas"], f["colhidas"], f["toques"], f["minutos"]),
            "Nada de vídeo editado à mão: a legenda descreve a decisão tomada, e o áudio é sintetizado pela produção.",
        ],
    },
    {
        "id": "moedas",
        "precisa": ("moedas_inicio", "moedas_fim"),
        "hashtags": ["#jogobrasileiro"],
        "titulo": lambda f, j: "De %d a %d moedas em %d min de %s" % (
            f["moedas_inicio"], f["moedas_fim"], f["minutos"], f["nome_curto"]),
        "corpo": lambda f, j: [
            "A fazenda começou com %d moedas e terminou a gravação com %d no bolso."
            % (f["moedas_inicio"], f["moedas_fim"]),
            "O bolso não enche sozinho: cada moeda veio de colheita vendida, e cada compra saiu dele.",
            "É a diferença entre fazenda idle e passatempo de espera — o número mede decisão, não sorte.",
        ],
    },
    {
        "id": "cultivo",
        "precisa": ("celulas_prontas", "plantas"),
        "hashtags": [],
        "titulo": lambda f, j: "%d células com %s pronto no fim da partida" % (
            f["celulas_prontas"], f["plantas"][0]),
        "corpo": lambda f, j: [
            "No fim da gravação, %d das %d células do terreno estavam com planta pronta."
            % (f["celulas_prontas"], f["celulas_total"]),
            "O cultivo da partida foi %s." % " e ".join(f["plantas"]),
            "Nenhuma célula anda junto com a outra: cada uma tem o seu relógio de crescimento.",
        ],
    },
    {
        "id": "tutorial",
        "precisa": ("tutorial_segundos", "telas"),
        "hashtags": ["#godot", "#gamedevbr"],
        "titulo": lambda f, j: "Tutorial de %s resolvido em %s segundo" % (
            f["nome_curto"], str(f["tutorial_segundos"]).replace(".", ",")),
        "corpo": lambda f, j: [
            "O tutorial do jogo abriu e fechou em %s segundo, com %d toque."
            % (str(f["tutorial_segundos"]).replace(".", ","), f["tutorial_toques"]),
            "Depois disso ninguém digita nada: um agente olha a tela e escolhe onde tocar.",
            "A captura atravessou %d telas diferentes antes do campo ficar cheio." % f["telas"],
        ],
    },
    {
        "id": "compra",
        "precisa": ("compras",),
        "hashtags": ["#godot", "#jogobrasileiro"],
        "titulo": lambda f, j: "O que o agente comprou jogando %s: %s" % (
            f["nome_curto"], f["compras"][0]),
        "corpo": lambda f, j: [
            "As melhorias compradas nesta gravação: %s." % ", ".join(f["compras"]),
            "Cada uma saiu de moeda economizada colheita a colheita, dentro da mesma partida.",
            "O jogo é %s, e a produção é %s." % (j["motor"], j["onde"]),
        ],
    },
    {
        "id": "comparacao",
        "precisa": ("_anterior",),
        "hashtags": ["#devlog", "#jogobrasileiro"],
        "titulo": lambda f, j: "%d colheitas contra %d da partida anterior" % (
            f["colhidas"], f["_anterior"]["colhidas"]),
        "corpo": lambda f, j: [
            "Esta gravação colheu %d; a anterior, que já está no canal, tinha colhido %d."
            % (f["colhidas"], f["_anterior"]["colhidas"]),
            "Os toques foram %d agora e %d antes — tudo lido do relatório, nada estimado."
            % (f["toques"], f["_anterior"]["toques"]),
            "A fazenda muda de uma partida para a outra, e o registro do canal mostra a diferença.",
        ],
    },
]

# ------------------------------------------------------------------ perguntas do leitor
# O banco de formas não pode ser limitado ao número de modelos que alguém digitou. Cada
# PERGUNTA abaixo é uma forma diferente de abrir o mesmo assunto — intenções de leitor
# distintas, não sinônimos. O assunto vem de um FATO real da casa (posts/fatos.json), com
# origem e data, que ainda não foi usado em vídeo. Forma × fato é o estoque.
PERGUNTAS_DO_LEITOR = [
    {
        "id": "como_funciona",
        "hashtags": ["#jogobrasileiro"],
        "titulo": lambda fa, f: "Como funciona: %s" % _resumo(fa["afirmacao"]),
        "corpo": lambda fa, f: [
            "%s." % _maiuscula(fa["afirmacao"]),
            "Na gravação desta partida: %d mudas plantadas e %d colheitas em %d minutos."
            % (f["plantadas"], f["colhidas"], f["minutos"]),
            "O dado não veio de fórum: veio do próprio jogo, medido durante a captura.",
        ],
    },
    {
        "id": "onde_jogar",
        "hashtags": ["#jogobrasileiro"],
        "titulo": lambda fa, f: "Onde jogar %s sem instalar loja" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "%s." % _maiuscula(fa["afirmacao"]),
            "A partida do vídeo saiu do build web: %d colheitas em %d minutos de tela."
            % (f["colhidas"], f["minutos"]),
            "Nada de cadastro, compra ou espera para abrir o jogo.",
        ],
    },
    {
        "id": "quanto_rende",
        "hashtags": [],
        "titulo": lambda fa, f: "Quanto rende %s em %d minutos" % (f["nome_curto"], f["minutos"]),
        "corpo": lambda fa, f: [
            "A conta da partida: %d mudas, %d colheitas e %d toques em %d minutos."
            % (f["plantadas"], f["colhidas"], f["toques"], f["minutos"]),
            "%s." % _maiuscula(fa["afirmacao"]),
            "Todo número deste vídeo vem do relatório da gravação, não de estimativa.",
        ],
    },
    {
        "id": "quem_fe_z",
        "hashtags": ["#godot", "#gamedevbr"],
        "titulo": lambda fa, f: "Quem fez %s e por quê" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "%s." % _maiuscula(fa["afirmacao"]),
            "Uma pessoa só, em português do Brasil, com o jogo rodando no navegador durante a gravação.",
            "O vídeo mostra a partida medida: %d colheitas e %d mudas plantadas." % (
                f["colhidas"], f["plantadas"]),
        ],
    },
    {
        "id": "o_que_tem_dentro",
        "hashtags": ["#godot"],
        "titulo": lambda fa, f: "O que tem dentro de %s" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "%s." % _maiuscula(fa["afirmacao"]),
            "O que aparece na tela desta gravação é a partida de verdade: %d toques no campo." % f["toques"],
            "Sem corte de tela e sem fala: a legenda descreve a decisão tomada no momento.",
        ],
    },
    {
        "id": "por_que_gratis",
        "hashtags": [],
        "titulo": lambda fa, f: "Por que %s é grátis de verdade" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "A pergunta é justa. A resposta: %s." % fa["afirmacao"],
            "Nesta gravação, %d colheitas saíram de %d mudas, sem nada bloqueado por pagamento."
            % (f["colhidas"], f["plantadas"]),
            "O que sustenta a casa é o trabalho aparecer, não o jogador pagar.",
        ],
    },
    {
        "id": "como_foi_gravado",
        "hashtags": ["#godot", "#jogobrasileiro"],
        "titulo": lambda fa, f: "Como este vídeo de %s foi gravado" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "Nada aqui foi editado à mão: o build web rodou no navegador e um agente decidiu cada toque.",
            "%s." % _maiuscula(fa["afirmacao"]),
            "O relatório da gravação fecha em %d mudas e %d colheitas." % (f["plantadas"], f["colhidas"]),
        ],
    },
    {
        "id": "o_que_muda_depois",
        "hashtags": ["#jogobrasileiro", "#ceifalume"],
        "titulo": lambda fa, f: "O que muda em %s depois de %d minutos" % (f["nome_curto"], f["minutos"]),
        "corpo": lambda fa, f: [
            "Em %d minutos de partida o campo passou por %d mudas e %d colheitas." % (
                f["minutos"], f["plantadas"], f["colhidas"]),
            "%s." % _maiuscula(fa["afirmacao"]),
            "Quem joga vê a diferença no próprio terreno, não em número de fórum.",
        ],
    },
    {
        "id": "onde_esta_a_comunidade",
        "hashtags": ["#godot", "#comunidade"],
        "titulo": lambda fa, f: "Onde falar com quem fez %s" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "%s." % _maiuscula(fa["afirmacao"]),
            "Quem fez o jogo responde por lá — e o vídeo mostra o que essa pessoa construiu: %d colheitas na partida."
            % f["colhidas"],
            "O convite é para conversar sobre o jogo, não para inflar número.",
        ],
    },
    {
        "id": "requisito",
        "hashtags": ["#navegador"],
        "titulo": lambda fa, f: "O que %s pede para rodar" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "%s." % _maiuscula(fa["afirmacao"]),
            "Não pediu nada aqui: o build abriu no navegador e a gravação rodou %d toques em %d minutos."
            % (f["toques"], f["minutos"]),
            "Sem conta, sem instalação obrigatória e sem fila de espera.",
        ],
    },
    {
        "id": "genero",
        "hashtags": [],
        "titulo": lambda fa, f: "%s é idle farm — e o que isso quer dizer" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "Idle farm é o jogo que continua enquanto você não está olhando. Aqui, %s." % fa["afirmacao"],
            "Na partida gravada isso aparece nos números: %d mudas e %d colheitas em %d minutos."
            % (f["plantadas"], f["colhidas"], f["minutos"]),
            "Nada de reflexo rápido: o ritmo é o do campo.",
        ],
    },
    {
        "id": "bastidor_do_dia",
        "hashtags": ["#godot", "#gamedevbr"],
        "titulo": lambda fa, f: "Bastidor de %s: o que está por trás da partida" % f["nome_curto"],
        "corpo": lambda fa, f: [
            "O vídeo é uma gravação crua de build web, feita por um agente que lê o estado da tela.",
            "%s." % _maiuscula(fa["afirmacao"]),
            "O que dá para medir da partida: %d toques no campo e %d colheitas." % (f["toques"], f["colhidas"]),
        ],
    },
]


def _maiuscula(texto):
    texto = str(texto or "").strip()
    return texto[:1].upper() + texto[1:] if texto else texto


VAZIAS_NO_FIM = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "ou", "com", "sem",
                 "por", "para", "pra", "em", "no", "na", "nos", "nas", "um", "uma", "que", "ate",
                 "até", "ao", "aos", "se", "sob", "sobre", "entre"}


def _resumo(texto, limite=58):
    """Primeiras palavras da afirmação, sem cortar no meio do sentido.

    Medido em 06/11/2026: o corte cru produziu o título "Como funciona: as plantações crescem e
    as vendas acontecem por até 8" — frase pendurada num número solto. Título de vídeo é a
    primeira coisa que o leitor vê; cortar assim é defeito, não estilo. Agora o fim vazio
    (preposição, artigo, conjunção ou número solto) cai fora.
    """
    inteiro = str(texto or "")
    # 1ª escolha: cortar numa fronteira natural (vírgula, dois pontos, ponto e vírgula) antes do
    # limite — é assim que uma frase é interrompida sem perder o sentido.
    corte = max(inteiro.rfind(",", 0, limite), inteiro.rfind(":", 0, limite),
                inteiro.rfind(";", 0, limite))
    if corte >= max(12, int(limite * 0.55)):
        return inteiro[:corte].strip().rstrip(",;:")
    palavras = inteiro.split()
    saida = ""
    for palavra in palavras:
        if len(saida) + len(palavra) + 1 > limite:
            break
        saida = (saida + " " + palavra).strip()
    palavras = saida.rstrip(",.;:").split()
    while palavras and (palavras[-1].lower() in VAZIAS_NO_FIM or palavras[-1].isdigit()):
        palavras.pop()
    return " ".join(palavras) or " ".join(str(texto or "").split()[:4])


def fatos_da_casa(raiz=RAIZ):
    """Os fatos com origem e data que podem virar assunto de vídeo (posts/fatos.json)."""
    try:
        with open(os.path.join(raiz, "posts", "fatos.json"), encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return []
    itens = dados.get("fatos") if isinstance(dados, dict) else dados
    saida = []
    for item in itens or []:
        if not isinstance(item, dict):
            continue
        # O vídeo é do gameplay do Ceifalume: fato de outro jogo da casa viraria "dois assuntos
        # no mesmo post", que o portão recusa — e com razão.
        if (item.get("assunto") or "").strip().lower() not in ("ceifalume", "casa", "oficio"):
            continue
        if item.get("classe") == "numero":
            continue  # número de OUTRA gravação: usaria um valor que não é o desta partida
        # Fato cuja origem é outro jogo não serve: ao citar a fonte, o texto falaria de dois
        # jogos e o portão recusaria — com razão (um assunto por post).
        texto_do_fato = "%s %s %s" % (item.get("afirmacao") or "", item.get("origem") or "",
                                      item.get("assunto") or "")
        outros = [j for j in ("prancheta",) if item.get("assunto") != j and j in texto_do_fato.lower()]
        if outros:
            continue
        if not (item.get("afirmacao") and item.get("origem") and item.get("id")):
            continue
        saida.append(item)
    return saida


def angulos_de_fato(fatos_usados, fatos=None, raiz=RAIZ):
    """Pergunta do leitor × fato ainda não usado. Um ângulo por par, na ordem declarada."""
    usados = set(fatos_usados or ())
    disponiveis = [x for x in (fatos if fatos is not None else fatos_da_casa(raiz))
                   if x.get("id") not in usados]
    angulos = []
    for fato in disponiveis:
        for pergunta in PERGUNTAS_DO_LEITOR:
            angulos.append({
                "id": "%s:%s" % (pergunta["id"], fato["id"]),
                "precisa": (),
                "hashtags": pergunta["hashtags"],
                "fato": fato["id"],
                "titulo": (lambda fa, f, _p=pergunta: _p["titulo"](fa, f)),
                "corpo": (lambda fa, f, _p=pergunta: _p["corpo"](fa, f)),
                "_fato": fato,
            })
    return angulos

FECHAMENTO = "Canal de dev solo: bastidores, versões e o que quebrou no caminho."
PROIBIDOS = ("garantido", "viral", "imperdivel", "imperdível", "melhor do mundo",
             "nao perca", "não perca", "em breve", "clique aqui")
MECANICA_INVENTADA = ("inimigo", "tiro", "chefe", "boss", "corrida", "pulo", "pular")


def relatorio_cru(slug, raiz=RAIZ):
    """O relatório da partida, cru. {} quando não existe (o redator então não escreve nada)."""
    kitg = _kit_gameplay()
    info = (getattr(kitg, "GAMEPLAY", {}) or {}).get(slug) or {}
    caminho = os.path.join(raiz, info.get("decisoes") or "")
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _compras(relatorio):
    """As compras que o agente fez na partida, do relatório ("comprar Poço (40 moedas · …)")."""
    nomes = []
    for d in relatorio.get("decisoes") or []:
        if not isinstance(d, dict):
            continue
        motivo = str(d.get("motivo") or "")
        if not motivo.lower().startswith("comprar"):
            continue
        nome = motivo[len("comprar"):].strip().split("(")[0].strip()
        if nome and nome not in nomes:
            nomes.append(nome)
    return nomes


def _plantas(relatorio, limite=3):
    """As plantas que estavam no campo no fim, sem repetir."""
    fim = ((relatorio.get("economia") or {}).get("fim") or {})
    plantas = []
    for campo in fim.get("camposLista") or []:
        nome = str((campo or {}).get("planta") or "").strip()
        if nome and nome not in plantas:
            plantas.append(nome)
    return plantas[:limite]


def fatos_do_pacote(slug, raiz=RAIZ):
    """Os números medidos + os nomes do jogo. {} quando a partida não foi medida."""
    kitg = _kit_gameplay()
    kit = _kit_youtube()
    n = kitg.numeros_da_partida(slug, raiz=raiz)
    if not n:
        return {}
    jogo = (kit.JOGOS.get(slug) or {})
    f = dict(n)
    f["nome"] = (jogo.get("nome") or slug) + ((" " + jogo.get("versao")) if jogo.get("versao") else "")
    f["nome_curto"] = jogo.get("nome") or slug
    f["nome_curto_upper"] = f["nome_curto"].upper()
    f["toques_por_minuto"] = int(round(n["toques"] / max(1, n["minutos"])))
    f["slug"] = slug
    j = dict(FATOS_DO_KIT.get(slug) or {})
    if not j:
        return {}
    f["_fatos_do_jogo"] = j
    # Fatos extras do relatório: cada ângulo novo declara de qual precisa ("precisa"), e ângulo
    # sem o fato é pulado com motivo — nunca preenchido com estimativa.
    rel = relatorio_cru(slug, raiz=raiz)
    economia = rel.get("economia") or {}
    inicio, fim = economia.get("inicio") or {}, economia.get("fim") or {}
    for chave, valor in (
        ("moedas_inicio", inicio.get("moedas")),
        ("moedas_fim", fim.get("moedas")),
        ("campos_inicio", inicio.get("campos")),
        ("campos_fim", fim.get("campos")),
        ("telas", rel.get("telas")),
        ("tutorial_toques", rel.get("tutorial_toques")),
    ):
        try:
            f[chave] = int(valor)
        except (TypeError, ValueError):
            pass
    try:
        f["tutorial_segundos"] = round(float(rel.get("tutorial_segundos") or 0), 1)
    except (TypeError, ValueError):
        pass
    f["tutorial_fechou"] = bool(rel.get("tutorial_fechou"))
    f["compras"] = _compras(rel)
    f["plantas"] = _plantas(rel)
    campos = fim.get("camposLista") or []
    if campos:
        f["celulas_total"] = len(campos)
        f["celulas_prontas"] = sum(1 for c in campos if (c or {}).get("pronto"))
    return f


def links_do_kit(slug, raiz=RAIZ):
    """As linhas oficiais de link — obrigatórias em toda descrição (o kit é a fonte)."""
    kit = _kit_youtube()
    try:
        base = kit.descricao(slug)
    except Exception:
        return ""
    linhas = [l for l in base.splitlines() if l.strip().startswith(("Jogar:", "Todos os canais"))]
    return "\n".join(linhas)


def texto_do_angulo(angulo, fatos, raiz=RAIZ):
    """(titulo, descricao) daquele ângulo. Descrição sempre com origem, links e hashtags."""
    j = fatos["_fatos_do_jogo"]
    if angulo.get("_fato"):
        fatos = dict(fatos, **{"_fato_da_casa": angulo["_fato"]})
        titulo = angulo["titulo"](angulo["_fato"], fatos)
        corpo = [str(x).strip() for x in angulo["corpo"](angulo["_fato"], fatos) if str(x).strip()]
    else:
        titulo = angulo["titulo"](fatos, j)
        corpo = [str(x).strip() for x in angulo["corpo"](fatos, j) if str(x).strip()]
    kitg = _kit_gameplay()
    kit = _kit_youtube()
    info = (getattr(kitg, "GAMEPLAY", {}) or {}).get(fatos["slug"]) or {}
    origem = info.get("origem") or ""
    partes = ["\n\n".join(corpo)]
    fato_da_casa = angulo.get("_fato") or {}
    if fato_da_casa:
        # Todo fato citado carrega a fonte: sem isso o vídeo afirma e o leitor não confere.
        partes.append("Fonte: %s (conferido em %s)." % (fato_da_casa.get("origem"),
                                                        fato_da_casa.get("quando")))
    if origem:
        partes.append(origem)
    partes.append(FECHAMENTO)
    links = links_do_kit(fatos["slug"], raiz=raiz)
    if links:
        partes.append(links)
    if angulo["hashtags"]:
        partes.append(" ".join(angulo["hashtags"]))
    descricao = "\n\n".join(partes)
    limite = getattr(kit, "LIMITE_DESCRICAO", 5000)
    return titulo[:getattr(kit, "LIMITE_TITULO", 100)], descricao[:limite]


def problemas_do_texto(titulo, descricao, fatos):
    """O que o redator se recusa a escrever — checado antes do portão, não depois."""
    baixo = (titulo + " " + descricao).lower()
    problemas = []
    for termo in PROIBIDOS:
        if termo in baixo:
            problemas.append("promessa que a casa não sustenta: \"%s\"" % termo)
    for termo in MECANICA_INVENTADA:
        if termo in baixo:
            problemas.append("mecânica que o jogo não tem: \"%s\"" % termo)
    if not (12 <= len(titulo) <= 90):
        problemas.append("título fora da faixa (%d caracteres)" % len(titulo))
    for obrigatorio in ("Jogar:", "Todos os canais"):
        if obrigatorio not in descricao:
            problemas.append("descrição sem a linha oficial \"%s\"" % obrigatorio)
    return problemas


def historico(raiz=RAIZ):
    """O que o canal já publicou, do mais novo para o mais antigo (o portão compara assim)."""
    caminho = os.path.join(raiz, "posts", "youtube-publicados.json")
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return []
    itens = dados.get("publicados") if isinstance(dados, dict) else dados
    if not isinstance(itens, list):
        return []
    saida = [{"canal": "youtube", "titulo": str(i.get("titulo") or ""),
              "texto": str(i.get("descricao") or i.get("texto") or ""),
              "angulo": i.get("angulo"), "id": i.get("id"), "quando": i.get("quando")}
             for i in itens if isinstance(i, dict)]
    saida.sort(key=lambda x: str(x.get("quando") or ""), reverse=True)
    return saida


def ultimo_angulo(publicacoes):
    for item in publicacoes or []:
        if item.get("angulo"):
            return item["angulo"]
    return None


def escolher(slug, raiz=RAIZ, hora_local=None, publicacoes=None, avaliador=None):
    """Escolhe o ângulo do vídeo. Devolve (escolha, recusas).

    escolha = {"angulo", "titulo", "descricao", "numeros"} ou None.
    recusas = [{"angulo", "motivo"}] — a lista inteira, para a decisão sair com número e motivo.
    """
    fatos = fatos_do_pacote(slug, raiz=raiz)
    if not fatos:
        return None, [{"angulo": None,
                       "motivo": "sem partida medida: não há número para descrever (nada é inventado)"}]
    portao = _portao()
    avalia = avaliador or portao.avalia
    hist = historico(raiz) if publicacoes is None else publicacoes
    hora = hora_local_do_canal() if hora_local is None else int(hora_local)
    anterior = ultimo_angulo(hist)
    # A comparação precisa da partida anterior publicada — e ela existe porque o registro guarda
    # os números de cada vídeo. Sem anterior, o ângulo não é oferecido (não se inventa passado).
    for item in hist:
        if isinstance(item.get("numeros"), dict) and item["numeros"].get("colhidas") is not None:
            fatos["_anterior"] = dict(item["numeros"], quando=item.get("quando"))
            break
    usados = {x.get("fato") for x in hist if isinstance(x, dict) and x.get("fato")}
    do_fato = angulos_de_fato(usados, raiz=raiz)
    # O canal não deve emendar dez vídeos sobre a própria partida: alterna assunto (fato da casa)
    # com número (partida). Se o último vídeo foi de fato, tenta a partida primeiro — e vice-versa.
    ultimo_teve_fato = bool(hist and isinstance(hist[0], dict) and hist[0].get("fato"))
    candidatos = ([a for a in do_fato] + list(ANGULOS)) if not ultimo_teve_fato \
        else (list(ANGULOS) + list(do_fato))
    recusas = []
    aprovados = []
    for angulo in candidatos:
        faltando = [c for c in (angulo.get("precisa") or ()) if fatos.get(c) in (None, "", [])]
        if faltando:
            recusas.append({"angulo": angulo["id"],
                            "motivo": "fato ausente no relatório desta partida: " + ", ".join(faltando)})
            continue
        titulo, descricao = texto_do_angulo(angulo, fatos, raiz=raiz)
        problemas = problemas_do_texto(titulo, descricao, fatos)
        if problemas:
            recusas.append({"angulo": angulo["id"], "motivo": "; ".join(problemas)})
            continue
        if anterior and angulo["id"] == anterior:
            recusas.append({"angulo": angulo["id"],
                            "motivo": "mesmo ângulo do último vídeo publicado (%s) — o ângulo roda" % anterior})
            continue
        decisao = avalia({"titulo": titulo, "texto": descricao}, canal="youtube",
                         publicacoes=hist, calendario=JANELA_DO_CANAL, hora_local=hora) or {}
        if not decisao.get("publica"):
            recusas.append({"angulo": angulo["id"], "motivo": str(decisao.get("motivo") or "recusado")})
            continue
        aprovados.append({"angulo": angulo["id"], "fato": angulo.get("fato"),
                          "titulo": titulo, "descricao": descricao,
                          "numeros": {k: fatos[k] for k in ("plantadas", "colhidas", "toques",
                                                            "minutos", "toques_por_minuto")}})
    if aprovados:
        # Todos os ângulos foram julgados (a recusa de cada um fica registrada); o primeiro
        # aprovado na ordem declarada é o que publica.
        return aprovados[0], recusas
    return None, recusas


def main(argv):
    slug = argv[1] if len(argv) > 1 else "ceifalume"
    escolha, recusas = escolher(slug)
    for r in recusas:
        print("✘ ângulo %s: %s" % (r["angulo"], r["motivo"]))
    if not escolha:
        print("nenhum ângulo aprovado — o vídeo não publica (e a recusa fica registrada)")
        return 1
    print("ângulo escolhido: %s" % escolha["angulo"])
    print("título: %s" % escolha["titulo"])
    print("descrição:\n%s" % escolha["descricao"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
