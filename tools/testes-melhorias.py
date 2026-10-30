#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes da página pública de melhorias.

A página só vale se ela não mentir e não envelhecer sozinha. Aqui se cobra:
  - os números vêm dos artefatos do repositório (e batem com eles);
  - quando o dado não existe, a página diz "não medido" em vez de zero;
  - os documentos das rodadas aparecem, com link, sem copiar o texto;
  - a escrita é atômica e o link para o painel existe.
"""
import importlib.util
import json
import os
import re
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FALHAS = []
TOTAL = []


def ok(nome, condicao, detalhe=None):
    TOTAL.append(nome)
    if condicao:
        print("OK  " + nome)
    else:
        FALHAS.append(nome)
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe is not None else ""))


def carregar():
    spec = importlib.util.spec_from_file_location(
        "melhorias", os.path.join(RAIZ, "tools", "melhorias.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = carregar()
html_pagina = m.pagina()
texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_pagina))

# ---------------------------------------------------------------- estrutura
ok("a página é HTML completo", html_pagina.strip().lower().startswith("<!doctype html"))
ok("tem título, descrição e canônica",
   "<title>" in html_pagina and 'name="description"' in html_pagina
   and 'rel="canonical"' in html_pagina)
ok("é responsiva e sem dependência externa (preview offline)",
   "viewport" in html_pagina and "http://" not in html_pagina.split("</style>")[0])

# ---------------------------------------------------------------- números honestos
ok("mostra os cartões com números", "rodadas documentadas" in texto and "suítes de teste" in texto)
ok("diz quantas suítes a barreira cobra",
   "cobradas na barreira do ciclo" in texto)
_arquivos, _cobradas = m.suites()
ok("a contagem de suítes bate com o diretório",
   str(len(_arquivos)) in texto and len(_arquivos) >= 25, (_arquivos and len(_arquivos)))
ok("a contagem de cobradas na barreira é a do workflow",
   str(len(_cobradas)) in texto and len(_cobradas) >= 10, len(_cobradas))

_c = m.cifras()
ok("os ciclos vêm do log de verdade", _c["ciclos"] > 0 and str(_c["ciclos"]) in texto, _c["ciclos"])
_aud = m.ler_json("posts/auditoria-inteligencia.json")
ok("o número de passos adaptativos vem da auditoria",
   (_aud.get("contagem") or {}).get("adaptativo") is None
   or str(_aud["contagem"]["adaptativo"]) in texto)
_dec = m.ler_json("posts/decisoes.json")
ok("as decisões/recusas/ignorâncias vêm do livro de decisões",
   (_dec.get("contagem") or {}).get("decididas") is None
   or str(_dec["contagem"]["decididas"]) in texto)
_gosto = m.ler_json("posts/perfil-de-gosto.json")
ok("o gosto mostra medidos × declarados e a amostra",
   "gosto medido no feed" in texto
   and (str(len(_gosto.get("medidos") or [])) in texto)
   and (str(_gosto.get("amostra")) in texto if _gosto else "amostra" in texto))

# ---------------------------------------------------------------- honestidade quando falta dado
ok("quando um número não existe, diz 'não medido' (nunca zero inventado)",
   m._num(None) == "não medido")
ok("número existente não vira 'não medido'", m._num(0) == "0" and m._num(5, "%") == "5%")

# ---------------------------------------------------------------- rodadas e docs
_rod = m.rodadas()
ok("lista as rodadas a partir dos documentos", len(_rod) >= 6, len(_rod))
ok("as rodadas vêm da mais nova para a mais antiga",
   [r[0] for r in _rod] == sorted([r[0] for r in _rod], reverse=True))
ok("cada rodada tem título (não só o nome do arquivo)",
   all(r[1] and len(r[1]) > 10 for r in _rod), [r[1] for r in _rod if len(r[1]) <= 10])
ok("cada rodada aponta para o documento no GitHub",
   all(r[2].startswith("docs/RODADA-") for r in _rod)
   and "github.com/reboclbrank-max/site/blob/main/docs/RODADA-" in html_pagina)
ok("a página NÃO copia o texto dos documentos (uma fonte só)",
   "##" not in texto and len(html_pagina) < 40000)

# ---------------------------------------------------------------- o que falta e links
ok("mostra o que ainda depende do dono", "O que ainda depende do dono" in texto)
ok("linka o painel do marketing", "marketing.html" in html_pagina)
ok("linka os canais oficiais", "canais.html" in html_pagina)
ok("diz quem gera a página e quando", "workflow postagem-diaria" in texto and "Gerado em" in texto)

# ---------------------------------------------------------------- escrita
tmp = tempfile.mkdtemp(prefix="melhorias-")
_alvo = os.path.join(tmp, "melhorias.html")
_antigo = m.SAIDA
m.SAIDA = _alvo
import io
_out, sys.stdout = sys.stdout, io.StringIO()
try:
    m.main([])
finally:
    sys.stdout = _out
    m.SAIDA = _antigo
ok("grava o arquivo", os.path.exists(_alvo))
ok("escrita atômica (sem .tmp sobrando)", not os.path.exists(_alvo + ".tmp"))
ok("o arquivo gravado é igual ao gerado em memória",
   open(_alvo, encoding="utf-8").read() == html_pagina)

# ---------------------------------------------------------------- encaixe no site e no ciclo
ok("a página está linkada no painel de marketing",
   "melhorias.html" in open(os.path.join(RAIZ, "marketing.html"), encoding="utf-8").read())
ok("a página está no sitemap",
   "melhorias.html" in open(os.path.join(RAIZ, "sitemap.xml"), encoding="utf-8").read())
_wf = open(os.path.join(RAIZ, ".github", "workflows", "postagem-diaria.yml"), encoding="utf-8").read()
ok("o ciclo gera a página", "tools/melhorias.py" in _wf)
ok("o ciclo commita a página", "melhorias.html" in _wf)
ok("o ciclo cobra estes testes", "testes-melhorias.py" in _wf)

print()
if FALHAS:
    print("%d de %d verificações das melhorias FALHARAM" % (len(FALHAS), len(TOTAL)))
    sys.exit(1)
print("%d/%d verificações da página de melhorias passaram" % (len(TOTAL), len(TOTAL)))
