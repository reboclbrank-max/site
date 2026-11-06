#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da medição de adesão — a regra escrita antes de olhar o número.

O que se prova aqui, sem rede e sem chave de API:

  1. A régua é declarada: janela, critério e o que ela NÃO mede.
  2. O veredito só sai com os três números (views do vídeo novo, mediana da base, inscritos).
  3. Antes das 72 horas o veredito é AINDA_MEDINDO — não se anuncia atração com o número fresco.
  4. Sem base de comparação não há veredito: mediana ausente é ausência, não zero.
  5. Se a API não devolve o vídeo novo, a medição falha e o JSON do dia não é reescrito.
  6. Sem YT_API_KEY nada é medido e nada é gravado.
  7. O medidor não publica, não altera vídeo e não chama nada além de leitura.
"""
import datetime
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import urllib.parse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + str(detalhe)[:160] if detalhe != "" else ""))


spec = importlib.util.spec_from_file_location("medir_adesao", os.path.join(RAIZ, "tools", "medir-adesao.py"))
ma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ma)

AGORA = datetime.datetime(2026, 11, 9, 12, 0, tzinfo=datetime.timezone.utc)

# ---- 1. a régua é declarada
ok("a régua declara a janela de 72 horas", ma.REGRA["janela_horas"] == 72, ma.REGRA)
ok("a régua diz o que mede", "views" in ma.REGRA["mede"] and "inscritos" in ma.REGRA["mede"])
ok("a régua diz o que NÃO mede (nada de fingir retenção)",
   "retenção" in ma.REGRA["nao_mede"], ma.REGRA["nao_mede"])
ok("a régua é comparativa (mediana do canal), não um número inventado",
   "mediana" in ma.REGRA["criterio"], ma.REGRA["criterio"])

# ---- 2. mediana e tempo
ok("mediana de lista vazia é ausência (None), não zero", ma.mediana([]) is None)
ok("mediana de três valores é o do meio", ma.mediana([10, 20, 30]) == 20.0)
ok("mediana não se deixa levar por um valor gigante", ma.mediana([10, 11, 400]) == 11.0)
ok("horas no ar são contadas a partir do Z do YouTube",
   ma.horas_desde("2026-11-06T16:08:00Z", AGORA) == 67.9, ma.horas_desde("2026-11-06T16:08:00Z", AGORA))
ok("data ilegível não vira número inventado", ma.horas_desde("ontem", AGORA) is None)

# ---- 3. veredito
estado, motivo, nums = ma.veredito(120, 40.0, 2, 80)
ok("vídeo acima da mediana com inscrito ganho PROVA atração", estado == "PROVADO", motivo)
ok("e o motivo traz os números", "120" in motivo and "40.0" in motivo, motivo)
estado, motivo, _ = ma.veredito(12, 40.0, 0, 80)
ok("vídeo abaixo da mediana NÃO prova atração", estado == "NAO_PROVADO", motivo)
ok("e o motivo diz as duas coisas que faltaram",
   "mediana" in motivo and "inscrito" in motivo, motivo)
estado, _, _ = ma.veredito(120, 40.0, 0, 80)
ok("views boas sem inscrito ganho não provam adesão", estado == "NAO_PROVADO", estado)
estado, motivo, _ = ma.veredito(120, 40.0, 3, 30)
ok("antes das 72 horas o veredito é AINDA_MEDINDO", estado == "AINDA_MEDINDO", motivo)
estado, motivo, _ = ma.veredito(120, None, 3, 90)
ok("sem mediana da base não há veredito", estado == "AINDA_MEDINDO" and "mediana" in motivo, motivo)
estado, _, _ = ma.veredito(None, 40.0, 1, 90)
ok("sem número do vídeo não há veredito", estado == "AINDA_MEDINDO", estado)

# ---- 5/6/7. a medição inteira, com API de mentira
CHAMADAS = []


def api_falsa(novo_existe=True, views_novo=18, inscritos=25):
    """Uma YouTube Data API de mentira, que responde pelo parâmetro `id=` de verdade."""
    CATALOGO = {
        "03313IcXvEo": {"publicado_em": "2026-11-06T16:08:00Z", "canal": "UCcanal"},
        "VID_ANTIGO": {"publicado_em": "2026-10-01T10:00:00Z", "views": 30},
        "VID_ANTIGO2": {"publicado_em": "2026-10-20T10:00:00Z", "views": 40},
        "VID_ANTIGO3": {"publicado_em": "2026-10-25T10:00:00Z", "views": 8},
    }

    def abrir(url, timeout=30):
        CHAMADAS.append(url)
        consulta = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)

        class Resposta:
            def __init__(self, corpo):
                self.corpo = json.dumps(corpo).encode("utf-8")

            def read(self):
                return self.corpo

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        if url.startswith(ma.URL_VIDEOS) and "playlistId" not in url:
            pedidos = [i for i in (consulta.get("id") or [""])[0].split(",") if i]
            itens = []
            for vid in pedidos:
                if vid == "03313IcXvEo" and not novo_existe:
                    continue
                dado = CATALOGO.get(vid)
                if dado is None:
                    continue
                if "snippet" in (consulta.get("part") or [""])[0] and "statistics" not in \
                        (consulta.get("part") or [""])[0]:
                    itens.append({"id": vid, "snippet": {"channelId": dado["canal"],
                                                         "channelTitle": "Rebocl Brank",
                                                         "publishedAt": dado["publicado_em"]}})
                    continue
                views = views_novo if vid == "03313IcXvEo" else dado.get("views", 0)
                itens.append({"id": vid,
                              "snippet": {"publishedAt": dado["publicado_em"]},
                              "statistics": {"viewCount": str(views), "likeCount": "2",
                                             "commentCount": "0"}})
            return Resposta({"items": itens})
        if url.startswith(ma.URL_CANAIS):
            return Resposta({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUcanal"}},
                                        "statistics": {"subscriberCount": str(inscritos)}}]})
        if url.startswith(ma.URL_ITENS):
            return Resposta({"items": [{"contentDetails": {"videoId": v}} for v in
                                       ("03313IcXvEo", "VID_ANTIGO3", "VID_ANTIGO2", "VID_ANTIGO")]})
        raise AssertionError("URL inesperada: " + url)
    return abrir


def bancada(publicados):
    tmp = tempfile.mkdtemp(prefix="bancada-adesao-")
    os.makedirs(os.path.join(tmp, "posts"), exist_ok=True)
    with open(os.path.join(tmp, "posts", "youtube-publicados.json"), "w", encoding="utf-8") as f:
        json.dump({"publicados": publicados}, f)
    return tmp


PUBLICADOS = [{"id": "03313IcXvEo", "titulo": "9 colheitas em 2 min de CEIFALUME 0.1",
               "angulo": "numeros", "quando": "2026-11-06T16:08:00Z"}]

tmp = bancada(PUBLICADOS)
CHAMADAS.clear()
dados = ma.medir("chave-de-teste", raiz=tmp, agora=AGORA, abrir=api_falsa())
ok("a medição lê o canal e a playlist de uploads",
   any(u.startswith(ma.URL_CANAIS) for u in CHAMADAS) and
   any(u.startswith(ma.URL_ITENS) for u in CHAMADAS), CHAMADAS)
ok("o vídeo novo é o primeiro publicado", dados["video_novo"]["id"] == "03313IcXvEo")
ok("as views do vídeo novo vêm da API", dados["video_novo"]["views"] == 18, dados["video_novo"])
ok("a base da régua são os vídeos ANTERIORES (o novo não entra na própria régua)",
   dados["base_da_regua"]["videos_comparados"] == 3, dados["base_da_regua"])
ok("a mediana da base é a dos anteriores", dados["base_da_regua"]["mediana_views"] == 30.0,
   dados["base_da_regua"])
ok("com 67,9 horas no ar o veredito é AINDA_MEDINDO", dados["veredito"] == "AINDA_MEDINDO",
   dados["veredito"])
ok("o relatório guarda a regra junto do número (para o número não ser lido sem a régua)",
   dados["regra"]["janela_horas"] == 72)
ok("o relatório traz os inscritos do canal", dados["canal"]["inscritos"] == 25, dados["canal"])
ok("o motivo do veredito vai escrito", bool(dados["motivo"]), dados["motivo"])

# depois da janela, com views acima da mediana e inscrito ganho
depois = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone.utc)
dados2 = ma.medir("chave-de-teste", raiz=tmp, agora=depois, abrir=api_falsa(views_novo=90))
ok("depois da janela, views acima da mediana viram veredito", dados2["veredito"] in
   ("PROVADO", "NAO_PROVADO"), dados2["veredito"])
ok("e o veredito vem com número, não com adjetivo",
   dados2["numeros"]["views_novo"] == 90 and dados2["numeros"]["mediana_base"] == 30.0,
   dados2["numeros"])

# ---- 6/5. falhas não viram número
vazio = bancada([])
dados3 = ma.medir("chave", raiz=vazio, agora=AGORA, abrir=api_falsa())
ok("sem vídeo publicado o relatório é SEM_VIDEO", dados3["veredito"] == "SEM_VIDEO", dados3)
shutil.rmtree(vazio, ignore_errors=True)

try:
    ma.medir("chave", raiz=tmp, agora=AGORA, abrir=api_falsa(novo_existe=False))
    ok("API sem o vídeo novo tem de falhar", False)
except RuntimeError as erro:
    ok("API sem o vídeo novo falha em vez de gravar zero", "nada é gravado" in str(erro), erro)

os.environ.pop("YT_API_KEY", None)
saida = os.path.join(tmp, "posts", "adesao.json")
ok("sem YT_API_KEY o medidor não mede", ma.main(["medir"]) == 2)
ok("e não grava arquivo nenhum", not os.path.exists(saida))

# JSON existente não é reescrito quando a API falha
with open(saida, "w", encoding="utf-8") as f:
    json.dump({"veredito": "ANTERIOR"}, f)


def abrir_quebrado(url, timeout=30):
    raise OSError("sem rede")


import urllib.request
_original = urllib.request.urlopen
urllib.request.urlopen = abrir_quebrado
try:
    os.environ["YT_API_KEY"] = "chave-de-teste"
    codigo = ma.main(["medir", "--saida", saida])
finally:
    urllib.request.urlopen = _original
    os.environ.pop("YT_API_KEY", None)
ok("medidor que falha sai com código de erro", codigo == 1, codigo)
ok("e o JSON do dia continua sendo o anterior (número velho não ganha data nova)",
   json.load(open(saida, encoding="utf-8"))["veredito"] == "ANTERIOR")
shutil.rmtree(tmp, ignore_errors=True)

# ---- 12. inscritos: a base vem da primeira leitura
ok("primeira leitura não inventa inscritos ganhos", ma.inscritos_de_referencia(None, 24) == (24, None))
ok("leitura seguinte compara com a base guardada",
   ma.inscritos_de_referencia({"inscritos_base": 24}, 27) == (24, 3))

# ---- 7. o medidor só lê
fonte = open(os.path.join(RAIZ, "tools", "medir-adesao.py"), encoding="utf-8").read()
ok("o medidor não faz POST (não publica, não altera vídeo)",
   "POST" not in fonte and "Request(" not in fonte)
ok("o medidor só usa os endpoints de leitura",
   all(endpoint.startswith("https://www.googleapis.com/youtube/v3/") for endpoint in
       (ma.URL_VIDEOS, ma.URL_CANAIS, ma.URL_ITENS)))

# ---- 13. o workflow mede e versiona
wf = open(os.path.join(RAIZ, ".github", "workflows", "metricas-youtube.yml"), encoding="utf-8").read()
ok("o workflow mede a adesão", "medir-adesao.py" in wf)
ok("o workflow roda o contrato da medição de adesão", "testes-medir-adesao.py" in wf)
ok("o workflow versiona posts/adesao.json", "posts/adesao.json" in wf)

print("\n%d/%d contratos da medição de adesão passaram" % (certos, certos + falhas))
raise SystemExit(0 if falhas == 0 else 1)
