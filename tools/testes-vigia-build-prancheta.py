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

    # ------------------------------------------------------------------ build novo vira FATO
    # (não vira tarefa de publicar: o pulso roda o postador sem argumento, e o motivo da tarefa
    # não chega ao texto — o que o redator lê de verdade são os fatos)
    fatos = os.path.join(tmp, "fatos.json")
    with open(fatos, "w", encoding="utf-8") as f:
        json.dump({"fatos": [{"id": "prancheta-trocas", "assunto": "prancheta",
                              "afirmacao": "até 5 trocas por partida"}]}, f)
    _fato = v.registrar_fato("30000000", "20000000", caminho=fatos, quando="2026-11-07")
    ok("build novo entra como fato do repertório", _fato and _fato["id"] == "prancheta-build-30000000",
       _fato)
    ok("o fato é do assunto prancheta", _fato and _fato["assunto"] == "prancheta", _fato)
    ok("a afirmação diz o build novo e o antigo",
       _fato and "30000000" in _fato["afirmacao"] and "20000000" in _fato["afirmacao"],
       _fato and _fato["afirmacao"])
    ok("a afirmação carrega a data", _fato and "2026-11-07" in _fato["afirmacao"], _fato)
    ok("o fato diz de onde foi medido", _fato and _fato["origem"] == "posts/prancheta-build.json",
       _fato)
    ok("o fato não é repetível (versão é evento, não característica)",
       _fato and _fato["repetivel"] is False and _fato.get("usa_uma_vez") is True, _fato)
    ok("o fato vence (atualização não é verdade eterna)",
       _fato and _fato.get("validade_dias") == 45, _fato)
    ok("a classe do fato é uma das que o redator usa",
       _fato and _fato["classe"] in ("mecanica", "numero", "bastidor", "cultura",
                                     "disponibilidade", "canal", "marco"), _fato and _fato["classe"])
    ok("fato tem afirmacao e assunto, como o redator exige",
       _fato and bool(_fato.get("afirmacao")) and bool(_fato.get("assunto")))
    ok("o mesmo build não vira fato duas vezes",
       v.registrar_fato("30000000", "20000000", caminho=fatos) is None)
    _fatos_gravados = json.load(open(fatos, encoding="utf-8"))["fatos"]
    ok("os fatos antigos não são tocados", _fatos_gravados[0]["id"] == "prancheta-trocas",
       _fatos_gravados[0])
    ok("a lista cresceu em um", len(_fatos_gravados) == 2, len(_fatos_gravados))

    # ------------------------------------------------------------------ main de ponta a ponta
    _salvo = (v.REGISTRO, v.medir, v.registrar_fato, v.FATOS)
    _chamadas = []
    v.REGISTRO = registro
    v.FATOS = fatos
    v.registrar_fato = lambda *a, **k: _chamadas.append(a) or None
    v.medir = lambda *a, **k: ("igual", "build igual", "20000000")
    v.main(["--gravar"])
    ok("build igual não vira fato", _chamadas == [], _chamadas)
    v.medir = lambda *a, **k: ("não medido", "sem rede", None)
    v.main(["--gravar"])
    ok("sem medida não vira fato", _chamadas == [], _chamadas)
    v.medir = lambda *a, **k: ("mudou", "build novo", "60000000")
    v.main(["--gravar"])
    ok("build diferente vira UM fato", len(_chamadas) == 1, _chamadas)
    ok("o fato recebe o build antigo como referência",
       _chamadas and _chamadas[0][1] == "20000000", _chamadas)
    v.REGISTRO, v.medir, v.registrar_fato, v.FATOS = _salvo

# ------------------------------------------------------------------ o fato é utilizável
# O que vale não é o fato existir no arquivo: é o redator conseguir montar pauta com ele. Se a
# classe não estiver entre as dos ângulos, o fato vira arquivo morto com cara de conteúdo.
with tempfile.TemporaryDirectory() as tmp:
    fatos = os.path.join(tmp, "fatos.json")
    import shutil
    shutil.copy(os.path.join(RAIZ, "posts", "fatos.json"), fatos)
    _fato = v.registrar_fato("19604665", "111111", caminho=fatos, quando="2026-11-07")
    spec_red = importlib.util.spec_from_file_location("redator", os.path.join(RAIZ, "tools", "redator.py"))
    red = importlib.util.module_from_spec(spec_red)
    spec_red.loader.exec_module(red)
    _fatos_lidos = red.carregar_fatos(fatos)
    ok("o redator lê o fato novo", any(f["id"] == _fato["id"] for f in _fatos_lidos))
    _vivos = red.fatos_vivos(_fatos_lidos, {"fatos_de_uma_vez": []})
    ok("o fato novo conta como vivo (não vencido, não gasto)",
       any(f["id"] == _fato["id"] for f in _vivos))
    import datetime as _dt
    _pautas = red.pautas_possiveis(_vivos, {"usos": []}, hoje=_dt.date(2026, 11, 7))
    _com_fato = [p for p in _pautas if _fato["id"] in p["fatos"]]
    ok("o redator monta pauta com o fato novo", bool(_com_fato),
       [p["angulo"] for p in _pautas][:5])
    ok("a pauta do fato novo é do assunto prancheta",
       _com_fato and all(p["assunto"] == "prancheta" for p in _com_fato), _com_fato)

# ------------------------------------------------------------------ quem usa este vigia
_pendencias = open(os.path.join(RAIZ, ".github/workflows/pendencias-do-dono.yml"),
                   encoding="utf-8").read()
ok("o relatório diário roda o vigia do PRANCHETA", "vigia-build-prancheta.py" in _pendencias)

print("\n%d/%d contratos do vigia do PRANCHETA passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
