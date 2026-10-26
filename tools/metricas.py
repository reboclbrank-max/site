#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede o que a casa postou e o que voltou — 2026-10-24.

POR QUE EXISTE: o postador publica 8 vezes por dia, mas até aqui ele só sabia
contar seguidores e quantidade de posts. Ninguém media **resultado por post**, então
"está funcionando?" não tinha resposta: o registro diário repetia
`engajamento=NAO_OBSERVAVEL`. Este medidor lê o que é público, calcula o desempenho
de cada post e compara as duas coisas que a casa faz o dia inteiro:

    PROMO   — conteúdo próprio falando dos jogos
    COMENTÁRIO — resposta genérica em post de terceiro

O número que importa não é "quantos posts": é quanto cada tipo devolve.

REGRAS (não regredir):
  * só leitura pública (API pública do Bluesky, sem token, sem credencial);
  * nenhum dado inventado: fonte que não responde entra como NAO_OBSERVAVEL;
  * não atribui causa — descreve o que foi observado e com que amostra;
  * não publica nada, não toca em fila, não consome segredo;
  * sem opinião sobre "melhor horário" quando a amostra é pequena: diz que é ruído.
"""
import collections
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

ATOR = os.environ.get("BSKY_ATOR", "reboclbrank.bsky.social")
API = "https://public.api.bsky.app/xrpc"
SAIDA = "posts/desempenho.md"
SAIDA_PLACAR = "posts/placar-metas.md"
METAS = "posts/metas.json"
MAX_FEED = 300

# Marcadores do conteúdo próprio. Se o texto fala dos jogos, é promo.
GATILHOS = ("PRANCHETA", "CEIFALUME", "prancheta", "ceifalume",
            "reboclbrank-max.github.io", "itch.io", "⚽", "🌙")


def http_json(url, tentativas=2):
    """GET público. Devolve (dados, None) ou (None, motivo) — nunca inventa."""
    for _ in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "rebocl-metricas/1.0 (+https://reboclbrank-max.github.io/site/)",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8")), None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
            motivo = type(e).__name__
    return None, motivo


def perfil():
    dados, erro = http_json(f"{API}/app.bsky.actor.getProfile?actor={ATOR}")
    if erro or not isinstance(dados, dict):
        return None, erro or "resposta vazia"
    return {
        "seguidores": dados.get("followersCount"),
        "seguindo": dados.get("followsCount"),
        "posts": dados.get("postsCount"),
    }, None


def feed_completo(limite=MAX_FEED):
    """Percorre o feed do próprio autor até `limite` itens (a API devolve 100 por página)."""
    itens, cursor, erro = [], None, None
    while len(itens) < limite:
        url = f"{API}/app.bsky.feed.getAuthorFeed?actor={ATOR}&limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        dados, erro = http_json(url)
        if erro or not isinstance(dados, dict):
            return itens, erro or "resposta vazia"
        pagina = dados.get("feed", [])
        if not pagina:
            break
        itens += pagina
        cursor = dados.get("cursor")
        if not cursor:
            break
    return itens[:limite], None


def engajamento(post):
    return (post.get("likeCount") or 0) + (post.get("repostCount") or 0) + (post.get("replyCount") or 0)


def classificar(texto):
    return "promo" if any(g in (texto or "") for g in GATILHOS) else "comentario"


def analisar(limite=MAX_FEED):
    itens, erro_feed = feed_completo(limite)
    p, erro_perfil = perfil()
    posts = []
    for item in itens:
        post = item.get("post") or {}
        autor = (post.get("author") or {}).get("handle")
        if autor != ATOR:
            continue
        registro = post.get("record") or {}
        quando = registro.get("createdAt")
        if not quando:
            continue
        posts.append({
            "uri": post.get("uri"),
            "quando": quando,
            "texto": (registro.get("text") or "")[:80],
            "classe": classificar(registro.get("text")),
            "likes": post.get("likeCount") or 0,
            "reposts": post.get("repostCount") or 0,
            "respostas": post.get("replyCount") or 0,
            "engajamento": engajamento(post),
            "repost_de_terceiro": bool(item.get("reason")),
        })
    # Repost de terceiro não é conteúdo da casa: entra na conta só como contexto.
    proprios = [x for x in posts if not x["repost_de_terceiro"]]
    grupos = collections.defaultdict(list)
    for x in proprios:
        grupos[x["classe"]].append(x)

    resumo = {}
    for classe, lista in grupos.items():
        valores = [x["engajamento"] for x in lista]
        resumo[classe] = {
            "posts": len(lista),
            "media": round(sum(valores) / len(valores), 2),
            "maximo": max(valores),
            "sem_engajamento": sum(1 for v in valores if v == 0),
            "taxa_sem_engajamento": round(100.0 * sum(1 for v in valores if v == 0) / len(valores), 1),
        }

    total = len(proprios)
    soma = sum(x["engajamento"] for x in proprios)
    # Se a fonte falhou, zero posts NÃO é medição: é ausência de leitura.
    fonte_ok = not erro_feed
    resumo["total"] = {
        "posts": total if fonte_ok else None,
        "engajamento_somado": soma if fonte_ok else None,
        "media": round(soma / total, 2) if (total and fonte_ok) else None,
        "fonte_ok": fonte_ok,
    }
    if fonte_ok and p and p.get("seguidores"):
        resumo["total"]["posts_por_seguidor"] = round(total / p["seguidores"], 1)
    conversa = interacao(proprios)
    return {
        "ator": ATOR,
        "interacao": conversa,
        "medido_em": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "perfil": p,
        "erro_perfil": erro_perfil,
        "erro_feed": erro_feed,
        "resumo": resumo,
        "posts": sorted(proprios, key=lambda x: x["quando"], reverse=True),
    }


def interacao(posts, max_threads=40):
    """Quem falou com a casa e quem ficou sem resposta.

    O postador publica e comenta, mas nunca leu notificação: se alguém responde, ninguém
    sabe. Aqui a thread dos posts recentes com resposta é lida (API pública) e o retorno
    é separado por origem, porque as duas coisas significam coisas diferentes:

      PROMO      — resposta ao conteúdo da casa. Se não foi respondida, é conversa perdida.
      COMENTÁRIO — resposta do autor do post alheio onde a casa comentou. É retribuição
                   educada ao comentário, não alguém pedindo atenção: não vira fila.

    Não publica nada, não responde nada: só mede e registra.
    """
    por_classe = {
        "promo": {"conversas": 0, "respostas": 0, "respondidas": 0, "pendentes": 0},
        "comentario": {"conversas": 0, "respostas": 0, "respondidas": 0, "pendentes": 0},
    }
    candidatos = [x for x in posts if x.get("respostas")][:max_threads]
    checados, erro = 0, None
    for x in candidatos:
        dados, erro_leitura = http_json(f"{API}/app.bsky.feed.getPostThread?uri={x['uri']}&depth=2")
        if erro_leitura or not isinstance(dados, dict):
            erro = erro_leitura or "resposta vazia"
            continue
        checados += 1
        classe = x.get("classe") if x.get("classe") in por_classe else "comentario"
        balde = por_classe[classe]
        terceiros = casa = 0
        for r in ((dados.get("thread") or {}).get("replies") or []):
            autor = ((r.get("post") or {}).get("author") or {}).get("handle")
            if autor == ATOR:
                casa += 1
            else:
                terceiros += 1
        if not terceiros:
            continue
        balde["conversas"] += 1
        balde["respostas"] += terceiros
        if casa:
            balde["respondidas"] += 1
        else:
            balde["pendentes"] += 1
    return {
        "posts_checados": checados,
        "por_classe": por_classe,
        "respostas_recebidas": sum(b["respostas"] for b in por_classe.values()),
        "respondidas": por_classe["promo"]["respondidas"],
        "pendentes": por_classe["promo"]["pendentes"],
        "fonte_ok": erro is None,
        "erro": erro,
    }


def observado_instagram():
    """Lê o que a API do Instagram devolve, sem gravar credencial em lugar nenhum.

    `NAO_OBSERVAVEL` aqui é ausência de leitura, não zero seguidores. O `ig_seguidores=0`
    registrado em 24/10/2026 só é zero de verdade se a API confirmar zero; sem token no
    ambiente, o registro tem de dizer que não houve leitura.
    """
    token = os.environ.get("IG_TOKEN")
    conta = os.environ.get("IG_USER_ID")
    if not token or not conta:
        return None, "sem credencial no runtime (IG_TOKEN/IG_USER_ID ausentes)"
    dados, erro = http_json_autorizado(
        f"https://graph.instagram.com/v21.0/{conta}?fields=followers_count,media_count", token)
    if erro or not isinstance(dados, dict):
        return None, f"leitura recusada ({erro or 'resposta vazia'})"
    if "followers_count" not in dados or "media_count" not in dados:
        return None, "resposta sem os contadores"
    leitura = {"seguidores": dados["followers_count"], "posts": dados["media_count"]}

    # Engajamento por publicação do Instagram. like_count/comments_count são campos
    # de leitura da própria conta e não exigem permissão de insights; se a chamada
    # for recusada, o campo fica ausente — não vira zero.
    midias, erro_midia = http_json_autorizado(
        f"https://graph.instagram.com/v21.0/{conta}/media"
        "?fields=id,like_count,comments_count,timestamp,media_type&limit=30", token)
    if not erro_midia and isinstance(midias, dict) and midias.get("data"):
        por_tipo = collections.defaultdict(list)
        for m in midias["data"]:
            eng = (m.get("like_count") or 0) + (m.get("comments_count") or 0)
            por_tipo[m.get("media_type") or "DESCONHECIDO"].append(eng)
        leitura["midias"] = len(midias["data"])
        leitura["por_tipo"] = {
            tipo: {"n": len(v), "media": round(sum(v) / len(v), 2),
                   "zero": sum(1 for x in v if x == 0)}
            for tipo, v in por_tipo.items()
        }
    else:
        leitura["midias_motivo"] = erro_midia or "lista de mídias vazia"
    return leitura, None


def http_json_autorizado(url, token, tentativas=2):
    """GET autenticado para leitura de contadores. Nunca imprime nem devolve o token."""
    for _ in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
                "User-Agent": "rebocl-metricas/1.0",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8")), None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
            motivo = getattr(e, "code", None) or type(e).__name__
    return None, motivo


CANAL_YOUTUBE_PADRAO = "UCQdxKtfRnqNLd1ZOs9B6eaQ"


def observado_itch(chaves=None):
    """Downloads e visitas do itch.io, por conta.

    A casa tem DUAS contas publicando (reboclbrank-max e rebocl-brank), e a API do
    itch só devolve os jogos da chave usada. Por isso a variável aceita várias chaves
    separadas por vírgula: uma por conta. Sem chave, é NAO_OBSERVAVEL — nunca zero.

    O itch não expõe seguidores por API (pedido ainda aberto no fórum do próprio
    itch), então `itch_seguidores` continua sem leitura automática de propósito.
    """
    bruto = chaves if chaves is not None else os.environ.get("ITCH_API_KEYS", "")
    lista = [k.strip() for k in (bruto or "").split(",") if k.strip()]
    if not lista:
        return None, "sem chave no runtime (ITCH_API_KEYS ausente)"
    total_downloads = total_visitas = 0
    jogos, contas_lidas, erros = [], 0, []
    for chave in lista:
        dados, erro = http_json_autorizado("https://api.itch.io/profile/games", chave)
        if erro or not isinstance(dados, dict) or "games" not in dados:
            erros.append(erro or "resposta sem lista de jogos")
            continue
        contas_lidas += 1
        for j in dados.get("games") or []:
            if j.get("published") is False:
                continue
            downloads = j.get("downloads_count") or 0
            total_downloads += downloads
            total_visitas += j.get("views_count") or 0
            jogos.append({"titulo": (j.get("title") or "")[:60],
                          "downloads": downloads,
                          "visitas": j.get("views_count") or 0})
    if not contas_lidas:
        return None, "leitura recusada (" + "; ".join(erros[:2]) + ")"
    return {"downloads": total_downloads, "visitas": total_visitas,
            "contas_lidas": contas_lidas, "contas_tentadas": len(lista),
            "jogos": sorted(jogos, key=lambda x: x["downloads"], reverse=True)}, None


def _duracao_em_segundos(iso):
    """Converte PT1M15S (formato do YouTube) em segundos. None se não entender."""
    achado = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso or "")
    if not achado:
        return None
    h, m, s = (int(g) if g else 0 for g in achado.groups())
    return h * 3600 + m * 60 + s


# Marcadores de conteúdo da casa nos títulos do YouTube. Fora deles, o vídeo é de
# outra empresa — e isso importa: medido em 24/10/2026, 145 de 150 envios recentes
# não eram dos jogos da casa.
MARCAS_DA_CASA = ("prancheta", "ceifalume", "rebocl", "devlog", "bastidor")


def classificar_youtube(titulo, descricao=""):
    texto = ((titulo or "") + " " + (descricao or "")).casefold()
    return "casa" if any(m in texto for m in MARCAS_DA_CASA) else "terceiros"


def resumo_youtube(videos):
    """Separa o canal em duas coisas que não são a mesma: conteúdo da casa e o resto.

    Não julga nem apaga nada: só mede quanto do canal fala dos jogos e quanto do
    retorno vem de cada lado. É o que faltava para explicar "160 vídeos, 24 inscritos".
    """
    grupos = {"casa": [], "terceiros": []}
    for v in videos:
        grupos[classificar_youtube(v.get("titulo"), v.get("descricao"))].append(v)

    def bloco(lista):
        if not lista:
            return {"n": 0, "views": 0, "media_views": None, "likes": 0, "comentarios": 0}
        # Campo ausente conta como zero AQUI porque é soma de um vídeo já lido; a
        # ausência de leitura do canal inteiro é tratada antes, em observado_youtube.
        views = sum(v.get("views") or 0 for v in lista)
        return {"n": len(lista), "views": views, "media_views": round(views / len(lista), 1),
                "likes": sum(v.get("likes") or 0 for v in lista),
                "comentarios": sum(v.get("comentarios") or 0 for v in lista)}

    resumo = {classe: bloco(lista) for classe, lista in grupos.items()}
    total = sum(g["views"] for g in resumo.values())
    if total:
        for classe in resumo:
            resumo[classe]["fatia_views"] = round(100.0 * resumo[classe]["views"] / total, 1)
    casa = sorted(grupos["casa"], key=lambda v: v["views"], reverse=True)
    resumo["casa"]["melhores"] = [
        {"titulo": v["titulo"], "views": v["views"], "segundos": v["segundos"], "quando": v["quando"]}
        for v in casa[:3]
    ]
    return resumo


def observado_youtube(chave=None, canal=None):
    """Inscritos, vídeos e shorts do canal, com leitura pública do YouTube.

    Só precisa de chave de API (não é OAuth): `channels.list` devolve contadores
    públicos. Para contar shorts, lê a playlist de envios e mede a duração dos
    últimos vídeos — custa 3 unidades de cota de 10.000, sem risco.
    Publicar vídeo é outra história: exige OAuth com o dono logado.
    """
    chave = chave if chave is not None else os.environ.get("YT_API_KEY", "")
    canal = canal or os.environ.get("YT_CHANNEL_ID") or CANAL_YOUTUBE_PADRAO
    if not chave:
        return None, "sem chave no runtime (YT_API_KEY ausente)"
    base = "https://www.googleapis.com/youtube/v3"
    dados, erro = http_json(f"{base}/channels?part=statistics,contentDetails&id={canal}&key={chave}")
    if erro or not isinstance(dados, dict) or not dados.get("items"):
        return None, "leitura recusada (" + (erro or "canal não encontrado") + ")"
    item = dados["items"][0]
    stat = item.get("statistics") or {}
    if "subscriberCount" not in stat:
        return None, "resposta sem contadores (canal pode ocultar inscritos)"
    leitura = {
        "inscritos": int(stat["subscriberCount"]),
        "videos": int(stat.get("videoCount") or 0),
        "visitas": int(stat.get("viewCount") or 0),
    }
    envios = (((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads"))
    coletados = []
    if envios:
        atual, shorts, conferidos = None, 0, 0
        for _ in range(2):  # até 50 vídeos recentes
            url = f"{base}/playlistItems?part=contentDetails&maxResults=50&playlistId={envios}&key={chave}"
            if atual:
                url += f"&pageToken={atual}"
            lista, erro_lista = http_json(url)
            if erro_lista or not isinstance(lista, dict):
                break
            ids = [((i.get("contentDetails") or {}).get("videoId")) for i in lista.get("items") or []]
            ids = [i for i in ids if i]
            if not ids:
                break
            videos, erro_videos = http_json(
                f"{base}/videos?part=statistics,snippet,contentDetails&id={','.join(ids[:50])}&key={chave}")
            if erro_videos or not isinstance(videos, dict):
                break
            for v in videos.get("items") or []:
                segundos = _duracao_em_segundos((v.get("contentDetails") or {}).get("duration"))
                conferidos += 1
                if segundos is not None and segundos <= 61:
                    shorts += 1
                st = v.get("statistics") or {}
                sn = v.get("snippet") or {}
                coletados.append({
                    "titulo": (sn.get("title") or "")[:80],
                    "descricao": (sn.get("description") or "")[:160],
                    "views": int(st.get("viewCount") or 0),
                    "likes": int(st.get("likeCount") or 0),
                    "comentarios": int(st.get("commentCount") or 0),
                    "segundos": segundos,
                    "quando": (sn.get("publishedAt") or "")[:10],
                })
            atual = lista.get("nextPageToken")
            if not atual:
                break
        if conferidos:
            leitura["shorts"] = shorts
            leitura["videos_conferidos"] = conferidos
        if coletados:
            leitura["videos_medidos"] = resumo_youtube(coletados)
    return leitura, None


# Duas semanas: é o prazo que o dono mesmo deu para o canal que não devolve nada deixar de
# ser pergunta técnica e virar decisão dele.
DIAS_PARA_VEREDITO = 14


def placar_metas(observado, caminho=METAS, hoje=None):
    """Compara as metas aprovadas em 15/10 com o que foi medido. Não inventa nada.

    Cada linha carrega alvo, observado, quanto falta e prazo. Sem leitura, o observado
    é `NAO_OBSERVAVEL` — nunca zero, nunca "quase lá".
    """
    hoje = hoje or datetime.date.today()
    try:
        with open(caminho, encoding="utf-8") as f:
            metas = json.load(f)
    except (OSError, ValueError):
        return [], "metas.json ilegivel"
    inicio = metas.get("ig_30_dias", {}).get("inicio")
    prazo = None
    if inicio:
        try:
            prazo = datetime.date.fromisoformat(inicio) + datetime.timedelta(days=30)
        except ValueError:
            prazo = None
    dias = (prazo - hoje).days if prazo else None

    # Linha de partida (13/10): sem ela, "0 seguidores" não diz nada — o canal pode estar
    # parado desde sempre ou ter perdido o que tinha. Com ela, o placar mostra o RETORNO.
    partida = metas.get("linha_de_partida_13_10") or {}

    def linha(nome, alvo, chave, fonte):
        valor = (observado or {}).get(chave)
        falta = None
        status = "SEM_LEITURA"
        if isinstance(valor, (int, float)):
            falta = max(0, round(alvo - valor, 1))
            status = "ATINGIDO" if valor >= alvo else "EM_CURSO"
        base = partida.get(chave)
        delta = round(valor - base, 1) if isinstance(valor, (int, float)) and isinstance(base, (int, float)) else None
        return {"meta": nome, "alvo": alvo, "observado": valor, "falta": falta,
                "status": status, "fonte": fonte, "partida": base, "delta": delta,
                "por_dia": (
                    round(falta / dias, 2) if (falta and dias and dias > 0) else None)}

    # Meta impossível de medir não fica eternamente em NAO_OBSERVAVEL: vira meta aposentada
    # (com evidência) e o que É medido no lugar dela entra como linha ACOMPANHADA — com
    # número e sem alvo inventado. Alvo é decisão do dono; leitura é obrigação do robô.
    def linha_acompanhada(nome, chave, fonte, motivo):
        valor = (observado or {}).get(chave)
        return {"meta": nome, "alvo": "—", "observado": valor, "falta": None,
                "status": "ACOMPANHADA" if isinstance(valor, (int, float)) else "SEM_LEITURA",
                "fonte": fonte, "partida": None, "delta": None, "por_dia": None,
                "motivo": motivo}

    linhas = []
    ig = metas.get("ig_30_dias", {})
    bsky = metas.get("bsky_30_dias", {})
    yt = metas.get("yt_30_dias", {})
    itch = metas.get("itch_30_dias", {})
    if "posts" in ig:
        linhas.append(linha("Instagram: publicações", ig["posts"], "ig_posts", "graph.instagram.com"))
    if "seguidores" in ig:
        linhas.append(linha("Instagram: seguidores", ig["seguidores"], "ig_seguidores", "graph.instagram.com"))
    if "seguidores" in bsky:
        linhas.append(linha("Bluesky: seguidores", bsky["seguidores"], "bsky_seguidores", "API pública do Bluesky"))
    if "inscritos" in yt:
        linhas.append(linha("YouTube: inscritos", yt["inscritos"], "yt_inscritos", "YouTube Data API v3 (chave no runner)"))
    if "shorts" in yt:
        linhas.append(linha("YouTube: shorts", yt["shorts"], "yt_shorts", "YouTube Data API v3 (chave no runner)"))
    if "downloads" in itch:
        linhas.append(linha("itch: downloads", itch["downloads"], "itch_downloads", "api.itch.io/profile/games (chave no runner)"))
    # 25/10/2026: `itch: seguidores` está APOSENTADA (metas.json). O itch não publica essa
    # contagem em API nem em página pública — conferido em 5 caminhos. Ficar em
    # NAO_OBSERVAVEL para sempre não informa nada e ainda parece culpa do robô.
    aposentada = metas.get("_meta_aposentada_25_10") or {}
    if "seguidores" in itch or aposentada:
        alvo_hist = (itch.get("seguidores") if "seguidores" in itch
                     else aposentada.get("alvo_original"))
        linha_ap = linha_acompanhada(
            "itch: seguidores (aposentada)", "itch_seguidores",
            "SEM_API: o itch não publica seguidores (conferido em 25/10/2026)",
            "aposentada em 25/10/2026 — " + (aposentada.get("motivo") or
                                                "o itch não publica contagem de seguidores"))
        linha_ap["alvo"] = alvo_hist if alvo_hist is not None else "—"
        linhas.append(linha_ap)
    if metas.get("itch_visitas"):
        linhas.append(linha_acompanhada(
            "itch: visitas", "itch_visitas", "api.itch.io/profile/games (chave no runner)",
            "medida no lugar de itch: seguidores, sem alvo (alvo é decisão do dono)"))
    # Meta aposentada não entra na conta de "sem leitura": ela não é mais meta a medir, é
    # registro do que foi retirado e por quê. Contá-la como falha esconderia o progresso.
    observavel = sum(1 for l in linhas
                     if l["status"] != "SEM_LEITURA" and "aposentada" not in l["meta"])
    dias_decorridos = None
    if inicio:
        try:
            dias_decorridos = (hoje - datetime.date.fromisoformat(inicio)).days
        except ValueError:
            dias_decorridos = None
    return linhas, {"dias_restantes": dias, "prazo": prazo.isoformat() if prazo else None,
                    "dias_decorridos": dias_decorridos,
                    "metas_com_leitura": observavel,
                    "metas_sem_leitura": sum(1 for l in linhas if l["status"] == "SEM_LEITURA"
                                             and "aposentada" not in l["meta"]),
                    "metas_aposentadas": sum(1 for l in linhas if "aposentada" in l["meta"])}


def gravar_placar(linhas, contexto, hoje=None):
    hoje = hoje or datetime.date.today()
    if not linhas:
        return None
    cab = ("# Placar das metas aprovadas\n\n"
           "> Compara `posts/metas.json` (aprovado em 15/10/2026) com o que foi realmente "
           "medido. `NAO_OBSERVAVEL` é ausência de leitura, **não** zero. `por_dia` é quanto "
           "seria necessário por dia para fechar no prazo — não é previsão.\n\n")
    dias = contexto.get("dias_restantes")
    prazo = contexto.get("prazo") or "sem prazo definido"
    rodape = (f"\nPrazo: **{prazo}**" + (f" · {dias} dia(s) restante(s)" if dias is not None else "")
              + f" · {contexto['metas_com_leitura']} meta(s) com leitura, "
                f"{contexto['metas_sem_leitura']} sem leitura automática"
              + (f" · {contexto['metas_aposentadas']} aposentada(s) com o motivo no arquivo"
                 if contexto.get("metas_aposentadas") else "") + ".\n")
    # Decisão que o placar passa a tomar sozinho: canal medido, com partida conhecida, que
    # não moveu um único número em N dias. Não atribui causa — só diz que o esforço não
    # voltou, e nomeia a decisão (manter ou aposentar) que passa a ser do dono.
    dias_dec = contexto.get("dias_decorridos")
    parados = [l for l in linhas if l.get("delta") == 0 and isinstance(dias_dec, int)
               and dias_dec >= DIAS_PARA_VEREDITO]
    if parados:
        rodape += ("\n> **Sem retorno em %d dias:** " % dias_dec
                   + ", ".join("%s (%s medido(s), nada a mais desde 13/10)" % (
                       l["meta"], l["observado"]) for l in parados)
                   + ". O esforço não voltou número nenhum. Manter o canal ou aposentá-lo é "
                     "decisão do dono, com este número na mão — o robô não decide isso e não "
                     "vai fingir que decide.\n")
    sem_api = [l for l in linhas if l["status"] == "SEM_LEITURA" and "SEM_API" in (l.get("fonte") or "")]
    if sem_api:
        rodape += ("\n> **Sem API, não sem robô:** " + ", ".join(l["meta"] for l in sem_api)
                   + ". O itch não publica contagem de seguidores em API nem em página pública "
                     "(5 caminhos conferidos em 25/10/2026). Essa meta está **aposentada** — o "
                     "registro com o motivo ficou em `posts/metas.json` — e o que o itch mede de "
                     "audiência (**itch: visitas**) entrou no placar como medida acompanhada, "
                     "com número e sem alvo inventado.\n")
    linhas_md = ["| meta | alvo | observado | falta | por dia | status | desde a partida |",
                 "|---|---|---|---|---|---|---|"]
    for l in linhas:
        obs = "NAO_OBSERVAVEL" if l["observado"] is None else l["observado"]
        falta = "—" if l["falta"] is None else l["falta"]
        por_dia = "—" if not l["por_dia"] else l["por_dia"]
        delta = "—" if l.get("delta") is None else ("+" + str(l["delta"]) if l["delta"] > 0 else str(l["delta"]))
        linhas_md.append(f"| {l['meta']} | {l['alvo']} | {obs} | {falta} | {por_dia} | {l['status']} | {delta} |")
    texto = cab + "\n".join(linhas_md) + "\n" + rodape
    caminho = os.path.join(os.path.dirname(SAIDA_PLACAR) or ".", os.path.basename(SAIDA_PLACAR))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho


def hora_brasilia(iso):
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (dt.hour - 3) % 24
    except (ValueError, AttributeError):
        return None


def por_hora(posts):
    """Engajamento por hora local. Devolve None quando a amostra não permite concluir nada."""
    baldes = collections.defaultdict(list)
    for x in posts:
        h = hora_brasilia(x["quando"])
        if h is not None:
            baldes[h].append(x["engajamento"])
    linhas = [{"hora": h, "media": round(sum(v) / len(v), 2), "n": len(v)}
              for h, v in sorted(baldes.items())]
    suficiente = len(posts) >= 100 and all(l["n"] >= 5 for l in linhas) if linhas else False
    return linhas, suficiente


def linha_do_dia(dados):
    """Uma linha curta e estável para o registro diário — sem inventar número."""
    p = dados["perfil"] or {}
    r = dados["resumo"]
    promo = r.get("promo", {})
    coment = r.get("comentario", {})
    total = r["total"]
    def valor(x):
        return "NAO_OBSERVAVEL" if x is None else x
    partes = [
        f"bsky_seguidores={valor(p.get('seguidores') if isinstance(p, dict) else None)}",
        f"posts_proprios={valor(total['posts'])}",
        f"eng_medio={valor(total['media'])}",
    ]
    if promo:
        partes.append(f"promo: n={promo['posts']} media={promo['media']} zero={promo['taxa_sem_engajamento']}%")
    if coment:
        partes.append(f"comentario: n={coment['posts']} media={coment['media']} zero={coment['taxa_sem_engajamento']}%")
    conv = dados.get("interacao") or {}
    if conv.get("fonte_ok") and conv.get("posts_checados"):
        pc = (conv.get("por_classe") or {}).get("promo", {})
        partes.append(f"respostas_recebidas={conv['respostas_recebidas']} "
                      f"promo_respostas={pc.get('respostas', 0)} promo_pendentes={pc.get('pendentes', 0)}")
    elif conv:
        partes.append("interacao=NAO_OBSERVAVEL")
    if dados.get("erro_feed"):
        partes.append(f"feed=NAO_OBSERVAVEL({dados['erro_feed']})")
    return " · ".join(partes)


def bloco_markdown(dados):
    hoje = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y")
    p = dados["perfil"] or {}
    r = dados["resumo"]
    horas, suficiente = por_hora(dados["posts"])
    linhas = [f"## {hoje}", "", f"> Medição pública em {dados['medido_em']} · fonte: API pública do Bluesky "
              f"(sem token). Descreve o que foi visto; não atribui causa e não é prova de entrega.", ""]
    if dados.get("erro_perfil") or dados.get("erro_feed"):
        linhas.append(f"- fonte indisponível: perfil={dados.get('erro_perfil')} feed={dados.get('erro_feed')}")
    linhas.append(f"- **{linha_do_dia(dados)}**")
    linhas.append("")
    linhas.append("| tipo | posts | engajamento médio | melhor | sem engajamento |")
    linhas.append("|---|---|---|---|---|")
    for classe, rotulo in (("promo", "conteúdo dos jogos"), ("comentario", "comentário em post alheio")):
        d = r.get(classe)
        if not d:
            continue
        linhas.append(f"| {rotulo} | {d['posts']} | {d['media']} | {d['maximo']} | {d['sem_engajamento']} ({d['taxa_sem_engajamento']}%) |")
    linhas.append("")
    ig = dados.get("instagram")
    if ig and ig.get("por_tipo"):
        linhas.append(f"**Instagram ({ig['seguidores']} seguidores · {ig['posts']} posts):** " +
                      " · ".join(f"{tipo} n={v['n']} média={v['media']} zero={v['zero']}"
                                 for tipo, v in ig["por_tipo"].items()))
        linhas.append("")
    elif dados.get("instagram_motivo"):
        linhas.append(f"**Instagram:** NAO_OBSERVAVEL ({dados['instagram_motivo']})")
        linhas.append("")
    it = dados.get("itch")
    if it:
        detalhe = " · ".join(f"{j['titulo']}: {j['downloads']}" for j in it["jogos"][:4])
        linhas.append(f"**itch.io:** {it['downloads']} download(s) e {it['visitas']} visita(s) em "
                      f"{it['contas_lidas']}/{it['contas_tentadas']} conta(s). {detalhe}")
        linhas.append("")
    elif dados.get("itch_motivo"):
        linhas.append(f"**itch.io:** NAO_OBSERVAVEL ({dados['itch_motivo']})")
        linhas.append("")
    yt = dados.get("youtube")
    if yt:
        shorts = yt.get("shorts")
        extra = f" · shorts={shorts} de {yt.get('videos_conferidos')} conferido(s)" if shorts is not None else ""
        linhas.append(f"**YouTube:** {yt['inscritos']} inscrito(s) · {yt['videos']} vídeo(s) · "
                      f"{yt['visitas']} visualizaç(ões){extra}")
        vm = yt.get("videos_medidos")
        if vm:
            casa, fora = vm["casa"], vm["terceiros"]
            linhas.append(f"**YouTube — o que o canal publica:** dos {casa['n'] + fora['n']} vídeos lidos, "
                          f"**{casa['n']} são dos jogos da casa** ({casa['views']} views, média {casa['media_views']}) "
                          f"e **{fora['n']} são de outros jogos** ({fora['views']} views, média {fora['media_views']})"
                          + (f" — os da casa são {casa['fatia_views']}% das visualizações." if "fatia_views" in casa else "."))
            if casa.get("melhores"):
                linhas.append("Melhores da casa: " + " · ".join(
                    f"\"{m['titulo'][:40]}\" ({m['views']})" for m in casa["melhores"]))
        linhas.append("")
    elif dados.get("youtube_motivo"):
        linhas.append(f"**YouTube:** NAO_OBSERVAVEL ({dados['youtube_motivo']})")
        linhas.append("")
    conv = dados.get("interacao") or {}
    if conv.get("posts_checados"):
        promo_c = (conv.get("por_classe") or {}).get("promo", {})
        coment_c = (conv.get("por_classe") or {}).get("comentario", {})
        linhas.append(
            f"**Conversa:** {conv['posts_checados']} conversa(s) lida(s). "
            f"Respostas ao conteúdo da casa: {promo_c.get('respostas', 0)} em {promo_c.get('conversas', 0)} thread(s), "
            f"{promo_c.get('respondidas', 0)} atendida(s), {promo_c.get('pendentes', 0)} pendente(s). "
            f"Retorno do autor de post comentado: {coment_c.get('respostas', 0)} em {coment_c.get('conversas', 0)} thread(s) "
            f"— é retribuição ao comentário, não fila de resposta.")
    elif conv:
        linhas.append(f"**Conversa:** NAO_OBSERVAVEL ({conv.get('erro')})")
    linhas.append("")
    if horas:
        linhas.append("**Horário (Brasília):** " + " · ".join(
            f"{l['hora']:02d}h={l['media']}(n={l['n']})" for l in horas))
        if not suficiente:
            linhas.append("")
            linhas.append("> ⚠ Amostra pequena por hora. Isso **não** sustenta escolher horário: a diferença "
                          "está dentro do ruído. Só vale depois de acumular mais posts com este medidor ligado.")
    return "\n".join(linhas) + "\n"


def gravar(dados):
    """Reescreve a seção de HOJE sem duplicar (o workflow roda 8x/dia) e preserva o histórico."""
    import re
    bloco = bloco_markdown(dados)
    cabecalho = (
        "# Desempenho do que foi postado\n\n"
        "> Medição pública e automática do que a casa publica e do que volta. "
        "`NAO_OBSERVAVEL` é ausência de leitura, **não** zero. Números aqui não provam entrega, "
        "alcance, download, conversão ou satisfação — mostram só o que a API pública devolveu.\n\n"
    )
    hoje = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y")
    anterior = ""
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            anterior = f.read()
    # Separa as seções "## data" que já existiam, descarta a de hoje e reordena.
    secoes = re.split(r"^## ", anterior, flags=re.M)[1:] if "## " in anterior else []
    antigas = ["## " + s.strip() + "\n" for s in secoes if s.strip() and not s.startswith(hoje)]
    novo = cabecalho + bloco + ("\n" + "\n".join(antigas) if antigas else "")
    caminho = os.path.join(os.path.dirname(SAIDA) or ".", os.path.basename(SAIDA))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(novo)
    return caminho


def main(argv):
    dados = analisar()
    ig, motivo_ig = observado_instagram()
    dados["instagram"] = ig
    dados["instagram_motivo"] = motivo_ig
    itch, motivo_itch = observado_itch()
    dados["itch"] = itch
    dados["itch_motivo"] = motivo_itch
    yt, motivo_yt = observado_youtube()
    dados["youtube"] = yt
    dados["youtube_motivo"] = motivo_yt
    perfil_dados = dados.get("perfil") or {}
    observado = {
        "bsky_seguidores": perfil_dados.get("seguidores"),
        "ig_posts": (ig or {}).get("posts"),
        "ig_seguidores": (ig or {}).get("seguidores"),
        "itch_downloads": (itch or {}).get("downloads"),
        "itch_visitas": (itch or {}).get("visitas"),
        "itch_seguidores": None,  # o itch não expõe seguidores por API
        "yt_inscritos": (yt or {}).get("inscritos"),
        "yt_shorts": (yt or {}).get("shorts"),
    }
    linhas_metas, contexto_metas = placar_metas(observado)
    dados["placar"] = linhas_metas
    dados["placar_contexto"] = contexto_metas
    if "--json" in argv:
        print(json.dumps(dados, ensure_ascii=False, indent=1))
        return 0
    caminho = gravar(dados)
    r = dados["resumo"]
    print(f"📊 desempenho — {dados['ator']}")
    if dados["perfil"]:
        print(f"   seguidores: {dados['perfil']['seguidores']} · posts totais: {dados['perfil']['posts']}")
    for classe, rotulo in (("promo", "conteúdo dos jogos"), ("comentario", "comentário em post alheio")):
        d = r.get(classe)
        if d:
            print(f"   {rotulo:<24} n={d['posts']:<4} média={d['media']:<5} zero={d['taxa_sem_engajamento']}%")
    print(f"   engajamento médio geral: {r['total']['media']}")
    print(f"   gravado em {caminho}")
    if linhas_metas:
        caminho_placar = gravar_placar(linhas_metas, contexto_metas)
        print(f"   instagram: {'sem leitura — ' + motivo_ig if motivo_ig else 'lido'}")
        print(f"   itch: {'sem leitura — ' + motivo_itch if motivo_itch else str(itch['downloads']) + ' download(s) e ' + str(itch['visitas']) + ' visita(s)'}")
        print(f"   youtube: {'sem leitura — ' + motivo_yt if motivo_yt else str(yt['inscritos']) + ' inscrito(s)'}")
        if not motivo_yt and yt.get("videos_medidos"):
            vm = yt["videos_medidos"]
            print(f"      da casa: n={vm['casa']['n']} · de outros jogos: n={vm['terceiros']['n']}")
        print(f"   placar de metas: {caminho_placar}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
