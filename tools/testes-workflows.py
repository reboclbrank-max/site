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


def passos_com_tee(fonte):
    """Passos que mandam a saída de um script da casa para `| tee` e o que os protege.

    DEFEITO MEDIDO (06/11/2026, runs 42312905574 e 42312907718): `python3 tools/enviar-youtube.py
    ... | tee` devolve o status do TEE, não o do envio. O PRANCHETA recusou ("porta fechada"),
    o CEIFALUME recusou ("vídeo idêntico já publicado") e os DOIS runs ficaram VERDES — exatamente
    a mentira que a regra "falha de envio nunca vira sucesso" proíbe. O enviar-itch.yml já tinha
    apanhado disso em 31/10/2026; os outros não.
    """
    linhas = fonte.split("\n")
    achados = []
    for i, linha in enumerate(linhas):
        if not re.search(r"python3 tools/[\w.-]+\.py.*\|\s*tee", linha) or "|| true" in linha:
            continue
        ini = next((j for j in range(i, -1, -1) if re.match(r"^\s*-\s+name:", linhas[j])), None)
        if ini is None:
            achados.append((linha.strip(), False))
            continue
        fim = ini + 1
        while fim < len(linhas) and not re.match(r"^\s*-\s+(name|uses):", linhas[fim]):
            fim += 1
        corpo = "\n".join(linhas[ini:fim])
        # `shell: bash -o pipefail {0}` NÃO basta: sem `-e` o bash segue depois da pipeline que
        # falhou e o passo termina com o status do último comando (medido em 06/11/2026, run
        # 42313566675 — recusa "porta fechada" impressa no log e run VERDE). Precisa de -e.
        protegido = ("pipefail" in corpo
                     and ("-eo pipefail" in corpo or "-epipefail" in corpo
                          or re.search(r"-o\s+pipefail\s+-e", corpo) is not None
                          or re.search(r"set\s+-e", corpo) is not None
                          or re.search(r"set\s+-[a-z]*e[a-z]*\s+-o\s+pipefail", corpo) is not None))
        achados.append((linha.strip(), bool(protegido)))
    return achados


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
    # 7b. BINÁRIO NÃO ENTRA NO GIT (06/11/2026). Os workflows de gravação commitavam o .mp4 de
    #     cada tomada: 4 por dia no CEIFALUME (≈9 MB) e 3 no PRANCHETA. O repositório chegou a
    #     325 MB de histórico e crescia ~40 MB/dia. O vídeo só é necessário DURANTE o run que o
    #     produziu (é ele que envia); o artefato guarda o arquivo. Este contrato impede a volta.
    import re as _re
    commitam_video = []
    for nome, texto in wfs.items():
        for linha in texto.splitlines():
            if "git add" in linha and _re.search(r"\.(mp4|webm|mov|mkv)\b", linha):
                commitam_video.append(nome)
                break
    ok("NENHUM workflow commita vídeo no main (binário vai como artefato)", not commitam_video,
       commitam_video)
    guardam = [n for n, t in wfs.items() if "upload-artifact" in t and "media/gameplay" in t]
    ok("os workflows de gravação guardam o vídeo como artefato", len(guardam) >= 2, guardam)
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

    # PIPE: nenhum passo esconde o código de saída atrás de `| tee`
    for nome, fonte in fontes().items():
        for linha, protegido in passos_com_tee(fonte):
            ok("%s: `| tee` não engole o código de saída (%s)" % (nome, linha[:44]), protegido,
               "sem pipefail no passo")

    # ENTREGA × STASH: gravar é inútil se o commit levar o vídeo junto
    for nome, fonte in fontes().items():
        # só vale para quem GRAVA e ENTrega um vídeo (os outros podem dar stash à vontade)
        if "git stash push -u" not in fonte or "upload-artifact" not in fonte \
                or re.search(r"media/gameplay/[\w.-]+\.mp4", fonte) is None:
            continue
        ok("%s: guarda o vídeo da entrega antes do stash" % nome, "/tmp/entrega" in fonte)
        ok("%s: devolve o vídeo depois do push" % nome,
           "cp \"$f\" \"media/gameplay/" in fonte)
        ok("%s: falha se o vídeo final sumir depois do commit" % nome,
           re.search(r"test\s+-s\s+media/gameplay/[\w.-]+\.mp4", fonte) is not None)

    # O CI QUE DIZ "TODAS AS SUÍTES" PRECISA DAS FERRAMENTAS (06/11/2026): o run 42318964201
    # reprovou 6 de 52 — todas por falta de Pillow ou de navegador. Workflow que roda a bateria
    # inteira instala o que a bateria mede, senão o verde é do que pulou.
    for nome, fonte in fontes().items():
        if "rodar-todas-as-suites.py" not in fonte:
            continue
        for ferramenta, marca in (("Pillow", "Pillow"),
                                  ("navegador do Node (gravador)", "playwright-core"),
                                  ("navegador do Python (suítes)", "python3 -m playwright install")):
            ok("%s: instala %s antes de rodar a bateria" % (nome, ferramenta),
               marca in fonte)

    # O MEDIDOR CONFERE O REGISTRO CONTRA O CANAL (07/11/2026)
    for nome, fonte in fontes().items():
        if "metricas-youtube.py" not in fonte:
            continue
        ok("%s: confere o registro do canal contra o que está no ar" % nome,
           "registro-do-vivo.py" in fonte)
        ok("%s: versiona o registro depois de conferir" % nome,
           "git add posts/youtube-publicados.json" in fonte)

    # O REGISTRO DA CAPA É COMMITADO (06/11/2026): quem envia capa anota em
    # posts/capas-aplicadas.json; se o passo de commit esquece esse arquivo, a anotação morre no
    # stash do fim do run e a ferramenta das capas repinta o que já estava pintado.
    for nome, fonte in fontes().items():
        if "enviar-youtube.py" not in fonte or "Registra o que foi publicado" not in fonte:
            continue
        ok("%s: o commit do envio versiona o registro de capas" % nome,
           "git add posts/capas-aplicadas.json" in fonte)

    # ---- CICLOS CONTIDOS TÊM A DECISÃO ESCRITA (07/11/2026) ---------------------------
    # O dono pediu decisão sobre dois ciclos parados desde 03/11. Medido: a agenda dos dois saiu
    # em `d2ded0a` (PR #7, "fase 0: contenção segura") — não "parou de funcionar", foi contida.
    # Decidido: NÃO voltam a ter agenda (o pulso 24h cobre o papel). O que este contrato impede é
    # o pior dos dois mundos: ficar sem agenda e sem explicação, e alguém "consertar" isso
    # recolocando um cron que a contenção tirou.
    for nome, marca in (("postagem-diaria.yml", "MORTO COMO AGENDA"),
                        ("marketing-continuo.yml", "NÃO revive a agenda")):
        fonte = fontes().get(nome, "")
        ok("%s: existe" % nome, bool(fonte))
        _gatilhos = fonte.split("permissions:")[0]
        ok("%s: não tem agenda (decisão medida, não esquecimento)" % nome,
           "schedule:" not in _gatilhos and "cron:" not in _gatilhos, _gatilhos[-160:])
        ok("%s: a decisão está escrita no arquivo, com o commit que a tomou" % nome,
           marca in fonte and "d2ded0a" in fonte,
           marca if marca not in fonte else "sem d2ded0a")
        ok("%s: exige a palavra do dono" % nome, "PUBLICAR" in fonte)

    # O bloco contínuo não pode chamar de falha o pulso que dormiu: foi isso que pintou de
    # vermelho 4 runs seguidos que tinham feito a coisa certa.
    _loop = open(os.path.join(RAIZ, "tools", "loop-24h.py"), encoding="utf-8").read()
    ok("o bloco contínuo perdoa o pulso que dormiu de propósito", "not dormiu" in _loop)

    # E a gravação de gameplay precisa nascer DENTRO da janela, senão o vídeo nunca pode sair.
    _gameplay = fontes().get("gravar-gameplay.yml", "")
    _horas = []
    for linha in _gameplay.splitlines():
        if linha.strip().startswith("- cron:"):
            _horas += [int(h) for h in linha.split('"')[1].split()[1].split(",")]
    ok("as gravações de gameplay nascem dentro da janela (9-22h de Brasília)",
       _horas and all(12 <= h <= 22 for h in _horas), _horas)
    ok("sobrou gravação de madrugada? (04h e 22h de Brasília eram inúteis)",
       all(h not in (7,) for h in _horas), _horas)

    # ---- A RÉGUA DE METAS TEM QUEM A ESCREVA (07/11/2026) -----------------------------
    # Medido: posts/placar-metas.md parado em 03/11 06:52Z ("9 dias restantes" quando faltavam 5).
    # O único workflow que COMMITAVA a medição era o postagem-diaria, cuja agenda saiu na
    # contenção. O diagnostico-da-casa mede, mas não tinha agenda nem commit — e o pulso seguia
    # decidindo com números de 03/11.
    _diag = fontes().get("medir-o-dia.yml", "")
    ok("existe um workflow com o papel de escrever a régua", bool(_diag), list(fontes())[:3])
    _gatilhos_diag = _diag.split("permissions:")[0]
    _crons_diag = [l.split('"')[1] for l in _gatilhos_diag.splitlines() if l.strip().startswith("- cron:")]
    ok("medir-o-dia tem agenda (a régua não fica sem quem a escreva)", bool(_crons_diag),
       _crons_diag)
    _horas_diag = []
    for _c in _crons_diag:
        _horas_diag += [int(x) for x in _c.split()[1].split(",") if x.isdigit()]
    ok("a medição do dia roda dentro da janela (9-22h de Brasília)",
       _horas_diag and all(12 <= h <= 22 for h in _horas_diag), _horas_diag)
    ok("medir-o-dia pode escrever no repositório (é o papel dele)",
       "contents: write" in _diag, [l for l in _diag.splitlines() if "contents:" in l])
    ok("diagnostico-da-casa continua só-leitura (não virou escritor de passagem)",
       "contents: read" in fontes().get("diagnostico-da-casa.yml", ""))
    ok("diagnostico-da-casa ganhou as ferramentas que as suítes pedem (Pillow)",
       "Pillow" in fontes().get("diagnostico-da-casa.yml", ""))
    ok("medir-o-dia versiona a régua de metas", "git add posts/placar-metas.md" in _diag)
    ok("medir-o-dia versiona o placar em JSON (é dele que o pulso lê o prazo)",
       "posts/placar-metas.json" in _diag.split("Versiona a medição")[-1],
       [l.strip() for l in _diag.splitlines() if "git add" in l])
    ok("o commit da medição entra pelo entrar-no-main (sem push seco)",
       "entrar-no-main.sh" in _diag.split("Versiona a medição")[-1])
    ok("o commit da medição só acontece quando algo mudou",
       "git diff --cached --quiet" in _diag.split("Versiona a medição")[-1])
    # O COMMIT DA MEDIÇÃO TAMBÉM PRECISA DOS SEGREDOS: o entrar-no-main re-roda o gerador no
    # merge, e sem segredos essa segunda rodada escrevia NAO_OBSERVAVEL sobre os números lidos.
    _passo_commit = _diag.split("Versiona a medição")[-1]
    ok("o passo que commita a medição leva os segredos (o merge re-roda o gerador)",
       all(chave in _passo_commit for chave in ("IG_TOKEN", "YT_API_KEY", "ITCH_API_KEYS")),
       [c for c in ("IG_TOKEN", "YT_API_KEY", "ITCH_API_KEYS") if c not in _passo_commit])
    ok("a régua pior que a atual é recusada (não vira NAO_OBSERVAVEL em cima de número)",
       "manter_regua(" in open(os.path.join(RAIZ, "tools", "metricas.py"), encoding="utf-8").read())

    ok("a medição deixa carimbo de quando foi medida (posts/placar-estado.json)",
       "placar-estado.json" in open(os.path.join(RAIZ, "tools", "metricas.py"),
                                    encoding="utf-8").read())
    ok("o estado da casa lê o carimbo da régua",
       "placar-estado.json" in open(os.path.join(RAIZ, "tools", "estado-da-casa.py"),
                                    encoding="utf-8").read())

    # ---- PRANCHETA TAMBÉM NASCE DENTRO DA JANELA (07/11/2026) --------------------------
    # Mesmo defeito do gravar-gameplay: "50 2,10,18" = 07:50, 12:50 e 22:50 de Brasília; as duas
    # pontas fora da janela 9-22h.
    _prancheta = fontes().get("gravar-prancheta.yml", "")
    _horas_pr = []
    for _linha in _prancheta.splitlines():
        if _linha.strip().startswith("- cron:"):
            _horas_pr += [int(h) for h in _linha.split('"')[1].split()[1].split(",")]
    ok("as gravações da prancheta nascem dentro da janela", _horas_pr and
       all(12 <= h <= 22 for h in _horas_pr), _horas_pr)
    ok("nada de prancheta às 07:50 nem às 22:50 de Brasília",
       not any((h - 3) % 24 in (7, 23) for h in _horas_pr), _horas_pr)

    print("\n%d/%d verificações de higiene de workflow passaram"
          % (len(certos), len(certos) + len(falhas)))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
