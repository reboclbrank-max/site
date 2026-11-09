#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fila de tarefas da casa — o que faltava para o pulso não recomeçar do zero.

Problema que resolve: o orquestrador decidia a cada pulso, mas não tinha *trabalho
pendente*. Se uma publicação falhasse, ela simplesmente não existia mais; e não havia
como saber o que estava na frente da fila.

Agora: as tarefas são DADOS (`posts/fila-tarefas.json`), com prioridade, tentativas e
resultado. O pulso pega a de maior prioridade que pode rodar, marca, e devolve. Falha
não desaparece: ela volta com tentativas+1 até o limite (3), depois fica `falhou` com o
motivo — visível, não silencioso.

Regra de ouro: **uma tarefa por TIPO por pulso** — nunca duas do mesmo tipo (duas publicações
no mesmo pulso é como a casa passou a postar duas vezes no mesmo minuto). O pulso fecha uma de
cada tipo pedido: uma `publicar` e uma `medir`.

ANTI-FOME (07/11/2026): medido no repositório, a fila tinha 8 pendentes, a mais velha de 03/11
com **0 tentativas**. O pulso fechava uma tarefa e o `perceber`/relógio enfileirava duas, e
`publicar` (prio 95) sempre vinha antes de `medir` (90) — a tarefa velha nunca chegava na vez.
Duas regras consertam isso: tarefa com mais de 24 h sobe na frente, e cada tipo tem teto de
pendentes (o que passa do teto não entra, em vez de virar depósito).
"""
import datetime
import hashlib
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO = os.path.join(RAIZ, "posts", "fila-tarefas.json")
MAX_TENTATIVAS = 3
TETO_POR_TIPO = 3      # pendentes por tipo: acima disso, o pulso não enfileira mais
FOME_HORAS = 24        # mais de um dia esperando = sobe na frente, qualquer que seja a prioridade
FOME_MEDIA_HORAS = 6   # meia fome: sobe um degrau

PRIORIDADES = {
    "medir": 90,        # medir sempre está na frente: sem número, o resto é chute
    "responder": 80,    # responder comentário vale mais que postar
    "publicar": 60,
    "pesquisar": 40,
    "aprender": 30,
}


def agora_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def vazia():
    return {"_o_que_e": "fila de tarefas da casa: prioridade, tentativas e resultado",
            "versao": 1, "tarefas": []}


def carregar(caminho=ARQUIVO):
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        return vazia()
    base = vazia()
    base.update(dados or {})
    base["tarefas"] = base.get("tarefas") or []
    _HASH_POR_ARQUIVO[caminho] = _hash_arquivo(caminho)
    return base


_HASH_POR_ARQUIVO = {}


def _hash_arquivo(caminho):
    """SHA-1 do arquivo no disco (para detectar escrita concorrente)."""
    try:
        with open(caminho, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()
    except OSError:
        return None


def arquivo_esta_inalterado(caminho=ARQUIVO):
    """True se o arquivo no disco é o mesmo que foi carregado pela última vez.

    Usado para detectar race de escrita: dois processos carregam o mesmo
    fila-tarefas.json, um grava, o outro grava por cima e perde as mudanças
    do primeiro. Se o hash mudou desde o carregar(), recusamos a gravação
    com motivo e números (regra da casa).
    """
    atual = _hash_arquivo(caminho)
    gravado = _HASH_POR_ARQUIVO.get(caminho)
    if gravado is None:
        return True  # nunca carregamos: não há o que comparar
    return atual == gravado


def gravar(dados, caminho=ARQUIVO):
    """Grava apenas se o arquivo não mudou desde o carregar().

    Devolve (ok, motivo). Se ok for False, o arquivo não foi gravado e o
    chamador deve recarregar e tentar de novo (ou abortar o pulso).
    """
    if not arquivo_esta_inalterado(caminho):
        atual = _hash_arquivo(caminho)
        gravado = _HASH_POR_ARQUIVO.get(caminho)
        return False, ("arquivo mudou desde o carregar: "
                       "hash gravado=%s, hash no disco=%s" % (gravado, atual))
    pasta = os.path.dirname(caminho)
    if pasta and not os.path.isdir(pasta):
        os.makedirs(pasta, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    _HASH_POR_ARQUIVO[caminho] = _hash_arquivo(caminho)
    return True, ""


def adicionar(dados, tipo, motivo="", quando=None, chave=None):
    """Cria tarefa se não existir uma igual pendente (chave evita duplicata)."""
    if chave:
        for t in dados["tarefas"]:
            if t.get("chave") == chave and t.get("estado") in ("pendente", "executando"):
                return None
    # TETO POR TIPO: fila não é depósito. O que passa do teto não entra — e a recusa é DITA, com
    # o número que a justifica (regra da casa: recusa sai com motivo e números).
    pendentes = pendentes_por_tipo(dados, tipo)
    if len(pendentes) >= TETO_POR_TIPO:
        recusa = {"tipo": tipo, "motivo": (motivo or "")[:120], "quando": quando or agora_iso(),
                  "teto": TETO_POR_TIPO, "ja_pendentes": len(pendentes),
                  "esperando": [t.get("id") for t in pendentes]}
        dados.setdefault("recusadas", []).append(recusa)
        dados["recusadas"] = dados["recusadas"][-50:]
        print("fila: recusada %s — %d já pendentes (teto %d): %s"
              % (tipo, len(pendentes), TETO_POR_TIPO, (motivo or "")[:60]))
        return None
    # ID ÚNICO (07/11/2026): o id saía do segundo da criação, e várias tarefas do mesmo pulso
    # nasciam no mesmo segundo — a fila real tem 13 ids repetidos em 46 tarefas. O id é o que
    # aparece no log ("fila: tarefa publicar-... -> feito"), então id repetido é log ambíguo:
    # não se sabe qual das quatro enfileiradas naquele minuto foi a que rodou.
    base = "%s-%s" % (tipo, (quando or agora_iso()).replace(":", "").replace("-", ""))
    ident, n = base, 2
    existentes = {t.get("id") for t in dados["tarefas"]}
    while ident in existentes:
        ident = "%s-%d" % (base, n)
        n += 1
    tarefa = {
        "id": ident,
        "tipo": tipo,
        "prioridade": PRIORIDADES.get(tipo, 10),
        "estado": "pendente",
        "tentativas": 0,
        "criada": quando or agora_iso(),
        "executada": None,
        "resultado": None,
        "motivo": motivo,
        "chave": chave,
    }
    dados["tarefas"].append(tarefa)
    return tarefa


def _quando(valor):
    """Data ISO (com ou sem Z) como datetime UTC. None quando não dá para ler."""
    if not valor:
        return None
    try:
        texto = str(valor).replace("Z", "+00:00")
        quando = datetime.datetime.fromisoformat(texto)
    except ValueError:
        return None
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=datetime.timezone.utc)
    return quando


def espera_horas(tarefa, agora=None):
    """Quantas horas a tarefa está esperando (0 quando a data não dá para ler)."""
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    criada = _quando(tarefa.get("criada"))
    if not criada:
        return 0.0
    return max(0.0, (agora - criada).total_seconds() / 3600.0)


def prioridade_efetiva(tarefa, agora=None):
    """Prioridade com a fome embutida: quem espera demais passa na frente.

    Sem isso, uma tarefa de prioridade 90 esperando três dias fica atrás de toda `publicar`
    (95) que o relógio cria a cada pulso — e nunca roda.
    """
    base = int(tarefa.get("prioridade", 0))
    horas = espera_horas(tarefa, agora)
    if horas >= FOME_HORAS:
        return base + 1000
    if horas >= FOME_MEDIA_HORAS:
        return base + 100
    return base


def pendentes_por_tipo(dados, tipo):
    return [t for t in dados["tarefas"]
            if t.get("tipo") == tipo and t.get("estado") in ("pendente", "executando")]


def proxima(dados, agora=None):
    """A próxima tarefa executável: prioridade EFETIVA, mais antiga primeiro no empate."""
    candidatas = [t for t in dados["tarefas"]
                  if t.get("estado") == "pendente" and int(t.get("tentativas", 0)) < MAX_TENTATIVAS]
    candidatas.sort(key=lambda t: (-prioridade_efetiva(t, agora), t.get("criada") or ""))
    return candidatas[0] if candidatas else None


def selecionar_pulso(dados, tipos=("publicar", "medir"), agora=None):
    """As tarefas deste pulso: no máximo UMA de cada tipo pedido.

    Duas do mesmo tipo no mesmo pulso é o defeito que a casa já pagou (duas publicações no mesmo
    minuto). Uma `publicar` + uma `medir` é o que o pulso deve fechar: publicar sem medir é
    atirar no escuro; medir sem publicar é número parado.
    """
    escolhidas = []
    for tipo in tipos:
        candidatas = [t for t in dados["tarefas"]
                      if t.get("tipo") == tipo and t.get("estado") == "pendente"
                      and int(t.get("tentativas", 0)) < MAX_TENTATIVAS]
        if not candidatas:
            continue
        candidatas.sort(key=lambda t: (-prioridade_efetiva(t, agora), t.get("criada") or ""))
        escolhidas.append(candidatas[0])
    for tarefa in escolhidas:
        tarefa["estado"] = "executando"
        tarefa["executada"] = agora_iso()
    return escolhidas


def pegar(dados, tarefa=None):
    tarefa = tarefa or proxima(dados)
    if not tarefa:
        return None
    tarefa["estado"] = "executando"
    tarefa["executada"] = agora_iso()
    return tarefa


def concluir(dados, tarefa, ok, resultado=""):
    """Fecha a tarefa. Falha volta para a fila até MAX_TENTATIVAS; depois fica `falhou`."""
    tarefa["resultado"] = (resultado or "")[:400]
    if ok:
        tarefa["estado"] = "feito"
        return "feito"
    tarefa["tentativas"] = int(tarefa.get("tentativas", 0)) + 1
    if tarefa["tentativas"] >= MAX_TENTATIVAS:
        tarefa["estado"] = "falhou"
        tarefa["resultado"] = ("desistiu após %d tentativas: " % tarefa["tentativas"]) + tarefa["resultado"]
        return "falhou"
    tarefa["estado"] = "pendente"
    return "nova tentativa (%d/%d)" % (tarefa["tentativas"], MAX_TENTATIVAS)


# AÇÕES IDEMPOTENTES: medir de novo dá o mesmo número; aprender de novo, a mesma lição. Ter
# cinco `medir` pendentes não é cinco vezes mais medição — é uma medição e quatro cópias velhas,
# e foi assim que a fila chegou a 8 pendentes com a mais antiga de 03/11. Publicar e pesquisar
# NÃO estão nesta lista: cada publicação vale por si e não pode ser podada.
IDEMPOTENTES = ("medir", "aprender")


def podar_repetidas(dados, agora=None):
    """Deixa no máximo UMA pendente por ação idempotente (a mais nova) e diz quantas podou.

    A poda não apaga a tarefa nem mente sobre ela: marca `vencida`, com o motivo e o id da que
    ficou. "Vencida" é diferente de "feita" — nada foi medido, nada foi aprendido.
    """
    podadas = []
    for tipo in IDEMPOTENTES:
        pendentes = [t for t in dados["tarefas"]
                     if t.get("tipo") == tipo and t.get("estado") == "pendente"]
        if len(pendentes) <= 1:
            continue
        pendentes.sort(key=lambda t: t.get("criada") or "", reverse=True)
        fica = pendentes[0]
        for velha in pendentes[1:]:
            velha["estado"] = "vencida"
            velha["resultado"] = ("vencida: %s mais nova assume (criada em %s)"
                                  % (fica["id"], (fica.get("criada") or "")[:16]))
            velha["adiamentos"] = int(velha.get("adiamentos", 0))
            podadas.append(velha)
    return podadas


def adiar(dados, tarefa, motivo=""):
    """Devolve a tarefa à fila SEM contar tentativa: ela não falhou, foi adiada.

    MEDIDO (07/11/2026, pulso 02:48Z): às 23h locais o pulso pegou a `publicar`, o portão
    respondeu "janela: fora da janela (23h local)" — e a tarefa foi fechada como `feito`. Uma
    publicação que não houve virou tarefa concluída, e a fila perdeu a tarefa sem que nada
    acontecesse. Adiar é diferente de falhar e diferente de concluir.
    """
    if not tarefa:
        return None
    tarefa["estado"] = "pendente"
    tarefa["adiamentos"] = int(tarefa.get("adiamentos", 0)) + 1
    tarefa["adiada_em"] = agora_iso()
    tarefa["resultado"] = ("adiada: " + (motivo or ""))[:200]
    return "adiada (%s)" % ((motivo or "")[:60])


def semear(dados, plano=None, agora=None):
    """Enche a fila a partir do plano do dia. Idempotente: não duplica o que já existe."""
    criadas = []
    dia = (agora or agora_iso())[:10]
    if plano:
        tema = (plano.get("tema_do_dia") or {}).get("texto")
        if tema:
            criadas.append(adicionar(dados, "publicar", motivo=tema[:80], chave="publicar-" + dia))
        risco = plano.get("meta_em_risco") or {}
        if risco.get("meta"):
            criadas.append(adicionar(dados, "pesquisar", motivo="meta em risco: " + str(risco["meta"]),
                                     chave="pesquisar-" + dia))
    criadas.append(adicionar(dados, "medir", motivo="placar e desempenho", chave="medir-" + dia))
    criadas.append(adicionar(dados, "aprender", motivo="horário: só com prova", chave="aprender-" + dia))
    return [c for c in criadas if c]


def resumo(dados):
    contagem = {}
    for t in dados["tarefas"]:
        contagem[t.get("estado", "?")] = contagem.get(t.get("estado", "?"), 0) + 1
    return contagem


def main(argv):
    dados = carregar()
    if "--semear" in argv:
        plano = None
        try:
            with open(os.path.join(RAIZ, "posts", "plano-do-dia.json"), encoding="utf-8") as f:
                plano = json.load(f)
        except Exception:
            plano = None
        criadas = semear(dados, plano)
        gravar(dados)
        print("tarefas criadas: %d" % len(criadas))
        for t in criadas:
            print("  + [%d] %s — %s" % (t["prioridade"], t["tipo"], t["motivo"]))
        return 0
    print("fila:", resumo(dados))
    nxt = proxima(dados)
    print("próxima:", (nxt or {}).get("tipo", "nada na fila"), "—", (nxt or {}).get("motivo", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
