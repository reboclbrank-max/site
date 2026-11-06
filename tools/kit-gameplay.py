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
    partes = []
    if n["colhidas"]:
        partes.append("%d colheita%s" % (n["colhidas"], "" if n["colhidas"] == 1 else "s"))
    if n["plantadas"]:
        partes.append("%d muda%s plantada%s" % (n["plantadas"], "" if n["plantadas"] == 1 else "s",
                                                "" if n["plantadas"] == 1 else "s"))
    if n["toques"]:
        partes.append("%d toques" % n["toques"])
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
    return ("Esta partida: %d mudas plantadas, %d colheitas e %d toques em %d minutos de "
            "gravação." % (n["plantadas"], n["colhidas"], n["toques"], n["minutos"]))


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


def montar():
    pacotes, problemas = [], {}
    for slug in GAMEPLAY:
        p, erros = pacote(slug)
        if erros:
            problemas[slug] = erros
        if p:
            pacotes.append(p)
    return {"pacotes": pacotes, "problemas": problemas}


def main():
    dados = montar()
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
