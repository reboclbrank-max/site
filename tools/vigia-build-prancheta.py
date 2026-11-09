#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vigia do build do PRANCHETA: qual versão está publicada no itch, e mudou?

POR QUE EXISTE (07/11/2026): o PRANCHETA é o único jogo da casa cujo build não passa por aqui —
ele vive publicado no itch e o dono sobe na mão. A conseqüência medida: a gravação automática
(`gravar-prancheta`) filma **a página do itch**, então ela filma o que estiver lá, novo ou velho,
e nada registra a diferença. O `administrar-itch` não cobre esse jogo (não há build no
repositório para empurrar).

Este vigia não sobe nada: ele lê o id do build que o itch está servindo e compara com o último que
a casa viu. Quando muda, a casa sabe — e diz. Sem isso, "atualizei o PRANCHETA" e "não atualizei"
são a mesma coisa para todo mundo aqui.

O id vem do endereço do jogador: `html-classic.itch.zone/html/<id>/index.html` (é assim que o
próprio `gravar-prancheta.js` descobre o build — mesma medida, um lugar só).

Uso:
    python3 tools/vigia-build-prancheta.py            # mede e diz se mudou (não escreve)
    python3 tools/vigia-build-prancheta.py --gravar   # mede e registra em posts/prancheta-build.json

Códigos: 0 mediu (novo ou igual) · 3 não deu para medir (rede, página sem build).
"""
import datetime
import json
import os
import re
import subprocess
import sys

import importlib.util

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "prancheta-build.json")
PAGINA = "https://rebocl-brank.itch.io/prancheta"

# O iframe do itch aponta para o build atual. Já apareceu como html-classic e como html.
PADRAO = re.compile(r"itch\.zone/html/(\d{4,})/")


def _fila():
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fila-tarefas.py")
    spec = importlib.util.spec_from_file_location("fila_tarefas", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def extrair_build(html):
    """O id do build no HTML da página; None quando a página não mostra build nenhum."""
    if not html:
        return None
    achados = PADRAO.findall(html)
    if not achados:
        return None
    # Se a página citar mais de um, vale o primeiro: é o iframe do jogador.
    return achados[0]


def buscar_texto(url, tempo=30):
    """Baixa a página. Levanta erro com o motivo — falha de rede não pode virar 'igual'."""
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", str(tempo), "-A", "Mozilla/5.0", url],
                           capture_output=True, text=True)
    except OSError as erro:
        raise RuntimeError("curl não rodou: %s" % erro)
    if r.returncode != 0:
        raise RuntimeError("curl falhou (código %d): %s"
                           % (r.returncode, (r.stderr or "").strip()[:160]))
    if not r.stdout.strip():
        raise RuntimeError("a página veio vazia (bloqueio ou rede)")
    return r.stdout


def ler_registro(caminho=None):
    # resolvido na hora: caminho fixo no `def` não aceita troca em teste (foi assim que o teste
    # do `medir` acabou medindo o itch de verdade na primeira versão).
    caminho = caminho or REGISTRO
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def comparar(build, registro):
    """(situação, frase). Situação é o que o resto da casa lê: novo, igual, mudou ou não medido."""
    if not build:
        return "não medido", "a página do itch não mostrou id de build — não afirmo nada"
    anterior = (registro or {}).get("build_id")
    if not anterior:
        return "novo", "build %s — primeiro registro da casa" % build
    if str(anterior) == str(build):
        quando = (registro or {}).get("medido_em") or "data não registrada"
        return "igual", "build %s — o mesmo desde %s" % (build, quando)
    quando = (registro or {}).get("medido_em") or "data não registrada"
    return "mudou", "build %s no lugar do %s (que a casa viu em %s)" % (build, anterior, quando)


def gravar(build, situacao, caminho=None, agora=None):
    """Registra o build medido. Só é chamado quando houve medida — nunca para 'não medido'."""
    if not build:
        raise ValueError("não se grava build que não foi medido")
    caminho = caminho or REGISTRO
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    registro = ler_registro(caminho)
    antes = registro.get("build_id")
    historico = registro.get("historico") or []
    if str(antes) != str(build) and antes:
        historico.append({"build_id": antes, "medido_em": registro.get("medido_em")})
    dados = {
        "_o_que_e": "qual build do PRANCHETA o itch está servindo, e desde quando a casa sabe",
        "build_id": str(build),
        "medido_em": agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pagina": PAGINA,
        "situacao": situacao,
        "historico": historico[-20:],
    }
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return dados


def medir(buscar=None, caminho=None, url=PAGINA):
    """Mede e devolve (situação, frase, build). Erro de rede vira 'não medido', não exceção.

    `buscar`/`caminho` são resolvidos na hora (e não no `def`) para que o teste possa trocar os
    dois sem tocar na rede — a primeira versão amarrava o padrão e o teste media o itch de verdade.
    """
    buscar = buscar or buscar_texto
    caminho = caminho or REGISTRO
    registro = ler_registro(caminho)
    try:
        html = buscar(url)
    except RuntimeError as erro:
        return "não medido", "não deu para medir: %s" % erro, None
    build = extrair_build(html)
    situacao, frase = comparar(build, registro)
    return situacao, frase, build


FATOS = os.path.join(RAIZ, "posts", "fatos.json")


def registrar_fato(build, anterior, caminho=None, quando=None):
    """Build novo vira FATO no repertório do redator — não vira post na marra.

    Por que fato e não tarefa de publicar (medido no código, 07/11/2026): o pulso executa
    `tools/postador.py` sem argumento nenhum, então uma tarefa "publicar" produz um post qualquer
    e o motivo escrito nela não chega ao texto — motivo que promete "divulgar a versão nova" e
    entrega outro assunto é mentira com carimbo. O que o redator realmente lê são os FATOS
    (`posts/fatos.json`): o assunto entra lá, com a afirmação que a casa pode sustentar, e o
    portão decide se e quando vira post.

    Deduplica por id: o mesmo build não vira fato duas vezes.
    """
    caminho = caminho or FATOS
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        dados = {"fatos": []}
    fatos = dados.setdefault("fatos", [])
    ident = "prancheta-build-%s" % build
    if any(str(f.get("id")) == ident for f in fatos):
        return None
    quando = quando or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    fato = {
        "id": ident,
        "assunto": "prancheta",
        # CLASSE IMPORTANTE (07/11/2026): o redator só monta pauta com as classes que os ângulos
        # permitem (`mecanica`, `numero`, `bastidor`, `cultura`, `disponibilidade`, `canal`,
        # `marco`). "estado" não existe lá — fato com classe inventada seria arquivo morto com
        # cara de conteúdo. Build novo é marco.
        "classe": "marco",
        "afirmacao": ("o PRANCHETA no itch passou para o build %s em %s (antes, o build %s)"
                      % (build, quando, anterior)),
        "origem": "posts/prancheta-build.json",
        "quando": quando,
        "repetivel": False,
        # anunciado uma vez só, e vence: "saiu atualização" não é verdade eterna
        "usa_uma_vez": True,
        "validade_dias": 45,
    }
    fatos.append(fato)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return fato


def main(argv):
    quer_gravar = "--gravar" in argv
    situacao, frase, build = medir()
    print("PRANCHETA no itch: " + frase)
    if situacao == "não medido":
        print("nada foi escrito: sem medida, sem registro")
        return 3
    if quer_gravar and situacao in ("novo", "mudou"):
        anterior = ler_registro().get("build_id")
        dados = gravar(build, situacao)
        print("registrado em posts/prancheta-build.json (build %s, %s)"
              % (dados["build_id"], dados["medido_em"]))
        if situacao == "mudou":
            fato = registrar_fato(build, anterior)
            if fato:
                print("repertório: fato %s registrado — o redator pode usar quando o portão abrir"
                      % fato["id"])
            else:
                print("repertório: esse build já estava registrado como fato")
    elif quer_gravar:
        print("registro já estava em dia — nada a escrever")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
