#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O que acontece quando o dono mexe em algo — gerado dos workflows, nunca escrito à mão.

POR QUE EXISTE (07/11/2026): o dono perguntou "o que vai acontecer quando eu atualizar um jogo ou
mudar algo?" e a resposta honesta exigia medir 41 workflows: quais rodam no push, em que caminho,
que horas são em Brasília e qual deles tem cadeado. Isso é conta, não prosa. Escrito à mão, o
documento envelhece em silêncio — o `ESTADO-AGORA.md` de 26/10 ainda dizia 160 vídeos.

Cada linha vem do próprio arquivo do workflow: os gatilhos do bloco `on:`, as horas dos crons
(convertidas para Brasília pelo `auditar-agendas.py`) e a descrição do comentário do topo do
arquivo. Nada aqui é redigido por mim.

Uso:
    python3 tools/o-que-acontece.py             # reescreve O-QUE-ACONTECE.md
    python3 tools/o-que-acontece.py --conferir   # falha se o documento não bater com os workflows
"""
import ast
import glob
import json
import os
import re
import sys

import importlib.util


def _carregar_agendas():
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auditar-agendas.py")
    spec = importlib.util.spec_from_file_location("auditar_agendas", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


agendas = _carregar_agendas()

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "O-QUE-ACONTECE.md")
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _texto(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def _bloco_on(texto):
    """O bloco `on:` do workflow, sem os comentários — é o que o GitHub lê."""
    linhas = []
    dentro = False
    for linha in texto.splitlines():
        if re.match(r"^on:", linha):
            dentro = True
            continue
        if dentro and re.match(r"^[a-z]", linha):  # outra chave de topo
            break
        if dentro and not linha.strip().startswith("#"):
            linhas.append(linha)
    return "\n".join(linhas)


def descricao(texto, limite=150):
    """A primeira frase útil do comentário do topo do arquivo — do próprio arquivo, não minha."""
    comentarios = []
    for linha in texto.splitlines()[1:]:
        if linha.startswith("#"):
            comentarios.append(linha.lstrip("#").strip())
        elif comentarios or linha.startswith("name:"):
            if comentarios:
                break
            continue
        else:
            continue
    # manchete em caixa alta não descreve nada ("A RÉGUA DE METAS PRECISA DE QUEM A ESCREVA"):
    # pula as linhas que são quase todas maiúsculas e fica com a primeira que explica.
    def _grita(linha):
        letras = [c for c in linha if c.isalpha()]
        return len(letras) > 8 and sum(1 for c in letras if c.isupper()) > 0.7 * len(letras)

    comentarios = [c for c in comentarios if c and not _grita(c)]
    junto = " ".join(comentarios)
    junto = re.sub(r"^[^\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+", "", junto)  # tira emoji do começo
    if not junto:
        return "(sem comentário no topo do arquivo)"
    frase = re.split(r"(?<=[.!?])\s", junto)[0]
    if len(frase) < 25 and len(junto) > len(frase):
        frase = junto
    if len(frase) > limite:
        frase = frase[:limite].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return frase


def _gatilhos(texto):
    on = _bloco_on(texto)
    return {
        "push": bool(re.search(r"^\s+push:", on, re.M)) or bool(re.search(r"^push:", on, re.M)),
        "agenda": "schedule:" in on,
        "manual": "workflow_dispatch:" in on,
        "pr": "pull_request:" in on,
    }


def _caminhos_do_push(texto):
    """Os caminhos que disparam o push — lidos por indentação, que é como o YAML funciona.

    (Regex com lookahead errava aqui: `branches:` era confundido com o fim do bloco e o
    `paths:` do push ficava de fora.)
    """
    on = _bloco_on(texto)
    linhas = on.splitlines()
    comeco = None
    for i, linha in enumerate(linhas):
        if linha.strip() == "push:":
            comeco = i
            recuo = len(linha) - len(linha.lstrip())
            break
    if comeco is None:
        return []
    bloco = []
    for linha in linhas[comeco + 1:]:
        if not linha.strip():
            continue
        if len(linha) - len(linha.lstrip()) <= recuo:
            break
        bloco.append(linha)
    dentro_de_paths = False
    caminhos = []
    for linha in bloco:
        enxuto = linha.strip()
        if enxuto.startswith("paths:"):
            dentro_de_paths = True
            continue
        if enxuto.endswith(":") and not enxuto.startswith("-"):
            dentro_de_paths = False
            continue
        if dentro_de_paths and enxuto.startswith("-"):
            valor = enxuto[1:].strip().strip("\"'")
            if valor:
                caminhos.append(valor)
    return caminhos


def _cadeados(texto):
    """Os campos de confirmação e a palavra que pedem — lidos dos inputs, não adivinhados.

    A palavra importa: o campo chama `confirmacao` em quase todos, mas o que se digita é
    PUBLICAR, APLICAR ou ENSAIO, e é isso que o dono precisa saber.
    """
    on = _bloco_on(texto)
    linhas = on.splitlines()
    achados = []
    dentro = False
    atual, descricao = None, []

    def _fechar():
        if atual in ("confirmacao", "publicar", "confirmar"):
            junto = " ".join(descricao)
            # a palavra é a que o dono digita, e cada workflow tem a sua: PUBLICAR, APLICAR,
            # EDITAR, SONDAR, PRIVAR/APAGAR. Sai do texto da descrição, sem vocabulário fixo.
            palavras = [p for p in re.findall(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ]{4,12})\b", junto)]
            achado = {"campo": atual, "palavra": " / ".join(palavras)}
            if achado not in achados:
                achados.append(achado)

    for linha in linhas:
        enxuto = linha.strip()
        if not enxuto:
            continue
        recuo = len(linha) - len(linha.lstrip())
        if enxuto.startswith("inputs:"):
            dentro = True
            continue
        if not dentro:
            continue
        if recuo <= 2:
            _fechar()
            dentro = False
            continue
        if recuo == 6 and enxuto.endswith(":"):
            _fechar()
            atual, descricao = enxuto[:-1].strip(), []
        elif recuo > 6:
            if enxuto.startswith("description:"):
                descricao.append(enxuto.split(":", 1)[1].strip().strip("\"'"))
    _fechar()
    return achados


def projetos_do_itch(raiz=RAIZ):
    """O que o `administrar-itch.py` sabe administrar — lido do PROJETOS do próprio arquivo.

    O dono perguntou "se eu atualizar um jogo, o que acontece?". A resposta depende desta lista,
    então ela é lida do código, não escrita por mim aqui.
    """
    caminho = os.path.join(raiz, "tools", "administrar-itch.py")
    try:
        arvore = ast.parse(_texto(caminho))
    except (OSError, SyntaxError):
        return None
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(
                getattr(t, "id", None) == "PROJETOS" for t in no.targets):
            try:
                return ast.literal_eval(no.value)
            except ValueError:
                return None
    return None


def jogos_com_build_no_repositorio(raiz=RAIZ):
    """{nome: (pasta, nº de arquivos)} dos jogos cujo build web está versionado aqui.

    Build é pasta com `index.html` e mais que a página de venda. O `ceifalume/` da raiz é um
    build; `jogos/prancheta/` tem um `index.html` só — é a página que leva ao itch, não o jogo.
    """
    candidatos = []
    if os.path.isdir(os.path.join(raiz, "ceifalume")):
        candidatos.append(("ceifalume", os.path.join(raiz, "ceifalume")))
    for alvo in sorted(glob.glob(os.path.join(raiz, "jogos", "*"))):
        if os.path.isdir(alvo):
            candidatos.append((os.path.basename(alvo), alvo))
    achados = {}
    for nome, caminho in candidatos:
        arquivos = [c for c in glob.glob(os.path.join(caminho, "**", "*"), recursive=True)
                    if os.path.isfile(c)]
        if os.path.exists(os.path.join(caminho, "index.html")) and len(arquivos) > 3:
            achados[nome] = (os.path.relpath(caminho, raiz), len(arquivos))
    return achados


def levantar(raiz=RAIZ):
    dados = {"push": [], "todos": [], "manual_sem_agenda": []}
    for caminho in sorted(glob.glob(os.path.join(raiz, ".github/workflows/*.yml"))):
        texto = _texto(caminho)
        nome = os.path.basename(caminho)[:-4]
        g = _gatilhos(texto)
        item = {"nome": nome, "descricao": descricao(texto), "gatilhos": g,
                "caminhos": _caminhos_do_push(texto) if g["push"] else [],
                "cadeado": _cadeados(texto)}
        dados["todos"].append(item)
        if g["push"]:
            dados["push"].append(item)
        elif g["manual"] and not g["agenda"]:
            dados["manual_sem_agenda"].append(item)

    agenda = []
    for linha in agendas.auditar(raiz):
        desc = next((i["descricao"] for i in dados["todos"] if i["nome"] == linha["workflow"]), "")
        agenda.append(dict(linha, descricao=desc))
    agenda.sort(key=lambda l: (min(l["brasilia"]) if l["brasilia"] else 99, l["workflow"]))
    dados["agenda"] = agenda
    dados["resumo"] = agendas.resumo(raiz)
    dados["projetos_itch"] = projetos_do_itch(raiz)
    dados["builds"] = jogos_com_build_no_repositorio(raiz)
    pastas_de_jogo = [os.path.basename(c) for c in glob.glob(os.path.join(raiz, "jogos", "*"))
                      if os.path.isdir(c)]
    dados["jogos"] = sorted(set(pastas_de_jogo) | set(dados["builds"]))
    return dados


def _hora(h):
    return "%02dh" % h


def horas_compactas(horas):
    """[0, 6, 7, 12, 13, ..., 23] -> "00h, 06h, 07h, 12h–23h". Sequência longa vira faixa."""
    if not horas:
        return "—"
    pedacos, inicio, anterior = [], None, None
    for h in sorted(horas):
        if inicio is None:
            inicio = anterior = h
            continue
        if h == anterior + 1:
            anterior = h
            continue
        pedacos.append((inicio, anterior))
        inicio = anterior = h
    pedacos.append((inicio, anterior))
    partes = []
    for a, b in pedacos:
        if a == b:
            partes.append(_hora(a))
        elif b == a + 1:
            partes.append("%s, %s" % (_hora(a), _hora(b)))
        else:
            partes.append("%s–%s" % (_hora(a), _hora(b)))
    return ", ".join(partes)


def gerar(raiz=RAIZ):
    d = levantar(raiz)
    r = d["resumo"]
    l = []
    l.append("# O que acontece quando você mexe em algo")
    l.append("")
    l.append("Gerado por `tools/o-que-acontece.py` a partir dos **%d** arquivos de "
             "`.github/workflows/` — cada linha vem do próprio workflow, não da minha memória. "
             "O `conferir-tudo` falha se este documento deixar de bater com eles." % r["workflows"])
    l.append("")

    # 1. push
    l.append("## 1. Você deu push no `main`")
    l.append("")
    l.append("Todo push publica o site (GitHub Pages), sem exceção e sem depender de teste verde. "
             "Além do site, roda o que casa com o caminho tocado:")
    l.append("")
    l.append("| caminho tocado | roda | o que faz |")
    l.append("| --- | --- | --- |")
    cobertos = set()
    for item in d["push"]:
        for caminho in item["caminhos"] or ["(qualquer)"[:0] or "?"]:
            cobertos.add(caminho)
            l.append("| `%s` | `%s` | %s |" % (caminho, item["nome"], item["descricao"]))
    if not any(i["cadeado"] for i in d["push"]) and not d["push"]:
        l.append("| — | — | nenhum workflow roda no push |")
    l.append("")
    l.append("Uma ressalva medida (07/11/2026, run 42340117439): o deploy do Pages pode travar em "
             "`syncing_files` e morrer por timeout — foi o que aconteceu naquele run, e o push "
             "seguinte publicou tudo. Deploy do site falhando não estraga o repositório; o próximo "
             "push reenvia. Se o site parecer velho, confira o último `pages build and deploy`.")
    l.append("")
    l.append("**O que NÃO roda no push:** mexer em `ceifalume/`, `jogos/` ou nas páginas da raiz "
             "não dispara teste nenhum. O site publica igual; a bateria inteira (`conferir-tudo`) "
             "só é chamada quando o push toca `tools/`, `posts/` ou os próprios workflows. "
             "Se a dúvida é \"será que eu quebrei alguma coisa?\", rode "
             "`python3 tools/rodar-todas-as-suites.py` antes de empurrar.")
    l.append("")

    # 2. o dia
    l.append("## 2. O dia sem você tocar em nada (hora de Brasília)")
    l.append("")
    l.append("**%d disparos automáticos por dia**, em %d workflows com agenda — esse é o que o "
             "cron PEDE. O que o GitHub entrega é outra conta (abaixo)."
             % (r["disparos_por_dia"], r["workflows_com_agenda"]))
    # O QUE O CRON PEDE NÃO É O QUE ACONTECE (07/11/2026): medido na semana, 14 disparos/dia
    # contra 63 pedidos. Sem esta linha o documento acima seria agenda no papel.
    try:
        with open(os.path.join(raiz, "posts", "cadencia.json"), encoding="utf-8") as f:
            cadencia = json.load(f)
    except (OSError, ValueError):
        cadencia = {}
    if cadencia.get("linhas"):
        l.append("")
        l.append("**Entrega medida do agendador** (janela de %s dia(s), medido em %s): **%s/dia** "
                 "de %s pedidos. O pior caso é `%s`. O cron do GitHub é melhor esforço: para um "
                 "pulso de 20 em 20 minutos ele entrega uma fração, e é por isso que a casa "
                 "precisa de corrente, não de agenda."
                 % (cadencia.get("janela_dias"), cadencia.get("medido_em"),
                    cadencia.get("total_medido_por_dia"), cadencia.get("total_esperado_por_dia"),
                    (sorted([x for x in cadencia["linhas"] if x.get("entrega_pct") is not None],
                            key=lambda x: x["entrega_pct"]) or [{"workflow": "—"}])[0]["workflow"]))
    # A DESCRIÇÃO DO WORKFLOW NÃO PODE MENTIR SOZINHA (07/11/2026): o comentário do topo do
    # `marketing-24h` diz "45 pulsos/dia". É o que o cron PEDE. Ao lado de cada linha entra o
    # que foi ENTREGUE, medido — senão a tabela repete a promessa como se fosse fato.
    cadencia_por_workflow = {}
    for item in cadencia.get("linhas") or []:
        # Só entra quem tem medida COMPARÁVEL: workflow que nasceu dentro da janela mediria a
        # própria idade, não a entrega (a `corrente` aparecia como 0,0/dia no dia em que nasceu).
        if (item.get("workflow") and item.get("medido_por_dia") is not None
                and item.get("entrega_pct") is not None):
            cadencia_por_workflow[item["workflow"]] = item
    l.append("")
    l.append("| hora (Brasília) | workflow | o que faz |")
    l.append("| --- | --- | --- |")
    for linha in d["agenda"]:
        horas = linha["brasilia"]
        quando = "todas as horas" if len(horas) == 24 else horas_compactas(horas)
        fora = ""
        if linha["fora_da_janela"]:
            fora = " ⚠️ fora da janela: %s" % ", ".join(_hora(h) for h in linha["fora_da_janela"])
        entrega = ""
        medida = cadencia_por_workflow.get(linha["workflow"])
        if medida:
            pct = medida.get("entrega_pct")
            entrega = " — **entregou %s/dia** de %s pedidos%s" % (
                medida["medido_por_dia"], medida.get("esperado_por_dia"),
                "" if pct is None else " (%.1f%%)" % pct)
        l.append("| %s | `%s` | %s%s%s |" % (quando, linha["workflow"],
                                             linha["descricao"] or "—", entrega, fora))
    l.append("")
    l.append("⚠️ = o workflow roda fora da janela 9h–22h. Não é erro por si: medir de madrugada "
             "é legítimo; **publicar** de madrugada não é, e o portão recusa.")
    l.append("")

    # 3. cadeados
    l.append("## 3. Quem publica e quem só mede")
    l.append("")
    cadeados = [i for i in d["todos"] if i["cadeado"]]
    if cadeados:
        l.append("Estes só escrevem no mundo com a palavra digitada no campo de confirmação "
                 "(**%d** workflows):" % len(cadeados))
        l.append("")
        for i in cadeados:
            campos = []
            for c in i["cadeado"]:
                if c["palavra"]:
                    campos.append("`%s` = **%s**" % (c["campo"], c["palavra"]))
                else:
                    campos.append("`%s`" % c["campo"])
            l.append("- `%s` — %s" % (i["nome"], ", ".join(campos)))
        l.append("")
    l.append("O resto mede, grava ou registra — e o registro é o produto. Quando um run não "
             "consegue provar o que fez, ele termina em recusa com o motivo, nunca em sucesso.")
    l.append("")

    # 4. só sob demanda
    l.append("## 4. O que só roda quando você pede")
    l.append("")
    manuais = d["manual_sem_agenda"]
    l.append("**%d** workflows não têm agenda: nenhum dispara sozinho, todos dependem de "
             "Actions → Run workflow." % len(manuais))
    l.append("")
    linha, atual = [], 0
    for item in manuais:
        pedaco = "`%s`" % item["nome"]
        if atual + len(pedaco) > 100:
            l.append("- " + ", ".join(linha))
            linha, atual = [], 0
        linha.append(pedaco)
        atual += len(pedaco) + 2
    if linha:
        l.append("- " + ", ".join(linha))
    l.append("")

    # 5. o que depende de você
    l.append("## 5. O que depende de você (e o que sobe sozinho)")
    l.append("")
    projetos = d["projetos_itch"]
    builds = d["builds"]
    if projetos is None:
        l.append("_Não consegui ler a lista `PROJETOS` do `administrar-itch.py` — sem isso, "
                 "não afirmo quem sobe sozinho._")
    else:
        l.append("O `administrar-itch` conhece **%d** projeto(s): %s. Só esses recebem build "
                 "automaticamente (uma vez por dia, madrugada); o resto não sobe sozinho."
                 % (len(projetos), ", ".join("`%s`" % k for k in sorted(projetos))))
        l.append("")
        l.append("| jogo | build versionado aqui | sobe sozinho? |")
        l.append("| --- | --- | --- |")
        for nome in sorted(set(builds) | set(projetos) | set(d["jogos"])):
            pasta, quantos = builds.get(nome, (None, 0))
            onde = ("`%s` (%d arquivos)" % (pasta, quantos)) if pasta else "não (só a página em `jogos/%s/`)" % nome
            sobe = ("sim — `administrar-itch` de madrugada" if nome in projetos
                    else "**não** — atualizar é upload no itch")
            l.append("| `%s` | %s | %s |" % (nome, onde, sobe))
        l.append("")
        sem_build = [n for n in projetos if n not in builds]
        if sem_build:
            l.append("⚠️ `%s` está na lista de administração mas não tem build aqui: o robô não "
                     "tem o que empurrar." % "`, `".join(sem_build))
            l.append("")
    l.append("Para o jogo que sobe sozinho, a gravação automática filma **o build deste "
             "repositório**. Para o que não sobe (o PRANCHETA vive publicado no itch), a "
             "gravação filma **a página do itch** — logo, build novo só aparece lá depois de "
             "o dono subir.")
    l.append("")
    # O QUE A CASA JÁ SABE DO PRANCHETA (07/11/2026): o vigia lê o build servido pelo itch todo
    # dia e grava em posts/prancheta-build.json. Se o arquivo sumir, a linha some — nada de
    # afirmar build que ninguém mediu.
    prancheta = {}
    try:
        with open(os.path.join(raiz, "posts", "prancheta-build.json"), encoding="utf-8") as f:
            prancheta = json.load(f)
    except (OSError, ValueError):
        prancheta = {}
    if prancheta.get("build_id"):
        l.append("O build do PRANCHETA que o itch está servindo hoje: **%s** (a casa viu em %s, "
                 "pelo `vigia-build-prancheta.py` que roda no relatório diário). Quando muda, "
                 "vira fato no repertório do redator — não vira post na marra."
                 % (prancheta["build_id"], str(prancheta.get("medido_em") or "data não registrada")[:16]))
        l.append("")
    return "\n".join(l) + "\n"


def main(argv):
    novo = gerar()
    if "--conferir" in argv:
        atual = _texto(SAIDA) if os.path.exists(SAIDA) else ""
        if atual != novo:
            print("O-QUE-ACONTECE.md está diferente dos workflows.")
            for a, b in zip(atual.splitlines(), novo.splitlines()):
                if a != b:
                    print("  no arquivo: " + a)
                    print("  gerado:     " + b)
                    break
            if len(atual.splitlines()) != len(novo.splitlines()):
                print("  linhas: %d no arquivo · %d geradas"
                      % (len(atual.splitlines()), len(novo.splitlines())))
            print("rode: python3 tools/o-que-acontece.py")
            return 1
        print("O-QUE-ACONTECE.md em dia com os %d workflows." % levantar()["resumo"]["workflows"])
        return 0
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(novo)
    print("escrito: %s (%d linhas)" % (os.path.relpath(SAIDA, RAIZ), novo.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
