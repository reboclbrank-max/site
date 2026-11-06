#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chamada do vídeo: leva quem já segue a casa até o vídeo que acabou de sair.

POR QUE EXISTE (06/11/2026). A régua de adesão mediu o óbvio que ninguém tinha medido: o canal
tem 24 inscritos, a mediana de views dos últimos 49 vídeos é **9**, e os três vídeos publicados
hoje estavam com **0 views**. Não é falha de título nem de horário — nada apontava para eles.
E a casa TEM audiência, só que em outro lugar: o Bluesky, com 32 seguidores e 300 posts
próprios (posts/desempenho.md). Atração não se prova esperando; prova-se ligando quem existe ao
que foi publicado.

O QUE FAZ: pega o vídeo mais recente do registro, escreve a chamada com o que o vídeo já afirma
(título + números medidos da partida) e publica no Bluesky com cartão de link. Passa pelo MESMO
portão dos outros canais e por três regras próprias:

  1. janela do dono (9h–22h de Brasília);
  2. o mesmo vídeo não é chamado duas vezes (ficam registradas todas as chamadas);
  3. texto igual ao de uma chamada anterior não sai.

Recusa sai com motivo escrito e fica registrada em `posts/chamadas.json` — chamada que não
aconteceu também é informação.

O QUE NÃO FAZ: não inventa número (usa o que o vídeo já diz), não menciona os dois jogos, não
promete ("imperdível", "viral"), e não publica sem credencial viva do Bluesky.
"""
import datetime
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO_VIDEOS = os.path.join("posts", "youtube-publicados.json")
REGISTRO_CHAMADAS = os.path.join("posts", "chamadas.json")
JANELA_DO_CANAL = {"janela": {"inicio": 9, "fim": 22}}
FUSO_DO_CANAL = -3
LIMITE_BLUESKY = 300
API = "https://bsky.social/xrpc"


def agora_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def hora_local(agora=None):
    agora = agora or agora_utc()
    return (agora + datetime.timedelta(hours=FUSO_DO_CANAL)).hour


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower()


def _modulo(nome, arquivo):
    import importlib.util
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _portao():
    return _modulo("portao_publicacao", "portao-publicacao.py")


def ler_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def video_mais_recente(raiz=RAIZ):
    dados = ler_json(os.path.join(raiz, REGISTRO_VIDEOS), {"publicados": []})
    itens = dados.get("publicados") if isinstance(dados, dict) else dados
    if not isinstance(itens, list) or not itens:
        return None
    validos = [x for x in itens if isinstance(x, dict) and x.get("id") and x.get("titulo")]
    if not validos:
        return None
    return validos[0]


def chamadas(raiz=RAIZ):
    dados = ler_json(os.path.join(raiz, REGISTRO_CHAMADAS), {"chamadas": []})
    itens = dados.get("chamadas") if isinstance(dados, dict) else dados
    return [x for x in itens or [] if isinstance(x, dict)]


def historico_do_canal(raiz=RAIZ):
    """As chamadas anteriores como publicações do canal bluesky — o portão compara com elas."""
    saida = []
    for item in chamadas(raiz):
        if (item.get("canal") or "") != "bluesky":
            continue
        saida.append({"canal": "bluesky", "titulo": item.get("titulo") or "",
                      "texto": item.get("texto") or "", "quando": item.get("quando")})
    saida.sort(key=lambda x: str(x.get("quando") or ""), reverse=True)
    return saida


def numeros_do_video(video):
    """A linha de fato da chamada: o que o vídeo já afirma, sem inventar nada."""
    numeros = video.get("numeros") if isinstance(video.get("numeros"), dict) else {}
    partes = []
    if numeros.get("plantadas"):
        partes.append("%d mudas" % numeros["plantadas"])
    if numeros.get("colhidas"):
        partes.append("%d colheitas" % numeros["colhidas"])
    if numeros.get("minutos"):
        partes.append("em %d minutos" % numeros["minutos"])
    return ", ".join(partes)


def montar_chamada(video):
    """O texto da chamada, com link. Curto porque o limite do Bluesky é 300 caracteres."""
    titulo = str(video.get("titulo") or "").strip()
    link = "https://youtu.be/" + str(video.get("id"))
    linha = numeros_do_video(video)
    partes = ["Vídeo novo no canal: \"%s\"." % titulo]
    if linha:
        partes.append("Na partida gravada: %s." % linha)
    corpo = " ".join(partes)
    espaço = LIMITE_BLUESKY - len(link) - 1
    if len(corpo) > espaço:
        corpo = corpo[:espaço - 1].rstrip(" ,.;:") + "…"
    return "%s\n%s" % (corpo, link)


def ja_chamado(video_id, raiz=RAIZ):
    for item in chamadas(raiz):
        if str(item.get("video_id")) == str(video_id) and item.get("resultado") == "publicado":
            return item
    return None


def texto_repetido(texto, raiz=RAIZ):
    alvo = _sem_acento(" ".join(str(texto or "").split()))
    for item in chamadas(raiz):
        anterior = _sem_acento(" ".join(str(item.get("texto") or "").split()))
        if anterior and anterior == alvo:
            return item
    return None


def decidir(video, texto, raiz=RAIZ, hora=None, publicacoes=None, avaliador=None):
    """(libera, motivo, números). Nenhuma chamada sai sem esta resposta."""
    if not video:
        return False, "nenhum vídeo publicado no registro — não há o que chamar", {}
    hora = hora_local() if hora is None else int(hora)
    anterior = ja_chamado(video["id"], raiz)
    if anterior:
        return False, ("este vídeo já foi chamado em %s (%s) — chamar de novo seria repetir"
                       % (anterior.get("quando"), anterior.get("canal"))), {"video": video["id"]}
    repetido = texto_repetido(texto, raiz)
    if repetido:
        return False, "texto igual ao de uma chamada anterior (%s)" % repetido.get("quando"), {}
    avalia = avaliador or _portao().avalia
    hist = historico_do_canal(raiz) if publicacoes is None else publicacoes
    titulo = str(video.get("titulo") or "")
    decisao = avalia({"titulo": titulo, "texto": texto}, canal="bluesky", publicacoes=hist,
                     calendario=JANELA_DO_CANAL, hora_local=hora,
                     credencial_disponivel=True) or {}
    numeros = {"video": video["id"], "historico_do_canal": len(hist)}
    numeros.update(decisao.get("numeros") or {})
    return bool(decisao.get("publica")), str(decisao.get("motivo") or ""), numeros


def _pedir(url, corpo, cabecalhos=None, abrir=urllib.request.urlopen):
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    cab = {"Content-Type": "application/json", "Accept": "application/json"}
    cab.update(cabecalhos or {})
    req = urllib.request.Request(url, data=dados, headers=cab,
                                 method="POST" if dados else "GET")
    with abrir(req, timeout=30) as resposta:
        texto = resposta.read().decode("utf-8")
    return json.loads(texto) if texto.strip() else {}


def publicar(texto, link, handle, senha, pedir=None):
    """Publica a chamada no Bluesky com cartão de link. Devolve (uri, erro)."""
    pedir = pedir or _pedir
    if not (handle and senha):
        return None, "sem credencial do Bluesky (BLUESKY_HANDLE/BLUESKY_APPPASS)"
    try:
        sessao = pedir(API + "/com.atproto.server.createSession",
                       {"identifier": handle, "password": senha})
        jwt = (sessao or {}).get("accessJwt")
        did = (sessao or {}).get("did")
        if not (jwt and did):
            return None, "o Bluesky não devolveu sessão"
        registro = {
            "text": texto[:LIMITE_BLUESKY],
            "createdAt": agora_utc().isoformat().replace("+00:00", "Z"),
            "langs": ["pt-BR"],
            "embed": {"$type": "app.bsky.embed.external",
                      "external": {"uri": link, "title": texto.splitlines()[0][:120],
                                   "description": "Gameplay gravado do jogo rodando no navegador."}},
        }
        resposta = pedir(API + "/com.atproto.repo.createRecord",
                         {"repo": did, "collection": "app.bsky.feed.post", "record": registro},
                         {"Authorization": "Bearer " + jwt})
        uri = (resposta or {}).get("uri")
        if not uri:
            return None, "o Bluesky não devolveu o uri do post"
        return uri, None
    except Exception as erro:
        return None, type(erro).__name__ + ": " + str(erro)[:140]


def registrar(entrada, raiz=RAIZ):
    caminho = os.path.join(raiz, REGISTRO_CHAMADAS)
    dados = ler_json(caminho, {"_o_que_e": "chamadas de vídeo publicadas nos canais da casa — "
                                            "é isto que impede chamar o mesmo vídeo duas vezes",
                               "chamadas": []})
    lista = [x for x in (dados.get("chamadas") or []) if isinstance(x, dict)]
    lista.insert(0, entrada)
    dados["chamadas"] = lista[:200]
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return caminho


def executar(raiz=RAIZ, ensaio=False, hora=None, publicacoes=None, avaliador=None,
             post=None, escrever=print):
    """(ok, mensagem). Ensaiar não publica e não registra publicação."""
    video = video_mais_recente(raiz)
    if not video:
        return False, "nenhum vídeo publicado no registro — não há o que chamar"
    texto = montar_chamada(video)
    libera, motivo, numeros = decidir(video, texto, raiz=raiz, hora=hora,
                                      publicacoes=publicacoes, avaliador=avaliador)
    escrever("chamada do vídeo %s (%s)" % (video["id"], video.get("angulo") or "sem ângulo"))
    escrever("portão: " + motivo)
    escrever("texto:\n" + texto)
    if not libera:
        if not ensaio:
            registrar({"quando": agora_utc().isoformat().replace("+00:00", "Z"),
                       "video_id": video["id"], "canal": "bluesky", "texto": texto,
                       "titulo": video.get("titulo"), "resultado": "recusado", "motivo": motivo,
                       "numeros": numeros}, raiz=raiz)
        return False, "recusado: " + motivo
    if ensaio:
        escrever("ensaio: nada é publicado e nada é registrado")
        return True, "ensaio ok"
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    senha = os.environ.get("BLUESKY_APPPASS", "").strip()
    uri, erro = publicar(texto, "https://youtu.be/" + str(video["id"]), handle, senha, pedir=post)
    entrada = {"quando": agora_utc().isoformat().replace("+00:00", "Z"),
               "video_id": video["id"], "canal": "bluesky", "texto": texto,
               "titulo": video.get("titulo"), "uri": uri,
               "resultado": "publicado" if uri else "falhou", "erro": erro,
               "numeros": numeros}
    registrar(entrada, raiz=raiz)
    if not uri:
        return False, "a chamada não saiu: " + str(erro)
    escrever("chamada publicada: " + str(uri))
    return True, "publicada: " + str(uri)


def main(argv):
    ensaio = "--ensaio" in argv
    ok, mensagem = executar(ensaio=ensaio)
    print(("✓ " if ok else "✗ ") + mensagem)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
