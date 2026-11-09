#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Colhe FATOS NOVOS das coisas que a casa já mediu — para a pauta não secar.

POR QUE EXISTE (08/11/2026): medido no relatório do dia, a casa tinha **19 pautas
possíveis ≈ 3,8 dias** no teto de 5 posts/dia. As pautas saem do repertório (cada par
assunto+ângulo não volta por 20 usos) e 23 dos 33 fatos de uma vez já tinham sido gastos.
Sem fato novo, o pulso simplesmente para de publicar — e o relatório diria "nada
publicado" sem dizer por quê.

A fonte do fato novo não é invenção: são os arquivos que a casa mesma mediu —
`posts/placar-metas.json` (downloads, visitas), `posts/youtube-publicados.json`,
`posts/youtube-metricas.json`, `posts/prancheta-build.json`. Cada fato que sai daqui
carrega `origem` (o arquivo) e `quando`, e **todo número da afirmação tem de existir no
arquivo de origem** — número que não está na origem é recusado, não arredondado.

Uso:
    python3 tools/colher-fatos.py                 # colhe e grava posts/fatos.json
    python3 tools/colher-fatos.py --ensaio        # mostra o que entraria, sem gravar
    python3 tools/colher-fatos.py --se-faltar-pauta   # o pulso usa esta: só colhe se a pauta
                                                      # estiver abaixo do piso (padrão 12 pares)

POR QUE --se-faltar-pauta (08/11/2026): rodar a colheita em todo pulso encheria o
repositório de fato do mesmo dia e o commit viraria ruído. O pulso chama assim, e a
colheita só acontece quando o repertório realmente está sem par assunto+ângulo livre.
Acima do piso o comando não escreve nada e devolve 0 — pulso limpo não vira commit.
"""
import datetime
import json
import os
import re
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FATOS = os.path.join(RAIZ, "posts", "fatos.json")
MAXIMO_POR_COLHETA = 8          # mais que isso vira enxurrada de fato do mesmo dia

# meta do placar → (assunto, classe) — o fato precisa saber de quem fala
ASSUNTO_DA_META = (
    ("itch", "ceifalume"),
    ("youtube", "casa"),
    ("instagram", "casa"),
    ("bluesky", "casa"),
)


def _slug(texto):
    """Slug sem acento: "publicações" vira `publicacoes`, não `publica-es`."""
    base = "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower())
                   if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def _ler_json(caminho, raiz=RAIZ):
    """(dados, texto) — texto cru serve para conferir que o número existe na origem."""
    try:
        texto = open(os.path.join(raiz, caminho), encoding="utf-8").read()
    except OSError:
        return None, ""
    try:
        return json.loads(texto), texto
    except ValueError:
        return None, texto


def numeros_de(texto):
    return re.findall(r"\d+(?:[.,]\d+)?", str(texto or ""))


def numeros_na_origem(valores, fonte_texto):
    """Todo número afirmado tem de estar escrito no arquivo de origem."""
    return all(str(v) in fonte_texto for v in valores)


def _assunto_da_meta(meta):
    baixo = _slug(meta)
    for chave, assunto in ASSUNTO_DA_META:
        if baixo.startswith(chave):
            return assunto
    return "casa"


def coletor_publicados(raiz=RAIZ, hoje=None):
    dados, texto = _ler_json("posts/youtube-publicados.json", raiz)
    if not dados:
        return [], [{"fonte": "youtube-publicados.json", "motivo": "arquivo ausente ou ilegível"}]
    fatos, pulados = [], []
    for item in dados.get("publicados") or []:
        vid = str(item.get("id") or "").strip()
        titulo = str(item.get("titulo") or "").strip()
        if not vid or not titulo:
            pulados.append({"fonte": "youtube-publicados.json", "motivo": "vídeo sem id ou título"})
            continue
        fatos.append({"id": "video-%s" % vid, "assunto": "casa", "classe": "canal",
                      "afirmacao": "o canal da casa publicou o vídeo \"%s\"" % titulo,
                      "origem": "posts/youtube-publicados.json",
                      "quando": (hoje or datetime.date.today()).isoformat(),
                      "usa_uma_vez": True, "valores": [vid]})
    return fatos, pulados


def coletor_metas(raiz=RAIZ, hoje=None):
    dados, texto = _ler_json("posts/placar-metas.json", raiz)
    if not dados:
        return [], [{"fonte": "placar-metas.json", "motivo": "arquivo ausente ou ilegível"}]
    dia = (hoje or datetime.date.today()).isoformat()
    fatos, pulados = [], []
    for linha in dados.get("linhas") or []:
        meta = str(linha.get("meta") or "").strip()
        observado = linha.get("observado")
        if not meta or not isinstance(observado, int):
            pulados.append({"fonte": "placar-metas.json",
                            "motivo": "meta sem número: %s" % (meta or "(sem nome)")})
            continue
        if linha.get("status") == "SEM_LEITURA":
            pulados.append({"fonte": "placar-metas.json", "motivo": "meta sem leitura: " + meta})
            continue
        if observado == 0:
            # ZERO NÃO VIRA FATO DE CONTEÚDO (08/11/2026): "Instagram: 0 seguidores" é verdade e
            # não é gancho de post nenhum. A meta parada já aparece no relatório do dono, com o
            # número e o motivo — o repertório não precisa carregar isso para a rua.
            pulados.append({"fonte": "placar-metas.json",
                            "motivo": "número zero não vira fato de conteúdo: " + meta})
            continue
        nome = _slug(meta.replace(":", " "))
        fatos.append({"id": "medido-%s-%s" % (nome, dia), "assunto": _assunto_da_meta(meta),
                      "classe": "numero",
                      "afirmacao": "%s: %d hoje, medido pela própria casa em %s"
                                   % (meta.replace(":", " —", 1), observado,
                                      dia[8:10] + "/" + dia[5:7]),
                      "origem": "posts/placar-metas.json", "quando": dia,
                      "validade_dias": 7, "repetivel": False,
                      "valores": [str(observado)]})
    return fatos, pulados


def coletor_atingidas(raiz=RAIZ, hoje=None):
    dados, texto = _ler_json("posts/placar-metas.json", raiz)
    if not dados:
        return [], []
    dia = (hoje or datetime.date.today()).isoformat()
    fatos = []
    for linha in dados.get("linhas") or []:
        if linha.get("status") != "ATINGIDO":
            continue
        meta, alvo, observado = (linha.get("meta"), linha.get("alvo"), linha.get("observado"))
        if not meta or not isinstance(alvo, int) or not isinstance(observado, int):
            continue
        fatos.append({"id": "marco-%s" % _slug(str(meta)), "assunto": _assunto_da_meta(str(meta)),
                      "classe": "marco",
                      "afirmacao": "a meta \"%s\" foi atingida: %d de %d"
                                   % (meta, observado, alvo),
                      "origem": "posts/placar-metas.json", "quando": dia, "usa_uma_vez": True,
                      "valores": [str(observado), str(alvo)]})
    return fatos, []


def coletor_build(raiz=RAIZ, hoje=None):
    dados, texto = _ler_json("posts/prancheta-build.json", raiz)
    if not dados:
        return [], [{"fonte": "prancheta-build.json", "motivo": "arquivo ausente ou ilegível"}]
    build = str(dados.get("build_id") or "").strip()
    if not build:
        return [], [{"fonte": "prancheta-build.json", "motivo": "sem build_id medido"}]
    medido = str(dados.get("medido_em") or "")[:10] or (hoje or datetime.date.today()).isoformat()
    return ([{"id": "marco-prancheta-build-%s" % _slug(build), "assunto": "prancheta",
              "classe": "marco",
              "afirmacao": "o itch está servindo o build %s do PRANCHETA desde %s"
                           % (build, medido[8:10] + "/" + medido[5:7]),
              "origem": "posts/prancheta-build.json", "quando": medido,
              "usa_uma_vez": True, "valores": [build]}], [])


def coletor_video_medido(raiz=RAIZ, hoje=None):
    dados, texto = _ler_json("posts/youtube-metricas.json", raiz)
    if not dados:
        return [], [{"fonte": "youtube-metricas.json", "motivo": "arquivo ausente ou ilegível"}]
    videos = [v for v in (dados.get("videos") or []) if isinstance(v.get("views"), int)]
    if not videos:
        return [], [{"fonte": "youtube-metricas.json", "motivo": "nenhum vídeo com views"}]
    topo = max(videos, key=lambda v: v["views"])
    if not topo["views"]:
        return [], [{"fonte": "youtube-metricas.json", "motivo": "todos os vídeos com 0 view"}]
    dia = (hoje or datetime.date.today()).isoformat()
    return ([{"id": "medido-views-%s-%s" % (_slug(topo["id"]), dia), "assunto": "casa",
              "classe": "numero",
              "afirmacao": "o vídeo \"%s\" está com %d views, medido em %s"
                           % (str(topo.get("titulo") or topo["id"]), topo["views"],
                              dia[8:10] + "/" + dia[5:7]),
              "origem": "posts/youtube-metricas.json", "quando": dia,
              "validade_dias": 3, "repetivel": False,
              "valores": [str(topo["views"])]}], [])



def coletor_jogos_html(raiz=RAIZ, hoje=None):
    """Extrai fatos das páginas dos jogos (JSON-LD embutido em HTML).

    Cada página de jogo expõe dados estruturados com versão e data de lançamento.
    A versão vira fato de classe ``numero`` para o ``oficio`` — o ofício de fazer
    jogos inclui versionar o que se faz. A data vira fato de classe ``marco``.
    Todo número afirmado tem de aparecer no HTML de origem (regua dura da colheita).
    """
    fatos, pulados = [], []
    dia = (hoje or datetime.date.today()).isoformat()
    for caminho in ("jogos/prancheta/index.html", "jogos/ceifalume/index.html"):
        _dados, texto = _ler_json(caminho, raiz)
        if not texto:
            pulados.append({"fonte": caminho, "motivo": "arquivo ausente ou ilegível"})
            continue
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', texto, re.S)
        if not m:
            pulados.append({"fonte": caminho, "motivo": "sem JSON-LD na página"})
            continue
        try:
            ld = json.loads(m.group(1))
        except ValueError:
            pulados.append({"fonte": caminho, "motivo": "JSON-LD ilegível"})
            continue
        nome = str(ld.get("name") or ld.get("alternateName") or caminho).strip()
        if not nome:
            pulados.append({"fonte": caminho, "motivo": "sem nome do jogo"})
            continue
        slug = _slug(nome)
        versao = str(ld.get("softwareVersion") or "").strip()
        if versao:
            fatos.append({"id": "oficio-versao-%s" % slug, "assunto": "oficio",
                          "classe": "numero",
                          "afirmacao": "o %s está na versão %s" % (nome, versao),
                          "origem": caminho, "quando": dia,
                          "valores": [versao]})
        publicado = str(ld.get("datePublished") or "").strip()[:10]
        if publicado and re.fullmatch(r"\d{4}-\d{2}-\d{2}", publicado):
            fatos.append({"id": "oficio-lancamento-%s" % slug, "assunto": "oficio",
                          "classe": "marco",
                          "afirmacao": "o %s foi lançado em %s" % (nome, publicado),
                          "origem": caminho, "quando": dia,
                          "usa_uma_vez": True, "valores": [publicado]})
    return fatos, pulados




COLETORES = (coletor_publicados, coletor_metas, coletor_atingidas, coletor_build,
             coletor_video_medido, coletor_jogos_html)


def colher(dados_de_fatos, raiz=RAIZ, hoje=None, limite=MAXIMO_POR_COLHETA,
           por_coletor=3, coletores=COLETORES):
    """Devolve (novos, recusados). Nunca repete fato, nunca inventa número.

    RODÍZIO ENTRE AS FONTES (08/11/2026): a primeira versão pegava os coletores em ordem e o
    `limite` de 8 era comido pelos 10 vídeos publicados — as metas medidas (downloads, visitas),
    o build do PRANCHETA e as views nunca entravam. Fato de vídeo é o mais abundante e o menos
    informativo; o rodízio garante que cada fonte ceda no máximo `por_coletor` por coleta.
    """
    existentes = {str(f.get("id")) for f in (dados_de_fatos.get("fatos") or []) if f.get("id")}
    recusados, filas = [], []
    for coletor in coletores:
        try:
            candidatos, pulados = coletor(raiz=raiz, hoje=hoje)
        except Exception as erro:  # noqa: BLE001 — coletor quebrado não derruba os outros
            recusados.append({"fonte": coletor.__name__,
                              "motivo": "coletor falhou: %s" % str(erro)[:80]})
            continue
        recusados.extend(pulados)
        fonte_texto = _texto_da_origem(candidatos, raiz)
        fila = []
        for fato in candidatos:
            if fato["id"] in existentes:
                recusados.append({"fonte": fato["origem"], "motivo": "já é fato: " + fato["id"]})
                continue
            if not str(fato.get("afirmacao") or "").strip():
                recusados.append({"fonte": fato["origem"], "motivo": "afirmação vazia"})
                continue
            if not numeros_na_origem(fato.get("valores") or [], fonte_texto):
                # NÚMERO QUE NÃO ESTÁ NA ORIGEM NÃO ENTRA: é assim que se evita fato inventado.
                recusados.append({"fonte": fato["origem"],
                                  "motivo": "número não está na origem: " + fato["id"]})
                continue
            fila.append({k: v for k, v in fato.items() if k != "valores"})
        filas.append(fila)

    novos = []
    while len(novos) < limite and any(filas):
        for fila in filas:
            if not fila:
                continue
            if len(novos) >= limite:
                break
            tirados = sum(1 for f in novos if f["origem"] == fila[0]["origem"])
            if tirados >= por_coletor:
                recusados.append({"fonte": fila[0]["origem"],
                                  "motivo": "cota da fonte nesta coleta (%d) cheia" % por_coletor})
                fila.clear()
                continue
            fato = fila.pop(0)
            novos.append(fato)
            existentes.add(fato["id"])
    return novos, recusados


def _texto_da_origem(candidatos, raiz):
    """Texto cru do arquivo de origem do primeiro candidato (todos vêm do mesmo arquivo)."""
    if not candidatos:
        return ""
    return _ler_json(candidatos[0]["origem"], raiz)[1]


def colher_e_gravar(raiz=RAIZ, hoje=None, ensaio=False, argv=None):
    """Colhe fatos e grava em posts/fatos.json.

    Se `argv` traz `--se-faltar-pauta[=N]`, a colheita só acontece quando os
    pares assunto+ângulo livres estão abaixo do piso (padrão 12). Acima do piso
    nada é escrito e o pulso fica limpo.
    """
    piso = PISO_DE_PAUTA
    if argv:
        for a in argv:
            if a == "--se-faltar-pauta":
                break
            if a.startswith("--se-faltar-pauta="):
                piso = int(a.split("=", 1)[1])
                break
        else:
            piso = None
        if piso is not None:
            livres, dados_existentes = pares_livres(raiz=raiz)
            if livres >= piso:
                return {"novos": [], "recusados": [],
                        "total": len(dados_existentes.get("fatos", [])) if isinstance(dados_existentes, dict) else 0,
                        "pauta_suficiente": livres}
    caminho = os.path.join(raiz, "posts", "fatos.json")
    dados, _texto = _ler_json("posts/fatos.json", raiz)
    if not isinstance(dados, dict) or not isinstance(dados.get("fatos"), list):
        return {"novos": [], "recusados": [{"fonte": "fatos.json",
                                            "motivo": "base ausente ou ilegível"}], "total": None}
    novos, recusados = colher(dados, raiz=raiz, hoje=hoje)
    if novos and not ensaio:
        dados["fatos"].extend(novos)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return {"novos": novos, "recusados": recusados, "total": len(dados["fatos"]) + (
        0 if not ensaio else len(novos))}


PISO_DE_PAUTA = 12       # pares assunto+ângulo livres abaixo disso = hora de colher


def _redator():
    """Importa o redator sem depender do nome do módulo (mesmo padrão do medidor)."""
    import importlib.util
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "redator.py")
    spec = importlib.util.spec_from_file_location("redator_da_colheita", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pares_livres(raiz=RAIZ):
    """Quantos pares assunto+ângulo o redator consegue montar agora (o que a pauta gasta)."""
    red = _redator()
    fatos = red.carregar_fatos()
    try:
        rep = json.load(open(os.path.join(raiz, "posts", "repertorio.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return 0, fatos
    return len(red.pautas_possiveis(fatos, rep)), fatos


def main(argv):
    ensaio = "--ensaio" in argv
    piso = PISO_DE_PAUTA
    for a in argv:
        if a.startswith("--se-faltar-pauta="):
            piso = int(a.split("=", 1)[1])
    if "--se-faltar-pauta" in argv or any(a.startswith("--se-faltar-pauta=") for a in argv):
        livres, _ = pares_livres()
        if livres >= piso:
            print("pauta suficiente: %d par(es) livre(s) (piso %d) — nada colhido, nada escrito"
                  % (livres, piso))
            return 0
        print("pauta curta: %d par(es) livre(s), abaixo do piso %d — colhendo" % (livres, piso))
    r = colher_e_gravar(ensaio=ensaio)
    if r["total"] is None and not r["novos"]:
        print("nada colhido: " + (r["recusados"][0]["motivo"] if r["recusados"] else "sem motivo"))
        return 3
    print("fatos novos: %d%s" % (len(r["novos"]), " (ensaio, não gravado)" if ensaio else ""))
    for f in r["novos"]:
        print("  + %s · %s · %s" % (f["id"], f["assunto"], f["afirmacao"][:90]))
    if r["recusados"]:
        print("recusados: %d" % len(r["recusados"]))
        for m in r["recusados"][:6]:
            print("  - %s: %s" % (m["fonte"], m["motivo"]))
    print("base agora: %s fato(s)" % r["total"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
