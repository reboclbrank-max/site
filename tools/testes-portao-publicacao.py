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


def checar(nome, condicao, detalhe=""):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome
          + ("" if condicao or not detalhe else "  [motivo: " + str(detalhe) + "]"))


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
                  canal="devlog", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  nota_juizo=0.9)
checar("primeira do canal é declarada, não bloqueada", r["publica"] is True and r["numeros"].get("primeira_do_canal") is True)

# 10. o canal é respeitado: histórico de um canal não barra o outro
r = portao.avalia(cand("O jogo que nasceu de uma ideia simples", "texto"),
                  canal="youtube", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  nota_juizo=0.9)
checar("histórico de site não barra youtube", r["publica"] is True)

# ---- 11. ESTILO: os defeitos que já foram publicados agora são recusa ----------------------
# Caso real de 06/11/2026: "Quer achar a gente de verdade? Só na **Prancheta**..." foi aprovado
# com o markdown cru, e o post que foi ao ar começava com "Voce" e terminava com #IdleFarm.
bom = "Ceifalume: plantar flor de lume junto à abóbora abre a colheita de 30 para 20 segundos"
r = portao.avalia(cand(bom, bom),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True, nota_juizo=0.9)
checar("texto limpo passa no estilo e publica", r["publica"] is True, r["motivo"])

r = portao.avalia(cand(bom, "Quer achar a gente? Só na **Prancheta**, lá tem tudo"),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True, nota_juizo=0.9)
checar("markdown cru no bluesky recusa", r["publica"] is False and "markdown" in r["motivo"], r["motivo"])

r = portao.avalia(cand(bom, "quer achar a gente de verdade? so na prancheta, la tem tudo"),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True)
checar("palavra sem acento recusa e diz a forma certa",
       r["publica"] is False and "acento" in r["motivo"] and "só" in r["motivo"], r["motivo"])

# o caso exato do post que foi ao ar em 06/11 ("Voce programa colheitas longas...")
r = portao.avalia(cand(bom, "Voce programa colheitas antes de dormir e acorda com o celeiro cheio"),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True)
checar("'Voce' sem acento recusa citando 'você'",
       r["publica"] is False and "você" in r["motivo"], r["motivo"])

r = portao.avalia(cand(bom, bom + " #IdleFarm"),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True)
checar("hashtag em inglês recusa", r["publica"] is False and "inglês" in r["motivo"], r["motivo"])

r = portao.avalia(cand(bom, bom + " #Ceifalume #JogoBrasileiro"),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True, nota_juizo=0.9)
checar("hashtag da casa em português passa", r["publica"] is True, r["motivo"])

r = portao.avalia(cand(bom, bom + " Fora dali, é risco."),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True)
checar("frase de pressão recusa", r["publica"] is False and "pressão" in r["motivo"], r["motivo"])

r = portao.avalia(cand(bom, bom + " 🌙🌙🌙🌙🌙"),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True)
checar("emoji demais recusa", r["publica"] is False and "emoji" in r["motivo"], r["motivo"])

r = portao.avalia(cand(bom, bom.upper()),
                  canal="bluesky", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  credencial_disponivel=True)
checar("caixa alta gritada recusa", r["publica"] is False and "caixa alta" in r["motivo"], r["motivo"])

# o site RENDERIZA markdown: a mesma marca não é defeito lá
r = portao.avalia(cand("Um devlog sobre o plantio da flor de lume",
                       "o **plantio** da flor de lume mudou o tempo de colheita do campo inteiro"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14,
                  nota_juizo=0.9)
checar("no site o markdown não é defeito", r["publica"] is True, r["motivo"])

# ---- 12. A NOTA DEIXOU DE SER OPCIONAL (06/11/2026) ---------------------------------------
# O dono recusou o limite "o portão não mede graça". Agora o portão calcula a nota sozinho, com
# régua declarada e mínimo calibrado (juizo.NOTA_MINIMA / NOTA_MINIMA_DESCRICAO).
r = portao.avalia(cand("Como a flor de lume adianta a colheita do Ceifalume",
                       "O milho do Ceifalume leva 116 segundos para ficar pronto. Colher na hora "
                       "certa mantém o celeiro girando. Grátis no navegador. #ceifalume"),
                  canal="site", publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("o portão calcula a nota quando ninguém passa nota",
       r["numeros"].get("nota_juizo") is not None and r["publica"] is True,
       (r["numeros"].get("nota_juizo"), r["motivo"]))

ruim = ("Dois mundos, um dev brasileiro. PRANCHETA é tática e CEIFALUME é fazenda idle, "
        "os dois feitos no Godot, os dois grátis, os dois da casa")
r = portao.avalia(cand("Dois mundos um dev brasileiro", ruim), canal="site",
                  publicacoes=[], calendario=CAL, hora_local=14)
checar("a nota baixa recusa com número no motivo",
       r["publica"] is False and ("juízo" in r["motivo"] or "assunto" in r["motivo"]),
       r["motivo"])
checar("a recusa por nota traz a nota e o mínimo", "nota_juizo" in r["numeros"],
       r["numeros"].get("nota_juizo"))

# descrição de vídeo tem régua própria: link e fonte contam a favor, hashtag não é exigida
s_desc = ("As plantações crescem por até 8 horas com o jogo fechado. A partida do vídeo fez "
          "9 colheitas em 2 minutos.\n\nFonte: posts/cenas.json (partida 62da85d4dd28, "
          "conferida em 2026-11-06).\n\nJogar: https://reboclbrank-max.github.io/site/jogos/ceifalume/")
r = portao.avalia(cand("Onde jogar CEIFALUME sem instalar loja", s_desc), canal="youtube",
                  publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("descrição de vídeo usa a régua de descrição e passa",
       r["publica"] is True and r["numeros"].get("nota_juizo", 0) >= 0.73, r["motivo"])
cortada = s_desc[:120] + "…"
r = portao.avalia(cand("Onde jogar CEIFALUME sem instalar loja", cortada), canal="youtube",
                  publicacoes=HISTORICO, calendario=CAL, hora_local=14)
checar("descrição cortada em reticências é recusada pela régua",
       r["publica"] is False and "juízo" in r["motivo"], r["motivo"])

certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos do portão de publicação passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
