#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do portão de publicação: recusar é o comportamento normal.

Nada aqui usa rede, segredo ou publicação. É a prova de que a casa sabe dizer NÃO.
"""
import importlib.util
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
espec = importlib.util.spec_from_file_location("portao", RAIZ / "tools" / "portao-publicacao.py")
portao = importlib.util.module_from_spec(espec)
espec.loader.exec_module(portao)

resultados = []


def checar(nome, condicao):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome)


CAL = {"janela": {"inicio": 9, "fim": 22}, "teto_diario": 1}

HISTORICO = [
    {"canal": "site", "titulo": "O jogo que nasceu de uma ideia simples",
     "texto": "comecei a desenhar o ceifalume pensando em um jogo de ritmo simples e limpo"},
    {"canal": "site", "titulo": "Gravei a prancha em madeira pela primeira vez",
     "texto": "a prancheta saiu do papel hoje gravei madeira ferramenta nova aprendi sobre corte"},
]


def cand(titulo, texto):
    return {"titulo": titulo, "texto": texto}


# 1. canal impossível não publica, com motivo próprio
r = portao.avalia(cand("Um título qualquer e próprio", "texto novo sobre outra coisa"), canal="itch", hora_local=14, calendario=CAL)
checar("itch não publica: a casa só mede", r["publica"] is False and "chave de API" in r["motivo"])
r = portao.avalia(cand("Um título qualquer e próprio", "x"), canal="instagram", hora_local=14, calendario=CAL)
checar("instagram recusa declarada sem credencial", r["publica"] is False and "credencial" in r["motivo"])
r = portao.avalia(cand("Um título qualquer e próprio", "x"), canal="tiktok", hora_local=14, calendario=CAL)
checar("canal desconhecido recusa", r["publica"] is False and "desconhecido" in r["motivo"])

# 2. falha fechada: sem calendário, nada publica
r = portao.avalia(cand("Um título qualquer e próprio", "texto"), canal="site", hora_local=14, calendario=None)
checar("sem calendário não publica (falha fechada)", r["publica"] is False and "calendário" in r["motivo"])
r = portao.avalia(cand("Um título qualquer e próprio", "texto"), canal="site", hora_local=6, calendario=CAL)
checar("fora da janela não publica", r["publica"] is False and "fora da janela" in r["motivo"])

# 3. repetição de título
r = portao.avalia(cand("O jogo que nasceu de uma ideia simples", "outro texto totalmente diferente aqui"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("título já publicado recusa", r["publica"] is False and "já publicado" in r["motivo"])
r = portao.avalia(cand("O jogo que nasceu de uma ideia simples!", "texto diferente"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("título quase igual também recusa", r["publica"] is False)

# 4. repetição de conteúdo
r = portao.avalia(cand("Ceifalume: o ritmo simples e limpo",
                       "comecei a desenhar o ceifalume pensando em um jogo de ritmo simples e limpo"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("texto repetido recusa e diz a semelhança", r["publica"] is False and "repetido" in r["motivo"])

# 5. fórmula genérica
r = portao.avalia(cand("Confira agora o novo vídeo da casa", "conteúdo novo"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("fórmula genérica recusa", r["publica"] is False and "fórmula" in r["motivo"])

# 6. título fora da faixa
r = portao.avalia(cand("Curto", "conteúdo novo e distinto"), canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("título curto demais recusa", r["publica"] is False and "faixa" in r["motivo"])

# 7. juízo abaixo do mínimo
r = portao.avalia(cand("Uma ideia nova sobre gravar madeira", "gravei a prancheta em madeira macia com formao novo e o som ficou bom"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14, nota_juizo=0.2)
checar("juízo baixo recusa", r["publica"] is False and "juízo" in r["motivo"])

# 8. publicação de verdade passa, e passa com número
r = portao.avalia(cand("Como escolhi o som do ceifalume",
                       "passei tres dias comparando o som da foice batendo na pedra ate achar o corte certo"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14, nota_juizo=0.8)
checar("texto novo e dentro da janela publica", r["publica"] is True)
checar("a decisão traz número, não adjetivo", "semelhanca_maxima" in r["numeros"] and "historico_do_canal" in r["numeros"])

# 9. primeira publicação do canal não é bloqueada por falta de histórico
r = portao.avalia(cand("O primeiro devlog da prancheta", "texto inicial do canal devlog"),
                  canal="devlog", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("primeira do canal é declarada, não bloqueada", r["publica"] is True and r["numeros"].get("primeira_do_canal") is True)

# 10. o canal é respeitado: histórico de um canal não barra o outro
r = portao.avalia(cand("O jogo que nasceu de uma ideia simples", "texto"),
                  canal="youtube", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("histórico de site não barra youtube", r["publica"] is True)

certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos do portão de publicação passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
