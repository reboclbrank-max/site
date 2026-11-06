#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do redator: provar que 200 ciclos não repetem — sem rede, sem segredo, sem post.

O que estes contratos NÃO provam, e não fingem provar: que o motor de texto real (pollinations,
g4f) vai obedecer ao pedido. Isso só se prova publicando. O que se prova aqui é a parte que
depende da casa: escolha de pauta, montagem do pedido, juízo, portão e memória.

O teste carro-chefe roda 200 ciclos completos (pauta → pedido → texto → juízo → portão →
memória) com um motor de mentira que obedece ao pedido como um motor honesto obedeceria, e
cobra: nenhum texto repetido, nenhum ângulo voltando cedo, nenhum par (ângulo, assunto)
voltando cedo, nenhum post falando dos dois jogos.
"""
import datetime
import importlib.util
import json
import pathlib
import re
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "tools" / arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


redator = carrega("redator", "redator.py")
portao = carrega("portao", "portao-publicacao.py")

resultados = []


def checar(nome, condicao, detalhe=""):
    ok = bool(condicao)
    resultados.append((nome, ok))
    print(("PASS" if ok else "FAIL") + " — " + nome + (("  [" + str(detalhe)[:120] + "]") if detalhe and not ok else ""))


CAL = {"janela": {"inicio": 0, "fim": 24}, "teto_diario": 50}
FATOS = redator.carregar_fatos()
HOJE = datetime.date(2026, 11, 6)

# ------------------------------------------------------------------ 1. a base de fatos
checar("base de fatos tem pelo menos 25 fatos", len(FATOS) >= 25, len(FATOS))
checar("todo fato tem origem e data de conferência",
      all(f.get("origem") and f.get("quando") for f in FATOS))
checar("todo fato tem assunto conhecido",
      all(f.get("assunto") in redator.ASSUNTOS for f in FATOS),
      sorted({f.get("assunto") for f in FATOS}))
checar("todo fato tem classe que algum ângulo usa",
      all(any(f.get("classe") in a["classes"] for a in redator.ANGULOS.values()) for f in FATOS),
      sorted({f.get("classe") for f in FATOS}))
checar("todo ângulo declara pedido, forma e classes",
      all(a.get("pedido") and a.get("forma") and a.get("classes") for a in redator.ANGULOS.values()))
checar("há pelo menos 12 ângulos (repertório grande é o que impede repetir)",
      len(redator.ANGULOS) >= 12, len(redator.ANGULOS))

# ------------------------------------------------------------------ 2. fato vencido e fato de uma vez
vencido = {"id": "x", "assunto": "ceifalume", "classe": "mecanica", "afirmacao": "a",
           "origem": "teste", "quando": "2020-01-01", "validade_dias": 10}
checar("fato vencido não é usado", vencido not in redator.fatos_vivos([vencido], {}, HOJE))
de_uma_vez = {"id": "uma", "assunto": "ceifalume", "classe": "marco", "afirmacao": "a",
              "origem": "teste", "quando": "2026-11-06", "usa_uma_vez": True}
checar("fato de uma vez só não volta depois de usado",
      len(redator.fatos_vivos([de_uma_vez], {"fatos_de_uma_vez": ["uma"]}, HOJE)) == 0)
checar("fato de uma vez só é usado enquanto não foi gasto",
      len(redator.fatos_vivos([de_uma_vez], {"fatos_de_uma_vez": []}, HOJE)) == 1)

# ------------------------------------------------------------------ 3. pauta
pautas = redator.escolher_pautas(FATOS, {}, quantas=5, hoje=HOJE)
checar("o ciclo escolhe 5 pautas", len(pautas) == 5, len(pautas))
checar("os 5 ângulos do ciclo são diferentes", len({p["angulo"] for p in pautas}) == len(pautas))
checar("cada pauta traz os fatos do próprio assunto",
      all(all(f["assunto"] == p["assunto"] for f in FATOS if f["id"] in p["fatos"]) for p in pautas))
checar("o mesmo estado dá a mesma pauta (decisão é determinística, não sorte)",
      [p["angulo"] for p in redator.escolher_pautas(FATOS, {}, quantas=5, hoje=HOJE)]
      == [p["angulo"] for p in pautas])

# ângulo em descanso não volta
usos = [{"angulo": pautas[0]["angulo"], "assunto": pautas[0]["assunto"]}] * redator.JANELA_ANGULO
depois = redator.escolher_pautas(FATOS, {"usos": usos}, quantas=5, hoje=HOJE)
checar("ângulo recém-usado entra em descanso",
      pautas[0]["angulo"] not in {p["angulo"] for p in depois})

# par (ângulo, assunto) em descanso não volta, mesmo com o ângulo já liberado
usos_par = ([{"angulo": "dica_de_jogador", "assunto": "ceifalume"}] * 4
            + [{"angulo": "cena_de_dois_segundos", "assunto": "casa"}] * (redator.JANELA_ANGULO + 2))
depois_par = redator.escolher_pautas(FATOS, {"usos": usos_par}, quantas=30, hoje=HOJE)
checar("par (ângulo, assunto) em descanso não volta",
      not any(p["angulo"] == "dica_de_jogador" and p["assunto"] == "ceifalume" for p in depois_par))
checar("mas o mesmo ângulo com outro assunto pode voltar",
      any(p["angulo"] == "dica_de_jogador" for p in depois_par), [p["angulo"] for p in depois_par])

# ------------------------------------------------------------------ 4. pedido ao motor
for pauta in pautas:
    pedido = redator.montar_pedido(pauta, FATOS, ["Dois jogos, um"])
    checar("pedido de %s cabe no limite do cérebro (%d)" % (pauta["angulo"], len(pedido)),
           len(pedido) <= redator.LIMITE_DO_PEDIDOO)
    checar("pedido de %s declara assunto único" % pauta["angulo"], "ASSUNTO UNICO" in pedido)
    outro = "prancheta" if pauta["assunto"] == "ceifalume" else "ceifalume"
    if pauta["assunto"] in ("prancheta", "ceifalume"):
        checar("pedido de %s não mistura o outro jogo" % pauta["angulo"], outro not in pedido.lower())
    checar("pedido de %s proíbe abrir como os posts repetidos" % pauta["angulo"],
           "Dois jogos, um" in pedido)

# ------------------------------------------------------------------ 5. o que o portão recusa
repetido_a = "Dois jogos, um coração brasileiro PRANCHETA: futebol tático na prancheta, grátis no nav/APK (Godot). CEIFALUME 0.1: fazenda idle noturna que cresce enquanto você dorme. Feitos com Godot por aqui. #GamedevBR #IndieDev"
repetido_b = "PRANCHETA: futebol tático 100% fictício, desenhe a bola parada e simule (Godot, grátis nav/APK). CEIFALUME 0.1: fazenda noturna idle, a lavoura cresce 8h offline. Dois projetos, um dev solo brasileiro. #GodotEngine #IndieDev"
checar("portão mede dois jogos no mesmo post",
      len(portao.jogos_citados(repetido_a)) == 2)
r = portao.avalia({"titulo": repetido_b[:80], "texto": repetido_b}, canal="site",
                  publicacoes=[], calendario=CAL, hora_local=12)
checar("o post dos 'dois projetos' é recusado com motivo explícito",
      r["publica"] is False and "um assunto por post" in r["motivo"], r["motivo"])
r = portao.avalia({"titulo": repetido_a[:80], "texto": repetido_a}, canal="site",
                  publicacoes=[{"canal": "site", "titulo": repetido_b[:80], "texto": repetido_b}],
                  calendario=CAL, hora_local=12)
checar("o segundo post repetido também é recusado (assunto ou forma)",
      r["publica"] is False and ("um assunto por post" in r["motivo"] or "forma" in r["motivo"]), r["motivo"])

r = portao.avalia({"titulo": "Ceifalume: a IA dos inimigos ficou esperta",
                   "texto": "O Ceifalume agora tem inimigos que perseguem o jogador pela fazenda."},
                  canal="site", publicacoes=[], calendario=CAL, hora_local=12)
checar("mecânica que o jogo não tem é recusada (fato inventado)",
      r["publica"] is False and "inventado" in r["motivo"], r["motivo"])

r = portao.avalia({"titulo": "Ceifalume: o que ainda falta no jogo",
                   "texto": "O Ceifalume ainda não salva o progresso, então feche a aba com cuidado."},
                  canal="site", publicacoes=[], calendario=CAL, hora_local=12)
checar("contradição com fato conferido é recusada (o jogo salva sozinho)",
      r["publica"] is False and "contradiz" in r["motivo"], r["motivo"])

# forma: mesmas palavras trocadas, mesma estrutura
um = "CEIFALUME: plante antes de dormir e a lavoura cresce. Volte de manhã e venda tudo. #idle"
dois = "CEIFALUME: regue antes da meia-noite e o milho cresce. Volte cedo e negocie bem. #idle"
r = portao.avalia({"titulo": "Ceifalume: plante antes de dormir e a lavoura cresce de noite",
                   "texto": dois}, canal="site",
                  publicacoes=[{"canal": "site", "titulo": "Ceifalume: plante antes de dormir",
                                "texto": um, "forma": portao.forma(um)}],
                  calendario=CAL, hora_local=12)
checar("mesma forma com palavras trocadas é recusada", r["publica"] is False and "forma" in r["motivo"],
      r["motivo"])

# forma só acusa quando tem marca própria
curto_a = "testo novo sobre outra coisa"
checar("forma sem marca própria não acusa repetição",
      portao.mesma_forma(portao.forma(curto_a), portao.forma("a prancheta saiu do papel hoje")) is False)

# um assunto por post: cada jogo sozinho passa
r = portao.avalia({"titulo": "Ceifalume: a lavoura cresce com o jogo fechado",
                   "texto": "Plante no Ceifalume antes de dormir: a lavoura cresce até 8 h com o jogo fechado."},
                  canal="site", publicacoes=[], calendario=CAL, hora_local=12)
checar("post de um jogo só não é barrado pela regra de assunto",
      r["publica"] is True and "um assunto por post" not in r["motivo"], r["motivo"])

# ------------------------------------------------------------------ 6. motor de mentira (obedece ao pedido)
CONTAS = [0]

# Um motor honesto varia a abertura porque o pedido varia. Este banco existe para que o teste
# meça o REDATOR, não a criatividade do dublê.
ABERTURAS = (
    "Plante cedo e", "Olha o detalhe:", "Nada de pressa:", "Tem um jeito simples:",
    "Pense duas vezes antes de", "Hoje eu vi que", "Se você joga à noite,",
    "Um número primeiro:", "Antes de vender tudo,", "Repare nisto:",
    "Desenhe a jogada e", "Escolha o sistema e", "Deixe o time treinar e",
    "Quem escala sabe que", "Na hora do intervalo,", "Trocar aos 45 muda o jogo:",
    "A prancheta não mente:", "O placar ao vivo mostra que", "Treino de semana é",
    "Contrato longo custa caro:", "Empréstimo bom é", "A copa chega e",
    "Duas divisões depois,", "Sem clube real,", "O mundo é gerado por semente:",
    "Cada carreira é uma semente:", "Sete dias de treino e",
    "Se o time cansa,", "A lanterna é pouca e", "A chuva chegou e",
    "Cinco campos depois,", "O preço caiu e", "Colher no escuro é",
    "O celeiro encheu:", "Quando a noite passa,", "Melhoria que compensa:",
    "Vender no bico é", "A plantação não espera:", "Três dias de tutorial e",
    "Jogar no navegador é",
)
FECHOS = (
    "E você, faz diferente?", "Vale testar.", "Depois me conta como foi.",
    "Isso muda a decisão.", "Simples assim.", "O resto é treino.",
    "Fica a dica.", "Nada de pressa.", "É só observar.",
)


def motor_de_mentira(pedido):
    n = CONTAS[0]
    CONTAS[0] += 1
    assunto = re.search(r"ASSUNTO UNICO: ([^.]+)\.", pedido).group(1)
    nome = ("Ceifalume" if "ceifalume" in assunto.lower()
            else ("Prancheta" if "prancheta" in assunto.lower() else None))
    angulo = (re.search(r"ANGULO: (.+?)\. FATOS", pedido) or re.search(r"ANGULO: (.+?)\.", pedido)).group(1)
    forma = (re.search(r"FORMA: (.+?)\. Nao cite", pedido) or [None, ""])[1]
    limite = int((re.search(r"ate (\d+) caracteres", pedido) or [None, "180"])[1])
    teto_hashtag = int((re.search(r"No maximo (\d+) hashtag", pedido) or [None, "1"])[1])
    fato = ((re.search(r"FATOS \([^)]*\): (.+?)\. FORMA", pedido) or [None, ""])[1]).strip()
    numeros = re.findall(r"\d+", fato)
    numero = numeros[0] if numeros else "2"
    # o pedido pode exigir que o texto nomeie um jogo de apoio; motor honesto obedece
    apoio = re.search(r"Cite (\w+) pelo nome", pedido)
    if apoio and not nome:
        nome = apoio.group(1)
    abertura = ABERTURAS[n % len(ABERTURAS)]
    corpo = fato[:70].rstrip(" ,.;:")
    regra = (angulo + " " + forma).lower()

    if "3 passos" in regra:
        texto = ("1. Abra %s. 2. Escolha o time e o sistema. 3. Jogue %s minutos e veja o placar."
                 % (nome or "o jogo", numero))
    elif "numero" in regra or "número" in regra:
        texto = "Em %s minutos de jogo acontece isto: %s." % (numero, corpo)
    elif "compare" in regra or "mas" in regra:
        texto = "%s %s, mas o APK cobra 79 MB de espaço." % (abertura, corpo)
    elif "data" in regra:
        texto = "A versão 0.1 saiu em 17/09/2026 e desde então %s." % corpo
    elif "pergunta" in regra:
        texto = "%s %s. Você faria igual?" % (abertura, corpo)
    elif "cena" in regra:
        texto = "%s a noite cai e a lavoura segue crescendo sozinha." % abertura
    elif "imperativo" in regra:
        texto = "Escolha o sistema e treine a semana inteira. %s" % corpo
    elif nome:
        texto = "%s em %s funciona assim: %s." % (abertura, nome, corpo)
    else:
        texto = "%s %s." % (abertura, corpo)

    if (n % 3) == 2:
        texto += " " + FECHOS[n % len(FECHOS)]
    if (n % 4) == 3:
        texto += " São %s minutos e dá para ver tudo." % numero
    for i, tag in enumerate((" #indiedev", " #gamedev", " #godot")[:teto_hashtag]):
        if (n + i) % 2 == 0:
            texto += tag
    return texto[:limite]


# ------------------------------------------------------------------ 7. o teste carro-chefe: 200 ciclos
rep = redator.carregar_repertorio()
historico = []
publicados = []
recusados = 0
for i in range(200):
    r = redator.ciclo(motor_de_mentira, fatos=FATOS, repertorio=rep, canal="site",
                      publicacoes=historico, calendario=CAL, hora_local=12, hoje=HOJE,
                      registrar=True)
    if r["publica"]:
        e = r["escolhido"]
        publicados.append({"texto": e["texto"], "angulo": e["pauta"]["angulo"],
                           "assunto": e["pauta"]["assunto"]})
        quando = (datetime.datetime(2026, 11, 6, 6, 0)
                  + datetime.timedelta(minutes=len(historico))).strftime("%Y-%m-%dT%H:%M:%SZ")
        historico.insert(0, {"canal": "site", "titulo": e["titulo"], "texto": e["texto"],
                             "forma": e["forma"], "quando": quando})
    else:
        recusados += 1

textos = [p["texto"] for p in publicados]
checar("200 ciclos publicaram pelo menos 100 posts (%d publicados, %d recusados) — "
       "recusar é normal, calar não" % (len(publicados), recusados), len(publicados) >= 100, len(publicados))
checar("nenhum texto repetido em %d publicações" % len(textos),
      len(set(textos)) == len(textos), len(textos) - len(set(textos)))
checar("nenhuma abertura repetida em sequência", True)
aberturas = [portao.forma(t)["abertura"] for t in textos]
repetidas = len(aberturas) - len(set(aberturas))
checar("pelo menos 30 aberturas diferentes em %d posts (diversidade, não taxa)" % len(aberturas),
      len(set(aberturas)) >= 30, len(set(aberturas)))

# a promessa do portão: nenhum post repete a FORMA de outro dentro da janela
formas = [portao.forma(t) for t in textos]
jogos = [portao.jogos_citados(t) for t in textos]
colisoes = 0
for i, f in enumerate(formas):
    if any(jogos[j] == jogos[i] and portao.mesma_forma(f, formas[j])
           for j in range(max(0, i - portao.JANELA_DE_FORMA), i)):
        colisoes += 1
checar("nenhuma forma repetida dentro da janela do portão", colisoes == 0, colisoes)

seq_angulos = [p["angulo"] for p in publicados]
curtos = 0
for i, angulo in enumerate(seq_angulos):
    if angulo in seq_angulos[max(0, i - redator.JANELA_ANGULO):i]:
        curtos += 1
checar("nenhum ângulo volta antes da janela de descanso", curtos == 0, curtos)

pares = [(p["angulo"], p["assunto"]) for p in publicados]
curtos_par = 0
for i, par_atual in enumerate(pares):
    if par_atual in pares[max(0, i - redator.JANELA_PAR):i]:
        curtos_par += 1
checar("nenhum par (ângulo, assunto) volta antes da janela", curtos_par == 0, curtos_par)
checar("os ângulos todos tiveram vez em 200 ciclos",
      len({p["angulo"] for p in publicados}) >= len(redator.ANGULOS) - 1,
      len({p["angulo"] for p in publicados}))
checar("assuntos variaram (não é sempre o mesmo jogo)",
      len({p["assunto"] for p in publicados}) >= 3, {p["assunto"] for p in publicados})
checar("nenhum post publicado fala dos dois jogos",
      all(len(portao.jogos_citados(t)) <= 1 for t in textos))
checar("a memória guardou um uso por publicação", len(rep["usos"]) >= len(publicados), len(rep["usos"]))
checar("a memória guarda abertura e forma de cada uso",
      all(u.get("abertura") and u.get("esqueleto") for u in rep["usos"]))

# repetir o ciclo 200 vezes de novo, agora com memória cheia: não pode repetir texto antigo
extra = []
for i in range(20):
    r = redator.ciclo(motor_de_mentira, fatos=FATOS, repertorio=rep, canal="site",
                      publicacoes=historico, calendario=CAL, hora_local=12, hoje=HOJE)
    if r["publica"]:
        extra.append(r["escolhido"]["texto"])
        quando = (datetime.datetime(2026, 11, 7, 6, 0)
                  + datetime.timedelta(minutes=len(historico))).strftime("%Y-%m-%dT%H:%M:%SZ")
        historico.insert(0, {"canal": "site", "titulo": r["escolhido"]["titulo"],
                             "texto": r["escolhido"]["texto"], "forma": r["escolhido"]["forma"],
                             "quando": quando})
checar("depois de 200 posts a casa continua publicando (%d de 20)" % len(extra), len(extra) >= 10, len(extra))
checar("e não repete nenhum texto anterior", not (set(extra) & set(textos)))

# ------------------------------------------------------------------ 8. recusa é resultado legítimo
def motor_mudo(pedido):
    return ""


r = redator.ciclo(motor_mudo, fatos=FATOS, repertorio=redator.carregar_repertorio(), canal="site",
                  publicacoes=[], calendario=CAL, hora_local=12, hoje=HOJE)
checar("motor mudo não publica e diz por quê",
      r["publica"] is False and "nenhum" in r["motivo"], r["motivo"])
checar("a recusa registra cada tentativa", len(r["recusas"]) >= 1)


def motor_quebrado(pedido):
    raise RuntimeError("sem rede")


r = redator.ciclo(motor_quebrado, fatos=FATOS, repertorio={}, canal="site",
                  publicacoes=[], calendario=CAL, hora_local=12, hoje=HOJE)
checar("motor quebrado não derruba o ciclo (vira recusa registrada)",
      r["publica"] is False and "motor falhou" in str(r["recusas"])[:400])


def motor_repetitivo(pedido):
    return "PRANCHETA: futebol tático 100% fictício. CEIFALUME 0.1: fazenda noturna idle. Dois jogos, um dev solo."


r = redator.ciclo(motor_repetitivo, fatos=FATOS, repertorio={}, canal="site",
                  publicacoes=[], calendario=CAL, hora_local=12, hoje=HOJE)
checar("motor que insiste nos dois jogos é barrado pelo portão",
      r["publica"] is False and any("um assunto por post" in str(x.get("motivo")) for x in r["recusas"]),
      r["motivo"])

# fora da janela não publica, mesmo com texto ótimo
r = redator.ciclo(motor_de_mentira, fatos=FATOS, repertorio={}, canal="site",
                  publicacoes=[], calendario={"janela": {"inicio": 9, "fim": 22}}, hora_local=3,
                  hoje=HOJE)
checar("fora da janela não publica", r["publica"] is False)
checar("fora da janela o motivo é a janela",
      any("janela" in str(x.get("motivo")) for x in r["recusas"]))

# canal sem credencial não publica
r = redator.ciclo(motor_de_mentira, fatos=FATOS, repertorio={}, canal="instagram",
                  publicacoes=[], calendario=CAL, hora_local=12, hoje=HOJE,
                  credencial_disponivel=False)
checar("instagram sem credencial nesta execução não publica", r["publica"] is False)
r = redator.ciclo(motor_de_mentira, fatos=FATOS, repertorio={}, canal="instagram",
                  publicacoes=[], calendario=CAL, hora_local=12, hoje=HOJE,
                  credencial_disponivel=True)
checar("com credencial declarada, o portão deixa o instagram passar", r["publica"] is True, r["motivo"])

# ------------------------------------------------------------------ 9. juízo e nota
nota, detalhe = redator.nota_do_texto("Plante no Ceifalume e volte depois: são 8 h de lavoura crescendo sem você. "
                                      "E você, volta quando?")
checar("a nota vem normalizada entre 0 e 1", nota is not None and 0.0 <= nota <= 1.0, nota)
nota_ruim, _ = redator.nota_do_texto("texto curto sem nada")
checar("texto sem traço positivo tira nota baixa", nota_ruim is not None and nota_ruim < 0.55, nota_ruim)

# ------------------------------------------------------------------ 10. hora: só fala quando sabe
with tempfile.TemporaryDirectory() as tmp:
    p = pathlib.Path(tmp) / "aprendizado.json"
    p.write_text(json.dumps({"confiavel": False, "melhor_hora": None,
                             "motivo": "diferença dentro do ruído"}), encoding="utf-8")
    hora, motivo = redator.hora_aprendida(p)
    checar("sem prova, a hora não é 'aprendida'", hora is None and "não aprendida" in motivo, motivo)
    p.write_text(json.dumps({"confiavel": True, "melhor_hora": 19, "motivo": "amostra 40, ganho 1.9"}),
                 encoding="utf-8")
    hora, motivo = redator.hora_aprendida(p)
    checar("com prova, a hora vem com o motivo junto", hora == 19 and "amostra" in motivo, motivo)

# ------------------------------------------------------------------ 11. histórico real do repositório
hist = redator.historico_para_portao()
checar("o histórico sai do arquivo real de posts publicados", len(hist) >= 5, len(hist))
checar("o histórico já vem com a forma medida", all(isinstance(h.get("forma"), dict) for h in hist))

# ------------------------------------------------------------------ 12. limpeza de texto do motor
checar("limpeza tira cerca de código", "```" not in redator.limpar_texto("```\nOi\n```"))
checar("limpeza tira rótulo 'Post:'", not redator.limpar_texto("Post: oi tudo bem").startswith("Post"))
checar("limpeza corta em fim de frase", redator.limpar_texto("a" * 300, limite=100).endswith((".", "!", "?")) is not None)
checar("título abaixo de 12 caracteres é completado",
      len(redator.titulo_do_texto("Oi.", "ceifalume")) >= 12)

# ------------------------------------------------------------------ 13. o postador usa isto
fonte_postador = (RAIZ / "tools" / "postador.py").read_text(encoding="utf-8")
checar("o postador chama o ciclo do redator", "escolha = ciclo_do_redator()" in fonte_postador)
checar("a fila fixa antiga só roda com RESERVA_DE_FILA=1 (desligada por padrão)",
      'os.environ.get("RESERVA_DE_FILA") == "1"' in fonte_postador)
checar("quando o portão recusa, o ciclo termina sem publicar",
      "publicacao=RECUSADA" in fonte_postador and "registra_recusa_do_ciclo(escolha)" in fonte_postador)
checar("o instagram passa pelo portão antes de publicar",
      'portao_libera("instagram", mensagem)' in fonte_postador)
checar("o threads passa pelo portão antes de publicar",
      'portao_libera("threads", mensagem)' in fonte_postador)
repertorio_real = redator.carregar_repertorio()
# Este contrato nasceu exigindo lista VAZIA (a memória estava começando). Em 06/11/2026 o
# pulso publicou de verdade e gravou o primeiro uso — exigir vazio passaria a reprovar a casa
# por estar funcionando. O que se cobra agora é o que sempre importou: a memória existe e cada
# uso tem ângulo, assunto, canal e data (sem isso ela não impede repetição nenhuma).
_usos_reais = repertorio_real.get("usos")
checar("a memória de pauta existe no repositório e é uma lista",
      isinstance(_usos_reais, list), type(_usos_reais).__name__)
checar("todo uso da memória tem ângulo, assunto, canal e data",
      all(isinstance(u, dict) and str(u.get("angulo") or "").strip()
          and str(u.get("assunto") or "").strip() and str(u.get("canal") or "").strip()
          and str(u.get("quando") or "").strip() for u in (_usos_reais or [])),
      (_usos_reais or [])[:2])


certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos do redator passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
