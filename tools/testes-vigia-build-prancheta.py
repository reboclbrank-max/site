#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do vigia do build do PRANCHETA. Nenhum teste toca a rede: o HTML vem de fixture."""
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "vigia", os.path.join(RAIZ, "tools", "vigia-build-prancheta.py"))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

certos = [0]
falhas = [0]


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos[0] += 1
        print("✔ " + nome)
    else:
        falhas[0] += 1
        print("✗ " + nome + (" — " + str(detalhe)[:300] if detalhe else ""))


PAGINA_CLASSIC = ('<html><body><div id="game_drop"><iframe src="https://html-classic.itch.zone/'
                  'html/19604665/index.html?platform=web"></iframe></div></body></html>')
PAGINA_NOVA = '<html><iframe src="https://html.itch.zone/html/777001/index.html"></iframe></html>'

# ------------------------------------------------------------------ achar o build
ok("acha o build no endereço html-classic", v.extrair_build(PAGINA_CLASSIC) == "19604665",
   v.extrair_build(PAGINA_CLASSIC))
ok("acha o build no endereço html (formato novo)", v.extrair_build(PAGINA_NOVA) == "777001",
   v.extrair_build(PAGINA_NOVA))
ok("página sem build não inventa id", v.extrair_build("<html>nada aqui</html>") is None)
ok("página vazia não inventa id", v.extrair_build("") is None)
ok("id curto demais não é build", v.extrair_build("itch.zone/html/12/index.html") is None)
ok("com dois builds, vale o do jogador (o primeiro)",
   v.extrair_build("itch.zone/html/111111/a itch.zone/html/222222/b") == "111111")

# ------------------------------------------------------------------ comparar
_sit, _frase = v.comparar("123456", {})
ok("sem registro anterior, o build é novo", _sit == "novo" and "primeiro registro" in _frase, _frase)
_sit, _frase = v.comparar("123456", {"build_id": "123456", "medido_em": "2026-11-07T05:00:00Z"})
ok("mesmo build é 'igual'", _sit == "igual", _frase)
ok("'igual' diz desde quando a casa sabe", "2026-11-07T05:00:00Z" in _frase, _frase)
_sit, _frase = v.comparar("999999", {"build_id": "123456", "medido_em": "2026-11-06T10:00:00Z"})
ok("build diferente é 'mudou'", _sit == "mudou", _frase)
ok("'mudou' diz o id antigo e o novo", "999999" in _frase and "123456" in _frase, _frase)
ok("'mudou' diz quando o antigo foi visto", "2026-11-06T10:00:00Z" in _frase, _frase)
_sit, _frase = v.comparar(None, {"build_id": "123456"})
ok("sem id na página, a situação é 'não medido'", _sit == "não medido", _frase)
ok("'não medido' não afirma nada", "não afirmo" in _frase, _frase)

with tempfile.TemporaryDirectory() as tmp:
    registro = os.path.join(tmp, "prancheta-build.json")

    # ------------------------------------------------------------------ falha nunca vira sucesso
    def buscar_quebrado(url):
        raise RuntimeError("curl falhou (código 28): timeout")

    _sit, _frase, _build = v.medir(buscar=buscar_quebrado, caminho=registro)
    ok("rede fora vira 'não medido', não exceção", _sit == "não medido", _frase)
    ok("a frase do erro diz o motivo", "timeout" in _frase, _frase)
    ok("sem medida, nenhum arquivo é escrito", not os.path.exists(registro))

    # ------------------------------------------------------------------ gravar
    try:
        v.gravar(None, "novo", caminho=registro)
        ok("gravar build inexistente é recusado", False)
    except ValueError:
        ok("gravar build inexistente é recusado", True)

    _dados = v.gravar("19604665", "novo", caminho=registro,
                      agora=__import__("datetime").datetime(2026, 11, 7, 5, 40,
                                                             tzinfo=__import__("datetime").timezone.utc))
    ok("o registro guarda o build", _dados["build_id"] == "19604665", _dados)
    ok("o registro guarda quando foi medido", _dados["medido_em"] == "2026-11-07T05:40:00Z", _dados)
    ok("o registro diz o que é (quem ler depois entende)", "_o_que_e" in _dados, _dados)
    ok("o registro guarda a página de onde veio", _dados["pagina"].startswith("https://"), _dados)
    ok("primeiro registro não inventa histórico", _dados["historico"] == [], _dados)

    _sit, _frase, _build = v.medir(buscar=lambda url: PAGINA_CLASSIC, caminho=registro)
    ok("medir de novo com o mesmo build dá 'igual'", _sit == "igual", _frase)

    _dados2 = v.gravar("20000000", "mudou", caminho=registro)
    ok("build novo entra substituindo o antigo", _dados2["build_id"] == "20000000", _dados2)
    ok("o build antigo fica no histórico",
       _dados2["historico"] and _dados2["historico"][-1]["build_id"] == "19604665", _dados2)

    _sit, _frase, _build = v.medir(buscar=lambda url: PAGINA_NOVA, caminho=registro)
    ok("medir depois da troca dá 'mudou' e cita os dois ids",
       _sit == "mudou" and "777001" in _frase and "20000000" in _frase, _frase)

    # ------------------------------------------------------------------ linha de comando
    _salvo_registro = v.REGISTRO
    _salvo_buscar = v.buscar_texto
    v.REGISTRO = registro
    v.buscar_texto = buscar_quebrado
    _codigo = v.main([])
    v.REGISTRO = _salvo_registro
    v.buscar_texto = _salvo_buscar
    ok("a linha de comando devolve 3 quando não mede", _codigo == 3, _codigo)

# ------------------------------------------------------------------ quem usa este vigia
_pendencias = open(os.path.join(RAIZ, ".github/workflows/pendencias-do-dono.yml"),
                   encoding="utf-8").read()
ok("o relatório diário roda o vigia do PRANCHETA", "vigia-build-prancheta.py" in _pendencias)

print("\n%d/%d contratos do vigia do PRANCHETA passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
