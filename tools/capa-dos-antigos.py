#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capa própria para os vídeos que subiram com a thumbnail automática do YouTube.

O QUE ESTAVA ERRADO (06/11/2026). Quando a casa passou a desenhar capa (tools/desenhar-capa.py),
os vídeos NOVOS ganharam capa única — e os antigos ficaram com o quadro automático do YouTube:
três vídeos com o mesmo tipo de imagem e título pequeno no canto. O dono viu no grid e cobrou.

O QUE ESTE ARQUIVO FAZ, em ordem:
  1. LISTA os vídeos do canal pela API (canal -> playlist de uploads), o que o token já permite;
  2. tira da lista os que já têm capa da casa (posts/capas-aplicadas.json);
  3. para cada um que sobra: baixa um QUADRO DO PRÓPRIO VÍDEO (i.ytimg.com), desenha o título
     real do vídeo por cima e aplica com thumbnails/set;
  4. grava o que aplicou (id, quando, sha256) — rodar de novo não repinta nem duplica.

O que NÃO faz: inventar título (usa o que está no ar, vindo da API), trocar título, publicar,
apagar. Capa é imagem; o vídeo não é tocado.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "capas-aplicadas.json")
PALAVRA = "APLICAR"


def _modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _agora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ registro
def carregar_registro(caminho=None):
    caminho = caminho or REGISTRO
    if not os.path.exists(caminho):
        return {"_o_que_e": "uma linha por vídeo que recebeu capa da casa", "aplicadas": []}
    try:
        with open(caminho, encoding="utf-8") as f:
            dado = json.load(f)
    except (OSError, ValueError):
        return {"aplicadas": []}
    if not isinstance(dado, dict) or not isinstance(dado.get("aplicadas"), list):
        return {"aplicadas": []}
    return dado


def gravar_registro(registro, caminho=None):
    caminho = caminho or REGISTRO
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(caminho + ".tmp", caminho)


# Nomes que identificam jogo da casa. Vídeo cujo título não cita nenhum deles NÃO recebe capa
# por omissão: em 06/11/2026 a lista de uploads sem capa tinha 34 vídeos, e 29 deles eram de
# 2025 com títulos que não são da casa (Racing Master, Cooking Bride, Summoners War, FIFA
# Rivals...). Pintar a marca da casa em cima do conteúdo dos outros seria errado — e o erro
# seria invisível, porque a ferramenta diria "capa aplicada" com sucesso.
NOMES_DA_CASA = ("ceifalume", "prancheta", "pelle", "brasa", "reboclbrank")


def da_casa(titulo):
    baixo = str(titulo or "").lower()
    return any(n in baixo for n in NOMES_DA_CASA)


def candidatos(videos, registro, so_da_casa=True):
    """Vídeos sem capa da casa, do mais novo para o mais antigo."""
    ja = {str(x.get("id")) for x in (registro or {}).get("aplicadas") or [] if isinstance(x, dict)}
    saida = []
    for v in videos or []:
        vid = str((v or {}).get("id") or "").strip()
        if not vid or vid in ja:
            continue
        if so_da_casa and not da_casa((v or {}).get("titulo")):
            continue
        saida.append(dict(v, id=vid))
    return saida


# ------------------------------------------------------------------ API
def _get_json(url, abrir=None):
    abrir = abrir or urllib.request.urlopen
    with abrir(urllib.request.Request(url, headers={"User-Agent": "rebocl/1"}), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def playlist_de_uploads(access_token, abrir=None):
    dados = _get_json("https://www.googleapis.com/youtube/v3/channels?part=contentDetails"
                      "&mine=true&access_token=" + str(access_token), abrir=abrir)
    itens = dados.get("items") or []
    if not itens:
        return None
    return (((itens[0].get("contentDetails") or {}).get("relatedPlaylists") or {})
            .get("uploads"))


def listar_videos(access_token, maximo=500, abrir=None):
    """[{id, titulo, publicado_em}] direto da playlist de uploads do canal.

    PAGINA DE VERDADE (07/11/2026): a versão anterior pedia `maxResults=50` e ignorava o
    `nextPageToken` — ou seja, com mais de 50 vídeos no canal ela lê 50 e PARA. Foi assim que o
    retrato da cobertura saiu "no_canal: 50, sem_capa: 0" enquanto o registro tinha 51 capas: 50
    não era o tamanho do canal, era o tamanho da página. Contagem truncada que parece exata é
    pior que contagem ausente.
    """
    playlist = playlist_de_uploads(access_token, abrir=abrir)
    if not playlist:
        return []
    videos, pagina, lidas = [], None, 0
    while lidas < int(maximo):
        url = ("https://www.googleapis.com/youtube/v3/playlistItems"
               "?part=snippet&maxResults=%d&playlistId=%s&access_token=%s"
               % (min(int(maximo) - lidas, 50), playlist, str(access_token)))
        if pagina:
            url += "&pageToken=" + str(pagina)
        dados = _get_json(url, abrir=abrir)
        for item in dados.get("items") or []:
            sn = item.get("snippet") or {}
            vid = ((sn.get("resourceId") or {}).get("videoId") or "").strip()
            if vid:
                videos.append({"id": vid, "titulo": (sn.get("title") or "").strip(),
                               "publicado_em": sn.get("publishedAt") or ""})
        lidas = len(videos)
        pagina = dados.get("nextPageToken")
        if not pagina or not (dados.get("items") or []):
            break
    return videos


def _movimento(caminho):
    """Quanto o quadro tem de imagem de verdade (0 a 1). Quadro preto ou chapado pontua baixo.

    POR QUE (07/11/2026): a capa nova do vídeo _ffmjSMsW0Y saiu com um quadro quase preto — o
    cartão do logo no fim do vídeo. A capa é a primeira coisa que se vê; quadro sem imagem é
    capa sem imagem. Aqui cada candidato é medido antes de virar capa.
    """
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return 0.0
    try:
        im = Image.open(caminho).convert("L").resize((160, 90))
    except Exception:  # noqa: BLE001
        return 0.0
    stat = ImageStat.Stat(im)
    media = stat.mean[0] / 255.0
    desvio = stat.stddev[0] / 255.0
    # brilho no meio da faixa (nem preto, nem estourado) e variação de tons (tem desenho na tela)
    brilho = 1.0 - abs(media - 0.5) * 2
    return round(0.6 * brilho + 0.4 * min(1.0, desvio * 3), 4)


def baixar_quadro(vid, destino, abrir=None, incluir_maxres=True):
    """O MELHOR quadro do próprio vídeo. Devolve o caminho ou None.

    O YouTube publica três quadros alternativos (hq1, hq2, hq3) além do principal. Antes ficava
    com o primeiro que baixasse — e o primeiro podia ser um cartão preto. Agora baixa os
    candidatos, mede cada um e fica com o que tem mais imagem.
    """
    abrir = abrir or urllib.request.urlopen
    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    # `maxresdefault` DEIXA DE SER QUADRO QUANDO O VÍDEO JÁ TEM CAPA PRÓPRIA (07/11/2026): o
    # YouTube serve a miniatura enviada nesse endereço. Repintar usando ela é devolver a mesma
    # imagem — foi o que aconteceu com _ffmjSMsW0Y, cuja "capa nova" era a capa antiga. Nos
    # vídeos que já estão no registro, o quadro vem dos automáticos (sddefault/hq1..3).
    nomes = ["sddefault", "hq1", "hq2", "hq3"]
    if incluir_maxres:
        nomes.insert(0, "maxresdefault")
    temporarios, melhores = [], []
    for nome in nomes:
        url = "https://i.ytimg.com/vi/%s/%s.jpg" % (vid, nome)
        caminho = "%s.%s.jpg" % (destino, nome)
        try:
            with abrir(urllib.request.Request(url, headers={"User-Agent": "rebocl/1"}),
                       timeout=60) as r:
                dados = r.read()
        except Exception:  # noqa: BLE001
            continue
        if len(dados) <= 5_000:
            continue
        with open(caminho, "wb") as f:
            f.write(dados)
        temporarios.append(caminho)
        melhores.append((_movimento(caminho), nome, caminho))
    if not melhores:
        return None
    melhores.sort(reverse=True)
    _, nome, escolhido = melhores[0]
    import shutil
    shutil.copyfile(escolhido, destino)
    for caminho in temporarios:
        try:
            os.remove(caminho)
        except OSError:
            pass
    return destino


# ------------------------------------------------------------------ desenho e aplicação
def desenhar_capa(vid, titulo, quadro, saida, raiz=RAIZ):
    """Capa com o título REAL do vídeo por cima de um quadro dele. Devolve o resumo."""
    if not str(titulo or "").strip():
        raise ValueError("vídeo sem título na API: capa sem título é template")
    desenhar = _modulo("desenhar_capa", "desenhar-capa.py")
    return desenhar.desenhar(quadro, saida, titulo, numeros="", assinatura="",
                             marca="reboclbrank-max.github.io/site")


def aplicar(access_token, vid, caminho, aplicar_fn=None):
    if aplicar_fn is None:
        enviar = _modulo("enviar_youtube", "enviar-youtube.py")
        aplicar_fn = enviar.definir_capa
    return aplicar_fn(access_token, vid, caminho)


def executar(access_token, confirmacao, raiz=RAIZ, limite=6, registro_caminho=None,
             listar=None, baixar=None, aplicar_fn=None, escrever=print, somente=None,
             forcar=False, todos=False):
    """Aplica capa nos vídeos antigos. Devolve (ok, relatório)."""
    if str(confirmacao or "").strip().upper() != PALAVRA:
        return False, {"motivo": "faltou a palavra %s: capa também é publicação, não sai sozinha"
                                 % PALAVRA, "aplicadas": [], "recusadas": []}
    registro = carregar_registro(registro_caminho)
    videos = (listar or listar_videos)(access_token, 50)
    if not videos:
        return False, {"motivo": "a API não devolveu vídeos (token sem permissão?)",
                       "aplicadas": [], "recusadas": []}
    alvos = candidatos(videos, registro, so_da_casa=not todos)
    if forcar:
        # repintar de propósito: quando o desenho da capa melhora, a capa velha envelhece junto.
        # O registro continua valendo como histórico (o id é reescrito, não duplicado).
        ja = {x["id"] for x in (registro.get("aplicadas") or [])}
        base = [v for v in videos if v.get("id")]
        if not (todos or somente):
            base = [v for v in base if da_casa(v.get("titulo"))]
        alvos = base if not somente else [v for v in base if v["id"] in set(somente)]
        registro["aplicadas"] = [x for x in (registro.get("aplicadas") or [])
                                 if x.get("id") not in {v["id"] for v in alvos}]
        void = ja
    if somente:
        queridos = {str(x).strip() for x in somente}
        alvos = [v for v in alvos if v["id"] in queridos]
    alvos = alvos[:max(0, int(limite))]
    aplicadas, recusadas = [], []
    for v in alvos:
        ja_pintado = any(isinstance(x, dict) and str(x.get("id")) == str(v["id"])
                         for x in (registro.get("aplicadas") or []))
        # `baixar` pode ser injetado por teste e não aceitar o parâmetro: tenta com, cai sem.
        if baixar is not None:
            quadro = baixar(v["id"], os.path.join(raiz, "media", "capas",
                                                  "%s-quadro.jpg" % v["id"]))
        else:
            quadro = baixar_quadro(v["id"], os.path.join(raiz, "media", "capas",
                                                         "%s-quadro.jpg" % v["id"]),
                                   incluir_maxres=not ja_pintado)
        if not quadro:
            recusadas.append({"id": v["id"], "motivo": "não consegui baixar quadro do vídeo"})
            escrever("✘ %s: sem quadro" % v["id"])
            continue
        saida = os.path.join(raiz, "media", "capas", "%s-capa.png" % v["id"])
        try:
            resumo = desenhar_capa(v["id"], v.get("titulo"), quadro, saida, raiz=raiz)
        except Exception as erro:  # noqa: BLE001
            recusadas.append({"id": v["id"], "motivo": "desenho falhou: " + str(erro)[:120]})
            escrever("✘ %s: desenho falhou" % v["id"])
            continue
        ok, msg = aplicar(access_token, v["id"], saida, aplicar_fn)
        if not ok:
            recusadas.append({"id": v["id"], "motivo": msg})
            escrever("✘ %s: %s" % (v["id"], msg))
            continue
        linha = {"id": v["id"], "quando": _agora(), "titulo": v.get("titulo"),
                 "capa": os.path.relpath(saida, raiz), "sha256": resumo["sha256"]}
        registro.setdefault("aplicadas", []).append(linha)
        aplicadas.append(linha)
        escrever("✓ %s · %s · sha %s" % (v["id"], v.get("titulo", "")[:52], resumo["sha256"]))
    if aplicadas and registro_caminho is not None:
        gravar_registro(registro, registro_caminho)
    pendentes = candidatos(videos, carregar_registro(registro_caminho), so_da_casa=not todos)
    return bool(aplicadas or not alvos), {
        "aplicadas": aplicadas, "recusadas": recusadas,
        "candidatos": len(pendentes),
        "fora_da_casa": len([v for v in videos if v.get("id") and not da_casa(v.get("titulo"))]),
    }


def main(argv):
    ap = argparse.ArgumentParser(description="capa própria para os vídeos antigos")
    ap.add_argument("--confirmacao", default="")
    ap.add_argument("--limite", type=int, default=6)
    ap.add_argument("--registro", default=REGISTRO)
    ap.add_argument("--so", nargs="*", default=None, help="ids específicos")
    ap.add_argument("--ensaio", action="store_true", help="lista os candidatos e não aplica")
    ap.add_argument("--todos", action="store_true",
                    help="inclui vídeos que não citam jogo da casa (cuidado: conteúdo alheio)")
    ap.add_argument("--forcar", action="store_true",
                    help="repinta mesmo quem já tem capa (quando o desenho melhorou)")
    a = ap.parse_args(argv[1:])
    if a.ensaio:
        registro = carregar_registro(a.registro)
        videos = listar_videos(_token())
        fila = candidatos(videos, registro, so_da_casa=not a.todos)
        for v in fila[:a.limite]:
            print("%s  %s  %s" % (v["id"], v.get("publicado_em", "")[:10], v.get("titulo", "")[:60]))
        # O ENSAIO FALA EM NÚMEROS MESMO QUANDO NÃO FALTA NADA (06/11/2026): a lista vazia saía
        # como log vazio, e log vazio não se distingue de passo que não rodou. O run 42321618066
        # terminou verde sem uma linha — e o ensaio anterior (42318213722) acusava o vídeo
        # O04ajm1t54Q como sem capa. Só a contagem prova qual dos dois aconteceu.
        # QUANTOS SÃO DA CASA, QUANTOS NÃO SÃO (07/11/2026). O dono perguntou pelos "118 sem
        # capa": eles não são dívida, são vídeos de OUTROS jogos, que a regra do canal deixa de
        # fora — pintar a marca da casa em vídeo alheio é o oposto de conteúdo próprio. O número
        # fica dito com nome, para não parecer trabalho pendente pela terceira rodada seguida.
        da_casa_videos = [v for v in videos if da_casa((v or {}).get("titulo"))]
        outros = len(videos) - len(da_casa_videos)
        print("ensaio: %d vídeo(s) sem capa nesta rodada · %d no canal (%d da casa, %d de outros "
              "jogos) · %d no registro"
              % (len(fila), len(videos), len(da_casa_videos), outros,
                 len((registro or {}).get("aplicadas") or [])))
        # O RETRATO FICA GRAVADO (07/11/2026): o ensaio contava em números e o número morria no
        # log do run. Agora o estado da casa lê este arquivo e responde "50 de 50, nenhum sem
        # capa" sem depender de abrir o Actions.
        _gravar_estado_capas(len(videos), len(fila),
                             registro_de_todos=len((registro or {}).get("aplicadas") or []),
                             da_casa=len(da_casa_videos), outros_jogos=outros)
        return 0
    ok, rel = executar(_token(), a.confirmacao, limite=a.limite, registro_caminho=a.registro,
                       somente=a.so, forcar=a.forcar, todos=a.todos)
    print(json.dumps({k: rel[k] for k in ("aplicadas", "recusadas")}, ensure_ascii=False, indent=1))
    if not ok:
        print("✘ " + rel.get("motivo", "nada aplicado"), file=sys.stderr)
    return 0 if ok else 1


def _gravar_estado_capas(no_canal, sem_capa, registro_de_todos=0, da_casa=None, outros_jogos=None):
    """Grava o retrato da cobertura de capas em posts/capas-estado.json (fonte do estado da casa)."""
    import datetime
    caminho = CAMINHO_ESTADO
    dados = {"_o_que_e": "retrato da cobertura de capas: quantos vídeos o canal tem e quantos estão sem capa",
             "no_canal": int(no_canal), "sem_capa": int(sem_capa),
             "no_registro": int(registro_de_todos),
             # DECISÃO DE 07/11/2026: vídeo de OUTRO jogo não recebe capa da casa. O número fica
             # no retrato para ninguém confundir ausência de capa com falta de trabalho.
             "_decisao": ("capa da casa só em vídeo que cita jogo da casa; os de outros jogos "
                          "ficam sem capa por regra, não por pendência"),
             "da_casa": None if da_casa is None else int(da_casa),
             "outros_jogos": None if outros_jogos is None else int(outros_jogos),
             "medido_em": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
            f.write("\n")
    except OSError:
        pass
    return caminho


# O CAMINHO É CONSTANTE DE MÓDULO (07/11/2026): a suíte `testes-capas-antigas` roda o ensaio
# de verdade, e caminho enterrado dentro da função fazia o teste escrever no repositório (a
# bateria inteira acusou "escreveu no repositório"). Agora o teste aponta a constante para o tmp.
CAMINHO_ESTADO = os.path.join(RAIZ, "posts", "capas-estado.json")


def _token():
    oauth = _modulo("youtube_oauth", "youtube_oauth.py")
    token, erro = oauth.renovar(os.environ.get("YT_CLIENT_ID", ""),
                                os.environ.get("YT_CLIENT_SECRET", ""),
                                os.environ.get("YT_REFRESH_TOKEN", ""))
    if not token:
        raise SystemExit("✘ sem token: " + str(erro))
    return token


if __name__ == "__main__":
    sys.exit(main(sys.argv))
