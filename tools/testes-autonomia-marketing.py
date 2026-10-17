#!/usr/bin/env python3
"""Barreira offline da autonomia de marketing: sem rede, segredos ou publicação."""
import importlib.util
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ARQ = RAIZ / "tools" / "postador.py"
ESPEC = importlib.util.spec_from_file_location("postador", ARQ)
postador = importlib.util.module_from_spec(ESPEC)
ESPEC.loader.exec_module(postador)

falhas = []
def verifica(nome, condicao):
    if condicao:
        print("✔", nome)
    else:
        print("✘", nome)
        falhas.append(nome)

verifica("aceita post curto e factual do Prancheta", postador.texto_gerado_seguro(
    "No Prancheta, desenhe a bola parada e veja a partida fictícia simular. Feito no Brasil."))
verifica("aceita expectativa honesta de Ceifalume", postador.texto_gerado_seguro(
    "Ceifalume está em desenvolvimento: uma fazenda noturna onde as plantações crescem com o jogo fechado."))
verifica("rejeita URL inesperada", not postador.texto_gerado_seguro(
    "Conheça o Prancheta, manager de futebol fictício: https://exemplo.invalido/promo"))
verifica("rejeita possível segredo", not postador.texto_gerado_seguro(
    "Prancheta é um jogo de futebol fictício. Token secreto: nao-compartilhe-isto."))
verifica("rejeita promessa incompatível de Ceifalume", not postador.texto_gerado_seguro(
    "Ceifalume já está lançado e disponível agora para jogar. Uma fazenda para todos."))
verifica("rejeita duplicata", not postador.texto_gerado_seguro(
    "No Prancheta, desenhe a bola parada e veja a partida fictícia simular. Feito no Brasil.",
    "No Prancheta, desenhe a bola parada e veja a partida fictícia simular. Feito no Brasil."))
verifica("política de autonomia existe", (RAIZ / "AUTONOMIA-MARKETING.md").is_file())
verifica("workflow usa checkout fixado", "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in
         (RAIZ / ".github" / "workflows" / "postagem-diaria.yml").read_text())

print(f"{8-len(falhas)}/8 verificações de autonomia de marketing passaram")
sys.exit(1 if falhas else 0)
