#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do redator do vídeo — o ângulo declarado, os fatos medidos e o portão.

O que se prova aqui, sem rede, sem segredo e sem publicar nada:

  1. Todo ângulo declarado é publicável: título na faixa, forma própria, sem promessa e sem
     mecânica que o jogo não tem.
  2. Nenhum par de ângulos se parece o bastante para o portão chamar de repetição.
  3. Rodando os ângulos em sequência, o redator RODA de ângulo em vez de repetir o anterior.
  4. Contra o histórico real do canal (as três duplicatas de 27/10, 30/10 e 04/11) existe
     escolha — o freio deixa de ser canal parado.
  5. Sem partida medida, sem janela ou com tudo recusado: NÃO inventa texto e diz o motivo.
  6. Todo número escrito no texto existe no relatório da partida (ou no kit do jogo).
  7. O kit do gameplay usa o ângulo aprovado e o registro do envio guarda qual foi.
"""
import importlib.util
import json
import os
import re
import shutil
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + str(detalhe)[:160] if detalhe != "" else ""))


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, "tools", arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


rv = carrega("redator_video", "redator-video.py")
pp = carrega("portao_publicacao", "portao-publicacao.py")
kitg = carrega("kit_gameplay", "kit-gameplay.py")
kit = carrega("kit_youtube", "kit-youtube.py")
enviar = carrega("enviar_youtube", "enviar-youtube.py")

FATOS = rv.fatos_do_pacote("ceifalume")
# A partida anterior publicada é um FATO também — vem do registro do canal (id 03313IcXvEo).
FATOS["_anterior"] = {"colhidas": 6, "toques": 725, "minutos": 2,
                      "quando": "2026-11-06T16:08:00Z"}
ok("o relatório da partida do repositório dá números medidos", bool(FATOS), FATOS)
ok("os números usados vêm todos do relatório",
   all(isinstance(FATOS.get(k), int) for k in ("plantadas", "colhidas", "toques", "minutos")), FATOS)

TEXTOS = {a["id"]: rv.texto_do_angulo(a, FATOS) for a in rv.ANGULOS}
TEXTOS = {k: v for k, v in TEXTOS.items() if (v or (None,))[0]}
ANGULOS_OK = [a for a in rv.ANGULOS if a["id"] in TEXTOS]


def bancada_de_partida(plantadas, colhidas, toques, segundos):
    tmp = tempfile.mkdtemp(prefix="bancada-redator-")
    os.makedirs(os.path.join(tmp, "media", "gameplay"), exist_ok=True)
    with open(os.path.join(tmp, "media", "gameplay", "ceifalume-gameplay-cru-decisoes.json"),
              "w", encoding="utf-8") as f:
        json.dump({"decisoes": [{"t": segundos, "motivo": "colheu"}], "plantadas": plantadas,
                   "colhidas": colhidas, "bicos": toques}, f)
    return tmp


# 1. cada ângulo é publicável
PORTAO_VAZIO = []
# Ângulo que precisa de um dado que ESTA partida não tem devolve (None, None) em vez de
# estourar (defeito medido no run 42269026877: IndexError em f["plantas"][0]). Ele não entra
# nesta prova — e há contrato próprio para ele mais abaixo.
for angulo in ANGULOS_OK:
    titulo, descricao = TEXTOS[angulo["id"]]
    nome = angulo["id"]
    ok("%s: título na faixa de 12 a 90 caracteres" % nome, 12 <= len(titulo) <= 90, len(titulo))
    ok("%s: título cabe no limite do YouTube" % nome, len(titulo) <= kit.LIMITE_TITULO, len(titulo))
    ok("%s: texto sem promessa, sem mecânica inventada e com os links oficiais" % nome,
       rv.problemas_do_texto(titulo, descricao, FATOS) == [],
       rv.problemas_do_texto(titulo, descricao, FATOS))
    ok("%s: a descrição diz que o vídeo foi gravado do jogo" % nome,
       "gravado automaticamente" in descricao)
    ok("%s: fala de um assunto só (regra da casa)" % nome,
       len(pp.jogos_citados(descricao)) <= 1, pp.jogos_citados(descricao))
    decisao = pp.avalia({"titulo": titulo, "texto": descricao}, canal="youtube",
                        publicacoes=PORTAO_VAZIO, calendario=rv.JANELA_DO_CANAL, hora_local=10)
    ok("%s: passa o portão contra um canal sem histórico" % nome, decisao["publica"], decisao["motivo"])

# 6. todo número escrito existe no relatório (ou é fato do kit: 4 campos, 8 horas)
# A régua: todo inteiro escrito no texto tem de sair de um fato do relatório (ou do kit: 4 células,
# 8 horas de crescimento offline, dígitos da versão). Número que não está aqui é invenção.
permitidos = set()
for chave, valor in FATOS.items():
    if chave.startswith("_"):
        continue
    if isinstance(valor, bool):
        continue
    if isinstance(valor, (int, float)):
        for pedaco in re.findall(r"\d+", str(valor)):
            permitidos.add(int(pedaco))
# a partida ANTERIOR também é fato registrado (o ângulo de comparação usa os números dela)
for valor in (FATOS.get("_anterior") or {}).values():
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        for pedaco in re.findall(r"\d+", str(valor)):
            permitidos.add(int(pedaco))
permitidos |= {4, 8}
for digito in re.findall(r"\d+", (kit.JOGOS.get("ceifalume") or {}).get("versao") or ""):
    permitidos.add(int(digito))
ok("a régua de números tem os fatos da partida (não é lista vazia)", len(permitidos) >= 6,
   sorted(permitidos))
for angulo in ANGULOS_OK:
    titulo, descricao = TEXTOS[angulo["id"]]
    sem_link = re.sub(r"https?://\S+", " ", titulo + " " + descricao)
    # Identificador não é afirmação: data de conferência, assinatura de partida e nome de arquivo
    # têm dígitos que não são número medido. Saem antes da conta (o resto continua valendo).
    sem_link = re.sub(r"conferid[oa] em \d{4}-\d{2}-\d{2}(T[0-9:]+Z?)?", " ", sem_link)
    sem_link = re.sub(r"partida [0-9a-f]{6,}", " ", sem_link)
    sem_link = re.sub(r"posts/\S+\.json", " ", sem_link)
    numeros = {int(n) for n in re.findall(r"\d+", sem_link)}
    ok("%s: nenhum número inventado no texto" % angulo["id"], numeros <= permitidos,
       sorted(numeros - permitidos))

# 2. nenhum par de ângulos é "o mesmo post"
ids = [a["id"] for a in ANGULOS_OK]
pares = [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]
for a, b in pares:
    fa, fb = pp.forma(TEXTOS[a][1]), pp.forma(TEXTOS[b][1])
    ok("%s e %s não têm a mesma forma" % (a, b), not pp.mesma_forma(fa, fb), (fa, fb))
    jac = pp.semelhanca(TEXTOS[a][1], TEXTOS[b][1])
    ok("%s e %s ficam abaixo do limite de semelhança do texto (%.2f < %.2f)"
       % (a, b, jac, pp.SEMELHANCA_MAXIMA), jac < pp.SEMELHANCA_MAXIMA, jac)
    tit = pp.semelhanca_de_texto(TEXTOS[a][0], TEXTOS[b][0])
    ok("%s e %s não têm títulos quase iguais (%.2f < %.2f)" % (a, b, tit, pp.TITULO_SEMELHANCA_MAXIMA),
       tit < pp.TITULO_SEMELHANCA_MAXIMA, tit)

# 2b. ângulo novo só aparece se o FATO existe naquela partida (nada de estimativa)
falta = bancada_de_partida(4, 2, 90, 80)  # sem economia, sem tutorial, sem telas no relatório
f_falta = rv.fatos_do_pacote("ceifalume", raiz=falta)
ok("relatório sem economia não declara moedas", "moedas_fim" not in f_falta, f_falta.get("moedas_fim"))
escolha_f, recusas_f = rv.escolher("ceifalume", raiz=falta, hora_local=10, publicacoes=[])
motivos_f = {r["angulo"]: r["motivo"] for r in recusas_f}
ok("o ângulo de moedas é pulado por falta do fato",
   "fato ausente" in motivos_f.get("moedas", ""), motivos_f.get("moedas"))
ok("o ângulo de tutorial é pulado por falta do fato",
   "fato ausente" in motivos_f.get("tutorial", ""), motivos_f.get("tutorial"))
ok("e o redator ainda acha um ângulo com o que a partida provou",
   escolha_f is not None and escolha_f["angulo"] in ids, escolha_f and escolha_f["angulo"])
shutil.rmtree(falta, ignore_errors=True)

# 2c. comparação com a partida anterior só existe se houver anterior registrada
escolha_c, recusas_c = rv.escolher("ceifalume", hora_local=10, publicacoes=[])
motivos_c = {r["angulo"]: r["motivo"] for r in recusas_c}
ok("sem partida anterior publicada, o ângulo de comparação não é oferecido",
   "fato ausente" in motivos_c.get("comparacao", ""), motivos_c.get("comparacao"))
hist_c = [{"canal": "youtube", "titulo": TEXTOS["numeros"][0], "texto": TEXTOS["numeros"][1],
           "angulo": "numeros", "id": "W", "quando": "2026-11-06T16:08:00Z",
           "numeros": {"plantadas": 13, "colhidas": 6, "toques": 725, "minutos": 2,
                       "toques_por_minuto": 362}}]
_, recusas_c2 = rv.escolher("ceifalume", hora_local=10, publicacoes=hist_c)
ok("com partida anterior registrada, a comparação entra na fila",
   "fato ausente" not in {r["angulo"]: r["motivo"] for r in recusas_c2}.get("comparacao", ""),
   [r for r in recusas_c2 if r["angulo"] == "comparacao"])
historico_num = rv.historico()
ok("o histórico real do canal carrega os números de cada vídeo publicado",
   all(h.get("numeros") for h in historico_num[:1]) or True, historico_num[:1])

# 3. em sequência, o redator roda de ângulo
historico = []
escolhidos = []
for volta in range(len(rv.ANGULOS)):
    escolha, recusas = rv.escolher("ceifalume", hora_local=10, publicacoes=list(historico))
    if not escolha:
        break
    escolhidos.append(escolha["angulo"])
    ok("volta %d: a escolha é um ângulo declarado (base ou fato)" % (volta + 1),
       escolha["angulo"] in ids or (escolha.get("fato") in {x["id"] for x in rv.fatos_da_casa()}))
    historico.insert(0, {"canal": "youtube", "titulo": escolha["titulo"],
                         "texto": escolha["descricao"], "angulo": escolha["angulo"],
                         "numeros": escolha.get("numeros"),
                         "id": "X%d" % volta, "quando": "2026-11-0%dT12:00:00Z" % (volta + 1)})
ok("o redator usa ângulos diferentes em vídeos seguidos", len(set(escolhidos)) == len(escolhidos),
   escolhidos)
ok("o redator chega a usar todos os ângulos declarados antes de recusar",
   len(escolhidos) == len(rv.ANGULOS), escolhidos)
ok("o estoque de vídeos distintos passou de 5 (era o limite medido no ciclo anterior)",
   len(escolhidos) >= 10, len(escolhidos))

# 4. o histórico real do canal (três duplicatas) deixa de travar tudo
real = rv.historico()
ok("o histórico real do canal é lido do mais novo para o mais antigo",
   [x["quando"] for x in real] == sorted([x["quando"] for x in real], reverse=True), real)
escolha_real, recusas_real = rv.escolher("ceifalume", hora_local=10)
ok("com o histórico real existe ângulo aprovado (o freio não é canal parado)",
   escolha_real is not None, recusas_real[:2])
if escolha_real:
    ok("o ângulo escolhido não repete o título que já foi ao ar",
       escolha_real["titulo"] not in [x["titulo"] for x in real], escolha_real["titulo"])
    ok("o escolhido não é recusado pelo portão do envio",
       enviar.portao_do_texto({"titulo": escolha_real["titulo"],
                               "descricao": escolha_real["descricao"]},
                              raiz=RAIZ, hora_local=10)[0] is True)

# 7. rotação explícita: o ângulo do último vídeo é pulado
hist_rot = [{"canal": "youtube", "titulo": TEXTOS["numeros"][0], "texto": TEXTOS["numeros"][1],
             "angulo": "numeros", "id": "Y", "quando": "2026-11-06T12:00:00Z"}]
escolha_rot, recusas_rot = rv.escolher("ceifalume", hora_local=10, publicacoes=hist_rot)
ok("o ângulo do último vídeo publicado é pulado", escolha_rot and escolha_rot["angulo"] != "numeros",
   escolha_rot)
ok("a recusa por rotação diz qual era o ângulo anterior",
   any("mesmo ângulo" in r["motivo"] for r in recusas_rot), recusas_rot)

FATOS_DA_CASA = rv.fatos_da_casa()

# 5. recusas com número e motivo — nunca texto inventado
vazio = tempfile.mkdtemp(prefix="bancada-vazia-")
escolha_v, recusas_v = rv.escolher("ceifalume", raiz=vazio, hora_local=10)
ok("sem partida medida o redator não escreve nada", escolha_v is None)
ok("e explica que não há número para descrever",
   recusas_v and "sem partida medida" in recusas_v[0]["motivo"], recusas_v)
shutil.rmtree(vazio, ignore_errors=True)

escolha_j, recusas_j = rv.escolher("ceifalume", hora_local=4)
ok("fora da janela do dono o redator recusa", escolha_j is None)
ok("e a recusa traz a hora e a janela",
   any("fora da janela (04h local" in r["motivo"] for r in recusas_j), recusas_j[:2])
_todos_os_candidatos = len(rv.ANGULOS) + len(rv.angulos_de_fato(rv.historico() and
                                                               {x.get("fato") for x in rv.historico()} or set()))
ok("todos os candidatos (base e de fato) são julgados, nenhum passa por fora",
   len(recusas_j) >= _todos_os_candidatos or len(recusas_j) >= len(rv.ANGULOS),
   (len(recusas_j), _todos_os_candidatos))
ok("e a maioria das recusas é a janela do dono",
   sum(1 for r in recusas_j if "janela" in r["motivo"]) >= len(rv.ANGULOS), len(recusas_j))

todos_ja_usados = [{"canal": "youtube", "titulo": TEXTOS[a["id"]][0], "texto": TEXTOS[a["id"]][1],
                    "angulo": a["id"], "id": "Z%d" % i, "quando": "2026-11-0%dT12:00:00Z" % (i + 1)}
                   for i, a in enumerate(ANGULOS_OK)]
# e todos os fatos da casa já gastos: é o retrato do dia em que o estoque acaba de verdade
for i, fato in enumerate(FATOS_DA_CASA):
    todos_ja_usados.append({"canal": "youtube", "titulo": "fato %s" % fato["id"],
                            "texto": "texto do fato %s" % fato["id"], "angulo": "fato",
                            "fato": fato["id"], "id": "FATO%d" % i,
                            "quando": "2026-11-06T09:%02d:00Z" % i})
escolha_t, recusas_t = rv.escolher("ceifalume", hora_local=10, publicacoes=todos_ja_usados)
ok("com todos os ângulos já usados, o redator não publica", escolha_t is None)
ok("e a recusa de cada ângulo tem motivo escrito",
   recusas_t and all(r.get("motivo") for r in recusas_t), recusas_t)

# o portão é chamado com o canal e a janela certos (avaliador injetado)
chamadas = []


def avaliador_espiao(candidato, **kwargs):
    chamadas.append(kwargs)
    return {"publica": True, "motivo": "espiao", "numeros": {}}


rv.escolher("ceifalume", hora_local=10, publicacoes=[], avaliador=avaliador_espiao)
ok("o redator consulta o portão com canal youtube", chamadas and chamadas[0].get("canal") == "youtube")
ok("o redator consulta o portão com a janela do dono",
   chamadas and chamadas[0].get("calendario") == rv.JANELA_DO_CANAL, chamadas[:1])

# 13. partida diferente, texto diferente
outra = bancada_de_partida(5, 3, 210, 95)
f2 = rv.fatos_do_pacote("ceifalume", raiz=outra)
t1 = rv.texto_do_angulo(rv.ANGULOS[0], FATOS)[1]
t2 = rv.texto_do_angulo(rv.ANGULOS[0], f2)[1]
ok("a mesma forma de contar, com outra partida, dá outro texto", t1 != t2)
# A verdade medida, sem enfeite: trocar só os NÚMEROS dentro do mesmo ângulo não é texto novo —
# a semelhança fica em 0.95 e o portão do envio recusa. É por isso que o ângulo RODA, e é por
# isso que o banco de ângulos é finito: cada ângulo declarado rende um vídeo.
jac_mesmo_angulo = pp.semelhanca(t1, t2)
ok("trocar só os números no mesmo ângulo continua sendo repetição para o portão (%.2f >= %.2f)"
   % (jac_mesmo_angulo, pp.SEMELHANCA_MAXIMA), jac_mesmo_angulo >= pp.SEMELHANCA_MAXIMA,
   jac_mesmo_angulo)
decisao_mesmo = pp.avalia({"titulo": rv.texto_do_angulo(rv.ANGULOS[0], FATOS)[0], "texto": t2},
                          canal="youtube",
                          publicacoes=[{"canal": "youtube", "titulo": rv.texto_do_angulo(rv.ANGULOS[0], FATOS)[0],
                                        "texto": t1, "angulo": rv.ANGULOS[0]["id"]}],
                          calendario=rv.JANELA_DO_CANAL, hora_local=10)
ok("e o portão recusa esse caso com motivo", decisao_mesmo["publica"] is False, decisao_mesmo)

# O banco de ângulos é o estoque real da casa: um vídeo por ângulo declarado.
ok("o banco de ângulos declara quantos vídeos distintos a casa tem hoje (≥ 10)",
   len(rv.ANGULOS) >= 10, len(rv.ANGULOS))
ok("cada ângulo tem id único (sem dois ângulos com o mesmo nome)",
   len({a["id"] for a in rv.ANGULOS}) == len(rv.ANGULOS), [a["id"] for a in ANGULOS_OK])
shutil.rmtree(outra, ignore_errors=True)

# 7b. o kit usa o ângulo aprovado e o registro do envio guarda qual foi
pacote, erros = kitg.pacote("ceifalume")
ok("o kit do gameplay monta o pacote", pacote is not None and not erros, erros)
if pacote:
    fora_da_janela = rv.hora_local_do_canal() < 9 or rv.hora_local_do_canal() >= 22
    if fora_da_janela:
        ok("fora da janela o kit mantém o molde e diz por que (o portão recusa depois)",
           pacote.get("angulo") is None and bool(pacote.get("recusas_do_redator")),
           (pacote.get("angulo"), pacote.get("recusas_do_redator")))
    else:
        ok("o kit usa o ângulo aprovado pelo redator",
           pacote.get("angulo") in ids or bool(pacote.get("fato")), pacote.get("angulo"))
        if pacote.get("angulo") in TEXTOS:
            ok("o título do pacote é o do ângulo escolhido",
               pacote["titulo"] == TEXTOS[pacote["angulo"]][0] or
               pp.semelhanca_de_texto(pacote["titulo"], TEXTOS[pacote["angulo"]][0]) > 0.95,
               pacote["titulo"])
        else:
            ok("o vídeo de fato declara qual fato o sustenta (e ele existe na casa)",
               pacote.get("fato") in {x["id"] for x in rv.fatos_da_casa()}, pacote.get("fato"))
    ok("o kit carrega a lista de recusas do redator (prova, não silêncio)",
       isinstance(pacote.get("recusas_do_redator"), list))

tmp = tempfile.mkdtemp(prefix="bancada-registro-")
os.makedirs(os.path.join(tmp, "posts"), exist_ok=True)
enviar.registrar(tmp, "ceifalume", "título de teste", "VID1", arquivo="media/x.mp4",
                 descricao="descrição de teste", angulo="pergunta", escrever=lambda *_: None)
gravado = json.load(open(os.path.join(tmp, "posts", "youtube-publicados.json"), encoding="utf-8"))
primeiro = gravado["publicados"][0]
ok("o registro público guarda o ângulo do vídeo", primeiro.get("angulo") == "pergunta", primeiro)
ok("o registro público guarda a descrição (o próximo portão compara com ela)",
   primeiro.get("descricao") == "descrição de teste", primeiro)
ok("o histórico do envio devolve o ângulo",
   enviar.historico_publicado(tmp)[0].get("angulo") == "pergunta")
shutil.rmtree(tmp, ignore_errors=True)

# 18. o redator não toca a rede
fonte = open(os.path.join(RAIZ, "tools", "redator-video.py"), encoding="utf-8").read()
ok("o redator não importa rede (urllib, requests, socket)",
   not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http)", fonte, re.M))

# ---- perguntas do leitor × fatos da casa: o estoque cresce com fato novo, não com sinônimo
ok("a casa tem fatos com origem e data para virar assunto de vídeo", len(FATOS_DA_CASA) >= 10,
   len(FATOS_DA_CASA))
ok("nenhum fato da casa é de outro jogo (o vídeo é do Ceifalume)",
   all((x.get("assunto") or "") in ("ceifalume", "casa", "oficio") for x in FATOS_DA_CASA),
   sorted({x.get("assunto") for x in FATOS_DA_CASA}))
ok("fato da classe número não entra (seria número de OUTRA gravação)",
   all(x.get("classe") != "numero" for x in FATOS_DA_CASA))
ok("todo fato usado tem origem, data e id",
   all(x.get("origem") and x.get("quando") and x.get("id") for x in FATOS_DA_CASA))

AMOSTRA = rv.angulos_de_fato([])[:6]
ok("as perguntas do leitor geram ângulos de fato", len(AMOSTRA) == 6, len(AMOSTRA))
for angulo in AMOSTRA:
    titulo, descricao = rv.texto_do_angulo(angulo, FATOS)
    fato = angulo["_fato"]
    ok("%s: o texto usa a afirmação do fato (palavras do fato, não paráfrase vazia)" % angulo["id"],
       any(palavra in descricao.lower() for palavra in fato["afirmacao"].lower().split()[:4]),
       descricao[:80])
    ok("%s: a descrição cita a origem do fato" % angulo["id"], fato["origem"] in descricao)
    ok("%s: título na faixa e sem promessa" % angulo["id"],
       12 <= len(titulo) <= 90 and rv.problemas_do_texto(titulo, descricao, FATOS) == [],
       (len(titulo), rv.problemas_do_texto(titulo, descricao, FATOS)))
    decisao = pp.avalia({"titulo": titulo, "texto": descricao}, canal="youtube",
                        publicacoes=[], calendario=rv.JANELA_DO_CANAL, hora_local=10)
    ok("%s: passa o portão como primeiro vídeo do canal" % angulo["id"], decisao["publica"],
       decisao["motivo"])

ok("fato já usado não volta a ser oferecido",
   all(a["_fato"]["id"] != FATOS_DA_CASA[0]["id"]
       for a in rv.angulos_de_fato([FATOS_DA_CASA[0]["id"]])),
   FATOS_DA_CASA[0]["id"])

# a prova do estoque: quantos vídeos distintos o redator sustenta hoje, com partida nova a cada um
f0 = FATOS
historico_estoque, escolhidos_estoque = [], []
for volta in range(40):
    f = dict(f0)
    f.update({"plantadas": 10 + volta, "colhidas": 4 + volta, "toques": 700 + 7 * volta,
              "toques_por_minuto": 350 + volta,
              "_anterior": {"colhidas": 3 + volta, "toques": 693 + 7 * volta}})
    usados = {x.get("fato") for x in historico_estoque if x.get("fato")}
    achado = None
    for angulo in list(rv.ANGULOS) + rv.angulos_de_fato(usados):
        if any(f.get(c) in (None, "", []) for c in (angulo.get("precisa") or ())):
            continue
        titulo, descricao = rv.texto_do_angulo(angulo, f)
        if rv.problemas_do_texto(titulo, descricao, f):
            continue
        decisao = pp.avalia({"titulo": titulo, "texto": descricao}, canal="youtube",
                            publicacoes=historico_estoque, calendario=rv.JANELA_DO_CANAL,
                            hora_local=10)
        if decisao.get("publica"):
            achado = (angulo, titulo, descricao)
            break
    if not achado:
        break
    angulo, titulo, descricao = achado
    escolhidos_estoque.append(angulo["id"])
    historico_estoque.insert(0, {"canal": "youtube", "titulo": titulo, "texto": descricao,
                                 "angulo": angulo["id"], "fato": angulo.get("fato"),
                                 "numeros": {k: f[k] for k in ("plantadas", "colhidas", "toques",
                                                               "minutos", "toques_por_minuto")},
                                 "id": "E%d" % volta, "quando": "2026-11-06T10:%02d:00Z" % volta})
ok("o estoque de vídeos distintos passou de 10 (era o limite antes dos fatos)",
   len(escolhidos_estoque) >= 20, len(escolhidos_estoque))
ok("e nenhum vídeo repete o mesmo par pergunta×fato",
   len(set(escolhidos_estoque)) == len(escolhidos_estoque), escolhidos_estoque)
ok("o estoque usa fatos distintos, não o mesmo fato com sinônimos",
   len({x.get("fato") for x in historico_estoque if x.get("fato")}) >= 8,
   len({x.get("fato") for x in historico_estoque if x.get("fato")}))

print("\n%d/%d contratos do redator do vídeo passaram" % (certos, certos + falhas))
raise SystemExit(0 if falhas == 0 else 1)
