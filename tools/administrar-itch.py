#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Administração automática do itch.io — sem clique do dono.

O que o itch permite automatizar, medido em 26/10:

  * SUBIR BUILD: sim. `butler push` com API key (é o único caminho de escrita que existe;
    a API oficial de leitura não tem POST nenhum).
  * LER ESTADO: sim. api.itch.io/profile/games, /games/{id}/uploads, /profile/builds.
  * EDITAR PÁGINA (texto, capa, tags), CRIAR PÁGINA, PUBLICAR RASCUNHO, ESCREVER DEVLOG:
    não. Não é limitação nossa nem falta de chave — o itch não expõe API para isso, e já
    declarou publicamente que não vai expor ("we don't provide APIs for people to post things
    since it may contribute to spam"). Isso fica no navegador, com o dono.

Então este script automatiza o que dá, e no que não dá ele NÃO finge: registra o que faria e
deixa o texto pronto. Regra da casa: medição errada é pior que medição ausente.

Decisão de envio é por medida, não por palpite: compara a impressão digital da pasta local com
o upload que está no itch. Igual = não faz nada. Diferente ou inexistente = envia.
"""
import hashlib
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))


def _modulo_do_envio():
    """Carrega tools/enviar-itch.py (nome com hífen não é importável direto)."""
    import importlib.util
    caminho = os.path.join(RAIZ, "tools", "enviar-itch.py")
    spec = importlib.util.spec_from_file_location("enviar_itch", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


itch = _modulo_do_envio()

NUNCA = os.path.join(RAIZ, "posts", "nunca-publicar.json")

# projeto no itch -> (pasta do build, canal). O canal é o do export web.
PROJETOS = {
    "ceifalume": {"pasta": "ceifalume", "alvo": "rebocl-brank/ceifalume",
                  "canal": "html5", "slug_itch": "ceifalume"},
}


def vetados(caminho=NUNCA):
    """Slugs que o dono mandou nunca publicar. Sem arquivo, assume o pior: nada é enviado."""
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        return [s.strip().lower() for s in dados.get("nunca_publicar") or []]
    except Exception:
        return ["*"]  # sem lista, ninguém sobe


def impressao(pasta, raiz=RAIZ):
    """Impressão digital do build: hash do conjunto (nome, tamanho, conteúdo).

    Serve para comparar local e remoto sem baixar 40 MB do itch.
    """
    base = os.path.join(raiz, pasta)
    if not os.path.isdir(base):
        return None
    itens = []
    total = 0
    for dirpath, _dirs, arquivos in os.walk(base):
        for nome in sorted(arquivos):
            caminho = os.path.join(dirpath, nome)
            rel = os.path.relpath(caminho, base).replace(os.sep, "/")
            with open(caminho, "rb") as f:
                resumo = hashlib.sha256(f.read()).hexdigest()
            tamanho = os.path.getsize(caminho)
            total += tamanho
            itens.append("%s|%d|%s" % (rel, tamanho, resumo))
    itens.sort()
    h = hashlib.sha256("\n".join(itens).encode("utf-8")).hexdigest()
    return {"hash": h, "bytes": total, "arquivos": len(itens)}


def uploads_do_jogo(nome, chave, get=None):
    """Uploads do jogo no itch (canal, tamanho, build_id). Só leitura.

    Vai direto na API porque `listar_jogos` devolve só o que o placar usa e descarta o `id`,
    e é o `id` que abre /games/{id}/uploads. Reaproveitar o resumo seria chute.
    """
    get = get or itch._get_json
    dados, erro = get("https://api.itch.io/profile/games", chave)
    if erro or not isinstance(dados, dict):
        return []
    slug_alvo = PROJETOS.get(nome, {}).get("alvo", "").split("/")[-1].lower()
    for jogo in dados.get("games") or []:
        url = (jogo.get("url") or "").rstrip("/").split("/")[-1].lower()
        if url == slug_alvo:
            uploads, erro2 = get("https://api.itch.io/games/%s/uploads" % jogo["id"], chave)
            if erro2 or not isinstance(uploads, dict):
                return []
            return uploads.get("uploads") or []
    return []


def interpretar_status(saida, canal, hash_local=None):
    """Lê `butler status alvo` e diz (existe, versao).

    Canal criado por butler NÃO aparece em /games/{id}/uploads — aquele endpoint lista upload
    feito pelo site. Quem enxerga canal é o próprio butler. Medido: depois do push, o endpoint
    continuou listando só os 2 uploads antigos.
    """
    texto = saida or ""
    existe = canal in texto and "no channel found" not in texto.lower()
    versao = None
    if existe and hash_local:
        for pedaco in texto.replace(":", " ").replace("/", " ").split():
            if pedaco.strip("()[],") == hash_local[:12]:
                versao = pedaco.strip("()[],")
                break
    return existe, versao


def decidir(nome, local, remotos, canal=None):
    """Devolve (acao, motivo). Ação é 'enviar', 'nada' ou 'bloqueado'.

    Tudo aqui é comparação de número medido — nada de "acho que mudou".
    """
    if nome.lower() in vetados() or "*" in vetados():
        return "bloqueado", "o dono vetou este jogo (posts/nunca-publicar.json)"
    if local is None:
        return "bloqueado", "não existe build na pasta (nada a enviar)"
    canal = canal or PROJETOS.get(nome, {}).get("canal", "html5")
    do_canal = [u for u in remotos if (u.get("channel_name") or "") == canal]
    if not do_canal:
        return "enviar", "canal '%s' ainda não existe no itch → primeiro envio" % canal
    remoto = do_canal[0]
    if int(remoto.get("size") or -1) == local["bytes"]:
        return "nada", "upload do canal tem exatamente %d bytes, igual ao local" % local["bytes"]
    return "enviar", "tamanho difere: local %d B · itch %s B" % (local["bytes"], remoto.get("size"))


def estado(nome, chave, raiz=RAIZ, get=None):
    """Só leitura: mostra a decisão e o que está no itch. É o modo padrão."""
    if nome not in PROJETOS:
        # jogo vetado costuma nem estar na lista de projetos: a decisão vem antes da rede,
        # porque nem consultar o itch sobre jogo vetado faz sentido.
        acao, motivo = decidir(nome, None, [])
        return acao, motivo, ["local: —", "itch: não consultado", "decisão: %s — %s" % (acao, motivo)]
    local = impressao(PROJETOS[nome]["pasta"], raiz=raiz)
    if nome.lower() in vetados():
        acao, motivo = decidir(nome, local, [])
        return acao, motivo, ["local: vetado", "itch: não consultado", "decisão: %s — %s" % (acao, motivo)]
    remotos = uploads_do_jogo(nome, chave, get=get)
    acao, motivo = decidir(nome, local, remotos)
    linhas = ["local: " + ("—" if not local else "%d arquivos, %d bytes, hash %s…"
                           % (local["arquivos"], local["bytes"], local["hash"][:12])),
              "itch: %d upload(s)" % len(remotos)]
    for u in remotos:
        linhas.append("  canal=%s size=%s build=%s id=%s"
                      % (u.get("channel_name"), u.get("size"), u.get("build_id"), u.get("id")))
    linhas.append("decisão: %s — %s" % (acao, motivo))
    return acao, motivo, linhas


def auto(nome, chave, raiz=RAIZ, get=None, identidade=None, executar=None,
         esperar=None, limite_s=300):
    """Administra: envia se (e só se) a medida disser que mudou, e prova no remoto.

    A prova é `butler status` relido depois do push, com espera: o itch processa o build
    ("Build is now processing") e a primeira leitura volta vazia. Ler uma vez só produziu
    falso negativo de verdade nesta casa — envio OK, log dizendo falha.
    """
    if nome.lower() in vetados() or "*" in vetados() or nome not in PROJETOS:
        acao, motivo = decidir(nome, None, [])
        return acao, motivo, ["decisão: %s — %s" % (acao, motivo)]
    local = impressao(PROJETOS[nome]["pasta"], raiz=raiz)
    if local is None:
        return "bloqueado", "não existe build na pasta (nada a enviar)", []
    alvo = PROJETOS[nome]["alvo"]
    canal = PROJETOS[nome]["canal"]
    linhas = ["local: %d arquivos, %d bytes, hash %s…"
              % (local["arquivos"], local["bytes"], local["hash"][:12])]

    codigo, saida = itch.rodar(["status", alvo], identidade=identidade,
                               executar=executar, chave=chave)
    existe, versao = interpretar_status(saida, canal, local["hash"])
    linhas.append("canal no itch: %s%s" % ("existe" if existe else "não existe",
                                           "" if not versao else " · versão " + versao))
    if existe and versao == local["hash"][:12]:
        return "nada", "build local e versão publicada são a mesma (%s)" % versao, linhas

    codigo, saida = itch.rodar(
        ["push", os.path.join(raiz, PROJETOS[nome]["pasta"]), "%s:%s" % (alvo, canal),
         "--assume-yes", "--hidden", "--if-changed", "--userversion", local["hash"][:12]],
        identidade=identidade, executar=executar, chave=chave)
    if codigo != 0:
        return "falhou", "butler recusou: " + (saida or "")[:400], linhas
    linhas.append("butler: " + " ".join((saida or "").split())[:280])

    # espera o itch processar e relê até confirmar
    esperar = esperar or (lambda s: time.sleep(s))
    passado = 0
    while passado < limite_s:
        passado += 20
        esperar(20)
        codigo, saida2 = itch.rodar(["status", alvo], identidade=identidade,
                                    executar=executar, chave=chave)
        existe2, versao2 = interpretar_status(saida2, canal, local["hash"])
        if existe2:
            linhas.append("remoto confirmado após %ds: canal %s · versão %s"
                          % (passado, canal, versao2 or "não exposta"))
            return "enviado", "canal '%s' confirmado no itch" % canal, linhas
    linhas.append("butler enviou, mas o canal não apareceu em %ds" % limite_s)
    return "enviado_nao_confirmado", "envio feito, confirmação pendente (itch processando)", linhas


def main(argv):
    if len(argv) < 2 or argv[1] not in ("estado", "auto"):
        print("uso: administrar-itch.py estado|auto [jogo]")
        return 2
    modo = argv[1]
    nome = argv[2] if len(argv) > 2 else "ceifalume"
    if nome not in PROJETOS:
        print("jogo desconhecido: " + nome)
        return 2
    chave = itch.chave_do_ambiente("ITCH_API_KEYS") or itch.chave_do_ambiente("ITCH_API_KEY")
    if not chave:
        print("sem chave do itch no ambiente (ITCH_API_KEYS) — não dá para administrar às cegas")
        return 1
    print("chave do itch: " + itch.resumo_de_chave(chave))
    if modo == "estado":
        acao, motivo, linhas = estado(nome, chave)
    else:
        identidade = itch.arquivo_de_identidade(chave)
        try:
            acao, motivo, linhas = auto(nome, chave, identidade=identidade)
        finally:
            try:
                os.unlink(identidade)
            except OSError:
                pass
    for linha in linhas:
        print("  " + linha)
    print(("✓ " if acao in ("nada", "enviado") else "✗ ") + acao + ": " + motivo)
    return 0 if acao in ("nada", "enviado") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
