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
        "hashtags": ["#indiedev"],
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
        "hashtags": ["#indiedev", "#godot"],
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
        "hashtags": ["#indiedev", "#godot", "#jogobrasileiro"],
        "titulo": lambda f, j: "Como um agente joga %s sozinho: %d min de gravação" % (
            f["nome_curto"], f["minutos"]),
        "corpo": lambda f, j: [
            "A gravação é do jogo rodando no navegador, capturada por um agente que olha o estado da tela e decide o próximo toque.",
            "Na prática: %d mudas semeadas, %d colheitas e %d toques em %d minutos de partida."
            % (f["plantadas"], f["colhidas"], f["toques"], f["minutos"]),
            "Nada de vídeo editado à mão: a legenda descreve a decisão tomada, e o áudio é sintetizado pela produção.",
        ],
    },
]

FECHAMENTO = "Canal de dev solo: bastidores, versões e o que quebrou no caminho."
PROIBIDOS = ("garantido", "viral", "imperdivel", "imperdível", "melhor do mundo",
             "nao perca", "não perca", "em breve", "clique aqui")
MECANICA_INVENTADA = ("inimigo", "tiro", "chefe", "boss", "corrida", "pulo", "pular")


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
    titulo = angulo["titulo"](fatos, j)
    corpo = [str(x).strip() for x in angulo["corpo"](fatos, j) if str(x).strip()]
    kitg = _kit_gameplay()
    kit = _kit_youtube()
    info = (getattr(kitg, "GAMEPLAY", {}) or {}).get(fatos["slug"]) or {}
    origem = info.get("origem") or ""
    partes = ["\n\n".join(corpo)]
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
    recusas = []
    for angulo in ANGULOS:
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
        return ({"angulo": angulo["id"], "titulo": titulo, "descricao": descricao,
                 "numeros": {k: fatos[k] for k in ("plantadas", "colhidas", "toques", "minutos",
                                                   "toques_por_minuto")}}, recusas)
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
