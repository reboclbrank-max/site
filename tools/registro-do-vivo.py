#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conferir o registro do canal contra o que está NO AR (e corrigir o resumo do registro).

POR QUE EXISTE (07/11/2026): o registro `posts/youtube-publicados.json` guarda um resumo da
descrição de cada vídeo. Três linhas antigas terminavam no meio de uma palavra ("…A trilha",
"…pt de produ…"), e a leitura disso era "as descrições estão truncadas no YouTube". Fui ver no
canal: as descrições estão INTEIRAS (666 a 720 caracteres, com links e hashtag no fim). O que
estava quebrado era o registro, não o vídeo — e três entradas estavam com a descrição VAZIA.

O que este script faz, sem tocar no YouTube:
  1. lê o id de cada vídeo do registro;
  2. abre a página pública do vídeo e lê a descrição e o título publicados;
  3. regrava no registro o resumo (corte em fim de parágrafo, nunca no meio de palavra),
     marca se está inteira, guarda o tamanho real no canal e a data da conferência.

Nada aqui envia, publica ou apaga: é leitura pública + escrita no nosso próprio JSON.
"""
import importlib.util
import json
import os
import re
import sys
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "youtube-publicados.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; casa-do-ceifalume/1.0)"}


def _resumo_da_descricao(*args, **kwargs):
    """O mesmo cortador do envio — um corte só na casa, para o registro não mentir diferente."""
    spec = importlib.util.spec_from_file_location(
        "enviar_youtube", os.path.join(RAIZ, "tools", "enviar-youtube.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo._resumo_da_descricao(*args, **kwargs)


def id_plausivel(vid):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", str(vid or "")))


def ler_do_canal(vid, abrir=None):
    """(titulo, descricao) publicados. (None, None) quando a página não traz os dados."""
    if not id_plausivel(vid):
        return None, None
    abrir = abrir or (lambda url: urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace"))
    try:
        html = abrir("https://www.youtube.com/watch?v=%s" % vid)
    except Exception:  # noqa: BLE001 — rede é instável; quem chama decide o que fazer
        return None, None
    return _extrair(html)


def _extrair(html):
    """Tira título e descrição do JSON que a própria página do YouTube carrega."""
    # A página do YouTube escreve o JSON COMPACTO ("shortDescription":"…"), mas um teste que monta
    # a página com json.dumps põe espaço depois dos dois pontos — e o extrator rígido devolvia
    # (None, None) sem dizer por quê. Aceitar espaço não afrouxa nada: o campo é o mesmo.
    # O campo se fecha na própria aspa (respeitando escape) e não depende do campo seguinte: exigir
    # "isCrawlable" logo depois fazia a leitura falhar em qualquer página que trouxesse outro campo.
    desc = re.search(r'"shortDescription"\s*:\s*"((?:[^"\\]|\\.)*)"', html or "", re.S)
    tit = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"lengthSeconds"', html or "")
    descricao = titulo = None
    if desc:
        try:
            descricao = json.loads('"' + desc.group(1) + '"')
        except ValueError:
            descricao = None
    if tit:
        try:
            titulo = json.loads('"' + tit.group(1) + '"')
        except ValueError:
            titulo = None
    return titulo, descricao


def conferir(registro_caminho=REGISTRO, abrir=None, hoje=None):
    """Confere cada vídeo e devolve (linhas, dados_atualizados, mudou, sem_resposta).

    NÃO grava: quem decide gravar é o main, depois de ver o resultado.
    """
    try:
        with open(registro_caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return ["registro ilegível: %s — nada tocado" % registro_caminho], None, False, 0
    itens = dados.get("publicados") if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        return ["registro sem a lista 'publicados' — nada tocado"], None, False, 0
    linhas, mudou, sem_resposta = [], False, 0
    for item in itens:
        if not isinstance(item, dict):
            continue
        vid = item.get("id")
        titulo, descricao = ler_do_canal(vid, abrir=abrir)
        if descricao is None:
            sem_resposta += 1
            linhas.append("%s: o canal não respondeu — registro fica como está" % vid)
            continue
        antes = (item.get("descricao") or "", item.get("descricao_completa"))
        item["descricao"] = _resumo_da_descricao(descricao)
        item["descricao_completa"] = len(descricao.strip()) <= 600
        item["descricao_no_canal"] = len(descricao.strip())
        item["conferido_em"] = hoje or "conferido"
        if titulo and not item.get("titulo"):
            item["titulo"] = titulo[:120]
        depois = (item["descricao"], item["descricao_completa"])
        mudou = mudou or (antes != depois)
        linhas.append("%s: no canal %d caracteres · registro %d · inteira=%s"
                      % (vid, len(descricao.strip()), len(item["descricao"]),
                         item["descricao_completa"]))
    return linhas, dados, mudou, sem_resposta


def gravar(registro_caminho, dados):
    with open(registro_caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="confere o registro do canal contra o que está no ar")
    ap.add_argument("--registro", default=REGISTRO)
    ap.add_argument("--ensaio", action="store_true", help="só mostra, não grava")
    ap.add_argument("--hoje", default="", help="data da conferência (padrão: data de hoje em UTC)")
    a = ap.parse_args(argv[1:])
    hoje = a.hoje
    if not hoje:
        import datetime
        hoje = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    linhas, dados, mudou, sem_resposta = conferir(a.registro, hoje=hoje)
    for linha in linhas:
        print(linha)
    total = len([x for x in ((dados or {}).get("publicados") or []) if isinstance(x, dict)]) or len(linhas)
    print("registro: %d vídeo(s) conferido(s) · %d sem resposta · %s"
          % (total - sem_resposta, sem_resposta, "mudou" if mudou else "sem mudança"))
    if dados is None:
        return 1
    if sem_resposta and sem_resposta == total:
        print("sem rede para conferir: nada tocado (SKIP)")
        return 2
    if a.ensaio:
        return 0
    if mudou:
        gravar(a.registro, dados)
        print("registro atualizado em %s" % a.registro)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
