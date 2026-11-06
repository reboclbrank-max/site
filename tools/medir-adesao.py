#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adesão: o canal está sendo visto por mais gente do que o normal? — com regra declarada.

POR QUE EXISTE (06/11/2026). O dono pediu "atrair". A casa vinha dizendo "não provado" sem
número nenhum — o que é honesto, mas não é medição. Este arquivo transforma a pergunta em três
números e uma regra escrita ANTES de olhar o resultado:

  REGRA DECLARADA (não ajustada depois de ver o número):
    Atração está PROVADA para um vídeo quando, 72 horas depois de publicado, ele tem
    MAIS visualizações que a MEDIANA dos vídeos que o canal já tinha antes dele — e o canal
    ganhou pelo menos 1 inscrito no mesmo período.
    Tradução: o vídeo novo trouxe mais gente que o vídeo típico da casa, e alguém decidiu ficar.
    Enquanto as 72 horas não fecham, o veredito é AINDA_MEDINDO. Se fecharem sem bater a
    régua, o veredito é NAO_PROVADO — e ele vem com os dois números ao lado.

O QUE ELE NÃO FAZ: não inventa, não projeta, não arredonda para cima. Se a API não responder,
ele falha e NÃO reescreve o JSON — número velho com data nova é mentira; número nenhum é
honesto. Também não mede "engajamento" de métrica privada: só views, likes, comentários e
inscritos, que são públicos.

Uso:
  YT_API_KEY=... python3 tools/medir-adesao.py
  YT_API_KEY=... python3 tools/medir-adesao.py --saida posts/adesao.json
"""
import datetime
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(RAIZ, "posts", "youtube-publicados.json")
SAIDA = os.path.join(RAIZ, "posts", "adesao.json")
URL_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
URL_CANAIS = "https://www.googleapis.com/youtube/v3/channels"
URL_ITENS = "https://www.googleapis.com/youtube/v3/playlistItems"

# A régua, escrita antes de ver o número. Mudar isto é ato humano explícito, com motivo.
REGRA = {
    "janela_horas": 72,
    "criterio": ("views do vídeo novo > mediana de views dos vídeos que o canal já tinha antes "
                 "dele e inscritos ganhos >= 1 na mesma janela"),
    "mede": "views, likes, comentários e inscritos (todos públicos)",
    "nao_mede": "tempo de exibição, retenção e origem do tráfego (só com OAuth do dono)",
}


def agora_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def instante(texto):
    """ISO-8601 do YouTube (com Z) para datetime com fuso. None quando não der."""
    texto = str(texto or "").strip()
    if not texto:
        return None
    try:
        return datetime.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def horas_desde(quando, agora=None):
    """Horas cheias desde `quando`. None quando a data não é legível."""
    inicio = instante(quando)
    if inicio is None:
        return None
    fim = agora or agora_utc()
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=datetime.timezone.utc)
    return round((fim - inicio).total_seconds() / 3600.0, 1)


def mediana(valores):
    """Mediana dos inteiros. None quando a lista está vazia (não é zero: é ausência)."""
    numeros = [int(v) for v in valores if isinstance(v, (int, float))]
    if not numeros:
        return None
    return float(statistics.median(numeros))


def veredito(novo, base, inscritos_ganhos, horas, regra=None):
    """(estado, motivo, números). Estado: PROVADO, NAO_PROVADO ou AINDA_MEDINDO."""
    regra = regra or REGRA
    janela = regra["janela_horas"]
    numeros = {"views_novo": novo, "mediana_base": base, "inscritos_ganhos": inscritos_ganhos,
               "horas_no_ar": horas, "janela_horas": janela}
    if novo is None or horas is None:
        return "AINDA_MEDINDO", "sem número do vídeo novo ou sem data legível", numeros
    if base is None:
        return "AINDA_MEDINDO", ("canal sem histórico de views para comparar — a régua exige "
                                 "mediana dos vídeos anteriores"), numeros
    if horas < janela:
        return "AINDA_MEDINDO", ("%s horas no ar de %d — a régua só fecha no fim da janela"
                                 % (horas, janela)), numeros
    passou_views = novo > base
    passou_inscritos = (inscritos_ganhos or 0) >= 1
    if passou_views and passou_inscritos:
        return "PROVADO", ("%d views contra mediana de %.1f, e %d inscrito(s) ganho(s)"
                           % (novo, base, inscritos_ganhos or 0)), numeros
    faltou = []
    if not passou_views:
        faltou.append("%d views não passaram a mediana de %.1f" % (novo, base))
    if not passou_inscritos:
        faltou.append("nenhum inscrito ganho na janela")
    return "NAO_PROVADO", "; ".join(faltou), numeros


def _pedir(url, parametros, chave, abrir=urllib.request.urlopen):
    consulta = urllib.parse.urlencode(dict(parametros, key=chave))
    with abrir(url + "?" + consulta, timeout=30) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def videos_por_id(ids, chave, abrir=urllib.request.urlopen):
    """{id: {views, likes, comentarios, publicado_em}} — em blocos de 50 (limite da API)."""
    saida = {}
    lista = [i for i in ids if i]
    for inicio in range(0, len(lista), 50):
        bloco = lista[inicio:inicio + 50]
        dados = _pedir(URL_VIDEOS, {"part": "snippet,statistics", "id": ",".join(bloco)},
                       chave, abrir)
        for item in dados.get("items") or []:
            estat = item.get("statistics") or {}
            saida[item.get("id")] = {
                "publicado_em": (item.get("snippet") or {}).get("publishedAt"),
                "views": int(estat.get("viewCount") or 0),
                "likes": int(estat.get("likeCount") or 0),
                "comentarios": int(estat.get("commentCount") or 0),
            }
    return saida


def canal_do_video(video_id, chave, abrir=urllib.request.urlopen):
    dados = _pedir(URL_VIDEOS, {"part": "snippet", "id": video_id}, chave, abrir)
    itens = dados.get("items") or []
    if not itens:
        return None, None
    canal = (itens[0].get("snippet") or {}).get("channelId")
    return canal, (itens[0].get("snippet") or {}).get("channelTitle")


def dados_do_canal(canal_id, chave, abrir=urllib.request.urlopen):
    """(id da playlist de uploads, inscritos)."""
    dados = _pedir(URL_CANAIS, {"part": "contentDetails,statistics", "id": canal_id}, chave, abrir)
    itens = dados.get("items") or []
    if not itens:
        return None, None
    uploads = ((itens[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    inscritos = int((itens[0].get("statistics") or {}).get("subscriberCount") or 0)
    return uploads, inscritos


def ultimos_do_canal(playlist, chave, quantos=50, abrir=urllib.request.urlopen):
    """Os ids dos últimos vídeos do canal (a playlist de uploads vem do mais novo ao mais velho)."""
    dados = _pedir(URL_ITENS, {"part": "contentDetails", "playlistId": playlist,
                               "maxResults": min(50, quantos)}, chave, abrir)
    ids = []
    for item in dados.get("items") or []:
        vid = (item.get("contentDetails") or {}).get("videoId")
        if vid:
            ids.append(vid)
    return ids


def publicados(raiz=RAIZ):
    try:
        with open(os.path.join(raiz, "posts", "youtube-publicados.json"), encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return []
    itens = dados.get("publicados") if isinstance(dados, dict) else dados
    return [i for i in itens or [] if isinstance(i, dict) and i.get("id")]


def inscritos_de_referencia(anterior, inscritos_agora):
    """(base, ganho). A base vem da primeira leitura guardada; sem ela, ainda não há ganho medido."""
    if isinstance(anterior, dict) and isinstance(anterior.get("inscritos_base"), int):
        base = anterior["inscritos_base"]
        return base, int(inscritos_agora or 0) - base
    return int(inscritos_agora or 0), None


def medir(chave, raiz=RAIZ, agora=None, abrir=urllib.request.urlopen):
    """Monta o relatório inteiro. Devolve dict pronto para gravar."""
    agora = agora or agora_utc()
    meus = publicados(raiz)
    if not meus:
        return {"quando": agora.isoformat().replace("+00:00", "Z"), "regra": REGRA,
                "veredito": "SEM_VIDEO", "motivo": "nenhum vídeo publicado registrado"}
    novo = meus[0]
    ids = [i["id"] for i in meus]
    stats = videos_por_id(ids, chave, abrir)
    if novo["id"] not in stats:
        raise RuntimeError("a API não devolveu o vídeo novo (%s) — nada é gravado" % novo["id"])
    canal_id, canal_nome = canal_do_video(novo["id"], chave, abrir)
    uploads, inscritos = (None, None)
    if canal_id:
        uploads, inscritos = dados_do_canal(canal_id, chave, abrir)
    do_canal = {}
    if uploads:
        do_canal = videos_por_id(ultimos_do_canal(uploads, chave, abrir=abrir), chave, abrir)
    # Base da régua: os vídeos que o canal JÁ tinha antes daquele que estamos julgando —
    # inclusive os antigos da casa, porque a régua é "mais que o normal do canal".
    corte = instante(novo.get("quando")) or instante(stats[novo["id"]].get("publicado_em"))
    base = [v["views"] for vid, v in do_canal.items()
            if vid != novo["id"] and instante(v.get("publicado_em")) and corte
            and instante(v.get("publicado_em")) < corte]
    base_mediana = mediana(base)
    horas = horas_desde(novo.get("quando") or stats[novo["id"]].get("publicado_em"), agora)
    anterior = None
    try:
        with open(os.path.join(raiz, "posts", "adesao.json"), encoding="utf-8") as f:
            anterior = json.load(f)
    except (OSError, ValueError):
        anterior = None
    base_inscritos, ganho = inscritos_de_referencia(anterior, inscritos)
    estado, motivo, numeros = veredito(stats[novo["id"]]["views"], base_mediana, ganho, horas)
    return {
        "quando": agora.isoformat().replace("+00:00", "Z"),
        "regra": REGRA,
        "canal": {"id": canal_id, "nome": canal_nome, "inscritos": inscritos,
                  "inscritos_base": base_inscritos, "inscritos_ganhos": ganho},
        "video_novo": {"id": novo["id"], "titulo": novo.get("titulo"), "angulo": novo.get("angulo"),
                       "quando": novo.get("quando"), **stats[novo["id"]]},
        "base_da_regua": {"videos_comparados": len(base), "mediana_views": base_mediana,
                          "views": sorted(base, reverse=True)[:20]},
        "veredito": estado,
        "motivo": motivo,
        "numeros": numeros,
        "publicados_medidos": [{"id": i["id"], **stats.get(i["id"], {})} for i in meus],
    }


def main(argv):
    chave = os.environ.get("YT_API_KEY", "").strip()
    saida = SAIDA
    if "--saida" in argv:
        saida = argv[argv.index("--saida") + 1]
    if not chave:
        print("sem YT_API_KEY: nada é medido (e nada é reescrito)")
        return 2
    try:
        dados = medir(chave)
    except Exception as erro:
        print("a medição falhou (%s) — o JSON do dia NÃO é reescrito" % str(erro)[:160])
        return 1
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("vídeo %s (%s): %d views em %s h" % (dados["video_novo"]["id"],
                                               dados["video_novo"].get("angulo") or "sem ângulo",
                                               dados["video_novo"]["views"],
                                               dados["numeros"].get("horas_no_ar")))
    print("base da régua: %d vídeos, mediana %.1f views" % (dados["base_da_regua"]["videos_comparados"],
                                                            dados["base_da_regua"]["mediana_views"] or 0))
    print("inscritos: %s (ganho medido: %s)" % (dados["canal"]["inscritos"],
                                                dados["canal"]["inscritos_ganhos"]))
    print("VEREDITO: %s — %s" % (dados["veredito"], dados["motivo"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
