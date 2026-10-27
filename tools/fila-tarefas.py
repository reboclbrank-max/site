#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fila de tarefas da casa — o que faltava para o pulso não recomeçar do zero.

Problema que resolve: o orquestrador decidia a cada pulso, mas não tinha *trabalho
pendente*. Se uma publicação falhasse, ela simplesmente não existia mais; e não havia
como saber o que estava na frente da fila.

Agora: as tarefas são DADOS (`posts/fila-tarefas.json`), com prioridade, tentativas e
resultado. O pulso pega a de maior prioridade que pode rodar, marca, e devolve. Falha
não desaparece: ela volta com tentativas+1 até o limite (3), depois fica `falhou` com o
motivo — visível, não silencioso.

Regra de ouro: **uma tarefa por pulso**. Duas tarefas no mesmo pulso é como a casa passou
a postar duas vezes no mesmo minuto.
"""
import datetime
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO = os.path.join(RAIZ, "posts", "fila-tarefas.json")
MAX_TENTATIVAS = 3

PRIORIDADES = {
    "medir": 90,        # medir sempre está na frente: sem número, o resto é chute
    "responder": 80,    # responder comentário vale mais que postar
    "publicar": 60,
    "pesquisar": 40,
    "aprender": 30,
}


def agora_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def vazia():
    return {"_o_que_e": "fila de tarefas da casa: prioridade, tentativas e resultado",
            "versao": 1, "tarefas": []}


def carregar(caminho=ARQUIVO):
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        return vazia()
    base = vazia()
    base.update(dados or {})
    base["tarefas"] = base.get("tarefas") or []
    return base


def gravar(dados, caminho=ARQUIVO):
    pasta = os.path.dirname(caminho)
    if pasta and not os.path.isdir(pasta):
        os.makedirs(pasta, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")


def adicionar(dados, tipo, motivo="", quando=None, chave=None):
    """Cria tarefa se não existir uma igual pendente (chave evita duplicata)."""
    if chave:
        for t in dados["tarefas"]:
            if t.get("chave") == chave and t.get("estado") in ("pendente", "executando"):
                return None
    tarefa = {
        "id": "%s-%s" % (tipo, (quando or agora_iso()).replace(":", "").replace("-", "")),
        "tipo": tipo,
        "prioridade": PRIORIDADES.get(tipo, 10),
        "estado": "pendente",
        "tentativas": 0,
        "criada": quando or agora_iso(),
        "executada": None,
        "resultado": None,
        "motivo": motivo,
        "chave": chave,
    }
    dados["tarefas"].append(tarefa)
    return tarefa


def proxima(dados):
    """A próxima tarefa executável: maior prioridade, mais antiga primeiro."""
    candidatas = [t for t in dados["tarefas"]
                  if t.get("estado") == "pendente" and int(t.get("tentativas", 0)) < MAX_TENTATIVAS]
    candidatas.sort(key=lambda t: (-int(t.get("prioridade", 0)), t.get("criada") or ""))
    return candidatas[0] if candidatas else None


def pegar(dados, tarefa=None):
    tarefa = tarefa or proxima(dados)
    if not tarefa:
        return None
    tarefa["estado"] = "executando"
    tarefa["executada"] = agora_iso()
    return tarefa


def concluir(dados, tarefa, ok, resultado=""):
    """Fecha a tarefa. Falha volta para a fila até MAX_TENTATIVAS; depois fica `falhou`."""
    tarefa["resultado"] = (resultado or "")[:400]
    if ok:
        tarefa["estado"] = "feito"
        return "feito"
    tarefa["tentativas"] = int(tarefa.get("tentativas", 0)) + 1
    if tarefa["tentativas"] >= MAX_TENTATIVAS:
        tarefa["estado"] = "falhou"
        tarefa["resultado"] = ("desistiu após %d tentativas: " % tarefa["tentativas"]) + tarefa["resultado"]
        return "falhou"
    tarefa["estado"] = "pendente"
    return "nova tentativa (%d/%d)" % (tarefa["tentativas"], MAX_TENTATIVAS)


def semear(dados, plano=None, agora=None):
    """Enche a fila a partir do plano do dia. Idempotente: não duplica o que já existe."""
    criadas = []
    dia = (agora or agora_iso())[:10]
    if plano:
        tema = (plano.get("tema_do_dia") or {}).get("texto")
        if tema:
            criadas.append(adicionar(dados, "publicar", motivo=tema[:80], chave="publicar-" + dia))
        risco = plano.get("meta_em_risco") or {}
        if risco.get("meta"):
            criadas.append(adicionar(dados, "pesquisar", motivo="meta em risco: " + str(risco["meta"]),
                                     chave="pesquisar-" + dia))
    criadas.append(adicionar(dados, "medir", motivo="placar e desempenho", chave="medir-" + dia))
    criadas.append(adicionar(dados, "aprender", motivo="horário: só com prova", chave="aprender-" + dia))
    return [c for c in criadas if c]


def resumo(dados):
    contagem = {}
    for t in dados["tarefas"]:
        contagem[t.get("estado", "?")] = contagem.get(t.get("estado", "?"), 0) + 1
    return contagem


def main(argv):
    dados = carregar()
    if "--semear" in argv:
        plano = None
        try:
            with open(os.path.join(RAIZ, "posts", "plano-do-dia.json"), encoding="utf-8") as f:
                plano = json.load(f)
        except Exception:
            plano = None
        criadas = semear(dados, plano)
        gravar(dados)
        print("tarefas criadas: %d" % len(criadas))
        for t in criadas:
            print("  + [%d] %s — %s" % (t["prioridade"], t["tipo"], t["motivo"]))
        return 0
    print("fila:", resumo(dados))
    nxt = proxima(dados)
    print("próxima:", (nxt or {}).get("tipo", "nada na fila"), "—", (nxt or {}).get("motivo", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
