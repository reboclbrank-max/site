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
        "arquivo": "media/gameplay/ceifalume-gameplay.mp4",
        "sufixo_titulo": " — gameplay gravado no navegador",
        "origem": ("Gameplay: gravado automaticamente do próprio jogo rodando no navegador "
                   "(build web do repositório), sem edição."),
    },
}


def _modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


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
    # o título do kit é mais informativo; se couber com o sufixo, usa o do kit
    candidato = base_titulo + info["sufixo_titulo"]
    if len(candidato) <= kit.LIMITE_TITULO:
        titulo = candidato
    descricao = kit.descricao(slug).replace(
        "Canal de dev solo:", info["origem"] + "\n\nCanal de dev solo:")

    p = {
        "id": slug + "-gameplay",
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
    if dados["problemas"]:
        for slug, erros in dados["problemas"].items():
            print("✘ %s: %s" % (slug, "; ".join(erros)))
        print("kit do gameplay NÃO está pronto — o envio seria recusado")
        return 1
    print("kit do gameplay gravado em posts/kit-gameplay.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
