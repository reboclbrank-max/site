#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guarda da higiene dos workflows: 32 arquivos é gente demais para conferir no olho.

POR QUE EXISTE (30/10/2026): os defeitos que mais custaram nesta casa não estavam no jogo, e sim
no encanamento dos runs:
  * `git push` seco derrubou o PRANCHETA (run 41030633953) com o vídeo gravado e fora do repo;
  * três tentativas de push falhando e o run terminando VERDE (run 41090257198);
  * `metricas-youtube` fazia push seco — o mesmo defeito, esperando a vez;
  * dois workflows sem `timeout-minutes` (um run travado pode segurar a fila por horas);
  * vinte sem `concurrency` (dois runs do mesmo fluxo disputam o mesmo JSON e o mesmo push).

Este teste é estático e roda em segundos: ele não executa workflow nenhum.
"""
import glob
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, ".github", "workflows")

certos, falhas = [], []


def ok(nome, condicao, detalhe=""):
    if condicao:
        certos.append(nome)
        print("OK  " + nome)
    else:
        falhas.append((nome, detalhe))
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe else ""))


def fontes():
    return {os.path.basename(f): open(f, encoding="utf-8").read()
            for f in sorted(glob.glob(os.path.join(PASTA, "*.yml")))}


def main():
    wfs = fontes()
    ok("os workflows foram lidos", len(wfs) >= 20, len(wfs))
    # O YAML é analisado sem executar scripts: parâmetros de workflow_dispatch
    # entram via env, nunca como fragmentos de shell que o Bash interpreta.
    import yaml as _yaml_entradas
    diretos = []
    padrao = re.compile(r"\$\{\{\s*(?:inputs|github\.event\.inputs)\.")
    for nome, fonte in wfs.items():
        doc = _yaml_entradas.safe_load(fonte) or {}
        for trabalho in (doc.get("jobs") or {}).values():
            for passo in (trabalho.get("steps") or []):
                corpo = passo.get("run") or ""
                if padrao.search(corpo):
                    diretos.append((nome, passo.get("name", "sem nome")))
    ok("inputs de workflow nao entram diretamente em shell", not diretos, diretos)
    ok("detector de injecao reprova fixture",
       bool(padrao.search('echo "' + '${' + '{ inputs.texto }}' + '"')))


    # 1. Push tem que sobreviver a outro commit no main e NUNCA falhar calado.
    secos = [n for n, s in wfs.items()
             if re.search(r"^\s*git push\s*$", s, re.M)]
    ok("nenhum workflow faz push seco", not secos, secos)
    sem_trava = [n for n, s in wfs.items()
                 if re.search(r"^\s*git push", s, re.M)
                 and "enviado=0" not in s]
    ok("todo workflow que empurra diz se o push entrou (e falha se não)", not sem_trava, sem_trava)
    sem_erro = [n for n, s in wfs.items()
                if re.search(r"^\s*git push", s, re.M) and "::error::" not in s]
    ok("todo workflow que empurra tem erro explícito no fim", not sem_erro, sem_erro)

    # 2. Trava de tempo: um run travado não pode segurar a fila.
    sem_timeout = [n for n, s in wfs.items() if "timeout-minutes" not in s]
    ok("todo workflow tem timeout-minutes", not sem_timeout, sem_timeout)

    # 3. Um run por fluxo por vez (dois ao mesmo tempo disputam o mesmo JSON e o mesmo push).
    sem_conc = [n for n, s in wfs.items() if "concurrency:" not in s]
    ok("todo workflow tem concurrency", not sem_conc, sem_conc)
    sem_grupo = [n for n, s in wfs.items()
                 if "concurrency:" in s and not re.search(r"concurrency:\s*\n\s*group:\s*\S+", s)]
    ok("o concurrency tem grupo nomeado", not sem_grupo, sem_grupo)

    # 4. Suíte órfã: teste que nada executa não protege nada.
    suites = [os.path.basename(f) for f in glob.glob(os.path.join(RAIZ, "tools", "testes-*"))
              if f.endswith((".py", ".js"))]
    juntos = "\n".join(wfs.values())
    orfas = [s for s in suites if s not in juntos]
    ok("toda suíte de teste é executada por algum workflow", not orfas, orfas)
    ok("há suíte suficiente para valer a pena o guarda", len(suites) >= 15, len(suites))

    # 5. Nada de segredo em texto claro no YAML (os valores vêm de secrets).
    vazados = []
    for nome, texto in wfs.items():
        for linha in texto.splitlines():
            if re.search(r"(API_KEY|TOKEN|COOKIE|SECRET)\s*[:=]\s*[A-Za-z0-9_\-]{20,}", linha):
                vazados.append("%s: %s" % (nome, linha.strip()[:60]))
    ok("nenhum segredo escrito no workflow", not vazados, vazados)

    # 6. Cron só em fluxo que faz sentido repetir (sondagem é de uma vez).
    cron_sondagem = [n for n, s in wfs.items()
                     if n.startswith(("sondar-", "provar-")) and re.search(r"^\s*-\s*cron:", s, re.M)]
    ok("sondagem não fica em cron", not cron_sondagem, cron_sondagem)

    # 7. Quem escreve no main e REGERA arquivo usa o ajudante que sabe fazer merge.
    #    MEDIDO (31/10/2026, runs 41128039668 e 41128399021): laço de rebase parava em conflito
    #    todas as vezes que dois escritores regeravam o mesmo arquivo, e o run ficava vermelho
    #    com o log do ciclo preso dentro dele.
    escrevem = [n for n, s in wfs.items() if "git push" in s or "entrar-no-main.sh" in s]
    sem_ajudante = [n for n in escrevem if "entrar-no-main.sh" not in wfs[n]
                    and not n.startswith(("gravar-", "editar-itch"))]
    ok("todo workflow que escreve no main usa o entrar-no-main (gravar-* manda binário e não "
       "conflita em arquivo gerado)", not sem_ajudante, sem_ajudante)
    ajudante = os.path.join(RAIZ, "tools", "entrar-no-main.sh")
    ok("o ajudante existe e é executável", os.path.exists(ajudante) and os.access(ajudante, os.X_OK))
    texto_ajudante = open(ajudante, encoding="utf-8").read() if os.path.exists(ajudante) else ""
    ok("o ajudante recusa conflito em arquivo que não é gerado",
       "git merge --abort" in texto_ajudante and "GERADOS=" in texto_ajudante)
    ok("o ciclo diário não voltou ao laço de rebase cego",
       "for tentativa in 1 2 3" not in wfs.get("postagem-diaria.yml", ""))
    ok("o relatório de pendências usa o ajudante",
       "entrar-no-main.sh" in wfs.get("pendencias-do-dono.yml", ""))
    ok("as métricas do YouTube usam o ajudante",
       "entrar-no-main.sh" in wfs.get("metricas-youtube.yml", ""))
    ok("o pulso 24h usa o ajudante", "entrar-no-main.sh" in wfs.get("marketing-24h.yml", ""))
    ok("o ciclo diário cobra o teste do ajudante",
       "testes-entrar-no-main.py" in wfs.get("postagem-diaria.yml", ""))
    ok("o diagnóstico da casa cobra o teste do ajudante",
       "testes-entrar-no-main.py" in wfs.get("diagnostico-da-casa.yml", ""))

    # 8. O `run:` de cada passo precisa ser shell VÁLIDO. Sintaxe quebrada só aparece quando o
    #    run dispara — e aí já custou um ciclo. `bash -n` lê sem executar.
    import glob as _glob, subprocess as _sp, yaml as _yaml
    quebrados = []
    for arquivo in sorted(_glob.glob(os.path.join(PASTA, "*.yml"))):
        try:
            doc = _yaml.safe_load(open(arquivo, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            quebrados.append("%s: YAML inválido (%s)" % (os.path.basename(arquivo), str(e)[:60]))
            continue
        for trabalho in (doc.get("jobs") or {}).values():
            for passo in trabalho.get("steps") or []:
                corpo = passo.get("run")
                if not isinstance(corpo, str):
                    continue
                # `${{ ... }}` é do GitHub, não do bash: troca por um valor inofensivo.
                corpo = re.sub(r"\$\{\{[^}]*\}\}", "X", corpo)
                r = _sp.run(["bash", "-n", "-c", corpo], capture_output=True, text=True)
                if r.returncode != 0:
                    quebrados.append("%s / %s: %s" % (
                        os.path.basename(arquivo), passo.get("name"), r.stderr.strip()[:80]))
    ok("todo bloco run: dos workflows é shell válido (bash -n)", not quebrados, quebrados)

    # 9. Imutabilidade dos steps: uma tag móvel pode apontar para outro código no
    # próximo cron, inclusive num workflow que tem acesso a credenciais.
    def referencia_imutavel(ref):
        if ref.startswith("./"):
            return True  # Ação local está no mesmo commit do checkout.
        if ref.startswith("docker://"):
            return bool(re.fullmatch(r"docker://[^\s@]+@sha256:[0-9a-f]{64}", ref))
        return bool(re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+@[0-9a-f]{40}", ref))

    ok("validador distingue commit fixo de tag móvel",
       referencia_imutavel("actions/setup-node@" + "a" * 40)
       and referencia_imutavel("./.github/actions/minha-acao")
       and not referencia_imutavel("actions/setup-node@v4")
       and not referencia_imutavel("actions/upload-artifact@main")
       and not referencia_imutavel("docker://exemplo/imagem:latest"))

    ok("scanner identifica uses aninhado ou em passo direto",
       bool(re.match(r"^\s*(?:-\s*)?uses:\s*(\S+)",
                     "        uses: actions/setup-node@v4"))
       and bool(re.match(r"^\s*(?:-\s*)?uses:\s*(\S+)",
                         "      - uses: actions/upload-artifact@v4")))

    referencias_moveis = []
    for nome, yaml_workflow in wfs.items():
        for numero_linha, linha in enumerate(yaml_workflow.splitlines(), 1):
            candidato = re.match(r"^\s*(?:-\s*)?uses:\s*(\S+)", linha)
            if candidato and not referencia_imutavel(candidato.group(1)):
                referencias_moveis.append("%s:%d (%s)" % (
                    nome, numero_linha, candidato.group(1)))
    ok("todas as Actions e workflows reutilizáveis apontam para SHA imutável",
       not referencias_moveis, referencias_moveis)

    print("\n%d/%d verificações de higiene de workflow passaram"
          % (len(certos), len(certos) + len(falhas)))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
