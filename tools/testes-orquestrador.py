#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira offline do orquestrador 24h, da pesquisa e do aprendizado.

Nenhum teste toca a rede: a execução é injetada (`rodar_fn`) e os arquivos são temporários.
O que se prova:
  - prioridade de decisão (medir > pesquisar > aprender > publicar > dormir);
  - janela e teto respeitados; intervalo mínimo de 2h entre publicações;
  - estado é lido/gravado e não perde o histórico;
  - pesquisa escolhe a meta de maior risco e não escolhe tema acima de 220 caracteres;
  - aprendizado NÃO troca horário com amostra pequena (a regra que evita achismo);
  - o workflow 24h existe, tem cron, concorrência e roda o orquestrador.
"""
import datetime
import importlib.util
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import orquestrador  # noqa: E402

UTC = datetime.timezone.utc
falhas = 0


def ok(nome, cond, detalhe=""):
    global falhas
    if cond:
        print("OK  " + nome)
    else:
        falhas += 1
        print("FALHOU  " + nome + ("  <" + str(detalhe) + ">" if detalhe else ""))


def em_utc_para_local(hora_local, dia=27):
    """UTC correspondente a `hora_local` em Brasília (UTC-3), virada de dia tratada."""
    total = hora_local + 3
    if total >= 24:
        return datetime.datetime(2026, 10, dia + 1, total - 24, 30, tzinfo=UTC)
    return datetime.datetime(2026, 10, dia, total, 30, tzinfo=UTC)


CAL = {"janela": {"inicio": 9, "fim": 22, "fuso": "America/Fortaleza"}, "teto_diario": 5}


def estado(**kw):
    base = orquestrador.estado_vazio()
    base.update(kw)
    return base


def main():
    # 1. medição vencida tem prioridade sobre tudo
    acao, motivo = orquestrador.decidir(em_utc_para_local(10), estado(), CAL)
    ok("sem medição registrada → mede primeiro", acao == "medir", acao)

    # 2. com medição fresca, dentro da janela → publica
    agora = em_utc_para_local(11)
    acao, motivo = orquestrador.decidir(
        agora, estado(ultima_medicao=orquestrador.iso(agora - datetime.timedelta(hours=1))), CAL)
    ok("medição fresca + janela → publicar", acao == "publicar", "%s (%s)" % (acao, motivo))

    # 3. intervalo mínimo entre publicações
    agora = em_utc_para_local(12)
    acao, motivo = orquestrador.decidir(agora, estado(
        ultima_medicao=orquestrador.iso(agora - datetime.timedelta(hours=1)),
        ultima_publicacao=orquestrador.iso(agora - datetime.timedelta(minutes=40))), CAL)
    ok("publicou há 40 min → dorme (mínimo 2h)", acao == "dormir" and "min" in motivo, "%s (%s)" % (acao, motivo))

    # 4. fora da janela não publica
    agora = em_utc_para_local(3)
    acao, motivo = orquestrador.decidir(agora, estado(
        ultima_medicao=orquestrador.iso(agora - datetime.timedelta(hours=1)),
        ultima_pesquisa=orquestrador.iso(agora - datetime.timedelta(hours=1)),
        ultima_aprendizagem=orquestrador.iso(agora - datetime.timedelta(hours=1))), CAL)
    ok("03h local, pesquisa já feita → dorme", acao == "dormir" and "janela" in motivo, "%s (%s)" % (acao, motivo))

    # 5. janelas diárias de pesquisa e aprendizado
    agora = em_utc_para_local(3)
    acao, _ = orquestrador.decidir(agora, estado(
        ultima_medicao=orquestrador.iso(agora - datetime.timedelta(hours=1))), CAL)
    ok("03h local sem pesquisa hoje → pesquisar", acao == "pesquisar", acao)
    agora = em_utc_para_local(4)
    acao, _ = orquestrador.decidir(agora, estado(
        ultima_medicao=orquestrador.iso(agora - datetime.timedelta(hours=1)),
        ultima_pesquisa=orquestrador.iso(agora - datetime.timedelta(hours=1))), CAL)
    ok("04h local sem aprendizado hoje → aprender", acao == "aprender", acao)

    # 6. pesquisa não repete no mesmo dia
    agora = em_utc_para_local(6)
    acao, motivo = orquestrador.decidir(agora, estado(
        ultima_medicao=orquestrador.iso(agora - datetime.timedelta(hours=1)),
        ultima_pesquisa=orquestrador.iso(agora - datetime.timedelta(minutes=90))), CAL)
    ok("pesquisa já feita hoje não repete", acao != "pesquisar", "%s (%s)" % (acao, motivo))

    # 7. estado: grava, lê e preserva histórico
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "estado.json")
        dados = orquestrador.carregar_estado(caminho)
        dados["pulsos"] = 7
        dados["historico"] = [{"acao": "publicar"}]
        orquestrador.gravar_estado(dados, caminho)
        lido = orquestrador.carregar_estado(caminho)
        ok("estado grava e relê", lido["pulsos"] == 7 and lido["historico"][0]["acao"] == "publicar")
        dados["historico"] = [{"n": i} for i in range(60)]
        orquestrador.gravar_estado(dados, caminho)
        ok("histórico fica limitado a 40", len(orquestrador.carregar_estado(caminho)["historico"]) == 40)

    # 8. execução injetada: publicar chama o postador
    chamadas = []

    def falso(comando, **_):
        chamadas.append(comando)
        return 0, "ok simulado"

    orquestrador.executar("publicar", rodar_fn=falso)
    ok("publicar chama tools/postador.py",
       chamadas and chamadas[0][-1].endswith("postador.py"), chamadas)

    # 9. pesquisa: meta de risco e tema
    spec = importlib.util.spec_from_file_location("pesq", os.path.join(RAIZ, "tools", "pesquisar-oportunidade.py"))
    pesq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pesq)

    placar = ("| meta | alvo | observado | falta | por dia | status |\n"
              "|---|---|---|---|---|---|\n"
              "| Instagram: seguidores | 50 | 0 | 50 | 2.94 | EM_CURSO |\n"
              "| itch: downloads | 100 | 46 | 54 | 3.18 | EM_CURSO |\n"
              "| YouTube: shorts | 4 | 5 | 0 | — | ATINGIDO |\n")
    riscos = pesq.metas_em_risco(placar)
    ok("pesquisa ordena por ritmo necessário (maior risco primeiro)",
       riscos[0][0].startswith("itch"), riscos[:2])

    desempenho = ("| tipo | posts | engajamento médio | melhor | sem engajamento |\n"
                  "|---|---|---|---|---|\n"
                  "| conteúdo dos jogos | 82 | 2.07 | 4 | 9 (11.0%) |\n"
                  "| comentário em post alheio | 218 | 0.84 | 3 | 91 (41.7%) |\n")
    ruins = pesq.formatos_ruins(desempenho)
    ok("pesquisa identifica formato com 40%+ de zeros",
       len(ruins) == 1 and "comentário" in ruins[0]["formato"], ruins)

    with tempfile.TemporaryDirectory() as pasta:
        fila = os.path.join(pasta, "fila.json")
        with open(fila, "w", encoding="utf-8") as f:
            json.dump({"posts": [{"texto": "x" * 300, "url": "u1"}, {"texto": "texto bom", "url": "u2"}]}, f)
        tema = pesq.escolher_tema(caminho_fila=fila)
        ok("pesquisa nunca escolhe tema acima de 220 caracteres", tema and tema["texto"] == "texto bom", tema)

    # 10. aprendizado: NÃO troca horário com amostra pequena
    spec = importlib.util.spec_from_file_location("apr", os.path.join(RAIZ, "tools", "aprender-horario.py"))
    apr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(apr)

    # (a) nenhuma hora chega a 30 posts: o relatório real de hoje é assim, tirando 01h
    pouca = [(0, 1.12, 8), (2, 2.0, 4), (8, 1.52, 23), (20, 1.31, 26)]
    confiavel, melhor, motivo, det = apr.decidir(pouca)
    ok("aprendizado não troca horário com amostra pequena",
       confiavel is False and melhor is None and "amostra" in motivo, motivo)
    ok("aprendizado registra a maior média observada sem agir",
       det.get("maior_media_observada", {}).get("hora") == 2, det.get("maior_media_observada"))

    # (b) uma hora passa da amostra mínima, mas o ganho não supera o desvio: mantém
    com_uma_elegivel = [(0, 1.12, 8), (1, 1.14, 36), (2, 2.0, 4), (8, 1.52, 23), (20, 1.31, 26)]
    confiavel_b, melhor_b, motivo_b, _ = apr.decidir(com_uma_elegivel)
    ok("amostra mínima sozinha não basta: ganho dentro do ruído mantém a janela",
       confiavel_b is False and melhor_b is None and "ruído" in motivo_b, motivo_b)

    forte = [(0, 1.0, 40), (10, 3.5, 45), (15, 1.1, 40), (20, 1.0, 50)]
    confiavel2, melhor2, _, _ = apr.decidir(forte)
    ok("aprendizado troca horário quando a prova existe", confiavel2 and melhor2 == 10, (confiavel2, melhor2))

    # 11. o workflow 24h existe e está amarrado
    caminho_wf = os.path.join(RAIZ, ".github", "workflows", "marketing-24h.yml")
    texto = open(caminho_wf, encoding="utf-8").read() if os.path.exists(caminho_wf) else ""
    ok("workflow 24h existe", bool(texto))
    ok("workflow 24h tem cron", "cron:" in texto)
    ok("workflow 24h roda o orquestrador", "tools/orquestrador.py" in texto)
    ok("workflow 24h tem concorrência (não duplica pulso)", "concurrency:" in texto)
    ok("workflow 24h commita o estado", "git commit" in texto)

    total = 21
    print("\n%d/%d testes do orquestrador 24h passaram" % (total - falhas, total))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
