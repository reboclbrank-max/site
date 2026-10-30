#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Perceber: o que PRECISA ser feito — olhando o estado da casa, não o relógio.

POR QUE EXISTE (30/10/2026): o orquestrador sabia *quando* fazer (relógio: medir de 6h em 6h,
publicar na janela). Não sabia *o que* está faltando. A diferença é a mesma entre um despertador
e alguém que olha a casa e vê a torneira pingando.

Este arquivo é o olho. Ele lê o estado medido (não opinião) e produz NECESSIDADES:

  - com número (o "porquê" é sempre um número medido em algum arquivo);
  - com dono (robô executa / dono decide);
  - com verificação ("como saber que ficou pronto").

As necessidades do robô são ENFILEIRADAS em `posts/fila-tarefas.json` — a fila já tem
prioridade sobre o relógio no pulso (`orquestrador.usar_fila`). Ou seja: perceber o problema
já é o primeiro passo de resolvê-lo, não um relatório para o dono ler.

Regra da casa: nada aqui é inventado. Se não deu para medir, o item vai para
`sem_medida` — nunca vira tarefa fantasma.
"""
import datetime
import importlib.util
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(RAIZ, "posts", "log.md")
SAIDA_JSON = os.path.join(RAIZ, "posts", "percebido.json")
SAIDA_MD = os.path.join(RAIZ, "posts", "percebido.md")

# Limites declarados: cada um é uma decisão, não um número mágico escondido.
HORAS_VELHO = 26        # depois de um dia sem atualizar, o arquivo está velho
DIAS_PENDENTE = 2       # pendência do dono parada há 2 dias merece ser lembrada
DIAS_KIT = 1            # vídeo pronto e não publicado por 1 dia já é atraso
REPETICAO_MAX = 10.0    # % de repetição tolerado desde o conserto de dedupe

ARTEFATOS_VENCIVEIS = [
    ("posts/orquestrador.json", "memória do pulso", "medir"),
    ("posts/plano-do-dia.json", "plano do dia", "pesquisar"),
    ("posts/aprendizado.json", "aprendizado de horário", "aprender"),
    ("posts/desempenho.md", "medição de desempenho", "medir"),
    ("posts/auditoria-inteligencia.json", "auditoria de inteligência", "medir"),
]


def agora_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def ler_json(caminho, padrao=None):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao if padrao is not None else {}


def idade_horas(caminho, agora=None):
    try:
        mtime = os.path.getmtime(caminho)
    except OSError:
        return None
    agora = agora or agora_utc()
    return (agora.timestamp() - mtime) / 3600.0


def idade_de_texto(quando, agora=None):
    """Idade em horas de um carimbo ISO ('2026-10-27T12:00:00Z') — ou None se ilegível."""
    if not quando:
        return None
    try:
        marca = datetime.datetime.strptime(str(quando)[:19], "%Y-%m-%dT%H:%M:%S")
        marca = marca.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None
    return ((agora or agora_utc()) - marca).total_seconds() / 3600.0


def precisar(o_que, porque, quem, como, verifica, tipo_fila=None, chave=None):
    return {"o_que": o_que, "porque": porque, "quem": quem, "como": como,
            "verifica": verifica, "tipo_fila": tipo_fila, "chave": chave}


# ---------------------------------------------------------------- os sentidos
def canais_cegos(ler_log, segredos, ciclos=20):
    """Canais que, nos últimos ciclos, SEMPRE disseram que falta segredo."""
    historico = ler_log(ciclos)
    necessidades = []
    for chave, segredo in segredos.items():
        linhas = [c["linhas"].get(chave) for c in historico if c["linhas"].get(chave)]
        if len(linhas) < 5:
            continue
        # Cego = nunca publicou na janela E alguma linha nomeia o que falta.
        # (o texto da linha mudou ao longo do tempo: "sem chave ainda", "configuracao de
        # publicacao ausente", "falta o segredo X" — a REGRA não pode depender da redação)
        publicou = [r for r in linhas if "✅" in r]
        cegas = [r for r in linhas if any(
            t in r for t in ("INDISPONIVEL", "falta o segredo", "sem chave",
                             "configuracao de publicacao ausente"))]
        if not publicou and cegas and len(linhas) >= 5:
            nome_segredo = " + ".join(segredo) if isinstance(segredo, (list, tuple)) else str(segredo)
            necessidades.append(precisar(
                "ligar o canal " + chave,
                "nunca publicou em %d ciclos: falta o segredo %s" % (len(linhas), nome_segredo),
                "dono",
                "criar o segredo %s em Settings → Secrets → Actions" % nome_segredo,
                "o canal sai de ⚪ para ✅ no próximo ciclo e no painel (marketing.html)",
                chave="dono-segredo-" + chave))
    return necessidades


def artefatos_velhos(agora=None, horas=HORAS_VELHO):
    necessidades = []
    for caminho, nome, tipo in ARTEFATOS_VENCIVEIS:
        completo = os.path.join(RAIZ, caminho)
        idade = idade_horas(completo, agora)
        if idade is None:
            necessidades.append(precisar(
                "regenerar " + nome, "arquivo ausente: %s" % caminho, "robô",
                "rodar o gerador no próximo ciclo", "o arquivo existe e muda de carimbo",
                tipo_fila=tipo, chave="velho-" + os.path.basename(caminho)))
        elif idade > horas:
            necessidades.append(precisar(
                "atualizar " + nome,
                "%s está parado há %.0f h (limite %d h)" % (caminho, idade, horas), "robô",
                "rodar o gerador no próximo ciclo", "o carimbo do arquivo fica mais novo",
                tipo_fila=tipo, chave="velho-" + os.path.basename(caminho)))
    return necessidades


def metas_em_risco(placar_linhas, dias_restantes=None, minimo_por_dia=1.0):
    """Metas cujo ritmo necessário por dia já passou do razoável (>= 1 por dia)."""
    necessidades = []
    for linha in placar_linhas:
        if linha.get("status") not in ("EM_CURSO",):
            continue
        try:
            por_dia = float(str(linha.get("por_dia", "")).replace(",", "."))
        except ValueError:
            continue
        if por_dia < minimo_por_dia:
            continue
        necessidades.append(precisar(
            "empurrar a meta: " + linha["meta"],
            "faltam %s e o ritmo necessário é %s por dia%s"
            % (linha.get("falta"), linha.get("por_dia"),
               (" (prazo em %s dias)" % dias_restantes) if dias_restantes else ""),
            "robô", "priorizar essa meta no próximo ciclo editorial",
            "o número observado sobe no placar (posts/placar-metas.md)",
            tipo_fila="publicar", chave="meta-" + linha["meta"]))
    return necessidades


def repeticao_alta(auditoria, maximo=REPETICAO_MAX):
    recorte = (auditoria or {}).get("repeticao_desde_o_conserto") or {}
    pct = recorte.get("pct")
    if pct is None or not recorte.get("ciclos"):
        return []
    if float(pct) <= maximo:
        return []
    return [precisar(
        "quebrar a repetição de texto",
        "%.1f%% dos ciclos repetem algo já publicado (limite %.1f%%)"
        % (float(pct), maximo),
        "robô", "trocar o tema do ciclo e variar o fecho",
        "o percentual cai em posts/auditoria-inteligencia.md",
        tipo_fila="publicar", chave="repeticao")]


def fila_travada(fila, agora=None):
    """Tarefas que desistiram (falhou) ou que estão pendentes há muito tempo."""
    necessidades = []
    tarefas = (fila or {}).get("tarefas") or []
    falhas = [t for t in tarefas if t.get("estado") == "falhou"]
    if falhas:
        tipos = sorted({t.get("tipo") for t in falhas})
        necessidades.append(precisar(
            "recolocar na fila o que desistiu",
            "%d tarefa(s) em 'falhou' (%s)" % (len(falhas), ", ".join(map(str, tipos))),
            "robô", "criar a tarefa de novo (a fila tenta 3× e para)",
            "a tarefa sai de 'falhou' em posts/fila-tarefas.json",
            tipo_fila="medir", chave="fila-falhou"))
    return necessidades


def kit_esperando(publicados, agora=None, dias=DIAS_KIT):
    """Vídeo medido e pronto que ainda não foi publicado (depende do dono: PUBLICAR)."""
    necessidades = []
    for kit in (publicados or []):
        if kit.get("id"):
            continue
        quando = kit.get("quando")
        idade_dias = None
        horas = idade_de_texto(quando, agora)
        if horas is not None:
            idade_dias = horas / 24.0
        necessidades.append(precisar(
            "publicar o vídeo do " + str(kit.get("slug", "?")),
            "kit pronto%s e sem id do YouTube — publicação é decisão do dono"
            % ((" há %.0f dia(s)" % idade_dias) if idade_dias is not None else ""),
            "dono", "rodar o workflow com a palavra PUBLICAR",
            "o vídeo ganha id em posts/youtube-publicados.json",
            chave="kit-" + str(kit.get("slug", "?"))))
    return necessidades


def pendencias_paradas(pendencias, agora=None, dias=DIAS_PENDENTE):
    necessidades = []
    for item in (pendencias or {}).get("itens") or []:
        if item.get("estado") == "feito":
            continue
        horas = idade_de_texto((pendencias or {}).get("quando"), agora)
        if horas is None or horas < dias * 24:
            continue
        necessidades.append(precisar(
            "destravar: " + str(item.get("titulo", "")),
            "parado há %.0f dia(s) esperando o dono (%s)" % (horas / 24.0, item.get("estado")),
            "dono", str(item.get("como", "ver posts/pendencias-do-dono.md")),
            "o item vira 'feito' em posts/pendencias-do-dono.json",
            chave="pendencia-" + str(item.get("id", item.get("titulo", "")))))
    return necessidades


# ---------------------------------------------------------------- o livro
def carregar_painel():
    caminho = os.path.join(RAIZ, "tools", "painel-marketing.py")
    spec = importlib.util.spec_from_file_location("painel_marketing", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def carregar_fila():
    caminho = os.path.join(RAIZ, "tools", "fila-tarefas.py")
    spec = importlib.util.spec_from_file_location("fila_tarefas", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def placar_linhas():
    """Reaproveita o leitor do livro de decisões (mesma régua, uma implementação)."""
    caminho = os.path.join(RAIZ, "tools", "decisoes.py")
    spec = importlib.util.spec_from_file_location("decisoes", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.tabela_placar()


def perceber(agora=None, enfileirar=True):
    agora = agora or agora_utc()
    painel = carregar_painel()
    segredos = dict(getattr(carregar_postador(), "SEGREDOS_DO_CANAL", {}) or {})
    log_texto = ""
    try:
        with open(LOG, encoding="utf-8") as f:
            log_texto = f.read()
    except OSError:
        pass

    def ler_log(n):
        return painel.ciclos_do_texto(log_texto)[:n]

    necessidades = []
    try:
        necessidades += canais_cegos(ler_log, segredos)
    except Exception:
        pass
    necessidades += artefatos_velhos(agora)
    dias = None
    try:
        contexto = (ler_json(os.path.join(RAIZ, "posts", "placar-metas.json")) or {})
        dias = (contexto.get("placar_contexto") or {}).get("dias_restantes")
    except Exception:
        dias = None
    try:
        necessidades += metas_em_risco(placar_linhas(), dias)
    except Exception:
        pass
    necessidades += repeticao_alta(
        ler_json(os.path.join(RAIZ, "posts", "auditoria-inteligencia.json")))
    fila = ler_json(os.path.join(RAIZ, "posts", "fila-tarefas.json"))
    necessidades += fila_travada(fila, agora)
    try:
        publicados = (ler_json(os.path.join(RAIZ, "posts", "youtube-publicados.json"))
                      .get("publicados") or [])
        necessidades += kit_esperando(publicados, agora)
    except Exception:
        pass
    necessidades += pendencias_paradas(
        ler_json(os.path.join(RAIZ, "posts", "pendencias-do-dono.json")), agora)

    # dedupe por chave, mantendo a ordem (robô primeiro: é o que pode ser resolvido agora)
    vistos, limpas = set(), []
    for item in necessidades:
        marca = item.get("chave") or item["o_que"]
        if marca in vistos:
            continue
        vistos.add(marca)
        limpas.append(item)

    do_robo = [i for i in limpas if i["quem"] == "robô"]
    do_dono = [i for i in limpas if i["quem"] == "dono"]

    enfileiradas = []
    if enfileirar and do_robo:
        try:
            fila_mod = carregar_fila()
            dados = fila_mod.carregar(os.path.join(RAIZ, "posts", "fila-tarefas.json"))
            for item in do_robo:
                criada = fila_mod.adicionar(dados, item["tipo_fila"] or "medir",
                                            motivo=item["o_que"] + ": " + item["porque"],
                                            chave=item.get("chave"))
                if criada:
                    enfileiradas.append(criada["id"])
            fila_mod.gravar(dados, os.path.join(RAIZ, "posts", "fila-tarefas.json"))
        except Exception as erro:      # fila quebrada não pode derrubar o ciclo
            print("aviso: fila não aceitou as tarefas (%s)" % str(erro)[:120])

    return {
        "quando": agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_lei": "necessidade sem número não entra; o robô enfileira o que pode fazer e "
                "entrega ao dono o que só ele pode decidir.",
        "robo": do_robo,
        "dono": do_dono,
        "enfileiradas": enfileiradas,
        "contagem": {"robo": len(do_robo), "dono": len(do_dono),
                     "enfileiradas": len(enfileiradas)},
    }


def carregar_postador():
    caminho = os.path.join(RAIZ, "tools", "postador.py")
    spec = importlib.util.spec_from_file_location("postador", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def markdown(dados):
    linhas = ["# O que precisa ser feito", "",
              "Gerado em %s pelo próprio ciclo, olhando o estado medido (não o relógio)."
              % dados["quando"], "", "> %s" % dados["_lei"], ""]
    linhas += ["## O robô já colocou na fila (%d)" % dados["contagem"]["robo"], ""]
    if dados["robo"]:
        linhas += ["| o que | por quê (medido) | como | verifica |", "| --- | --- | --- | --- |"]
        for i in dados["robo"]:
            linhas.append("| %s | %s | %s | %s |" % (i["o_que"], i["porque"], i["como"], i["verifica"]))
    else:
        linhas.append("Nada pendente do lado do robô nesta rodada.")
    linhas += ["", "## Espera o dono (%d)" % dados["contagem"]["dono"], ""]
    if dados["dono"]:
        linhas += ["| o que | por quê (medido) | como | verifica |", "| --- | --- | --- | --- |"]
        for i in dados["dono"]:
            linhas.append("| %s | %s | %s | %s |" % (i["o_que"], i["porque"], i["como"], i["verifica"]))
    else:
        linhas.append("Nada esperando o dono nesta rodada.")
    return "\n".join(linhas) + "\n"


def escrever(caminho, texto):
    with open(caminho + ".tmp", "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(caminho + ".tmp", caminho)


def main(argv):
    dados = perceber()
    escrever(SAIDA_JSON, json.dumps(dados, ensure_ascii=False, indent=1) + "\n")
    escrever(SAIDA_MD, markdown(dados))
    c = dados["contagem"]
    print("percebido: %d para o robô (%d enfileiradas) · %d para o dono"
          % (c["robo"], c["enfileiradas"], c["dono"]))
    for item in dados["robo"]:
        print("  robô · %s — %s" % (item["o_que"], item["porque"]))
    for item in dados["dono"]:
        print("  dono · %s — %s" % (item["o_que"], item["porque"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
