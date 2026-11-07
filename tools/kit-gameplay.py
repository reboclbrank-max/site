#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kit de envio do GAMEPLAY — o pacote do vídeo gravado do jogo rodando.

POR QUE EXISTE (27/10/2026): o kit do YouTube já tinha dois pacotes (trailer do CEIFALUME e
reel do PRANCHETA), os dois feitos à mão. O gameplay é outra coisa: é o build do jogo rodando
no navegador, gravado por `tools/gravar-gameplay.js` e conferido por `tools/validar-video.py`.

Este script não inventa texto novo: título, descrição, tags e links vêm do kit oficial
(`tools/kit-youtube.py`), que é a fonte única dos fatos da casa. O que ele acrescenta é uma
linha dizendo a verdade sobre a origem do vídeo — sem essa linha, o vídeo seria apresentado
como se fosse editado à mão.

O arquivo do vídeo precisa existir E ter passado na validação: kit apontando para vídeo que
não existe é recusado aqui, não no momento do envio.
"""
import importlib.util
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))

SAIDA = os.path.join(RAIZ, "posts", "kit-gameplay.json")

# slug do jogo -> (arquivo do gameplay, título próprio, linha de origem)
GAMEPLAY = {
    "prancheta": {
        # PRANCHETA: o relatório dele é outro (passos do roteiro, não plantio). O redator do vídeo
        # aprendeu a ler os dois — antes o texto do PRANCHETA saía de uma ferramenta paralela, sem
        # rotação de ângulo e sem a régua de "título quase igual" (dívida apontada em 06/11/2026).
        "arquivo": "media/gameplay/prancheta-gameplay.mp4",
        "sufixo_titulo": " — gameplay gravado no navegador",
        "decisoes": "media/gameplay/prancheta-cru-decisoes.json",
        "origem": ("Gameplay: gravado automaticamente do PRANCHETA rodando no build web do "
                   "itch.io. A trilha é sintetizada pelo script de produção e as legendas "
                   "descrevem o que o agente fez na partida."),
    },
    "ceifalume": {
        # o arquivo do kit é o que tem as INSTRUÇÕES na tela (rodada 111): é esse que vai ao YouTube
        "arquivo": "media/gameplay/ceifalume-gameplay-instrucoes.mp4",
        "sufixo_titulo": " — gameplay gravado no navegador",
        # Relatório da partida: é dele que sai o título desta gravação. Sem ele o título volta
        # a ser fixo — e título fixo foi o que pôs o mesmo vídeo três vezes no canal (06/11/2026).
        "decisoes": "media/gameplay/ceifalume-gameplay-cru-decisoes.json",
        "origem": ("Gameplay: gravado automaticamente do próprio jogo rodando no navegador "
                   "(build web do repositório). A trilha é sintetizada pelo próprio script de "
                   "produção e as legendas descrevem o que o agente fez na partida."),
    },
}


def _modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _redator():
    """O redator do vídeo (tools/redator-video.py) — quem escolhe o ângulo da gravação."""
    spec = importlib.util.spec_from_file_location(
        "redator_video", os.path.join(RAIZ, "tools", "redator-video.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def texto_do_video(slug, raiz=RAIZ):
    """(escolha, recusas) do redator. `escolha` é None quando nenhum ângulo foi aprovado.

    Sem ângulo aprovado o kit NÃO fica sem texto: ele mantém o molde e o portão do envio
    recusa a repetição depois. Kit que se recusa a montar derrubaria a gravação inteira.
    """
    try:
        escolha, recusas = _redator().escolher(slug, raiz=raiz)
    except Exception as erro:  # redator quebrado não pode impedir a gravação
        return None, [{"angulo": None, "motivo": "redator falhou: " + str(erro)[:120]}]
    return escolha, recusas


def numeros_da_partida(slug, raiz=RAIZ):
    """Os fatos daquela partida, do relatório que o agente escreveu jogando. {} se não houver.

    Só entra o que foi MEDIDO: quantas mudas foram plantadas, quantas colheitas saíram, quantos
    toques o agente deu e quanto durou. Nada aqui é estimado para o título ficar bonito.
    """
    info = GAMEPLAY.get(slug) or {}
    caminho = os.path.join(raiz, info.get("decisoes") or "")
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}
    decisoes = dados.get("decisoes") or []
    if slug == "prancheta":
        # Relatório do PRANCHETA: 13 passos do roteiro, quantos foram CONFIRMADOS por mudança de
        # tela e quantos toques o agente deu na partida. Não há "plantadas": cada jogo mede o que
        # ele tem, e o texto só usa o que existir.
        if not isinstance(decisoes, list) or not decisoes:
            return {}
        confirmados = dados.get("passos_confirmados")
        if confirmados is None:
            confirmados = sum(1 for d in decisoes if isinstance(d, dict) and d.get("ok"))
        try:
            toques = int(dados.get("toques_partida") or 0)
        except (TypeError, ValueError):
            toques = 0
        segundos = 0.0
        try:
            segundos = float(decisoes[-1].get("t") or 0)
        except (TypeError, ValueError):
            segundos = 0.0
        return {"passos": len(decisoes), "passos_confirmados": int(confirmados or 0),
                "toques_partida": toques, "segundos": round(segundos),
                "minutos": max(1, int(round(segundos / 60.0))),
                "estrategia": str(dados.get("estrategia") or "posse_normal")}
    segundos = 0.0
    if isinstance(decisoes, list) and decisoes and isinstance(decisoes[-1], dict):
        try:
            segundos = float(decisoes[-1].get("t") or 0)
        except (TypeError, ValueError):
            segundos = 0.0
    try:
        plantadas = int(dados.get("plantadas") or 0)
        colhidas = int(dados.get("colhidas") or 0)
        toques = int(dados.get("bicos") or 0)
    except (TypeError, ValueError):
        return {}
    if not (plantadas or colhidas):
        return {}
    return {"plantadas": plantadas, "colhidas": colhidas, "toques": toques,
            "segundos": round(segundos), "minutos": max(1, int(round(segundos / 60.0)))}


def titulo_da_partida(slug, kit, raiz=RAIZ):
    """Título que descreve ESTA partida — ou None quando não há número medido para dizer.

    A régua: título de vídeo do canal não pode ser o mesmo duas vezes. Deixar o título fixo e
    mudar só o arquivo é o que produziu três uploads do "CEIFALUME 0.1 — gameplay gravado no
    navegador". Com os números da partida, o título muda porque a partida mudou.
    """
    n = numeros_da_partida(slug, raiz)
    if not n:
        return None
    jogo = kit.JOGOS.get(slug) or {}
    nome = (jogo.get("nome") or slug) + ((" " + jogo.get("versao")) if jogo.get("versao") else "")
    # CADA JOGO MEDE O QUE TEM (06/11/2026). Aqui se lia n["colhidas"] direto, o que só valia
    # para o CEIFALUME: o kit é montado para TODOS os jogos, e ao gerar o pacote do PRANCHETA
    # (que não tem colheita) o run 42318206616 morreu com KeyError 'colhidas' no passo 12 — depois
    # de gravar o vídeo. Título se monta com o que existe, nunca com o que se supõe.
    partes = []

    def _plural(qtd, singular, plural):
        return "%d %s" % (qtd, singular if qtd == 1 else plural)

    if n.get("colhidas"):
        partes.append(_plural(n["colhidas"], "colheita", "colheitas"))
    if n.get("plantadas"):
        partes.append(_plural(n["plantadas"], "muda plantada", "mudas plantadas"))
    if n.get("passos"):
        partes.append(_plural(n["passos"], "passo", "passos"))
    if n.get("passos_confirmados"):
        partes.append("%d confirmados" % n["passos_confirmados"])
    _toques = n.get("toques") or n.get("toques_partida") or 0
    if _toques:
        partes.append(_plural(_toques, "toque", "toques"))
    corpo = ", ".join(partes)
    titulo = "%s: %s em %d min de jogo" % (nome, corpo, n["minutos"]) if corpo else None
    if not titulo:
        return None
    return titulo[:kit.LIMITE_TITULO]


def linha_da_partida(slug, raiz=RAIZ):
    """A frase que diz, na descrição, o que aconteceu naquela partida (ou "")."""
    n = numeros_da_partida(slug, raiz)
    if not n:
        return ""
    # MESMA LIÇÃO DO TÍTULO (06/11/2026, run 42318967911): esta linha também lia as chaves do
    # CEIFALUME direto e estourava no PRANCHETA. A frase é montada com o que existe.
    partes = []
    if n.get("plantadas"):
        partes.append("%d mudas plantadas" % n["plantadas"])
    if n.get("colhidas"):
        partes.append("%d colheitas" % n["colhidas"])
    if n.get("passos"):
        partes.append("%d passos do roteiro" % n["passos"])
    if n.get("passos_confirmados"):
        partes.append("%d confirmados por imagem" % n["passos_confirmados"])
    _toques = n.get("toques") or n.get("toques_partida") or 0
    if _toques:
        partes.append("%d toques" % _toques)
    if not partes:
        return ""
    return ("Esta partida: %s em %d minuto%s de gravação."
            % (", ".join(partes), n.get("minutos") or 1,
               "" if (n.get("minutos") or 1) == 1 else "s"))


def pacote(slug):
    """Pacote no mesmo formato que tools/enviar-youtube.py consome."""
    kit = _modulo("kit_youtube", "kit-youtube.py")
    if slug not in kit.JOGOS:
        return None, ["jogo desconhecido: " + str(slug)]
    if slug not in GAMEPLAY:
        return None, ["sem gameplay definido para " + slug]
    info = GAMEPLAY[slug]
    caminho = os.path.join(RAIZ, info["arquivo"])
    erros = []
    if not os.path.exists(caminho):
        erros.append("vídeo não existe ainda: " + info["arquivo"])
    elif os.path.getsize(caminho) < 100_000:
        erros.append("vídeo pequeno demais: %d B" % os.path.getsize(caminho))

    base_titulo = kit.titulo(slug)
    titulo = (kit.JOGOS[slug]["nome"] + (" " + kit.JOGOS[slug]["versao"]
              if kit.JOGOS[slug].get("versao") else "") + info["sufixo_titulo"])
    # 1ª escolha: o que ESTA partida tem de próprio. Sem relatório, cai no título fixo — e o
    # portão do vídeo (tools/enviar-youtube.py) recusa a repetição em vez de publicá-la.
    titulo = titulo_da_partida(slug, kit) or titulo
    candidato = base_titulo + info["sufixo_titulo"]
    descricao = kit.descricao(slug).replace(
        "Canal de dev solo:", info["origem"] + "\n\nCanal de dev solo:")
    linha = linha_da_partida(slug)
    if linha:
        descricao = descricao.replace(info["origem"] + "\n\n",
                                      info["origem"] + "\n\n" + linha + "\n\n", 1)

    # O redator tem a palavra final: ele escolhe o ângulo e escreve com os números da partida,
    # passando pelo mesmo portão dos outros canais. Sem ângulo aprovado, vale o molde acima —
    # e o portão do envio recusa a repetição com número e motivo.
    escolha_redator, recusas = texto_do_video(slug, RAIZ)
    angulo = (escolha_redator or {}).get("angulo")
    fato = (escolha_redator or {}).get("fato")
    if escolha_redator:
        titulo, descricao = escolha_redator["titulo"], escolha_redator["descricao"]

    p = {
        "id": slug + "-gameplay",
        "angulo": angulo,
        # qual fato da casa sustentou o texto (o redator não repete fato já usado)
        "fato": fato,
        # os números vão junto: é com eles que o próximo vídeo pode comparar partidas
        "numeros": (escolha_redator or {}).get("numeros"),
        "slug": slug,
        "arquivo": info["arquivo"],
        "arquivo_existe": os.path.exists(caminho),
        "bytes": os.path.getsize(caminho) if os.path.exists(caminho) else 0,
        "capa": kit.JOGOS[slug].get("capa"),
        "capa_existe": bool(kit.JOGOS[slug].get("capa")
                            and kit._verificar_arquivo(kit.JOGOS[slug]["capa"])),
        "dimensoes": kit.dimensoes_mp4(info["arquivo"]) if os.path.exists(caminho) else None,
        "formato": "vídeo normal (16:9)",
        "titulo": titulo[:kit.LIMITE_TITULO],
        "descricao": descricao[:kit.LIMITE_DESCRICAO],
        "tags": kit.tags(slug),
        "idioma": "pt-BR",
        "categoria": "Gaming",
        "visibilidade": "público",
        "feito_para_criancas": "não",
        "origem": info["origem"],
        "recusas_do_redator": recusas,
    }
    erros += kit.validar(p)
    return p, erros


def montar(slugs=None):
    """Monta os pacotes dos jogos pedidos (padrão: todos).

    POR QUE O RECORTE (06/11/2026): cada workflow grava UM jogo. O run 42319687317 gravou o
    CEIFALUME, montou o kit para todos e foi reprovado porque o vídeo do PRANCHETA — que aquele
    run não gravou — não existia no disco. A gravação tinha dado certo e o run saía vermelho:
    o kit cobrava do run um vídeo que não era dele.
    """
    alvo = list(slugs) if slugs else list(GAMEPLAY)
    desconhecidos = [x for x in alvo if x not in GAMEPLAY]
    if desconhecidos:
        raise SystemExit("jogo fora do kit: %s (os do kit: %s)"
                         % (", ".join(desconhecidos), ", ".join(GAMEPLAY)))
    pacotes, problemas = [], {}
    for slug in alvo:
        p, erros = pacote(slug)
        if erros:
            problemas[slug] = erros
        if p:
            pacotes.append(p)
    return {"pacotes": pacotes, "problemas": problemas}


def jogos_pedidos(argv):
    """Lê `--jogo slug` (repetível) ou `--jogo=slug`. Sem nenhum, monta o kit inteiro."""
    pedidos = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--jogo" and i + 1 < len(argv):
            pedidos.append(argv[i + 1])
            i += 2
            continue
        if arg.startswith("--jogo="):
            pedidos.append(arg.split("=", 1)[1])
            i += 1
            continue
        raise SystemExit("argumento desconhecido: %s (uso: kit-gameplay.py [--jogo slug]...)" % arg)
    return pedidos


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pedidos = jogos_pedidos(argv)
    dados = montar(pedidos or None)
    if pedidos:
        # O kit versionado é de TODOS os jogos: o que este run não mediu continua como estava, em
        # vez de desaparecer do arquivo que o outro workflow lê.
        try:
            with open(SAIDA, encoding="utf-8") as f:
                antigo = json.load(f)
        except (OSError, ValueError):
            antigo = {}
        mantidos = [p for p in (antigo.get("pacotes") or [])
                    if isinstance(p, dict) and p.get("slug") not in pedidos]
        if mantidos:
            dados["pacotes"] = dados["pacotes"] + mantidos
            print("mantidos do kit anterior: %s" % ", ".join(str(p.get("slug")) for p in mantidos))
        fora = [x for x in GAMEPLAY if x not in pedidos]
        if fora:
            print("não montado neste run (--jogo): %s" % ", ".join(fora))
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    for p in dados["pacotes"]:
        print("pacote %s · %s · %d B · %s" % (p["id"], p["arquivo"], p["bytes"],
                                              p["titulo"][:60]))
        print("  ângulo: %s" % (p.get("angulo") or "nenhum — o portão do envio vai recusar a repetição"))
        for recusa in p.get("recusas_do_redator") or []:
            print("  ✘ ângulo %s: %s" % (recusa.get("angulo"), recusa.get("motivo")))
    if dados["problemas"]:
        for slug, erros in dados["problemas"].items():
            print("✘ %s: %s" % (slug, "; ".join(erros)))
        print("kit do gameplay NÃO está pronto — o envio seria recusado")
        return 1
    print("kit do gameplay gravado em posts/kit-gameplay.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
