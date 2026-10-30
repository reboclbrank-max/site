#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Higiene de media/: nada de artefato intermediário versionado, nada de arquivo órfão.

POR QUE EXISTE (30/10/2026): o repositório tinha 9,7 MB de vídeo versionado que ninguém lê —
`trecho-*.mp4` (pedaços que o produzir-video.py cria e apaga), `trilha.m4a` e `cartao.mp4`
(gerados a cada run). Commitar isso não acelera nada: todo cliente clona o arquivo e o CI
regenera por cima. O custo é clone mais lento e histórico pesado.

Este teste falha de dois jeitos, e os dois são recuperáveis:
  * artefato intermediário versionado  → `git rm --cached` + linha no .gitignore;
  * arquivo de mídia que nada cita     → apagar ou passar a citar.
"""
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Nomes que o pipeline gera durante o run. Se algum deles estiver versionado, é engano.
INTERMEDIARIOS = [
    r"^media/gameplay/trecho-\d+\.mp4$",
    r"^media/gameplay/cru-.*\.mp4$",
    r"^media/gameplay/.*-cru\.mp4$",
    r"^media/gameplay/cartao\.mp4$",
    r"^media/gameplay/trilha\.m4a$",
]

certos = []
falhas = []


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos.append(nome)
        print("OK  " + nome)
    else:
        falhas.append((nome, detalhe))
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe else ""))


def versionados():
    saida = subprocess.run(["git", "ls-files", "media"], cwd=RAIZ, capture_output=True, text=True)
    if saida.returncode != 0:      # fora do git (cópia sem .git): não é defeito
        return None
    return [l for l in saida.stdout.splitlines() if l.strip()]


def citado(nome_arquivo, fontes):
    base = os.path.basename(nome_arquivo)
    for caminho in fontes:
        try:
            with open(caminho, encoding="utf-8", errors="ignore") as f:
                if base in f.read():
                    return True
        except OSError:
            continue
    return False


def main():
    lista = versionados()
    if lista is None:
        print("○ fora do git: nada a conferir (o CI sempre roda dentro do repositório)")
        return 0

    pesados = [f for f in lista if os.path.getsize(os.path.join(RAIZ, f)) > 200_000]
    ok("a lista de mídia versionada foi lida", len(lista) > 0, lista)

    intermediarios = [f for f in lista
                      if any(re.match(p, f) for p in INTERMEDIARIOS)]
    ok("nenhum artefato intermediário de vídeo está versionado", not intermediarios,
       "versionados: %s" % intermediarios)

    # Órfão: arquivo pesado de mídia que nenhum código, página ou workflow cita.
    fontes = []
    for pasta, extensoes in (("tools", (".py", ".js")), ("", (".html",))):
        raiz_pasta = os.path.join(RAIZ, pasta) if pasta else RAIZ
        for nome in os.listdir(raiz_pasta):
            if nome.endswith(extensoes) and os.path.isfile(os.path.join(raiz_pasta, nome)):
                fontes.append(os.path.join(raiz_pasta, nome))
    for pasta in ("jogos", "blog"):
        base = os.path.join(RAIZ, pasta)
        if os.path.isdir(base):
            for sub, _d, arquivos in os.walk(base):
                fontes += [os.path.join(sub, a) for a in arquivos if a.endswith(".html")]
    base_wf = os.path.join(RAIZ, ".github", "workflows")
    if os.path.isdir(base_wf):
        fontes += [os.path.join(base_wf, a) for a in os.listdir(base_wf) if a.endswith(".yml")]

    orfaos = [f for f in pesados if not citado(f, fontes)]
    ok("nenhum arquivo de mídia pesado está órfão (nada cita)", not orfaos,
       "sem citação: %s" % orfaos)

    # O que NÃO pode ser ignorado: o vídeo que o site e o kit entregam.
    for obrigatorio in ("media/gameplay/ceifalume-gameplay-instrucoes.mp4",
                        "media/gameplay/ceifalume-gameplay.mp4"):
        ok("o vídeo entregue continua versionado: " + os.path.basename(obrigatorio),
           obrigatorio in lista, "sumiu do git")

    with open(os.path.join(RAIZ, ".gitignore"), encoding="utf-8") as f:
        ignorados = f.read()
    ok("o .gitignore impede o artefato de voltar", "media/gameplay/trecho-*.mp4" in ignorados
       and "media/gameplay/trilha.m4a" in ignorados, "regra ausente")

    # Dependência de runtime não se versiona: quem precisa instala (os dois workflows de gravação
    # rodam `npm install --no-save playwright-core@1`). 14 MB e 117 arquivos saíram do git em
    # 30/10 por isso.
    no_git = subprocess.run(["git", "ls-files", "node_modules"], cwd=RAIZ,
                            capture_output=True, text=True)
    ok("nenhuma dependência de runtime versionada (node_modules)",
       not (no_git.stdout or "").strip(), "arquivos: %d" % len((no_git.stdout or "").split()))
    ok("o .gitignore barra o node_modules de voltar", "node_modules/" in ignorados)
    ok("os dois workflows que usam navegador instalam a dependência",
       "npm install" in open(os.path.join(base_wf, "gravar-gameplay.yml"), encoding="utf-8").read()
       and "npm install" in open(os.path.join(base_wf, "gravar-prancheta.yml"), encoding="utf-8").read(),
       "workflow sem npm install")

    print("\n%d/%d verificações de higiene de media passaram" % (len(certos), len(certos) + len(falhas)))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
