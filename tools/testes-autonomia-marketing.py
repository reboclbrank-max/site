#!/usr/bin/env python3
"""Barreira offline da autonomia de marketing: sem rede, segredos ou publicação."""
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def carrega(nome, caminho):
    espec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


postador = carrega("postador", RAIZ / "tools" / "postador.py")
retaguarda = carrega("retaguarda_postagem", RAIZ / "tools" / "retaguarda-postagem.py")

falhas = []
verificacoes = 0


def verifica(nome, condicao):
    global verificacoes
    verificacoes += 1
    if condicao:
        print("✔", nome)
    else:
        print("✘", nome)
        falhas.append(nome)


verifica("aceita post curto e factual do Prancheta", postador.texto_gerado_seguro(
    "No Prancheta, desenhe a bola parada e veja a partida fictícia simular. Feito no Brasil."))
verifica("aceita lançamento factual de Ceifalume", postador.texto_gerado_seguro(
    "Ceifalume 0.1 já está disponível: plante numa fazenda noturna e acompanhe o progresso mesmo com o jogo fechado."))
verifica("rejeita estado vencido de Ceifalume", not postador.texto_gerado_seguro(
    "Em breve: Ceifalume está em desenvolvimento, uma fazenda noturna para jogar depois."))
verifica("rejeita URL inesperada", not postador.texto_gerado_seguro(
    "Conheça o Prancheta, manager de futebol fictício: https://exemplo.invalido/promo"))
verifica("rejeita possível segredo", not postador.texto_gerado_seguro(
    "Prancheta é um jogo de futebol fictício. Token secreto: nao-compartilhe-isto."))
verifica("aceita disponibilidade factual de Ceifalume", postador.texto_gerado_seguro(
    "Ceifalume já está lançado e disponível agora para jogar: uma fazenda noturna grátis, sem conta."))
verifica("rejeita duplicata", not postador.texto_gerado_seguro(
    "No Prancheta, desenhe a bola parada e veja a partida fictícia simular. Feito no Brasil.",
    "No Prancheta, desenhe a bola parada e veja a partida fictícia simular. Feito no Brasil."))

verifica("rota de Prancheta aponta para a página certa", postador.destino_editorial(
    "No Prancheta, desenhe a bola parada e decida a partida.") == postador.DESTINOS_EDITORIAIS["prancheta"])
verifica("rota de Ceifalume aponta para a página certa", postador.destino_editorial(
    "Ceifalume é uma fazenda noturna de colheita à luz da lanterna.") == postador.DESTINOS_EDITORIAIS["ceifalume"])
verifica("assunto misto cai no catálogo", postador.destino_editorial(
    "Prancheta e Ceifalume são jogos da Rebocl Brank.") == postador.DESTINOS_EDITORIAIS["catalogo"])
verifica("convite genérico leva ao hub público", postador.destino_editorial(
    "Acompanhe a casa Rebocl nos canais oficiais.") == postador.DESTINOS_EDITORIAIS["canais"])
verifica("URL sugerida fora da lista não passa", postador.destino_oficial(
    "https://exemplo.invalido", "Prancheta é um manager de futebol.") == postador.DESTINOS_EDITORIAIS["prancheta"])
mensagem_curta = postador.mensagem_editorial(
    "Ceifalume 0.1 já está disponível: plante e colha numa fazenda noturna.", postador.DESTINOS_EDITORIAIS["ceifalume"])
verifica("mensagem preserva destino e cabe no menor canal", mensagem_curta.endswith(postador.DESTINOS_EDITORIAIS["ceifalume"]) and len(mensagem_curta) <= postador.LIMITE_MENSAGEM_MICROBLOG)


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

LOG_CICLO = "\n## 20/10/2026 00:25 UTC\n\n| canal | resultado |\n"
AGORA_RECENTE = dt.datetime(2026, 10, 20, 1, 25, tzinfo=dt.timezone.utc)
AGORA_ATRASADO = dt.datetime(2026, 10, 20, 4, 26, tzinfo=dt.timezone.utc)
RUN_ATUAL = [{"id": "pulso-1", "status": "in_progress"}]

verifica("retaguarda preserva ciclo recente", retaguarda.decide_retaguarda(LOG_CICLO, RUN_ATUAL, "pulso-1", AGORA_RECENTE) == ("preservar", "ciclo-recente"))
verifica("retaguarda solicita só lacuna maior que a tolerância", retaguarda.decide_retaguarda(LOG_CICLO, RUN_ATUAL, "pulso-1", AGORA_ATRASADO) == ("despachar", "lacuna-confirmada"))
verifica("retaguarda não duplica postagem em andamento", retaguarda.decide_retaguarda(LOG_CICLO, RUN_ATUAL + [{"id": "postar-2", "status": "queued"}], "pulso-1", AGORA_ATRASADO) == ("preservar", "outra-execucao-em-andamento"))
verifica("retaguarda falha fechada sem o próprio pulso", retaguarda.decide_retaguarda(LOG_CICLO, [{"id": "outro", "status": "completed"}], "pulso-1", AGORA_ATRASADO)[0] == "interromper")
verifica("retaguarda ignora carimbo de teste", retaguarda.decide_retaguarda(LOG_CICLO + "## 20/10/2026 04:25 UTC — TESTE\n", RUN_ATUAL, "pulso-1", AGORA_ATRASADO) == ("despachar", "lacuna-confirmada"))

with tempfile.TemporaryDirectory() as temporario:
    caminho = pathlib.Path(temporario) / "log.md"
    caminho.write_text(LOG_CICLO, encoding="utf-8")
    verifica("trava do postador segura ciclo menor que duas horas", postador.ciclo_ainda_recente(AGORA_RECENTE, caminho))
    verifica("trava do postador libera o próximo bloco planejado", not postador.ciclo_ainda_recente(dt.datetime(2026, 10, 20, 2, 26, tzinfo=dt.timezone.utc), caminho))

postador.resultados.clear()
postador.canal("sonda", lambda: ("INDISPONIVEL", "leitura ausente"))
verifica("sonda sem leitura não recebe selo verde", postador.resultados == [("sonda", "INDISPONIVEL", "leitura ausente")])
postador.resultados.clear()

verifica("recuperação de credencial para em revisão humana", postador.recuperacao_credencial_pendente() == (
    "PULADO", "recuperação de credencial exige revisão humana; nenhuma caixa, senha, token ou cofre é alterado"))

fila_editorial = json.loads((RAIZ / "posts" / "fila.json").read_text(encoding="utf-8"))
verifica("fila usa somente destinos canônicos e cabe inteira", all(
    item.get("url") in postador.URLS_DE_DESTINO_PERMITIDAS
    and len(item.get("texto", "")) <= postador.LIMITE_TEXTO_EDITORIAL
    and len(postador.mensagem_editorial(item.get("texto", ""), item.get("url", ""))) <= postador.LIMITE_MENSAGEM_MICROBLOG
    and "em breve: ceifalume" not in item.get("texto", "").casefold()
    for item in fila_editorial.get("posts", [])
))
hub = (RAIZ / "canais.html").read_text(encoding="utf-8")
verifica("hub público liga jogos e canais já oficiais", (RAIZ / "canais.html").is_file() and all(url in hub for url in (
    postador.DESTINOS_EDITORIAIS["prancheta"], postador.DESTINOS_EDITORIAIS["ceifalume"],
    "https://bsky.app/profile/reboclbrank.bsky.social", "https://mastodon.social/@ReboclBrank",
    "https://discord.gg/AnJr5nqx4K", "https://t.me/ceifalume",
)))
verifica("páginas e sitemap apontam ao hub oficial", all("canais.html" in (RAIZ / pagina).read_text(encoding="utf-8") for pagina in (
    "index.html", "jogos.html", "jogos/prancheta/index.html", "jogos/ceifalume/index.html", "sitemap.xml",
)))

verifica("superfícies públicas não anunciam Ceifalume como futuro", all(
    "em breve: ceifalume" not in (RAIZ / pagina).read_text(encoding="utf-8").casefold()
    and "ceifalume (a fazenda não dorme) em breve" not in (RAIZ / pagina).read_text(encoding="utf-8").casefold()
    for pagina in ("jogos.html", "postar.html", "posts/fila.json")
))
verifica("contrato de roteamento está documentado", (RAIZ / "MARKETING-ROTEAMENTO.md").is_file())

fonte_postador = (RAIZ / "tools" / "postador.py").read_text(encoding="utf-8")
verifica("configuração ausente não usa o mesmo estado de trava", "INDISPONIVEL" in fonte_postador and "def indisponivel(" in fonte_postador)
verifica("postador não recupera conta nem escreve no cofre privado", fonte_postador.count("COFARE_URL") == 2 and all(
    trecho not in fonte_postador for trecho in (
        "def salva_cofare", "COFARE_URL.replace", "IMAP4_SSL", "auth/password/edit", 'grant_type\": \"password')))
verifica("consultas de métrica não põem token na URL", "?fields=followers_count,media_count&access_token=" not in fonte_postador)
verifica("Threads não renova token automaticamente", "refresh_access_token" not in fonte_postador and "salva_cofare(" not in fonte_postador)

workflow = (RAIZ / ".github" / "workflows" / "postagem-diaria.yml").read_text(encoding="utf-8")
verifica("política de autonomia existe", (RAIZ / "AUTONOMIA-MARKETING.md").is_file())
verifica("workflow usa checkout fixado", "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in workflow)
verifica("workflow mantém exatamente pulso e 8 ciclos planejados", workflow.count("- cron:") == 2 and "cron: '17 0,3,6,9,12,15,18,21 * * *'" in workflow)
verifica("pulso e postagem usam concorrências separadas", "group: ${{ github.event.schedule == '13,33,53 * * * *' && 'postagem-acorda' || 'postagem-diaria' }}" in workflow)
verifica("pulso usa retaguarda fail-closed", "python3 tools/retaguarda-postagem.py /tmp/posts-log.md" in workflow and "timeout-minutes: 3" in workflow and "Retaguarda conservadora da cadência de marketing\n        run:" in workflow)

print(f"{verificacoes-len(falhas)}/{verificacoes} verificações de autonomia de marketing passaram")
sys.exit(1 if falhas else 0)
