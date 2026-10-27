#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aprendizado diário: existe horário melhor? Só responde "sim" com prova.

O relatório `posts/desempenho.md` já avisa, com todas as letras, que a diferença por hora
está dentro do ruído com a amostra atual. Este script transforma esse aviso em regra:

  - lê a linha "**Horário (Brasília):**" do relatório (hora=media(n=amostra));
  - exige AMOSTRA_MINIMA por hora candidata (30) — abaixo disso, não decide nada;
  - calcula a média do melhor horário e compara com a mediana geral;
  - só declara "confiável" se a amostra passa E a diferença for maior que o desvio
    padrão das médias (regra simples e conservadora, escrita aqui para ser auditável).

Saída: posts/aprendizado.json — com `decisao` explícita: manter ou trocar.
"""
import datetime
import json
import os
import re
import statistics
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESEMPENHO = os.path.join(RAIZ, "posts", "desempenho.md")
SAIDA = os.path.join(RAIZ, "posts", "aprendizado.json")

AMOSTRA_MINIMA = 30


def ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def por_hora(texto):
    """[(hora, media, amostra)] da linha de horário do relatório mais recente."""
    achados = []
    for linha in texto.splitlines():
        if "Horário (Brasília)" not in linha:
            continue
        for m in re.finditer(r"(\d{2})h=([\d.]+)\(n=(\d+)\)", linha):
            achados.append((int(m.group(1)), float(m.group(2)), int(m.group(3))))
        break  # o relatório mais recente vem primeiro
    return achados


def decidir(horas, amostra_minima=AMOSTRA_MINIMA):
    """(confiavel, melhor_hora, motivo, detalhe)"""
    if not horas:
        return False, None, "sem leitura de horário no relatório", {}
    elegiveis = [h for h in horas if h[2] >= amostra_minima]
    detalhe = {
        "horas_lidas": len(horas),
        "amostra_total": sum(h[2] for h in horas),
        "elegiveis": len(elegiveis),
        "amostra_minima": amostra_minima,
    }
    if not elegiveis:
        melhor_bruto = max(horas, key=lambda h: h[1])
        return (False, None,
                "amostra insuficiente: nenhuma hora tem %d posts (o maior n é %d) — não troca nada"
                % (amostra_minima, max(h[2] for h in horas)),
                dict(detalhe, maior_media_observada={"hora": melhor_bruto[0], "media": melhor_bruto[1],
                                                     "n": melhor_bruto[2]}))
    melhor = max(elegiveis, key=lambda h: h[1])
    medias = [h[1] for h in horas]
    mediana = statistics.median(medias)
    desvio = statistics.pstdev(medias) if len(medias) > 1 else 0.0
    ganho = melhor[1] - mediana
    confiavel = ganho > desvio and melhor[2] >= amostra_minima
    motivo = ("melhor hora %02dh (media %.2f, n=%d) supera a mediana %.2f por mais de um desvio (%.2f)"
              % (melhor[0], melhor[1], melhor[2], mediana, desvio)) if confiavel else (
              "diferença dentro do ruído: melhor %02dh (%.2f) vs mediana %.2f, desvio %.2f"
              % (melhor[0], melhor[1], mediana, desvio))
    return confiavel, (melhor[0] if confiavel else None), motivo, dict(
        detalhe, mediana=mediana, desvio=desvio, melhor={"hora": melhor[0], "media": melhor[1], "n": melhor[2]})


def main(argv):
    horas = por_hora(ler(DESEMPENHO))
    confiavel, melhor, motivo, detalhe = decidir(horas)
    resultado = {
        "quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "confiavel": confiavel,
        "melhor_hora": melhor,
        "decisao": "trocar" if confiavel else "manter",
        "motivo": motivo,
        "detalhe": detalhe,
        "_regra": "só troca horário com amostra >= %d por hora E ganho maior que um desvio padrão" % AMOSTRA_MINIMA,
    }
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("decisão: %s · %s" % (resultado["decisao"].upper(), motivo))
    print("gravado em posts/aprendizado.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
