#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria de inteligência: em quais passos a casa ADAPTA e em quais ela só repete ritual.

POR QUE EXISTE (30/10/2026): o dono perguntou se a casa vai agir "de forma inteligente e sábia".
Inteligência, aqui, não é adjetivo: é comportamento que MUDA quando o resultado muda. Este
script mede isso no próprio diário (`posts/log.md`), passo por passo:

  adaptativo — o resultado varia entre ciclos (há leitura real alimentando decisão);
  ritual     — o resultado é sempre idêntico: nada entra, nada é aprendido, só se repete;
  cego       — sempre indisponível/falta segredo: não é ritual, é falta de olho.

E mede também o texto publicado: quantas variações distintas saíram nos últimos ciclos. Repetir
a mesma frase 20 vezes com resultado "✅" é o exemplo mais claro de ritual com cara de sucesso.

Nada é inventado: se o log não tem a linha, o passo aparece como "sem registro".
"""
import datetime
import importlib.util
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(RAIZ, "posts", "log.md")
SAIDA_MD = os.path.join(RAIZ, "posts", "auditoria-inteligencia.md")
SAIDA_JSON = os.path.join(RAIZ, "posts", "auditoria-inteligencia.json")
CICLOS = 40          # janela: os últimos 40 ciclos com passos detalhados
MIN_AMOSTRA = 5      # menos que isso não se classifica nada


def carregar_painel():
    caminho = os.path.join(RAIZ, "tools", "painel-marketing.py")
    spec = importlib.util.spec_from_file_location("painel_marketing", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def textos(caminho=LOG):
    """O texto publicado em cada ciclo (a linha '> ' do diário), do mais novo ao mais antigo."""
    try:
        with open(caminho, encoding="utf-8") as f:
            bruto = f.read()
    except OSError:
        return []
    saida = []
    for bloco in re.split(r"\n## ", bruto):
        achado = re.search(r"^> (.+)$", bloco, re.M)
        if achado:
            saida.append(achado.group(1).strip())
    return saida


def pares(caminho=LOG):
    """[(quando, texto publicado)] em ordem cronológica — para medir repetição por data."""
    try:
        with open(caminho, encoding="utf-8") as f:
            bruto = f.read()
    except OSError:
        return []
    saida = []
    for bloco in re.split(r"\n## ", bruto):
        quando = re.match(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2})", bloco.strip())
        achado = re.search(r"^> (.+)$", bloco, re.M)
        if quando and achado:
            saida.append((quando.group(1), achado.group(1).strip()))
    return saida


def repeticao(pares_lista):
    """(ciclos, repetidos) — quantos textos já tinham sido publicados antes, contando em ordem."""
    vistos = set()
    repetidos = 0
    for _quando, texto in pares_lista:
        chave = " ".join(re.sub(r"[^0-9a-z]+", " ", texto.lower()).split())[:60]
        if chave and chave in vistos:
            repetidos += 1
        vistos.add(chave)
    return len(pares_lista), repetidos


def normalizar(resultado):
    """Reduz o resultado à categoria que interessa: ok / cego / espera / outro."""
    r = (resultado or "").strip()
    if not r:
        return "sem registro"
    if "INDISPONIVEL" in r or "falta o segredo" in r or "ausente" in r or "sem chave" in r:
        return "cego"
    if r.startswith("➖") or "fora da janela" in r or "cadencia" in r or "sai no" in r:
        return "espera"
    if "✅" in r:
        return "ok"
    return "outro"


# "✅" que não fez nada de novo: já registrado hoje, cadência cumprida, nada a fazer.
# É a classe mais perigosa, porque parece trabalho: verde no log, zero mudança no mundo.
SINAIS_DE_NADA = ("ja registrad", "já registrad", "ja cumprida", "já cumprida", "sem link de",
                  "1 ciclo por dia", "1 por dia", "nada a fazer", "sem novidade", "ja registrado")


def confessa(historico):
    """Quantos resultados do passo confessam, no próprio texto, que nada de novo foi feito."""
    return sum(1 for r in historico
               if any(s in (r or "").lower() for s in SINAIS_DE_NADA))


def fachada(historico):
    """True se TODOS os resultados são ✅ que confessam não ter feito nada de novo."""
    if not historico:
        return False
    return confessa(historico) == len(historico) and all("✅" in (r or "") for r in historico)


def classificar(historico):
    """Classe de um passo a partir dos resultados que ele devolveu ciclo após ciclo.

    Critério: conta RESULTADOS DISTINTOS. Um só = ritual (nada entra, nada muda); dois =
    binário (liga/desliga); três ou mais = há leitura alimentando decisão (adaptativo).
    Sempre indisponível não é ritual, é cego. E ✅ que confessa "já registrado" é fachada.
    """
    n = len(historico)
    if n < MIN_AMOSTRA:
        return "sem amostra", {"n": n}
    categorias = [normalizar(r) for r in historico]
    distintas_cat = set(categorias)
    distintas_bruto = set((r or "").strip() for r in historico)
    _confessa = confessa(historico)
    if distintas_cat == {"cego"}:
        return "cego", {"n": n, "categorias": sorted(distintas_cat)}
    if fachada(historico):
        return "fachada", {"n": n, "categorias": sorted(distintas_cat), "confessa": _confessa}
    if len(distintas_bruto) == 1:
        return "ritual", {"n": n, "categorias": sorted(distintas_cat), "confessa": _confessa}
    if len(distintas_bruto) == 2:
        return "binário", {"n": n, "categorias": sorted(distintas_cat), "confessa": _confessa}
    return "adaptativo", {"n": n, "categorias": sorted(distintas_cat),
                          "resultados_distintos": len(distintas_bruto), "confessa": _confessa}


def auditar(caminho=LOG, janela=CICLOS):
    painel = carregar_painel()
    try:
        with open(caminho, encoding="utf-8") as f:
            bruto = f.read()
    except OSError:
        return {"quando": None, "passos": [], "texto": {}, "erro": "log ausente"}
    ciclos = painel.ciclos_do_texto(bruto)[:janela]
    ciclos = list(reversed(ciclos))  # do mais antigo ao mais novo, para ler a evolução

    passos = {}
    for ciclo in ciclos:
        for nome, resultado in ciclo["linhas"].items():
            passos.setdefault(nome, []).append(resultado)

    tabela = []
    for nome, hist in passos.items():
        classe, detalhe = classificar(hist)
        tabela.append({"passo": nome, "classe": classe, "detalhe": detalhe,
                       "ultimo": hist[-1] if hist else ""})
    ordem = {"fachada": 0, "ritual": 1, "cego": 2, "binário": 3, "sem amostra": 4, "adaptativo": 5}
    tabela.sort(key=lambda t: (ordem.get(t["classe"], 9), -t["detalhe"].get("n", 0)))

    lista_textos = textos(caminho)
    recentes = len(ciclos)
    # o arquivo é cronológico: os mais recentes são o FIM da lista
    recorte = lista_textos[-recentes:] if recentes else []
    distintos = len(set(recorte)) if recorte else 0
    pct_repeticao = round(100.0 * (1 - distintos / recentes), 1) if recentes else 0.0

    conta = {}
    for linha in tabela:
        conta[linha["classe"]] = conta.get(linha["classe"], 0) + 1
    # Depois do conserto de dedupe de 26/10, a repetição tem de ser medida à parte:
    # misturar as duas épocas esconde (ou inventa) melhora.
    todos = pares(caminho)
    desde = [x for x in todos if x[0][6:10] + x[0][3:5] + x[0][:2] >= "20261026"]
    n_desde, rep_desde = repeticao(desde)
    return {
        "quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repeticao_desde_o_conserto": {
            "corte": "26/10/2026", "ciclos": n_desde, "repetidos": rep_desde,
            "pct": round(100.0 * rep_desde / n_desde, 1) if n_desde else 0.0,
        },
        "janela": recentes,
        "passos": tabela,
        "contagem": conta,
        "texto": {"ciclos": recentes, "distintos": distintos, "repeticao_pct": pct_repeticao},
        "_lei": "inteligência se mede por mudança de comportamento; passo que nunca muda "
                "não é inteligente, é ritual — e ritual com '✅' é o mais enganoso de todos.",
    }


def markdown(dados):
    j = dados.get("janela", 0)
    c = dados.get("contagem", {})
    t = dados.get("texto", {})
    linhas = [
        "# Onde a casa pensa e onde ela repete", "",
        "Gerado em %s sobre os últimos **%d ciclos** do diário (`posts/log.md`)." % (dados.get("quando"), j),
        "", "> %s" % dados["_lei"], "",
        "## Resumo", "",
        "| classe | passos | o que significa |", "| --- | --- | --- |",
        "| adaptativo | %d | o resultado varia: há leitura alimentando decisão |" % c.get("adaptativo", 0),
        "| binário | %d | liga/desliga — varia pouco, mas varia |" % c.get("binário", 0),
        "| fachada | %d | diz ✅ todo ciclo, mas o próprio texto confessa que nada de novo foi feito |"
        % c.get("fachada", 0),
        "| ritual | %d | sempre o mesmo resultado: nada entra, nada se aprende |" % c.get("ritual", 0),
        "| cego | %d | sempre indisponível: falta olho, não falta vontade |" % c.get("cego", 0),
        "| sem amostra | %d | apareceu pouco na janela |" % c.get("sem amostra", 0),
        "",
        "**Texto publicado:** %d ciclos, **%d textos distintos** — repetição de %.1f%% na janela."
        % (t.get("ciclos", 0), t.get("distintos", 0), t.get("repeticao_pct", 0.0)),
        "",
        "**Desde o conserto de dedupe (%s):** %d ciclos, %d repetidos — **%.1f%%**."
        % (dados.get("repeticao_desde_o_conserto", {}).get("corte", "?"),
           dados.get("repeticao_desde_o_conserto", {}).get("ciclos", 0),
           dados.get("repeticao_desde_o_conserto", {}).get("repetidos", 0),
           dados.get("repeticao_desde_o_conserto", {}).get("pct", 0.0)),
        "",
        "## Passo por passo", "",
        "| passo | classe | ciclos na janela | confessa 'nada de novo' | último resultado |",
        "| --- | --- | --- | --- | --- |",
    ]
    for linha in dados.get("passos", []):
        ultimo = (linha.get("ultimo") or "").replace("|", "/")[:90]
        conf = linha["detalhe"].get("confessa", 0)
        n = linha["detalhe"].get("n", 0)
        linhas.append("| %s | **%s** | %s | %s | %s |"
                      % (linha["passo"], linha["classe"], n,
                         ("%d/%d" % (conf, n)) if conf else "—", ultimo))
    return "\n".join(linhas) + "\n"


def escrever(caminho, texto):
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(caminho + ".tmp", caminho)


def main(argv):
    dados = auditar()
    escrever(SAIDA_JSON, json.dumps(dados, ensure_ascii=False, indent=1) + "\n")
    escrever(SAIDA_MD, markdown(dados))
    c = dados.get("contagem", {})
    print("auditoria: %d adaptativos · %d fachada · %d ritual · %d cegos · %d sem amostra "
          "(janela de %d ciclos)"
          % (c.get("adaptativo", 0), c.get("fachada", 0), c.get("ritual", 0), c.get("cego", 0),
             c.get("sem amostra", 0), dados.get("janela", 0)))
    print("texto: %d ciclos, %d distintos (repetição %.1f%%)"
          % (dados["texto"]["ciclos"], dados["texto"]["distintos"], dados["texto"]["repeticao_pct"]))
    r = dados["repeticao_desde_o_conserto"]
    print("desde o conserto (%s): %d ciclos, %d repetidos (%.1f%%)"
          % (r["corte"], r["ciclos"], r["repetidos"], r["pct"]))
    print("gravado em posts/auditoria-inteligencia.json e .md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
