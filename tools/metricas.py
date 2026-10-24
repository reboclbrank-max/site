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
    return {"seguidores": dados["followers_count"], "posts": dados["media_count"]}, None


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

    def linha(nome, alvo, chave, fonte):
        valor = (observado or {}).get(chave)
        falta = None
        status = "SEM_LEITURA"
        if isinstance(valor, (int, float)):
            falta = max(0, round(alvo - valor, 1))
            status = "ATINGIDO" if valor >= alvo else "EM_CURSO"
        return {"meta": nome, "alvo": alvo, "observado": valor, "falta": falta,
                "status": status, "fonte": fonte, "por_dia": (
                    round(falta / dias, 2) if (falta and dias and dias > 0) else None)}

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
        linhas.append(linha("YouTube: inscritos", yt["inscritos"], "yt_inscritos", "sem leitura automática"))
    if "shorts" in yt:
        linhas.append(linha("YouTube: shorts", yt["shorts"], "yt_shorts", "sem leitura automática"))
    if "downloads" in itch:
        linhas.append(linha("itch: downloads", itch["downloads"], "itch_downloads", "sem leitura automática"))
    if "seguidores" in itch:
        linhas.append(linha("itch: seguidores", itch["seguidores"], "itch_seguidores", "sem leitura automática"))
    observavel = sum(1 for l in linhas if l["status"] != "SEM_LEITURA")
    return linhas, {"dias_restantes": dias, "prazo": prazo.isoformat() if prazo else None,
                    "metas_com_leitura": observavel, "metas_sem_leitura": len(linhas) - observavel}


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
                f"{contexto['metas_sem_leitura']} sem leitura automática.\n")
    linhas_md = ["| meta | alvo | observado | falta | por dia | status |",
                 "|---|---|---|---|---|---|"]
    for l in linhas:
        obs = "NAO_OBSERVAVEL" if l["observado"] is None else l["observado"]
        falta = "—" if l["falta"] is None else l["falta"]
        por_dia = "—" if not l["por_dia"] else l["por_dia"]
        linhas_md.append(f"| {l['meta']} | {l['alvo']} | {obs} | {falta} | {por_dia} | {l['status']} |")
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
    perfil_dados = dados.get("perfil") or {}
    observado = {
        "bsky_seguidores": perfil_dados.get("seguidores"),
        "ig_posts": (ig or {}).get("posts"),
        "ig_seguidores": (ig or {}).get("seguidores"),
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
        print(f"   placar de metas: {caminho_placar}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
