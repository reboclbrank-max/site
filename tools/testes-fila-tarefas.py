#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da fila de tarefas: não perde escrita, não duplica, não trava.

Tudo com arquivos de amostra em pasta temporária — nenhum contrato mexe na base da casa.
"""
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("fila", os.path.join(RAIZ, "tools", "fila-tarefas.py"))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

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
    with open(destino, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, ensure_ascii=False, indent=1)
        fp.write("\n")


# ------------------------------------------------------------------ carregar / gravar
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json",
            {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    ok("carregar lê o arquivo existente", dados["versao"] == 1 and dados["tarefas"] == [],
       dados)
    sucesso_gravar, motivo = f.gravar(dados, caminho)
    ok("gravar escreve o arquivo sem alterá-lo", sucesso_gravar, motivo)
    ok("arquivo nao mudado: arquivo_esta_inalterado True",
       f.arquivo_esta_inalterado(caminho))

with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json",
            {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    f.carregar(caminho)
    # outra "mão" grava o arquivo (simula race)
    with open(caminho, "w", encoding="utf-8") as fp:
        fp.write("lixo")
    sucesso_gravar, motivo = f.gravar({"tarefas": []}, caminho)
    ok("gravar recusa quando arquivo mudou (race detectado)", not sucesso_gravar,
       (sucesso_gravar, motivo))
    ok("motivo menciona hash", "hash" in motivo.lower(), motivo)

# ------------------------------------------------------------------ adicionar
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json", {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    t = f.adicionar(dados, "publicar", motivo="tema do dia", chave="publicar-2026-11-08")
    ok("adicionar cria tarefa com estado pendente",
       t is not None and t["estado"] == "pendente" and t["tipo"] == "publicar",
       t)
    ok("adicionar com chave duplica? não: segunda chamada retorna None",
       f.adicionar(dados, "publicar", motivo="x", chave="publicar-2026-11-08") is None)

# ------------------------------------------------------------------ teto por tipo
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json", {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    for i in range(3):
        f.adicionar(dados, "publicar", motivo="p%d" % i, chave="pub-%d" % i)
    # 4a deve ser recusada (teto = 3)
    r = f.adicionar(dados, "publicar", motivo="p3", chave="pub-3")
    ok("teto por tipo: 4a publicar e recusada", r is None)
    ok("recusada registrada em dados['recusadas']",
       len(dados.get("recusadas", [])) >= 1,
       dados.get("recusadas"))

# ------------------------------------------------------------------ proxima / selecionar_pulso
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json", {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    f.adicionar(dados, "aprender", motivo="a", chave="aprender-1")   # prio 30
    f.adicionar(dados, "medir", motivo="m", chave="medir-1")         # prio 90
    f.adicionar(dados, "publicar", motivo="p", chave="publicar-1")   # prio 60
    nxt = f.proxima(dados)
    ok("proxima escolhe a de maior prioridade efetiva (medir=90)",
       nxt["tipo"] == "medir", nxt)
    # selecionar_pulso pega uma de cada tipo
    escolhidas = f.selecionar_pulso(dados, tipos=("publicar", "medir"))
    ok("selecionar_pulso pega uma publicar e uma medir",
       len(escolhidas) == 2 and
       {t["tipo"] for t in escolhidas} == {"publicar", "medir"},
       [t["tipo"] for t in escolhidas])
    # ambas estao em executando
    ok("tarefas selecionadas estao em executando",
       all(t["estado"] == "executando" for t in escolhidas))

# ------------------------------------------------------------------ concluir
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json", {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    t = f.adicionar(dados, "medir", motivo="m", chave="medir-1")
    f.selecionar_pulso(dados, tipos=("medir",))
    resultado = f.concluir(dados, t, ok=True, resultado="mediu 40 downloads")
    ok("concluir com ok=True deixa estado feito",
       t["estado"] == "feito" and resultado == "feito",
       (t["estado"], resultado))

    # falha com tentativas < MAX volta para pendente
    t2 = f.adicionar(dados, "medir", motivo="m2", chave="medir-2")
    f.selecionar_pulso(dados, tipos=("medir",))
    r2 = f.concluir(dados, t2, ok=False, resultado="falhou de rede")
    ok("concluir com ok=False e tentativas=1 deixa pendente (nova tentativa)",
       t2["estado"] == "pendente" and t2["tentativas"] == 1,
       (t2["estado"], t2["tentativas"]))
    ok("motivo da nova tentativa menciona tentativas",
       "nova tentativa" in r2, r2)

    # falha com MAX_TENTATIVAS -> falhou
    t3 = f.adicionar(dados, "medir", motivo="m3", chave="medir-3")
    t3["tentativas"] = f.MAX_TENTATIVAS - 1  # ja esta na ultima
    f.selecionar_pulso(dados, tipos=("medir",))
    r3 = f.concluir(dados, t3, ok=False, resultado="desistiu")
    ok("concluir com ok=False no limite deixa falhou",
       t3["estado"] == "falhou", t3["estado"])

# ------------------------------------------------------------------ adiar
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json", {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    t = f.adicionar(dados, "publicar", motivo="fora da janela", chave="pub-janela")
    f.selecionar_pulso(dados, tipos=("publicar",))
    r = f.adiar(dados, t, motivo="janela fechada")
    ok("adiar deixa pendente e nao conta tentativa",
       t["estado"] == "pendente" and t["tentativas"] == 0,
       (t["estado"], t["tentativas"]))
    ok("adiar registra adiamentos=1", t.get("adiamentos") == 1, t.get("adiamentos"))

# ------------------------------------------------------------------ podar repetidas
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json", {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    # 3 medir pendentes (idempotente)
    for i in range(3):
        f.adicionar(dados, "medir", motivo="m%d" % i, chave="medir-%d" % i)
    podadas = f.podar_repetidas(dados)
    ok("podar_repetidas deixa apenas 1 medir pendente",
       len([t for t in dados["tarefas"] if t["tipo"] == "medir" and t["estado"] == "pendente"]) == 1,
       [t["estado"] for t in dados["tarefas"] if t["tipo"] == "medir"])
    ok("as podadas ficam com estado vencida",
       all(t["estado"] == "vencida" for t in podadas),
       [t["estado"] for t in podadas])

# ------------------------------------------------------------------ semear
with tempfile.TemporaryDirectory() as tmp:
    caminho = os.path.join(tmp, "posts", "fila-tarefas.json")
    escreve(tmp, "posts/fila-tarefas.json", {"_o_que_e": "fila", "versao": 1, "tarefas": []})
    dados = f.carregar(caminho)
    plano = {"tema_do_dia": {"texto": "tema do dia de teste"},
             "meta_em_risco": {"meta": "itch: downloads"}}
    criadas = f.semear(dados, plano)
    ok("semear cria 4 tarefas (publicar, pesquisar, medir, aprender)",
       len(criadas) == 4, [t["tipo"] for t in criadas])
    # semear de novo nao duplica (chaves sao por dia)
    criadas2 = f.semear(dados, plano)
    ok("semear idempotente: 0 criadas na segunda chamada",
       len(criadas2) == 0, len(criadas2))

print("\n%d/%d contratos da fila de tarefas passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
