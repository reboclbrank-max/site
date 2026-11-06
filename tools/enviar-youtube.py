#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envio de vídeo ao YouTube pelo pacote do kit — com dois portões, e nenhum é o relógio.

HISTÓRIA (06/11/2026). Até aqui a regra era "só com a palavra PUBLICAR", e o resultado medido
foi: o canal com 163 vídeos e **títulos repetidos** (o mesmo "CEIFALUME 0.1 — gameplay gravado
no navegador" foi ao ar três vezes), 24 inscritos e 5.471 visualizações. Palavra humana não é
critério: ela libera o primeiro envio e libera a duplicata do mesmo jeito.

Agora existem dois caminhos, e os dois têm prova:

  MANUAL  (CONFIRMACAO=PUBLICAR) — o dono pediu. Continua valendo, e continua registrando.
  AUTOMÁTICO (CONFIRMACAO=AUTOMATICO) — dois portões, e nenhum é a palavra:
          1) ARQUIVO: o sha256 do arquivo não pode estar em `posts/videos-enviados.json`;
          2) FORMA: título e descrição passam pelo `tools/portao-publicacao.py` (canal
             youtube, janela 09-22h de Brasília) contra o que o canal já publicou. Sem isso,
             gravar de novo o mesmo jogo viraria o mesmo título pela quarta vez — o arquivo
             muda (outra partida), o texto não. Foi exatamente o defeito medido em 06/11/2026.

O que ele faz: pega o pacote já validado em `posts/kit-youtube.json`, renova o token a partir
do refresh_token guardado nos segredos e faz o upload resumable. Tudo o que aparece no vídeo
(título, descrição, tags) vem do kit — aqui não se inventa texto.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import youtube_oauth as oauth


def _validador_do_kit():
    """Importa tools/kit-youtube.py (nome com hífen) e devolve a função de validação."""
    import importlib.util
    caminho = os.path.join(RAIZ, "tools", "kit-youtube.py")
    spec = importlib.util.spec_from_file_location("kit_youtube", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.validar

KIT = os.path.join(RAIZ, "posts", "kit-youtube.json")
URL_UPLOAD = ("https://www.googleapis.com/upload/youtube/v3/videos"
              "?uploadType=resumable&part=snippet,status")
PALAVRA_CONFIRMACAO = "PUBLICAR"
PALAVRA_AUTOMATICA = "AUTOMATICO"
REGISTRO_IMPRESSOES = os.path.join("posts", "videos-enviados.json")
REGISTRO_PUBLICADOS = os.path.join("posts", "youtube-publicados.json")

# O horário do canal é o do dono: Brasília (UTC-3). "Horário perfeito" é critério dele, então
# vídeo publicado às 4h da manhã local também é repetição de erro — a janela vale para o vídeo.
FUSO_DO_CANAL = -3
JANELA_DO_CANAL = {"janela": {"inicio": 9, "fim": 22}}


def impressao(caminho):
    """sha256 do arquivo — a identidade real do vídeo, não o nome dele."""
    import hashlib
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_registro(raiz=RAIZ):
    caminho = os.path.join(raiz, REGISTRO_IMPRESSOES)
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict) and isinstance(dados.get("enviados"), list):
            return dados
    except (OSError, ValueError):
        pass
    return {"_o_que_e": "impressão sha256 de cada vídeo já enviado ao YouTube — é isto que "
                       "impede o mesmo vídeo de subir duas vezes",
            "enviados": []}


def ja_enviado(sha, raiz=RAIZ):
    """O registro daquele vídeo exato, ou None."""
    for item in ler_registro(raiz).get("enviados") or []:
        if isinstance(item, dict) and item.get("sha256") == sha:
            return item
    return None


def registrar_impressao(sha, slug, vid, arquivo, raiz=RAIZ, quando=None, escrever=print):
    dados = ler_registro(raiz)
    lista = [x for x in (dados.get("enviados") or []) if isinstance(x, dict) and x.get("sha256") != sha]
    lista.insert(0, {"sha256": sha, "slug": slug, "id": vid, "arquivo": arquivo,
                     "quando": quando or datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"})
    dados["enviados"] = lista[:200]
    caminho = os.path.join(raiz, REGISTRO_IMPRESSOES)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    escrever("impressão registrada: " + sha[:12] + "… (vídeo " + str(vid) + ")")
    return caminho


def pode_enviar_sozinho(pacote, raiz=RAIZ, impressora=None):
    """(ok, motivo). O portão do vídeo: só passa o que é comprovadamente novo."""
    caminho = arquivo_do_video(pacote, raiz)
    if not os.path.exists(caminho):
        return False, "arquivo ausente: " + str(pacote.get("arquivo"))
    sha = (impressora or impressao)(caminho)
    anterior = ja_enviado(sha, raiz)
    if anterior:
        return False, ("vídeo idêntico já publicado (https://youtu.be/%s, em %s) — repetir "
                       "seria duplicata" % (anterior.get("id"), anterior.get("quando")))
    return True, "vídeo novo (sha256 %s…)" % sha[:12]


def _portao_de_texto():
    """Importa tools/portao-publicacao.py (nome com hífen) — o mesmo portão dos outros canais."""
    import importlib.util
    caminho = os.path.join(RAIZ, "tools", "portao-publicacao.py")
    spec = importlib.util.spec_from_file_location("portao_publicacao", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def hora_local_do_canal(agora=None):
    """Hora cheia em Brasília — a janela do canal é medida nesse relógio, não em UTC."""
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=datetime.timezone.utc)
    return (agora + datetime.timedelta(hours=FUSO_DO_CANAL)).hour


def historico_publicado(raiz=RAIZ):
    """O que o canal já publicou, do mais novo para o mais antigo.

    Lê `posts/youtube-publicados.json` (o registro público que o chat lê). A ordem importa: o
    portão compara com os recentes primeiro — lista em ordem cronológica deixaria passar
    repetição contra o começo da história.
    """
    caminho = os.path.join(raiz, REGISTRO_PUBLICADOS)
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return []
    itens = dados.get("publicados") if isinstance(dados, dict) else dados
    if not isinstance(itens, list):
        return []
    saida = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        saida.append({"canal": "youtube",
                      "titulo": str(item.get("titulo") or ""),
                      "texto": str(item.get("descricao") or item.get("texto") or ""),
                      "angulo": item.get("angulo"),
                      "id": item.get("id"), "quando": item.get("quando")})
    saida.sort(key=lambda x: str(x.get("quando") or ""), reverse=True)
    return saida


def portao_do_texto(pacote, raiz=RAIZ, hora_local=None, publicacoes=None, avaliador=None):
    """(libera, motivo, números). O portão de FORMA do vídeo: título novo, janela do dono.

    O sha256 só sabe dizer "este arquivo é o mesmo". Ele não sabe que "CEIFALUME 0.1 — gameplay
    gravado no navegador" já foi ao ar três vezes com arquivos diferentes. Quem sabe é este.
    """
    avalia = avaliador or _portao_de_texto().avalia
    candidato = {"titulo": str(pacote.get("titulo") or ""),
                 "texto": str(pacote.get("descricao") or "")}
    historico = historico_publicado(raiz) if publicacoes is None else publicacoes
    hora = hora_local_do_canal() if hora_local is None else int(hora_local)
    decisao = avalia(candidato, canal="youtube", publicacoes=historico,
                     calendario=JANELA_DO_CANAL, hora_local=hora) or {}
    return (bool(decisao.get("publica")), str(decisao.get("motivo") or ""),
            decisao.get("numeros") or {})


def carregar_kit(caminho=KIT):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def pacote_do_kit(dados, slug):
    """Aceita tanto o slug do jogo quanto o id do pacote (ex.: "ceifalume-gameplay").

    Sem isso, o vídeo de gameplay — que é do mesmo jogo mas de outro pacote — não teria
    como ser escolhido sem duplicar o kit inteiro.
    """
    for p in dados.get("pacotes") or []:
        if p.get("slug") == slug or p.get("id") == slug:
            return p
    return None


def metadados(pacote):
    """Corpo do upload — construído a partir do kit, sem texto novo."""
    return {
        "snippet": {
            "title": pacote["titulo"],
            "description": pacote["descricao"],
            "tags": pacote["tags"],
            "categoryId": "20",           # Gaming
            "defaultLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }


def arquivo_do_video(pacote, raiz=RAIZ):
    return os.path.join(raiz, pacote["arquivo"])


def validar_antes(pacote, raiz=RAIZ, validador=None):
    """(erros). Reaproveita a barreira do kit: kit inválido não vira upload."""
    erros = []
    if not pacote:
        return ["pacote ausente no kit"]
    if validador:
        erros += validador(pacote)
    caminho = arquivo_do_video(pacote, raiz)
    if not os.path.exists(caminho):
        erros.append("arquivo ausente: " + pacote.get("arquivo", "?"))
    elif os.path.getsize(caminho) < 10_000:
        erros.append("arquivo pequeno demais para ser vídeo")
    if not pacote.get("titulo") or not pacote.get("descricao"):
        erros.append("título ou descrição vazios")
    return erros


def iniciar_upload(access_token, metadados_json, tamanho, abrir=None):
    """Abre a sessão de upload resumable. Devolve (url_da_sessao, erro)."""
    abrir = abrir or urllib.request.urlopen
    req = urllib.request.Request(URL_UPLOAD, data=json.dumps(metadados_json).encode(),
                                 method="POST",
                                 headers={"Authorization": "Bearer " + access_token,
                                          "Content-Type": "application/json; charset=UTF-8",
                                          "X-Upload-Content-Length": str(tamanho),
                                          "X-Upload-Content-Type": "video/mp4",
                                          "User-Agent": "rebocl-envio/1.0"})
    try:
        with abrir(req, timeout=60) as r:
            url = r.headers.get("Location")
            if not url:
                return None, "o YouTube não devolveu a URL de sessão"
            return url, None
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")[:200]
        return None, "abertura recusada (%s): %s" % (e.code, corpo)


def enviar_bytes(url_sessao, caminho, abrir=None):
    """Envia o arquivo inteiro numa requisição (vídeos da casa têm poucos MB)."""
    abrir = abrir or urllib.request.urlopen
    with open(caminho, "rb") as f:
        corpo = f.read()
    req = urllib.request.Request(url_sessao, data=corpo, method="PUT",
                                 headers={"Content-Type": "video/mp4",
                                          "Content-Length": str(len(corpo)),
                                          "User-Agent": "rebocl-envio/1.0"})
    try:
        with abrir(req, timeout=600) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, "envio recusado (%s): %s" % (e.code, e.read().decode("utf-8", "replace")[:200])


def registrar(raiz, slug, titulo, vid, quando=None, arquivo=None, escrever=print, descricao=None,
              angulo=None):
    """Grava o que foi publicado em posts/youtube-publicados.json.

    Por que existe (27/10/2026): o envio imprimia o link no log do run e nada ficava registrado.
    O dono perguntava "o que já saiu?" e a resposta dependia de abrir o histórico do GitHub. Com
    este registro, o chat responde (!youtube) lendo um JSON público — e o registro é do que
    realmente voltou do YouTube (id devolvido pela API), não do que a gente achou que enviou.
    """
    destino = os.path.join(raiz, "posts", "youtube-publicados.json")
    try:
        atual = json.load(open(destino, encoding="utf-8"))
    except Exception:
        atual = {"publicados": []}
    lista = atual.get("publicados") or []
    lista = [x for x in lista if str(x.get("id")) != str(vid)]
    lista.insert(0, {
        "id": vid,
        "url": "https://youtu.be/" + str(vid),
        "slug": slug,
        "titulo": (titulo or "")[:120],
        # a descrição fica guardada porque é ela que o portão de forma compara depois: sem o
        # texto, a próxima gravação passaria só por não ter com o que se comparar.
        "descricao": (descricao or "")[:400],
        # o ângulo é o que faz o redator rodar: com ele gravado, o próximo vídeo escolhe outro
        "angulo": angulo or None,
        "arquivo": arquivo or "",
        "quando": quando or datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    })
    atual["publicados"] = lista[:50]
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(atual, f, ensure_ascii=False, indent=1)
    escrever("registro: posts/youtube-publicados.json (" + str(len(atual["publicados"])) + " vídeo(s))")
    return destino


def executar(slug, confirmacao, raiz=RAIZ, renovar=None, validador=None,
             iniciar=None, enviar=None, escrever=print, impressora=None,
             hora_local=None, publicacoes=None):
    """Executa o envio. Devolve (ok, mensagem).

    Dois caminhos declarados: MANUAL (palavra PUBLICAR) e AUTOMÁTICO (palavra AUTOMATICO +
    vídeo comprovadamente novo). Qualquer outra coisa é recusa.
    """
    pedido = str(confirmacao or "").strip().upper()
    if pedido not in (PALAVRA_CONFIRMACAO, PALAVRA_AUTOMATICA):
        return False, ("faltou a confirmação explícita (palavra %s ou %s): a casa não publica "
                       "sozinha sem prova" % (PALAVRA_CONFIRMACAO, PALAVRA_AUTOMATICA))
    # KIT_YOUTUBE permite apontar para outro kit (o do gameplay gravado, por exemplo) sem
    # mexer no padrão. O caminho padrão continua sendo o kit oficial do YouTube.
    caminho_kit = (os.environ.get("KIT_YOUTUBE")
                   or os.environ.get("KIT")
                   or os.path.join(raiz, "posts", "kit-youtube.json"))
    dados = carregar_kit(caminho_kit)
    pacote = pacote_do_kit(dados, slug)
    erros = validar_antes(pacote, raiz=raiz,
                          validador=validador or _validador_do_kit())
    if erros:
        return False, "kit recusado: " + "; ".join(erros)
    sha = (impressora or impressao)(arquivo_do_video(pacote, raiz))
    if pedido == PALAVRA_AUTOMATICA:
        libera, motivo = pode_enviar_sozinho(pacote, raiz=raiz, impressora=impressora)
        if not libera:
            return False, "portão do vídeo recusou: " + motivo
        # Arquivo novo não basta: outra partida gravada dá outro arquivo e o MESMO título.
        libera_forma, motivo_forma, numeros_forma = portao_do_texto(
            pacote, raiz=raiz, hora_local=hora_local, publicacoes=publicacoes)
        escrever("portão do texto: " + motivo_forma)
        if numeros_forma:
            escrever("portão do texto (números): " + json.dumps(numeros_forma, ensure_ascii=False, sort_keys=True))
        if not libera_forma:
            return False, "portão do texto recusou: " + motivo_forma
    client_id = os.environ.get("YT_CLIENT_ID", "")
    client_secret = os.environ.get("YT_CLIENT_SECRET", "")
    refresh = os.environ.get("YT_REFRESH_TOKEN", "")
    token, erro = (renovar or oauth.renovar)(client_id, client_secret, refresh)
    if erro:
        return False, erro
    caminho = arquivo_do_video(pacote, raiz)
    tamanho = os.path.getsize(caminho)
    escrever("enviando %s (%d bytes) — %s" % (pacote["arquivo"], tamanho, pacote["titulo"][:60]))
    url, erro = (iniciar or iniciar_upload)(token, metadados(pacote), tamanho)
    if erro:
        return False, erro
    resultado, erro = (enviar or enviar_bytes)(url, caminho)
    if erro:
        return False, erro
    vid = (resultado or {}).get("id")
    if not vid:
        return False, "o YouTube não devolveu o id do vídeo"
    if str(os.environ.get("YT_REGISTRO", "1")).strip() != "0":
        try:
            registrar(raiz, slug, pacote.get("titulo"), vid, arquivo=pacote.get("arquivo"),
                      escrever=escrever, descricao=pacote.get("descricao"),
                      angulo=pacote.get("angulo"))
            registrar_impressao(sha, slug, vid, pacote.get("arquivo"), raiz=raiz,
                                escrever=escrever)
        except Exception as erro:
            # o vídeo JÁ subiu: falhar aqui não pode esconder isso
            escrever("aviso: não consegui registrar o envio (" + str(erro)[:120] + ")")
    return True, "publicado: https://youtu.be/" + vid


def main(argv):
    slug = argv[0] if argv else "prancheta"
    confirmacao = os.environ.get("CONFIRMACAO", "")
    ok, msg = executar(slug, confirmacao)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
