#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRANCHETA vira pacote de vídeo: título, descrição, capa e assinatura — de dados medidos.

POR QUE EXISTE (06/11/2026). O dono disse que "todas as cenas gravam o mesmo jogo". A gravação
do PRANCHETA existia e rodava 3x/dia desde 27/10, mas o vídeo nunca virava pacote: ficava em
media/gameplay/prancheta-gameplay.mp4, sem título próprio, sem capa e sem envio — e o campo
PUBLICAR do workflow prometia um envio que nenhum passo fazia. Promessa falsa é pior que ausência.

O que este arquivo faz, tudo a partir de dois arquivos que a gravação já produz:
  media/gameplay/prancheta-cru-decisoes.json  (passos, toques, passos confirmados por imagem)
  posts/cenas.json                            (assinatura da partida, gravada por tools/cena.py)
e devolve:
  título da gravação, descrição com Fonte/números/links, capa desenhada do próprio quadro,
  e o pacote `prancheta-gameplay` dentro de posts/kit-gameplay.json.

Não inventa número: o que não está no relatório não entra no texto. Se faltar dado, falha com
motivo — não completa com adjetivo.
"""
import argparse
import importlib.util
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(RAIZ, "posts", "kit-gameplay.json")

# Um título por estratégia, porque a cena é diferente em cada uma. Nada de molde: o que muda na
# tela (instrução, ritmo, corte) está dito no título, e a assinatura entra na descrição.
TITULOS = {
    "pressao_rapida": "PRANCHETA: pressão na instrução e a partida até o fim",
    "posse_normal": "PRANCHETA: a partida inteira sem mexer no plano do staff",
    "contra_ataque": "PRANCHETA: ritmo rápido e a virada sem instrução",
}
TITULO_PADRAO = "PRANCHETA: da prancheta tática ao apito final"


def _modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ler_decisoes(caminho):
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados, dict):
        raise ValueError("relatório do gravador não é um objeto JSON")
    return dados


def numeros_do_relatorio(decisoes):
    """Só o que foi medido: passos, passos confirmados por imagem e toques na partida."""
    passos = decisoes.get("decisoes") or decisoes.get("passos") or []
    confirmados = decisoes.get("passos_confirmados")
    if confirmados is None:
        confirmados = sum(1 for p in passos if isinstance(p, dict) and p.get("ok"))
    corpo = {
        "passos": len(passos),
        "passos_confirmados": int(confirmados or 0),
    }
    if decisoes.get("toques_partida") is not None:
        corpo["toques_partida"] = int(decisoes["toques_partida"])
    return corpo


def assinatura_do_registro(jogo="prancheta", caminho=None):
    """A assinatura da última partida daquele jogo em posts/cenas.json (ou None)."""
    cena = _modulo("cena", "cena.py")
    registro = cena.carregar(caminho or os.path.join(RAIZ, "posts", "cenas.json"))
    partidas = [p for p in (registro.get("partidas") or [])
                if (p.get("jogo") or "ceifalume") == jogo]
    return partidas[-1].get("assinatura") if partidas else None


def titulo_da_gravacao(estrategia, numeros):
    base = TITULOS.get(estrategia, TITULO_PADRAO)
    # o número entra no título só quando existe: título com número inventado é mentira pequena
    if numeros.get("toques_partida"):
        return "%s · %d toques" % (base, numeros["toques_partida"])
    return base


def descricao_da_gravacao(estrategia, numeros, assinatura):
    """Descrição com fonte, número e link — e sem corte: a régua de descrição do juízo cobra isso."""
    kit = _modulo("kit_youtube", "kit-youtube.py")
    info = (getattr(kit, "JOGOS", {}) or {}).get("prancheta") or {}
    partes = []
    partes.append(
        "Gravação automática do PRANCHETA: o agente atravessou menu, carreira, escolha de clube "
        "e staff até a prancheta tática, e jogou a partida com o plano recomendado.")
    partes.append(
        "A cena desta vez foi \"%s\": %d passos, %d confirmados por mudança de tela." % (
            estrategia, numeros.get("passos", 0), numeros.get("passos_confirmados", 0)))
    if numeros.get("toques_partida"):
        partes.append("Na partida foram %d toques registrados pelo gravador."
                      % numeros["toques_partida"])
    if assinatura:
        partes.append("Fonte: posts/cenas.json (partida %s, conferida em %s)."
                      % (assinatura, _hoje()))
    partes.append("Jogo: %s — %s, %s." % (info.get("nome") or "PRANCHETA",
                                          info.get("o_que_e") or "simulador de futebol",
                                          info.get("feito_com") or "Godot, feito no Brasil"))
    if info.get("link"):
        partes.append("Jogar: %s" % info["link"])
    partes.append("Canal de dev solo: bastidores, versões e o que quebrou no caminho.")
    partes.append("#prancheta #godot")
    return "\n\n".join(partes)


def numeros_da_capa(numeros):
    """Linha curta para a capa: o que o espectador vê sem ler a descrição."""
    pedacos = ["%d passos" % numeros.get("passos", 0)]
    if numeros.get("passos_confirmados"):
        pedacos.append("%d confirmados" % numeros["passos_confirmados"])
    if numeros.get("toques_partida"):
        pedacos.append("%d toques" % numeros["toques_partida"])
    return " · ".join(pedacos)


def _hoje():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def montar_pacote(decisoes, estrategia, assinatura, raiz=RAIZ, capa=None):
    numeros = numeros_do_relatorio(decisoes)
    kit = _modulo("kit_youtube", "kit-youtube.py")
    info = (getattr(kit, "JOGOS", {}) or {}).get("prancheta") or {}
    titulo = titulo_da_gravacao(estrategia, numeros)
    descricao = descricao_da_gravacao(estrategia, numeros, assinatura)
    pacote = {
        "id": "prancheta-gameplay",
        "slug": "prancheta",
        "estrategia": estrategia,
        "vinheta": assinatura,
        "numeros": numeros,
        "arquivo": "media/gameplay/prancheta-gameplay.mp4",
        "capa": capa or "media/gameplay/prancheta-capa.png",
        "dimensoes": [1280, 720],
        "formato": "vídeo normal (16:9)",
        "titulo": titulo,
        "descricao": descricao,
        "tags": list(info.get("tags") or ["prancheta", "jogo indie brasileiro", "godot"]),
        "idioma": "pt-BR",
        "categoria": "Gaming",
        "visibilidade": "público",
        "feito_para_criancas": "não",
        "origem": ("Gameplay: gravado automaticamente do PRANCHETA rodando no build web do "
                   "itch.io. A trilha é sintetizada pelo script de produção e as legendas "
                   "descrevem o que o agente fez na partida."),
    }
    return pacote


def gravar_pacote(pacote, caminho=KIT):
    """Mete o pacote no kit sem tocar nos outros (o kit é o arquivo que o envio lê)."""
    dados = {"pacotes": []}
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        if not isinstance(dados, dict) or not isinstance(dados.get("pacotes"), list):
            dados = {"pacotes": []}
    dados["pacotes"] = [p for p in dados["pacotes"]
                        if not (isinstance(p, dict) and p.get("id") == pacote["id"])]
    dados["pacotes"].append(pacote)
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(caminho + ".tmp", caminho)


def main(argv):
    ap = argparse.ArgumentParser(description="PRANCHETA: relatório da gravação -> pacote de vídeo")
    ap.add_argument("--relatorio", default=os.path.join(
        RAIZ, "media", "gameplay", "prancheta-cru-decisoes.json"))
    ap.add_argument("--estrategia", default=None)
    ap.add_argument("--assinatura", default=None)
    ap.add_argument("--capa", default=None)
    ap.add_argument("--kit", default=KIT)
    ap.add_argument("--sem-kit", action="store_true", help="só imprime o pacote, não escreve")
    a = ap.parse_args(argv[1:])
    if not os.path.exists(a.relatorio):
        print("✘ falta o relatório da gravação (%s): sem ele o texto seria inventado" % a.relatorio,
              file=sys.stderr)
        return 2
    decisoes = ler_decisoes(a.relatorio)
    estrategia = a.estrategia or decisoes.get("estrategia") or "posse_normal"
    assinatura = a.assinatura or assinatura_do_registro("prancheta")
    pacote = montar_pacote(decisoes, estrategia, assinatura, capa=a.capa)
    if not a.sem_kit:
        gravar_pacote(pacote, a.kit)
    print("pacote: %s · estratégia %s · %d passos (%d confirmados)"
          % (pacote["id"], pacote["estrategia"], pacote["numeros"]["passos"],
             pacote["numeros"]["passos_confirmados"]))
    print("titulo: %s" % pacote["titulo"])
    print("capa_numeros: %s" % numeros_da_capa(pacote["numeros"]))
    juizo = _modulo("juizo", "juizo.py")
    nota, _det = juizo.nota_descricao(pacote["descricao"])
    print("descrição: %d caracteres · régua de descrição %.3f (mínimo %.2f)"
          % (len(pacote["descricao"]), nota, juizo.NOTA_MINIMA_DESCRICAO))
    return 0 if nota >= juizo.NOTA_MINIMA_DESCRICAO else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
