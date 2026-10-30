#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Livro de decisões da casa: o que o robô decide, o que ele RECUSA decidir e o que ele não sabe.

POR QUE EXISTE (30/10/2026): o dono perguntou se a autonomia tem "o controle e a sabedoria das
decisões". Controle já existia (o ciclo roda, mede, corrige). Sabedoria não é decidir mais: é
decidir com o número na mão e **saber onde parar**. Este arquivo é a prova auditável disso.

Três listas, e nenhuma delas é opinativa:

  decididas    — cada decisão traz o NÚMERO que a sustenta e o arquivo de onde ele veio;
  recusadas    — decisões que o robô **não toma** (e por quê: ruído, amostra pequena, ou porque
                 é escolha de vida do dono, não conta de máquina);
  ignorancias  — perguntas que a casa NÃO sabe responder com o que mede. Aparecem nomeadas,
                 porque ignorância declarada é melhor que palpite com cara de dado.

Regra de honestidade embutida: se a fonte não existir ou não tiver número, o item NÃO vira
decisão — ele desce para "sem medida". Nada aqui é escrito à mão; tudo é lido do repositório.
"""
import datetime
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANO = os.path.join(RAIZ, "posts", "plano-do-dia.json")
APRENDIZADO = os.path.join(RAIZ, "posts", "aprendizado.json")
PLACAR = os.path.join(RAIZ, "posts", "placar-metas.md")
NUNCA = os.path.join(RAIZ, "posts", "nunca-publicar.json")
SAIDA_JSON = os.path.join(RAIZ, "posts", "decisoes.json")
SAIDA_MD = os.path.join(RAIZ, "posts", "decisoes.md")


def ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _tem_numero(texto):
    return bool(re.search(r"\d", str(texto or "")))


def tabela_placar():
    """Linhas da tabela de posts/placar-metas.md (a régua de metas escrita pelo metricas.py)."""
    linhas = []
    for linha in ler(PLACAR).splitlines():
        if not linha.lstrip().startswith("|"):
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(celulas) < 7 or celulas[0].lower() == "meta" or set(celulas[0]) <= {"-"}:
            continue
        linhas.append({"meta": celulas[0], "alvo": celulas[1], "observado": celulas[2],
                       "falta": celulas[3], "por_dia": celulas[4], "status": celulas[5]})
    return linhas


def numero_ou_none(texto):
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def decididas():
    itens = []

    plano = ler_json(PLANO)
    risco = plano.get("meta_em_risco") or {}
    if risco.get("meta") and _tem_numero(risco.get("falta")):
        itens.append({
            "decisao": "priorizar a meta mais atrasada antes de qualquer vaidade",
            "numero": "%s — faltam %g (%g por dia até o prazo)"
                      % (risco["meta"], float(risco.get("falta")), float(risco.get("por_dia") or 0)),
            "regra": "ranking de risco do plano do dia (falta ÷ dias restantes)",
            "fonte": "posts/plano-do-dia.json",
        })

    evitar = (plano.get("formatos_a_evitar") or [])
    if evitar and _tem_numero(evitar[0].get("pct")):
        alvo = evitar[0]
        itens.append({
            "decisao": "parar de insistir no formato que mais devolve zero",
            "numero": "%s: %s%% de zeros em %s tentativas"
                      % (alvo.get("formato"), alvo.get("pct"), alvo.get("total")),
            "regra": "zero medido repetido é recusa, não azar",
            "fonte": "posts/plano-do-dia.json",
        })

    apr = ler_json(APRENDIZADO)
    if apr.get("decisao") == "trocar" and apr.get("melhor_hora") is not None:
        itens.append({
            "decisao": "mudar o horário de publicação",
            "numero": "melhor %02dh — %s" % (int(apr["melhor_hora"]), apr.get("motivo", "")),
            "regra": "só troca com amostra ≥ 30 por hora e ganho maior que um desvio padrão",
            "fonte": "posts/aprendizado.json",
        })

    for linha in tabela_placar():
        if linha["status"] == "ATINGIDO":
            itens.append({
                "decisao": "meta batida — parar de empurrar e só manter",
                "numero": "%s: %s medido(s) contra alvo %s" % (linha["meta"], linha["observado"], linha["alvo"]),
                "regra": "quem bateu a meta não continua gastando esforço nela",
                "fonte": "posts/placar-metas.md",
            })
    return itens


def recusadas():
    itens = []

    apr = ler_json(APRENDIZADO)
    if apr and apr.get("decisao") == "manter" and apr.get("motivo"):
        det = apr.get("detalhe") or {}
        itens.append({
            "decisao": "trocar o horário de publicação",
            "porque": "recusada por falta de prova: %s" % apr["motivo"],
            "numero": "amostra total %s · mínimo por hora %s · horas elegíveis %s"
                      % (det.get("amostra_total", "—"), det.get("amostra_minima", "—"),
                         det.get("elegiveis", "—")),
            "fonte": "posts/aprendizado.json",
        })
    elif not apr:
        itens.append({
            "decisao": "trocar o horário de publicação",
            "porque": "recusada por falta de medida: não existe relatório de horário lido ainda",
            "numero": "nenhuma amostra registrada",
            "fonte": "posts/aprendizado.json (ausente)",
        })

    # O placar já escreve, com todas as letras, onde a conta acaba e a escolha começa.
    texto = ler(PLACAR)
    achado = re.search(r"Sem retorno em (\d+) dias:\*\*(.+?)\.\s", texto, re.S)
    if achado:
        itens.append({
            "decisao": "manter ou aposentar um canal que não devolve número",
            "porque": "é escolha de vida do projeto, não conta de máquina — o robô entrega o "
                      "número e não finge que decide",
            "numero": "sem retorno em %s dias: %s" % (achado.group(1),
                                                     re.sub(r"\s+", " ", achado.group(2))[:180]),
            "fonte": "posts/placar-metas.md",
        })

    nunca = ler_json(NUNCA)
    for nome in nunca.get("nunca_publicar") or []:
        itens.append({
            "decisao": "publicar %s" % nome,
            "porque": "vetado pelo dono (%s) — a casa herda a regra e não a rediscute"
                      % nunca.get("motivo", "pedido registrado"),
            "numero": "pedido em %s" % nunca.get("pedido_em", "—"),
            "fonte": "posts/nunca-publicar.json",
        })
    return itens


def ignorancias():
    itens = []
    for linha in tabela_placar():
        if linha["status"] == "SEM_LEITURA" or linha["observado"] == "NAO_OBSERVAVEL":
            itens.append({
                "pergunta": "quanto a meta \"%s\" já andou?" % linha["meta"],
                "porque": "o canal não publica esse número (nem API, nem página pública) — "
                          "ausência de leitura não é zero",
                "fonte": "posts/placar-metas.md",
            })
    itens.append({
        "pergunta": "o texto do post é bom?",
        "porque": "engajamento mede reação, não julgamento. Um post pode ter número e continuar "
                  "sem graça — isso quem sabe é quem lê, não o log",
        "fonte": "regra da casa (nenhum arquivo mede gosto)",
    })
    itens.append({
        "pergunta": "vale a pena continuar existindo com esse público?",
        "porque": "nenhuma métrica do repositório responde isso; o robô para na borda do dado",
        "fonte": "regra da casa",
    })
    return itens


def livro():
    d, r, i = decididas(), recusadas(), ignorancias()
    return {
        "quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_lei": "decidir com número na mão, declarar a recusa e nomear a ignorância. "
                "Decisão sem número não entra.",
        "decididas": d,
        "recusadas": r,
        "ignorancias": i,
        "contagem": {"decididas": len(d), "recusadas": len(r), "ignorancias": len(i)},
    }


def markdown(livro_dados):
    linhas = ["# Livro de decisões da casa", "",
              "Gerado em %s a partir dos próprios registros do repositório." % livro_dados["quando"],
              "", "> %s" % livro_dados["_lei"], "",
              "## O que a casa decide sozinha (%d)" % livro_dados["contagem"]["decididas"], "",
              "| decisão | número que sustenta | regra | fonte |", "| --- | --- | --- | --- |"]
    for it in livro_dados["decididas"]:
        linhas.append("| %s | %s | %s | `%s` |" % (it["decisao"], it["numero"], it["regra"], it["fonte"]))
    linhas += ["", "## O que a casa se recusa a decidir (%d)" % livro_dados["contagem"]["recusadas"], "",
               "| decisão | por que não | número | fonte |", "| --- | --- | --- | --- |"]
    for it in livro_dados["recusadas"]:
        linhas.append("| %s | %s | %s | `%s` |" % (it["decisao"], it["porque"], it["numero"], it["fonte"]))
    linhas += ["", "## O que a casa não sabe (e diz) (%d)" % livro_dados["contagem"]["ignorancias"], "",
               "| pergunta | por que fica sem resposta | fonte |", "| --- | --- | --- |"]
    for it in livro_dados["ignorancias"]:
        linhas.append("| %s | %s | `%s` |" % (it["pergunta"], it["porque"], it["fonte"]))
    return "\n".join(linhas) + "\n"


def escrever(caminho, texto):
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(caminho + ".tmp", caminho)


def main(argv):
    dados = livro()
    escrever(SAIDA_JSON, json.dumps(dados, ensure_ascii=False, indent=1) + "\n")
    escrever(SAIDA_MD, markdown(dados))
    c = dados["contagem"]
    print("decisões: %d decididas · %d recusadas · %d ignorâncias declaradas"
          % (c["decididas"], c["recusadas"], c["ignorancias"]))
    print("gravado em posts/decisoes.json e posts/decisoes.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
