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
verifica("consultas de métrica não põem token na URL", "?fields=followers_count,media_count&access_token=" not in fonte_postador)
verifica("renovação Threads não põe token na URL", "refresh_access_token?grant_type=threads_access_token&access_token=" not in fonte_postador)

workflow = (RAIZ / ".github" / "workflows" / "postagem-diaria.yml").read_text(encoding="utf-8")
verifica("política de autonomia existe", (RAIZ / "AUTONOMIA-MARKETING.md").is_file())
verifica("workflow usa checkout fixado", "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in workflow)
verifica("workflow mantém exatamente pulso e 8 ciclos planejados", workflow.count("- cron:") == 2 and "cron: '17 0,3,6,9,12,15,18,21 * * *'" in workflow)
verifica("pulso e postagem usam concorrências separadas", "group: ${{ github.event.schedule == '13,33,53 * * * *' && 'postagem-acorda' || 'postagem-diaria' }}" in workflow)
verifica("pulso usa retaguarda fail-closed", "python3 tools/retaguarda-postagem.py /tmp/posts-log.md" in workflow and "timeout-minutes: 3" in workflow and "Retaguarda conservadora da cadência de marketing\n        run:" in workflow)

# ---------------------------------------------------------------------------------------
# Conteúdo repetido no ar (defeito medido em 26/10/2026)
#
# O perfil da casa publicou O MESMO texto 53 vezes — cinco delas em um único dia. A causa não
# foi falta de tema: foi (1) um único motor de texto, sem retaguarda, e (2) um dedupe que
# comparava o candidato COM quebra de linha contra um registro que gravava " ⏎ " no lugar
# dela. Dedupe que nunca compara igual não é dedupe.
from collections import Counter

_registro = ("⚽ Sou TÉCNICO, não jogador. ⏎ PRANCHETA é um manager de futebol 100% fictício"
             " ⏎ Grátis no navegador ou APK.")
_igual = "⚽ Sou TÉCNICO, não jogador.\nPRANCHETA é um manager de futebol 100% fictício\nGrátis no navegador ou APK."
verifica("dedupe reconhece repetição mesmo com quebra de linha diferente",
         postador.ja_foi_publicado(_igual, _registro))
verifica("dedupe não bloqueia texto novo",
         not postador.ja_foi_publicado("🌙 A fazenda não dorme: plante à luz da lanterna", _registro))
verifica("o crivo editorial usa o dedupe normalizado",
         not postador.texto_gerado_seguro(_igual, _registro))
verifica("existe mais de um motor de texto (motor único é ponto único de falha)",
         len(postador.MOTORES_DE_TEXTO) >= 2)
verifica("o motor de texto informa o motivo quando todos falham",
         callable(postador.cerebro_com_motivo))
_fonte_postador = (RAIZ / "tools" / "postador.py").read_text(encoding="utf-8")
verifica("o log do ciclo diz QUAL motor escreveu (ou por que nenhum escreveu)",
         'motivo_geracao = motivo or "motor respondeu"' in _fonte_postador)
verifica("a fila de reserva respeita o dedupe", "ja_foi_publicado(item[\"texto\"], ja_publicados)" in _fonte_postador)
verifica("fila esgotada varia o fecho em vez de repetir a frase",
         "variacao_de_fecho(indice_tema)" in _fonte_postador)
verifica("os fechos de reserva são distintos entre si",
         len({postador.variacao_de_fecho(i) for i in range(8)}) == 8)

# Ponte entre redes: existia no código e nunca chegou à rede (0 menções em 100 posts).
_temas_falsos = ["tema %d" % i for i in range(40)]
_ciclos = [postador.tema_do_ciclo(_temas_falsos, i) for i in range(80)]
verifica("a ponte entre redes roda por construção (1 a cada 8 ciclos)",
         sum(1 for t in _ciclos if "Instagram" in t) == 10)
verifica("a ponte repete o mesmo canal-alvo (Instagram), sem inventar URL",
         all("instagram" in t.lower() for t in _ciclos if "Instagram" in t))
verifica("tema comum continua variando entre os ciclos sem ponte",
         len({t for t in _ciclos if "Instagram" not in t}) > 20)
verifica("o ciclo registra o tema no log (para poder ser cobrado)",
         '"tema do ciclo"' in _fonte_postador)
# ---------------------------------------------------------------------------------------
# O crivo reprovava o verbo do próprio jogo (medido em 26/10/2026)
#
# A regra de segredo usava "senha\b" SEM fronteira à esquerda, então casava dentro de
# "deSENHA". Resultado: todo post que dizia "desenhe a bola parada" — a descrição oficial do
# PRANCHETA — era reprovado, o gerador caía na fila fixa e repetia a mesma frase.
verifica("o crivo aceita o verbo do jogo ('desenhe a bola parada')",
         postador.texto_gerado_seguro(
             "Desenhe a bola parada no PRANCHETA e veja a partida simular. Grátis no navegador.", ""))
verifica("o crivo continua barrando senha de verdade",
         not postador.texto_gerado_seguro("mande a senha do painel para o PRANCHETA", ""))
verifica("o crivo continua barrando link no corpo",
         not postador.texto_gerado_seguro("acesse https://exemplo.example e jogue PRANCHETA", ""))
verifica("o crivo continua barrando token",
         not postador.texto_gerado_seguro("use o token da api no PRANCHETA", ""))

# ---------------------------------------------------------------------------------------
# Cadência de ponte sem convite não leva ninguém
#
# Pedimos o tema de ponte ao motor e ele escreveu um post bonito sobre os jogos, sem citar o
# Instagram. A ponte tem que GARANTIR o convite, não esperar boa vontade do modelo.
_tema_ponte = postador.TEMAS_PONTE[0]
_sem_cta = "Desenhe a bola parada no PRANCHETA e veja a partida simular. Grátis no navegador."
_com_cta, _mexeu = postador.garantir_ponte(_sem_cta, _tema_ponte)
verifica("no ciclo de ponte, o convite ao Instagram é garantido", _mexeu and "instagram" in _com_cta.lower())
verifica("o texto com convite continua dentro do limite", len(_com_cta) <= postador.LIMITE_TEXTO_EDITORIAL)
verifica("o texto com convite continua passando no crivo", postador.texto_gerado_seguro(_com_cta, ""))
verifica("o convite não põe URL no corpo (o link vem do destino oficial)",
         "http" not in _com_cta.lower())
verifica("tema comum não é alterado", postador.garantir_ponte(_sem_cta, "dica tatica de defesa")[1] is False)
verifica("o destino do tema de ponte é o hub de canais",
         postador.destino_editorial("", _tema_ponte) == postador.DESTINOS_EDITORIAIS["canais"])
verifica("o log avisa quando o convite foi anexado",
         "convite da ponte anexado" in _fonte_postador)

# O gameplay publicado tem que estar na página do jogo, não só no YouTube
#
# Em 30/10 o vídeo de 2 minutos com as instruções foi publicado (youtu.be/GuE7af6dYo8) e ficou
# só no canal: quem chegava na página do jogo não via a prova de que o jogo roda. O teste trava
# os três elos: página -> vídeo local, página -> YouTube, e o arquivo existe no repositório.
_pagina_jogo = (RAIZ / "jogos/ceifalume/index.html").read_text(encoding="utf-8")
verifica("a página do Ceifalume toca o gameplay gravado", "media/gameplay/ceifalume-gameplay-instrucoes.mp4" in _pagina_jogo)
verifica("a página do Ceifalume leva ao gameplay no YouTube", "https://youtu.be/GuE7af6dYo8" in _pagina_jogo)
verifica("o gameplay citado pela página existe no repositório",
         (RAIZ / "media/gameplay/ceifalume-gameplay-instrucoes.mp4").is_file()
         and (RAIZ / "media/gameplay/ceifalume-gameplay-instrucoes.mp4").stat().st_size > 1_000_000)
verifica("o gameplay entrou no sameAs do schema VideoGame", _pagina_jogo.count("GuE7af6dYo8") >= 2)
verifica("a página diz que as instruções ficam na tela", "instruções" in _pagina_jogo and "rodapé" in _pagina_jogo)
verifica("o registro de publicação no YouTube cita esse vídeo",
         "GuE7af6dYo8" in (RAIZ / "posts/youtube-publicados.json").read_text(encoding="utf-8"))

print(f"{verificacoes-len(falhas)}/{verificacoes} verificações de autonomia de marketing passaram")
sys.exit(1 if falhas else 0)
