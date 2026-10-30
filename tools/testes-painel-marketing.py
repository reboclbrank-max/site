#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testa o painel público do marketing — sem rede, com log de mentira.

O painel é a vitrine da autonomia. Se ele mentir, a autonomia vira propaganda:
  * canal que publicou é mostrado como publicando;
  * canal sem segredo aparece desligado COM o nome do segredo (é o que liga em 30 s);
  * canal em trava anti-spam não é mostrado como falha;
  * o ciclo mostrado é o MAIS NOVO (o log é escrito do antigo para o novo);
  * nada de número inventado: sem medida, a página não escreve zero.
"""
import importlib.util
import os
import datetime
import re
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("painel", os.path.join(RAIZ, "tools", "painel-marketing.py"))
painel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(painel)

certos, falhas = [], []


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos.append(nome)
        print("OK  " + nome)
    else:
        falhas.append((nome, detalhe))
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe else ""))


def texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


html = painel.pagina()
t = texto(html)

ok("a página é HTML completo", html.strip().lower().startswith("<!doctype html"))
ok("tem título e descrição", "<title>" in html and 'name="description"' in html)
ok("é responsiva e sem dependência externa (preview funciona offline)",
   "viewport" in html and "http://" not in html.split("</style>")[0])
ok("mostra o estado do Bluesky como publicando", "Bluesky" in t and "publicando" in t)
ok("canal desligado aparece com o nome do segredo",
   "TELEGRAM_TOKEN" in t or "MASTODON_TOKEN" in t or "DISCORD_WEBHOOK" in t)
ok("explica que a autonomia não pede aprovação", "sem aprovação manual" in t)
ok("mostra o último ciclo", "Último ciclo" in t)

# O log é cronológico: o painel NÃO pode mostrar o primeiro bloco como se fosse o mais novo.
# A checagem é sobre a ORDEM, não sobre uma data cravada (o log cresce a cada ciclo).
def _dt(q):
    return datetime.datetime.strptime(q.replace(" UTC", ""), "%d/%m/%Y %H:%M")


_log = painel.ler_log()
_datas = [_dt(c["quando"]) for c in _log if c.get("quando")]
ok("os ciclos vêm do mais novo para o mais antigo",
   len(_datas) >= 2 and _datas == sorted(_datas, reverse=True),
   "%d ciclos · topo=%s" % (len(_datas), _datas[0].strftime("%d/%m/%Y %H:%M") if _datas else "sem log"))

# E o log de teste (fora de ordem) tem de sair ordenado do mais novo para o mais antigo.
_fixture = (
    "# Log\n\n## 01/01/2026 03:00 UTC\n\n| canal | resultado |\n| --- | --- |\n| bluesky | OK |\n\n"
    "## 02/01/2026 03:00 UTC\n\n| canal | resultado |\n| --- | --- |\n| bluesky | OK |\n"
)
_cru = painel.ciclos_do_texto(_fixture)
ok("o painel reordena mesmo quando o arquivo está fora de ordem",
   [c["quando"] for c in _cru] == ["02/01/2026 03:00 UTC", "01/01/2026 03:00 UTC"],
   [c["quando"] for c in _cru])
ok("cada ciclo traz as linhas de canal", bool(_log) and "bluesky" in _log[0]["linhas"])

_ok_bs, _ind_bs, _ = painel.contar(_log, "bluesky")
ok("bluesky conta como publicando", _ok_bs > 50, _ok_bs)
_ok_tg, _ind_tg, _ = painel.contar(_log, "telegram")
ok("telegram conta como desligado", _ind_tg > 0, _ind_tg)

# trava anti-spam não é falha
_log_falso = [{"quando": "30/10/2026 00:00 UTC", "_chave": None,
               "linhas": {"instagram": "➖ fora da janela do instagram (dia 13h-16h)"}}]
_ok_i, _ind_i, _pulo_i = painel.contar(_log_falso, "instagram")
ok("trava de janela conta como espera, não como falha", _pulo_i == 1 and _ind_i == 0, (_ok_i, _ind_i, _pulo_i))

ok("não usa '0' como número medido quando não há medida", painel.metrica("nao_existe.json") is None)
# O livro de decisões é a parte "sabedoria": decide com número, recusa o resto, nomeia a ignorância.
ok("a página mostra o que a casa decide sozinha", "O que a casa decide sozinha" in t)
ok("a página mostra o que a casa se recusa a decidir", "se recusa a decidir" in t)
ok("a página nomeia o que a casa não sabe", "não sabe (e diz)" in t)
ok("cada decisão exibida cita a fonte do número", ".json" in t or "placar-metas.md" in t)

ok("a página cita as pendências do dono quando existem",
   "depende do dono" in t or not os.path.exists(os.path.join(RAIZ, "posts", "pendencias-do-dono.json")))
ok("não promete publicação sem prova (sem 'todos os canais ativos')", "todos os canais" not in t.lower())
ok("o HTML não vaza segredo com valor (só o NOME do segredo)",
   not re.search(r"(sk-|Bearer |token=[A-Za-z0-9]{10,})", html))

# escrita atômica: gera .tmp e troca (nunca deixa a página pela metade)
_fonte = open(os.path.join(RAIZ, "tools", "painel-marketing.py"), encoding="utf-8").read()
ok("a escrita é atômica (tmp + replace)", ".tmp" in _fonte and "os.replace" in _fonte)

print("\n%d/%d verificações do painel de marketing passaram" % (len(certos), len(certos) + len(falhas)))
sys.exit(0 if not falhas else 1)
