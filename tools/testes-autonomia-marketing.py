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

def teste_arte_reserva():
    chamadas = []
    def criar(url):
        chamadas.append(url)
        if url == "principal":
            raise RuntimeError("cdn recusada")
        return "container-reserva"
    retorno = postador.cria_container_com_reserva(criar, "principal", ["reserva"])
    return retorno == ("container-reserva", "reserva", True) and chamadas == ["principal", "reserva"]

def teste_sem_reserva_nao_publica():
    try:
        postador.cria_container_com_reserva(lambda _: (_ for _ in ()).throw(RuntimeError("falhou")), "principal", ["reserva"])
    except RuntimeError:
        return True
    return False

def teste_espera_midia_pronta():
    estados = iter([{"status_code": "IN_PROGRESS"}, {"status_code": "FINISHED"}])
    pausas = []
    postador.espera_container_instagram("abc", "segredo-teste", lambda *_: next(estados), lambda s: pausas.append(s), tentativas=3, intervalo=3)
    return pausas == [3]

def teste_midia_com_erro_nao_publica():
    try:
        postador.espera_container_instagram("abc", "segredo-teste", lambda *_: {"status_code": "ERROR"}, lambda _: None, tentativas=2)
    except RuntimeError:
        return True
    return False

verifica("arte reserva entra antes da publicação se CDN falhar", teste_arte_reserva())
verifica("sem container não tenta publicar", teste_sem_reserva_nao_publica())
verifica("espera mídia do Instagram terminar antes de publicar", teste_espera_midia_pronta())
verifica("mídia com erro não chega ao publish", teste_midia_com_erro_nao_publica())
verifica("espelhos próprios de Instagram estão declarados", len(postador.IG_ARTE_RESERVA) >= 2 and all(u.startswith("https://raw.githubusercontent.com/reboclbrank-max/site/") for u in postador.IG_ARTE_RESERVA))
verifica("política de autonomia existe", (RAIZ / "AUTONOMIA-MARKETING.md").is_file())
workflow = (RAIZ / ".github" / "workflows" / "postagem-diaria.yml").read_text()
verifica("workflow usa checkout fixado", "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in workflow)
verifica("workflow escalona os 8 ciclos fora do topo da hora", "cron: '17 0,3,6,9,12,15,18,21 * * *'" in workflow)

TOTAL = 14
print(f"{TOTAL-len(falhas)}/{TOTAL} verificações de autonomia de marketing passaram")
sys.exit(1 if falhas else 0)
