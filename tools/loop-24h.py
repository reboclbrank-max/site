#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bloco contínuo: em vez de acordar a cada 15 min, fica trabalhando por horas seguidas.

Por que existe: o cron do GitHub é "melhor esforço" e às vezes pula. Um job que roda
um laço interno de várias horas reduz muito o número de pulsos perdidos — é o mais perto
de "processo sempre vivo" que o GitHub Actions permite (o job tem teto de 6 horas).

Cada pulso:
  1. roda o orquestrador (ele decide: medir / pesquisar / aprender / publicar / dormir);
  2. atualiza a memória;
  3. commita o estado (para pulso atrasado não duplicar trabalho);
  4. dorme o intervalo.

Travas de segurança (para não virar máquina desgovernada):
  - respeita o botão de desligar: se existir `posts/PARAR`, o laço termina na hora;
  - número máximo de pulsos por bloco (--pulsos);
  - janela de publicação continua valendo (quem decide é o orquestrador, não o laço);
  - intervalo mínimo entre pulsos (--intervalo, padrão 600 s).
"""
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAR = os.path.join(RAIZ, "posts", "PARAR")


def rodar(comando, timeout=900):
    r = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, timeout=timeout)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()[-500:]


def commitar(rotulo):
    """Commita o estado do pulso, com rebase e retentativa (outros robôs empurram junto)."""
    codigo, _ = rodar(["git", "add", "posts/"])
    if codigo != 0:
        return False, "git add falhou"
    codigo, _ = rodar(["git", "-c", "user.name=rebocl",
                       "-c", "user.email=reboclbrank@gmail.com",
                       "commit", "-m", "🤖 pulso %s" % rotulo])
    if codigo != 0:
        return True, "nada a commitar"
    for _ in range(3):
        ok_pull, _ = rodar(["git", "pull", "--rebase", "-q", "origin", "main"])
        if ok_pull == 0:
            ok_push, saida = rodar(["git", "push", "-q", "origin", "main"])
            if ok_push == 0:
                return True, "estado publicado"
        time.sleep(4)
    return False, "não consegui publicar o estado"


def main(argv):
    pulsos = 30
    intervalo = 600
    if "--pulsos" in argv:
        pulsos = int(argv[argv.index("--pulsos") + 1])
    if "--intervalo" in argv:
        intervalo = int(argv[argv.index("--intervalo") + 1])

    print("bloco contínuo: até %d pulsos, %ds entre eles (%.1f h)"
          % (pulsos, intervalo, pulsos * intervalo / 3600.0))

    for i in range(1, pulsos + 1):
        if os.path.exists(PARAR):
            print("botão de parar encontrado (posts/PARAR) — encerrando o bloco")
            return 0
        inicio = time.time()
        codigo, saida = rodar([sys.executable, "tools/orquestrador.py"])
        print("--- pulso %d/%d (código %d)" % (i, pulsos, codigo))
        print(saida)
        rodar([sys.executable, "tools/memoria.py"])
        ok, msg = commitar("#%d" % i)
        print("estado: %s" % msg)
        if i == pulsos:
            break
        espera = max(0, intervalo - (time.time() - inicio))
        time.sleep(espera)
    print("bloco encerrado")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
