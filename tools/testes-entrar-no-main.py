#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova que tools/entrar-no-main.sh entra no main nos três casos que importam.

Medido em 31/10/2026: os sete workflows que escrevem no main usavam "rebase e tenta de novo", e
o rebase para quando os dois lados REgeram o mesmo arquivo (marketing.html, publicacoes.json,
posts/log.md). Dois runs seguidos do ciclo das 21h ficaram vermelhos assim
(41128039668, 41128399021) com o log do ciclo preso dentro do run.

Os três casos, todos medidos aqui com repositórios de verdade em diretório temporário:
  1. main andou, mas sem tocar no que eu toquei  → rebase/push, como antes;
  2. main andou e mexeu no MESMO arquivo gerado → merge, fica a versão do main, o gerador
     reescreve a partir da fonte, e o resultado final é o da fonte (não o do main nem o meu);
  3. main andou e mexeu num arquivo que NÃO é gerado → recusa, desfaz o merge e sai com 1,
     sem sobrescrever ninguém e sem deixar o repositório no meio de um merge.
"""
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SCRIPT = os.path.join(AQUI, "entrar-no-main.sh")

TOTAL, FALHAS = [], []


def ok(descricao, condicao, detalhe=""):
    TOTAL.append(descricao)
    if condicao:
        print("OK  " + descricao)
        return True
    FALHAS.append(descricao)
    print("FALHOU  " + descricao + ("  <" + str(detalhe)[:220] + ">" if detalhe else ""))
    return False


def git(repo, *args, env=None, check=False):
    ambiente = dict(os.environ)
    ambiente.update({"GIT_AUTHOR_NAME": "teste", "GIT_AUTHOR_EMAIL": "t@local",
                     "GIT_COMMITTER_NAME": "teste", "GIT_COMMITTER_EMAIL": "t@local",
                     "GIT_TERMINAL_PROMPT": "0"})
    if env:
        ambiente.update(env)
    r = subprocess.run(["git"] + list(args), cwd=repo, capture_output=True, text=True,
                       env=ambiente)
    if check and r.returncode != 0:
        raise RuntimeError("git %s falhou: %s" % (" ".join(args), r.stderr[-400:]))
    return r


def escrever(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def montar(tmp):
    """origin + dois clones (a = o run, b = o outro escritor)."""
    origin = os.path.join(tmp, "origin.git")
    git(tmp, "init", "-q", "--bare", "-b", "main", origin, check=True)
    a = os.path.join(tmp, "a")
    b = os.path.join(tmp, "b")
    git(tmp, "init", "-q", "-b", "main", a, check=True)
    git(a, "remote", "add", "origin", origin, check=True)
    # fontes + gerados + código escrito à mão
    escrever(os.path.join(a, "posts", "fonte.json"), '{"n": 1}\n')
    escrever(os.path.join(a, "tools", "gerar.py"),
             "import json, sys\n"
             "n = json.load(open('posts/fonte.json'))['n']\n"
             "open('marketing.html','w').write('painel v%d\\n' % n)\n")
    escrever(os.path.join(a, "marketing.html"), "painel v1\n")
    escrever(os.path.join(a, "posts", "log.md"), "- ciclo 1\n")
    escrever(os.path.join(a, "tools", "codigo.py"), "x = 1\n")
    git(a, "add", "-A", check=True)
    git(a, "commit", "-q", "-m", "inicio", check=True)
    git(a, "push", "-q", "origin", "HEAD:main", check=True)
    git(tmp, "clone", "-q", origin, b, check=True)
    return origin, a, b


def outro_escritor(b, arquivo, texto, mensagem):
    escrever(os.path.join(b, arquivo), texto)
    git(b, "add", "-A", check=True)
    git(b, "commit", "-q", "-m", mensagem, check=True)
    git(b, "push", "-q", "origin", "HEAD:main", check=True)


def rodar_helper(a, gerar="python3 tools/gerar.py", tentativas="2"):
    ambiente = dict(os.environ, GERAR=gerar, TENTATIVAS=tentativas)
    return subprocess.run(["bash", SCRIPT, "run de teste"], cwd=a, capture_output=True,
                          text=True, env=ambiente, timeout=120)


def main():
    ok("o script existe", os.path.exists(SCRIPT))
    ok("o script não é um laço de rebase cego (fala em merge)",
       "git merge" in open(SCRIPT, encoding="utf-8").read())

    # ---------------------------------------------------------------- caso 1: rebase limpo
    tmp = tempfile.mkdtemp()
    try:
        _origin, a, b = montar(tmp)
        outro_escritor(b, "tools/outro.py", "y = 2\n", "outro escritor mexe em arquivo alheio")
        escrever(os.path.join(a, "posts", "log.md"), "- ciclo 1\n- ciclo 2\n")
        git(a, "add", "-A", check=True)
        git(a, "commit", "-q", "-m", "ciclo 2", check=True)
        r = rodar_helper(a)
        ok("caso 1: main andou sem tocar no meu arquivo → entra por rebase",
           r.returncode == 0 and "por rebase" in r.stdout, r.stdout + r.stderr)
        git(b, "fetch", "-q", "origin", "main", check=True)
        ok("caso 1: o commit do outro escritor não foi perdido",
           "outro.py" in git(b, "ls-tree", "-r", "--name-only", "origin/main").stdout)
        ok("caso 1: o meu ciclo também está no main",
           "ciclo 2" in git(b, "show", "origin/main:posts/log.md").stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --------------------------------------- caso 2: conflito em arquivo GERADO é resolvido
    tmp = tempfile.mkdtemp()
    try:
        _origin, a, b = montar(tmp)
        # o outro escritor muda a FONTE e o gerado a partir dela
        escrever(os.path.join(b, "posts", "fonte.json"), '{"n": 2}\n')
        outro_escritor(b, "marketing.html", "painel v2\n", "outro escritor regerou o painel")
        # eu mexo no log E regero o painel com a MINHA fonte (que ainda diz 1) — é exatamente
        # o que um run faz: o gerado dele sai diferente do gerado do outro escritor
        escrever(os.path.join(a, "posts", "log.md"), "- ciclo 1\n- ciclo 2\n")
        escrever(os.path.join(a, "marketing.html"), "painel v1 (meu run)\n")
        git(a, "add", "-A", check=True)
        git(a, "commit", "-q", "-m", "ciclo 2", check=True)
        r = rodar_helper(a)
        ok("caso 2: entra no main mesmo com conflito em arquivo gerado",
           r.returncode == 0, r.stdout + r.stderr)
        ok("caso 2: o caminho usado foi o merge (rebase pararia no conflito do gerado)",
           "merge" in r.stdout, r.stdout)
        git(b, "fetch", "-q", "origin", "main", check=True)
        painel = git(b, "show", "origin/main:marketing.html").stdout
        fonte = git(b, "show", "origin/main:posts/fonte.json").stdout
        ok("caso 2: a fonte do outro escritor sobreviveu", '"n": 2' in fonte, fonte)
        ok("caso 2: o gerado final é o da FONTE (v2), não o meu (v1)", "painel v2" in painel,
           painel)
        ok("caso 2: o meu trabalho também entrou",
           "ciclo 2" in git(b, "show", "origin/main:posts/log.md").stdout)
        ok("caso 2: nada de arquivo .orig/.rej sobrando no main",
           ".orig" not in git(b, "ls-tree", "-r", "--name-only", "origin/main").stdout)
        ok("caso 2: sem merge pendente no meu clone",
           not os.path.exists(os.path.join(a, ".git", "MERGE_HEAD")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------ caso 3: conflito em arquivo NÃO gerado é recusado, não chutado
    tmp = tempfile.mkdtemp()
    try:
        _origin, a, b = montar(tmp)
        outro_escritor(b, "tools/codigo.py", "x = 2  # do outro\n", "outro escritor muda o código")
        escrever(os.path.join(a, "tools", "codigo.py"), "x = 3  # meu\n")
        git(a, "add", "-A", check=True)
        git(a, "commit", "-q", "-m", "meu código", check=True)
        _meu = git(a, "rev-parse", "HEAD").stdout.strip()
        r = rodar_helper(a)
        ok("caso 3: recusa entrar no main com conflito em código",
           r.returncode == 1, r.stdout + r.stderr)
        ok("caso 3: diz QUAL arquivo impediu", "tools/codigo.py" in r.stdout, r.stdout)
        ok("caso 3: o código do outro escritor continua no main (nada sobrescrito)",
           "do outro" in git(b, "show", "origin/main:tools/codigo.py").stdout)
        ok("caso 3: o meu clone não fica no meio de um merge",
           not os.path.exists(os.path.join(a, ".git", "MERGE_HEAD")))
        ok("caso 3: o meu commit continua aqui (nada foi perdido)",
           git(a, "rev-parse", "HEAD").stdout.strip() == _meu)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---------------------------------------------------------------- higiene do script
    fonte = open(SCRIPT, encoding="utf-8").read()
    ok("o script roda com 'set -uo pipefail' (erro não passa verde)", "set -uo pipefail" in fonte)
    ok("o script desfaz o merge quando recusa", "git merge --abort" in fonte)
    ok("o script resolve só caminho declarado como gerado", "GERADOS=" in fonte
       and "posts/[^/]+" in fonte)
    ok("o script tem teto de tentativas", "TENTATIVAS" in fonte)

    print()
    if FALHAS:
        print("%d de %d verificações do entrar-no-main FALHARAM" % (len(FALHAS), len(TOTAL)))
        sys.exit(1)
    print("%d/%d verificações do entrar-no-main passaram" % (len(TOTAL), len(TOTAL)))


if __name__ == "__main__":
    main()
