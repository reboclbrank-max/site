#!/usr/bin/env python3
"""Barreira offline da autonomia de marketing: sem rede, segredos ou publicação."""
import datetime as dt
import importlib.util
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

print(f"{verificacoes-len(falhas)}/{verificacoes} verificações de autonomia de marketing passaram")
sys.exit(1 if falhas else 0)
