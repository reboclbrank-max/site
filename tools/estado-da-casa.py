#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estado da casa em um bloco — o que o dono pergunta e o chat deveria responder.

POR QUE EXISTE (07/11/2026): as informações existiam espalhadas em seis JSON. Para responder
"como está?" era preciso abrir `youtube-publicados.json` (o que saiu), `capas-aplicadas.json`
(quantas capas), `fila-tarefas.json` (o que está na frente e há quanto tempo), `orquestrador.json`
(quantos pulsos) e o último ensaio das capas (quantos vídeos do canal estão sem capa). Número que
exige seis arquivos é número que ninguém lê — e foi assim que "3 descrições truncadas" e "fila
faminta" passaram dias sem ser vistos.

Este script não mede nada novo e não escreve nada: ele junta o que já está medido, com a data de
cada medida. Fonte que não existe é dita, não inventada.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(RAIZ, "posts")


def _ler(nome):
    try:
        with open(os.path.join(POSTS, nome), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _lista(dados, *chaves):
    if isinstance(dados, list):
        return dados
    if not isinstance(dados, dict):
        return []
    for chave in chaves:
        if isinstance(dados.get(chave), list):
            return dados[chave]
    return []


def _horas(quando, agora=None):
    import datetime
    if not quando:
        return None
    try:
        valor = datetime.datetime.fromisoformat(str(quando).replace("Z", "+00:00"))
    except ValueError:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=datetime.timezone.utc)
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    return round(max(0.0, (agora - valor).total_seconds() / 3600.0), 1)


def _corte(texto, limite=48):
    """Corta no fim de uma palavra. Título cortado no meio ("11 mudas plantadas, )") parece erro
    de leitura, e é o primeiro número que o dono vê."""
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return corte + "…"


def estado(agora=None):
    """Devolve um dicionário só com o que foi lido de arquivo — nada estimado."""
    publicados = _lista(_ler("youtube-publicados.json"), "publicados")
    capas = _lista(_ler("capas-aplicadas.json"), "aplicadas")
    fila = _lista(_ler("fila-tarefas.json"), "tarefas")
    capas_estado = _ler("capas-estado.json") or {}
    prancheta = _ler("prancheta-build.json") or {}
    orq = _ler("orquestrador.json") or {}

    pendentes = [t for t in fila if isinstance(t, dict) and t.get("estado") == "pendente"]
    por_tipo = {}
    for tarefa in pendentes:
        por_tipo[tarefa.get("tipo")] = por_tipo.get(tarefa.get("tipo"), 0) + 1
    mais_velha = None
    for tarefa in pendentes:
        horas = _horas(tarefa.get("criada"), agora)
        if horas is not None and (mais_velha is None or horas > mais_velha[1]):
            mais_velha = (tarefa.get("id"), horas)

    sem_capa = capas_estado.get("sem_capa")
    no_canal = capas_estado.get("no_canal")
    regua = _ler("placar-estado.json") or {}
    return {
        "regua_medida_em": regua.get("medido_em"),
        "regua_horas": _horas(regua.get("medido_em"), agora),
        "regua_dias_restantes": regua.get("dias_restantes"),
        "regua_prazo": regua.get("prazo"),
        "publicados": len(publicados),
        "ultimo_publicado": (publicados[0].get("id") if publicados else None),
        "ultimo_publicado_titulo": (publicados[0].get("titulo") if publicados else None),
        "capas_aplicadas": len(capas),
        "capas_no_canal": no_canal,
        "capas_sem_capa": sem_capa,
        "capas_medido_em": capas_estado.get("medido_em"),
        "capas_outros_jogos": capas_estado.get("outros_jogos"),
        "capas_da_casa": capas_estado.get("da_casa"),
        "capas_com_capa_no_canal": capas_estado.get("com_capa_no_canal"),
        "prancheta_build": prancheta.get("build_id"),
        "prancheta_medido_em": prancheta.get("medido_em"),
        "fila_pendentes": len(pendentes),
        "fila_por_tipo": por_tipo,
        "fila_mais_velha": mais_velha[0] if mais_velha else None,
        "fila_mais_velha_horas": mais_velha[1] if mais_velha else None,
        "fila_feitas": len([t for t in fila if isinstance(t, dict) and t.get("estado") == "feito"]),
        "pulsos": orq.get("pulsos"),
        "ultima_publicacao_do_pulso": orq.get("ultima_publicacao"),
        "ultima_medicao_do_pulso": orq.get("ultima_medicao"),
    }


def texto(dados=None):
    """O bloco que o dono lê — em linha, com o número na frente."""
    d = dados if isinstance(dados, dict) else estado()
    linhas = []

    linhas.append("Vídeos publicados: %d%s" % (
        d["publicados"],
        (" · último: %s (%s)" % (d["ultimo_publicado"], _corte(d["ultimo_publicado_titulo"])))
        if d["ultimo_publicado"] else ""))

    # SEM RAZÃO INVENTADA (07/11/2026): o canal tem 169 vídeos e só 51 têm capa da casa — os
    # outros 118 não são da casa e ficam fora por regra. "51 de 169" faria parecer descuido e
    # "169 de 169" seria mentira. O bloco diz os três números com nome: aplicadas, tamanho do
    # canal e quantos DA CASA estão sem capa.
    linha = "Capas da casa: %d aplicada(s)" % d["capas_aplicadas"]
    if d["capas_no_canal"]:
        # "DE OUTROS JOGOS" SAIU DA FRASE (07/11/2026): o classificador olha o TÍTULO, e 40 dos 51
        # vídeos pintados têm título genérico ("Como funciona: as plantações crescem..."). Chamar
        # 158 de "de outros jogos" seria palpite com cara de medida. O que é medido fica: tamanho
        # do canal, quantos têm capa da casa e quantos citam jogo da casa no título.
        linha += " · canal com %d vídeos" % d["capas_no_canal"]
        if d.get("capas_com_capa_no_canal"):
            linha += ", %d com capa da casa" % d["capas_com_capa_no_canal"]
        if d.get("capas_da_casa") is not None:
            linha += ", %d citam jogo da casa no título" % d["capas_da_casa"]
    if d["capas_sem_capa"] == 0:
        linha += " · nenhum da casa sem capa"
    elif d["capas_sem_capa"]:
        linha += " · %d da casa sem capa" % d["capas_sem_capa"]
    if d.get("capas_medido_em"):
        linha += " (medido em %s)" % str(d["capas_medido_em"])[:16]
    linhas.append(linha)

    # O PRANCHETA É O ÚNICO JOGO QUE NÃO SOBE POR AQUI (07/11/2026): o build dele vive no itch e
    # o dono publica na mão. Sem esta linha, "atualizei o PRANCHETA" e "não atualizei" eram a
    # mesma coisa para todo mundo da casa. O vigia lê o id do build servido e diz qual é.
    if d.get("prancheta_build"):
        linha = "PRANCHETA no itch: build %s" % d["prancheta_build"]
        if d.get("prancheta_medido_em"):
            linha += " (a casa viu em %s)" % str(d["prancheta_medido_em"])[:16]
        linha += " · esse build não sobe por aqui: o dono publica no itch"
        linhas.append(linha)

    if d["fila_pendentes"]:
        tipos = ", ".join("%s %d" % (tipo, qtd) for tipo, qtd in sorted(d["fila_por_tipo"].items()))
        velha = ""
        if d["fila_mais_velha"]:
            velha = " · a mais velha: %s há %s h" % (d["fila_mais_velha"], d["fila_mais_velha_horas"])
        linhas.append("Fila: %d pendente(s) (%s)%s · %d feita(s)" % (
            d["fila_pendentes"], tipos, velha, d["fila_feitas"]))
    else:
        linhas.append("Fila: vazia · %d tarefa(s) já feita(s)" % d["fila_feitas"])

    # A RÉGUA VELHA APARECE (07/11/2026): a régua de metas ficou 4 dias parada e o pulso decidia
    # com números de 03/11. Um relatório que mostra a decisão e esconde a idade do número que a
    # sustenta é o mesmo defeito com outra roupa.
    if d.get("regua_horas") is not None:
        horas = d["regua_horas"]
        vencida = " · VENCIDA (medir de novo)" if horas > 24 else ""
        linha = "Régua de metas: medida há %.1f h · prazo %s · %s dia(s) restante(s)%s" % (
            horas, d.get("regua_prazo") or "—",
            "?" if d.get("regua_dias_restantes") is None else d["regua_dias_restantes"], vencida)
        linhas.append(linha)

    pulsos = d.get("pulsos")
    if pulsos is not None:
        partes = ["Pulsos: %s" % pulsos]
        if d.get("ultima_publicacao_do_pulso"):
            partes.append("última publicação %s" % d["ultima_publicacao_do_pulso"])
        if d.get("ultima_medicao_do_pulso"):
            partes.append("última medição %s" % d["ultima_medicao_do_pulso"])
        linhas.append(" · ".join(partes))

    faltando = [nome for nome, chave in (("vídeos publicados", "publicados"),
                                         ("capas", "capas_aplicadas"),
                                         ("fila", "fila_pendentes"))
                if d.get(chave) is None]
    if faltando:
        linhas.append("Sem registro para: " + ", ".join(faltando) + " (nada foi inventado)")
    return "\n".join(linhas)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="estado da casa em um bloco")
    ap.add_argument("--json", action="store_true", help="imprime os dados crus")
    a = ap.parse_args(argv[1:])
    dados = estado()
    if a.json:
        print(json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=True))
    else:
        print(texto(dados))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
