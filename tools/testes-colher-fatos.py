#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do colhedor de fatos: nem inventa número, nem repete fato, nem deixa a pauta secar.

Tudo com arquivos de amostra em pasta temporária — nenhum contrato mexe na base da casa.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("colher", os.path.join(RAIZ, "tools", "colher-fatos.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


def escreve(raiz, caminho, dados):
    destino = os.path.join(raiz, caminho)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)


def base(raiz):
    escreve(raiz, "posts/fatos.json", {"_o_que_e": "base da casa", "fatos": []})


# ------------------------------------------------------------------ réguas
ok("slug tira acento em vez de virar hífen", c._slug("publicações") == "publicacoes",
   c._slug("publicações"))
ok("slug de meta com dois-pontos", c._slug("itch: downloads") == "itch-downloads")
ok("número presente na origem é aceito", c.numeros_na_origem(["48"], "observado: 48 downloads"))
ok("número ausente da origem é recusado", not c.numeros_na_origem(["49"], "observado: 48"))
ok("lista vazia de números passa (nada a conferir)", c.numeros_na_origem([], "x"))

# ------------------------------------------------------------------ coletores
with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/youtube-publicados.json",
            {"publicados": [{"id": "abc123", "titulo": "Um vídeo de verdade"},
                            {"id": "", "titulo": "sem id"}]})
    fatos, pulados = c.coletor_publicados(raiz=tmp)
ok("vídeo publicado vira fato com id do vídeo", len(fatos) == 1 and fatos[0]["id"] == "video-abc123",
   [f["id"] for f in fatos])
ok("vídeo sem id não vira fato, e fica o motivo", pulados and "sem id" in pulados[0]["motivo"],
   pulados)
ok("o fato aponta o arquivo de origem",
   fatos[0]["origem"] == "posts/youtube-publicados.json", fatos[0]["origem"])
ok("o fato de vídeo é de uma vez só (não se anuncia duas vezes)",
   fatos[0].get("usa_uma_vez") is True)

with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/placar-metas.json", {"linhas": [
        {"meta": "itch: downloads", "observado": 48, "alvo": 100, "status": "RENOVADA"},
        {"meta": "Instagram: seguidores", "observado": 0, "alvo": 50, "status": "PARADA"},
        {"meta": "itch: seguidores (aposentada)", "observado": None, "status": "SEM_LEITURA"},
        {"meta": "YouTube: shorts", "observado": 7, "alvo": 4, "status": "ATINGIDO"}]})
    fatos, pulados = c.coletor_metas(raiz=tmp, hoje=__import__("datetime").date(2026, 11, 8))
ok("meta com número vira fato", any(f["id"].startswith("medido-itch-downloads") for f in fatos),
   [f["id"] for f in fatos])
ok("meta de número zero NÃO vira fato de conteúdo",
   not any("instagram-seguidores" in f["id"] and f["classe"] == "numero" for f in fatos),
   [f["id"] for f in fatos])
ok("e o motivo do zero fica escrito", any("zero" in p["motivo"] for p in pulados), pulados)
ok("meta sem número também não vira fato",
   not any("aposentada" in f["id"] for f in fatos), [f["id"] for f in fatos])
ok("a meta do itch fala do ceifalume, não da casa",
   next(f for f in fatos if "itch-downloads" in f["id"])["assunto"] == "ceifalume",
   [(f["id"], f["assunto"]) for f in fatos])
_num = next(f for f in fatos if "itch-downloads" in f["id"])
ok("o fato de número vence (não é verdade eterna)", _num.get("validade_dias") == 7,
   _num.get("validade_dias"))

with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/prancheta-build.json", {"build_id": "19604665", "medido_em": "2026-11-07T05:38:08Z"})
    fatos, _ = c.coletor_build(raiz=tmp)
ok("o build do PRANCHETA vira fato de marco",
   fatos and fatos[0]["id"] == "marco-prancheta-build-19604665" and fatos[0]["classe"] == "marco",
   fatos and fatos[0]["id"])
ok("o build é assunto prancheta", fatos and fatos[0]["assunto"] == "prancheta")

with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/youtube-metricas.json", {"videos": [
        {"id": "a", "titulo": "vídeo fraco", "views": 3},
        {"id": "b", "titulo": "vídeo forte", "views": 120}]})
    fatos, _ = c.coletor_video_medido(raiz=tmp)
ok("o vídeo mais visto é o que vira fato", fatos and "120" in fatos[0]["afirmacao"],
   fatos and fatos[0]["afirmacao"])
with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/youtube-metricas.json", {"videos": [{"id": "a", "titulo": "x", "views": 0}]})
    fatos, pulados = c.coletor_video_medido(raiz=tmp)
ok("canal com tudo em zero não vira fato (e diz por quê)", fatos == [] and pulados, pulados)

with tempfile.TemporaryDirectory() as tmp:
    fatos, pulados = c.coletor_publicados(raiz=tmp)
ok("fonte ausente não vira fato nem exceção", fatos == [] and "ausente" in pulados[0]["motivo"],
   pulados)

ok("canal com tudo em zero não vira fato (e diz por quê)", fatos == [] and pulados, pulados)

# ------------------------------------------------------------------ coletor de páginas dos jogos (HTML)
def _escreve_html(raiz, caminho, nome, versao, publicado):
    destino = os.path.join(raiz, caminho)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    ld = {"@context": "https://schema.org", "@type": "VideoGame", "name": nome,
          "softwareVersion": versao, "datePublished": publicado}
    html = ('<!DOCTYPE html><html><head>'
            '<script type="application/ld+json">%s</script>'
            '</head><body></body></html>' % json.dumps(ld, ensure_ascii=False))
    with open(destino, "w", encoding="utf-8") as f:
        f.write(html)

with tempfile.TemporaryDirectory() as tmp:
    _escreve_html(tmp, "jogos/prancheta/index.html", "Prancheta", "0.1", "2026-10-06")
    _escreve_html(tmp, "jogos/ceifalume/index.html", "Ceifalume", "0.1", "2026-09-17")
    fatos, pulados = c.coletor_jogos_html(raiz=tmp)
ok("coletor de jogos extrai versão como numero de oficio",
   any(f["id"] == "oficio-versao-prancheta" and f["classe"] == "numero"
       and f["assunto"] == "oficio" and "0.1" in f["afirmacao"] for f in fatos),
   [(f["id"], f["classe"], f["afirmacao"]) for f in fatos])
ok("coletor de jogos extrai lançamento como marco de oficio",
   any(f["id"] == "oficio-lancamento-prancheta" and f["classe"] == "marco"
       and f["assunto"] == "oficio" and "2026-10-06" in f["afirmacao"] for f in fatos),
   [(f["id"], f["classe"], f["afirmacao"]) for f in fatos])
ok("coletor de jogos também cobre o Ceifalume",
   any(f["id"] == "oficio-versao-ceifalume" for f in fatos),
   [f["id"] for f in fatos])
ok("coletor de jogos não tem pulados com arquivos válidos", pulados == [], pulados)

with tempfile.TemporaryDirectory() as tmp:
    # HTML sem JSON-LD
    os.makedirs(os.path.join(tmp, "jogos", "prancheta"), exist_ok=True)
    with open(os.path.join(tmp, "jogos", "prancheta", "index.html"), "w", encoding="utf-8") as f:
        f.write("<html><body>sem json-ld</body></html>")
    fatos, pulados = c.coletor_jogos_html(raiz=tmp)
ok("página sem JSON-LD não vira fato nem exceção", fatos == [] and pulados,
   pulados)

with tempfile.TemporaryDirectory() as tmp:
    # número que não está na origem é recusado
    _escreve_html(tmp, "jogos/prancheta/index.html", "Prancheta", "0.1", "2026-10-06")
    def mentiroso(raiz=tmp, hoje=None):
        return ([{"id": "oficio-versao-falso", "assunto": "oficio", "classe": "numero",
                  "afirmacao": "o jogo está na versão 99.9", "origem": "jogos/prancheta/index.html",
                  "quando": "2026-11-08", "valores": ["99.9"]}], [])
    fatos, rec = c.colher({"fatos": []}, raiz=tmp, coletores=(mentiroso,))
ok("número que não está na origem HTML é recusado",
   fatos == [] and any("não está na origem" in r["motivo"] for r in rec),
   rec)

with tempfile.TemporaryDirectory() as tmp:
    # arquivo ausente não quebra a coleta
    fatos, pulados = c.coletor_jogos_html(raiz=tmp)
ok("arquivo de jogo ausente não gera exceção", fatos == [] and pulados,
   pulados)
# ------------------------------------------------------------------ a coleta
def coletores_de_teste(grande=0):
    def videos(raiz=RAIZ, hoje=None):
        return ([{"id": "video-%d" % i, "assunto": "casa", "classe": "canal",
                  "afirmacao": "vídeo %d publicado" % i, "origem": "posts/youtube-publicados.json",
                  "quando": "2026-11-08", "usa_uma_vez": True} for i in range(grande)], [])

    def metas(raiz=RAIZ, hoje=None):
        return ([{"id": "medido-x", "assunto": "casa", "classe": "numero",
                  "afirmacao": "48 downloads", "origem": "posts/placar-metas.json",
                  "quando": "2026-11-08"}], [])
    return (videos, metas)


with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/youtube-publicados.json", {"publicados": []})
    escreve(tmp, "posts/placar-metas.json", {"linhas": [{"meta": "itch: downloads", "observado": 48}]})
    _novos, _ = c.colher({"fatos": []}, raiz=tmp, coletores=coletores_de_teste(10))
ok("o rodízio não deixa 10 vídeos comerem a cota das metas medidas",
   any(f["id"] == "medido-x" for f in _novos),
   [f["id"] for f in _novos])
ok("cada fonte cede no máximo 3 por coleta",
   sum(1 for f in _novos if f["id"].startswith("video-")) <= 3,
   [f["id"] for f in _novos])

_existentes = [{"id": "video-0", "assunto": "casa", "classe": "canal", "afirmacao": "x",
                "origem": "posts/youtube-publicados.json", "quando": "2026-11-08"}]
with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/youtube-publicados.json", {"publicados": []})
    _novos, _rec = c.colher({"fatos": _existentes}, raiz=tmp, coletores=coletores_de_teste(2))
ok("fato que já existe não é colhido de novo", all(f["id"] != "video-0" for f in _novos),
   [f["id"] for f in _novos])
ok("e o motivo é 'já é fato'", any("já é fato" in r["motivo"] for r in _rec),
   [r["motivo"] for r in _rec][:3])


def coletor_mentiroso(raiz=RAIZ, hoje=None):
    return ([{"id": "inventado-1", "assunto": "casa", "classe": "numero",
              "afirmacao": "o jogo tem 999 fases", "origem": "posts/placar-metas.json",
              "quando": "2026-11-08", "valores": ["999"]}], [])


with tempfile.TemporaryDirectory() as tmp:
    escreve(tmp, "posts/placar-metas.json", {"linhas": [{"meta": "itch: downloads", "observado": 48}]})
    _novos, _rec = c.colher({"fatos": []}, raiz=tmp, coletores=(coletor_mentiroso,))
ok("fato com número que não está na origem é RECUSADO",
   _novos == [] and any("não está na origem" in r["motivo"] for r in _rec), _rec)
ok("o fato recusado não entra no arquivo", _novos == [])

# ------------------------------------------------------------------ gravar
with tempfile.TemporaryDirectory() as tmp:
    base(tmp)
    escreve(tmp, "posts/youtube-publicados.json", {"publicados": [{"id": "abc", "titulo": "t"}]})
    escreve(tmp, "posts/placar-metas.json", {"linhas": [{"meta": "itch: downloads", "observado": 48}]})
    escreve(tmp, "posts/prancheta-build.json", {"build_id": "19604665", "medido_em": "2026-11-07"})
    escreve(tmp, "posts/youtube-metricas.json", {"videos": [{"id": "z", "views": 120, "titulo": "x"}]})
    _r1 = c.colher_e_gravar(raiz=tmp)
    _lido = json.load(open(os.path.join(tmp, "posts/fatos.json"), encoding="utf-8"))
    ok("a coleta grava os fatos novos", len(_lido["fatos"]) == len(_r1["novos"]) > 0,
       (len(_lido["fatos"]), len(_r1["novos"])))
    ok("a coleta preserva o cabeçalho da base (_o_que_e)", _lido.get("_o_que_e") == "base da casa")
    _r2 = c.colher_e_gravar(raiz=tmp)
    ok("colher duas vezes não duplica fato", _r2["novos"] == [], [f["id"] for f in _r2["novos"]])
    _r3 = c.colher_e_gravar(raiz=tmp, ensaio=True)
    ok("ensaio não grava", _r3["novos"] == [] and
       len(json.load(open(os.path.join(tmp, "posts/fatos.json"), encoding="utf-8"))["fatos"]) ==
       len(_lido["fatos"]))

with tempfile.TemporaryDirectory() as tmp:
    _r = c.colher_e_gravar(raiz=tmp)
ok("sem base de fatos a coleta não inventa arquivo", _r["novos"] == [] and _r["recusados"],
   _r["recusados"])

# ------------------------------------------------------------------ colhe só se a pauta estiver curta
def _montar_raiz_com_redator(raiz, n_fatos=6):
    """Cria posts/fatos.json com fatos vivos de cada classe e repertorio sem usos."""
    fatos = []
    classes_assuntos = [
        ("mecanica", "casa"), ("numero", "casa"), ("cultura", "casa"),
        ("bastidor", "casa"), ("disponibilidade", "casa"), ("marco", "casa"),
    ]
    for i in range(n_fatos):
        classe, assunto = classes_assuntos[i % len(classes_assuntos)]
        fatos.append({"id": "fato-teste-%d" % i, "assunto": assunto, "classe": classe,
                      "afirmacao": "afirmação de teste %d" % i, "origem": "x",
                      "quando": "2026-11-08"})
    escreve(raiz, "posts/fatos.json", {"_o_que_e": "teste", "fatos": fatos})
    escreve(raiz, "posts/repertorio.json",
            {"_o_que_e": "repertorio de teste", "pares": {}, "usos": [],
             "fatos_de_uma_vez": []})

with tempfile.TemporaryDirectory() as tmp:
    _montar_raiz_com_redator(tmp)
    n, _ = c.pares_livres(raiz=tmp)
ok("pares_livres conta pares livres num repertório cheio (não é zero porque há fatos de classe)",
   n > 0, n)
ok("pares_livres devolve a lista de fatos junto com a contagem",
   isinstance(c.pares_livres(raiz=tmp)[1], list))

with tempfile.TemporaryDirectory() as tmp:
    _montar_raiz_com_redator(tmp)
    r_acima = c.colher_e_gravar(raiz=tmp, argv=["--se-faltar-pauta"])
ok("acima do piso, colher_e_gravar não escreve nada",
   r_acima["novos"] == [] and r_acima.get("pauta_suficiente") is not None,
   r_acima)

with tempfile.TemporaryDirectory() as tmp:
    _montar_raiz_com_redator(tmp)
    r_abaixo = c.colher_e_gravar(raiz=tmp, argv=["--se-faltar-pauta=3"])
ok("abaixo do piso, colher_e_gravar ainda não cria fato sem fonte real",
   r_abaixo["novos"] == [] and r_abaixo["total"] == 0,
   r_abaixo["novos"])

ok("piso padrão de 12 pares existe",
   c.PISO_DE_PAUTA == 12)

# ------------------------------------------------------------------ a casa de verdade
_dados_reais, _ = c._ler_json("posts/fatos.json")
_novos_reais, _rec_reais = c.colher(_dados_reais or {"fatos": []}, raiz=RAIZ)
ok("na base real, todo fato novo tem origem que existe",
   all(os.path.exists(os.path.join(RAIZ, f["origem"])) for f in _novos_reais),
   [f["origem"] for f in _novos_reais if not os.path.exists(os.path.join(RAIZ, f["origem"]))])
ok("na base real, todo fato novo tem data", all(f.get("quando") for f in _novos_reais),
   [f["id"] for f in _novos_reais if not f.get("quando")])
ok("na base real, nenhum fato novo repete id existente",
   not ({f["id"] for f in _novos_reais} &
        {f["id"] for f in (_dados_reais or {}).get("fatos", [])}))

print("\n%d/%d contratos do colhedor de fatos passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
