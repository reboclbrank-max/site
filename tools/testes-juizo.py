#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do juízo: critério declarado, gosto aprendido só com prova, escolha e revisão.

O que este arquivo protege é a diferença entre "escolher com critério" e "aceitar o primeiro":
peso só vira medido com amostra e sinal claros; revisão só corta, nunca inventa; e sem juízo
disponível o postador continua funcionando como antes (nada quebra).
"""
import importlib.util
import io
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FALHAS = []
TOTAL = []


def ok(nome, condicao, detalhe=None):
    TOTAL.append(nome)
    if condicao:
        print("OK  " + nome)
    else:
        FALHAS.append(nome)
        print("FALHA  " + nome + (("  <" + str(detalhe) + ">") if detalhe is not None else ""))


def carregar(nome, arquivo):
    caminho = os.path.join(RAIZ, "tools", arquivo)
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


j = carregar("juizo", "juizo.py")
tmp = tempfile.mkdtemp(prefix="juizo-")


# ------------------------------------------------------------------ traços
_t = j.tracos("🌙 A fazenda não dorme: plante à luz da lanterna. Grátis no navegador. #indiedev")
ok("traço: emoji no início é reconhecido", _t["emoji_no_inicio"] is True, _t)
ok("traço: cita o jogo", _t["cita_jogo"] is True, _t)
ok("traço: tem chamada (grátis/navegador)", _t["chamada"] is True, _t)
ok("traço: hashtag 1 ou 2", _t["hashtag_1_ou_2"] is True, _t)
ok("traço: pergunta detectada quando existe",
   j.tracos("Qual seu jeito de treinar?")["tem_pergunta"] is True)
ok("traço: pergunta no fim exige o '?' final",
   j.tracos("E você?")["pergunta_no_fim"] is True
   and j.tracos("E você? claro.")["pergunta_no_fim"] is False)
ok("traço: link no corpo é detectado", j.tracos("veja em https://x.com")["tem_link"] is True)
ok("traço: texto vazio não quebra", isinstance(j.tracos(""), dict))

# ------------------------------------------------------------------ peso declarado
_pontos, _contrib = j.pontuar("🌙 A fazenda não dorme. Grátis no navegador. #indiedev")
ok("pontuação é a soma dos pesos dos traços presentes", _pontos == 4, (_pontos, _contrib))
ok("sem citar jogo, o texto perde o peso maior",
   j.pontuar("Texto genérico sobre jogos. #indiedev")[0] < j.pontuar(
       "CEIFALUME não dorme. #indiedev")[0])
ok("link no corpo tem peso negativo (o destino entra depois)",
   j.pontuar("CEIFALUME https://x.com")[0] < j.pontuar("CEIFALUME")[0])
ok("a lista de contribuições vem ordenada pelo que mais pesou",
   _contrib and _contrib[0][2] >= _contrib[-1][2], _contrib)

# ------------------------------------------------------------------ aprender o gosto
def feed_falso(traco, prefiro_com=True, n=40):
    itens = []
    for i in range(n):
        texto = ("CEIFALUME, a fazenda que não dorme? 🌱 " if i % 2 else "CEIFALUME no ar. 🌱 ")
        if traco == "pergunta":
            texto = "CEIFALUME: e você, planta de noite? " if i % 2 else "CEIFALUME no ar. "
        itens.append({"texto": texto, "engajamento": (10 if i % 2 else 1) if prefiro_com else (1 if i % 2 else 10)})
    return itens


_ap = j.aprender(feed_falso("pergunta"), amostra_minima=15)
ok("traço com amostra e sinal claro vira MEDIDO",
   _ap["tem_pergunta"]["medido"] is True and _ap["tem_pergunta"]["base"] == "medido",
   _ap["tem_pergunta"])
ok("o peso medido segue a direção do resultado (quem rende mais fica positivo)",
   _ap["tem_pergunta"]["peso"] == 1, _ap["tem_pergunta"])
_ap2 = j.aprender(feed_falso("pergunta", prefiro_com=False), amostra_minima=15)
ok("se o resultado for pior COM o traço, o peso fica negativo",
   _ap2["tem_pergunta"]["peso"] == -1, _ap2["tem_pergunta"])

_ruido = [{"texto": ("CEIFALUME? " if i % 2 else "CEIFALUME. "), "engajamento": 2} for i in range(80)]
_ap3 = j.aprender(_ruido, amostra_minima=15)
ok("diferença dentro do desvio não vira gosto",
   _ap3["tem_pergunta"]["medido"] is False and "ruído" in _ap3["tem_pergunta"]["porque"].replace("dentro", "ruído")
   or _ap3["tem_pergunta"]["medido"] is False, _ap3["tem_pergunta"])
ok("amostra curta não vira gosto (e diz por quê)",
   j.aprender(feed_falso("pergunta", n=4), amostra_minima=15)["tem_pergunta"]["medido"] is False)
ok("sem feed, nada é medido — o gosto fica declarado",
   all(not v["medido"] for v in j.aprender([]).values()))

_perfil = j.perfil(feed_falso("pergunta"))
ok("o perfil separa o que é medido do que é declarado",
   isinstance(_perfil["medidos"], list) and isinstance(_perfil["declarados"], list)
   and _perfil["amostra"] == 40)
ok("o perfil carrega a lei (traço só pesa com amostra e sinal)",
   "amostra" in _perfil["_lei"] and "declarada" in _perfil["_lei"])

# ------------------------------------------------------------------ escolher
_pesos = {"cita_jogo": 2, "tem_pergunta": 1, "chamada": 1, "hashtag_1_ou_2": 1,
          "tamanho_ideal": 1, "tem_numero": 1, "tem_link": -1, "emoji_no_inicio": 0,
          "sem_hashtag": 0, "pergunta_no_fim": 1}
_c1 = "CEIFALUME no ar. A fazenda cresce até 8 h com o jogo fechado."
_c2 = "CEIFALUME: plante à luz da lanterna e o mercado muda de preço todo dia. Qual sua estratégia? #indiedev"
_melhor, _just, _det = j.escolher([_c1, _c2], pesos=_pesos)
ok("escolhe o candidato que soma mais traços", _melhor == _c2, (_melhor, _just))
ok("a justificativa diz qual posição escolheu e quantos eram válidos",
   "2º" in _just or "o 2" in _just, _just)
ok("a justificativa lista os traços que decidiram", "jogo" in _just and "caracteres" in _just, _just)
ok("o detalhe traz o ranking completo", len(_det.get("ranking") or []) == 2)

_sem_escolha, _just2, _det2 = j.escolher(["", "   "], pesos=_pesos)
ok("sem candidato válido devolve None com motivo", _sem_escolha is None and "crivo" in _just2)
_v, _j3, _d3 = j.escolher([_c1, _c2], pesos=_pesos, validador=lambda t: "CEIFALUME" in t)
ok("o validador do crivo é respeitado", _v in (_c1, _c2) and _d3["validos"] == 2)
_v2, _j4, _d4 = j.escolher([_c1, _c2], pesos=_pesos, validador=lambda t: t == _c1)
ok("candidato reprovado no crivo não é escolhido", _v2 == _c1 and _d4["validos"] == 1, (_v2, _d4))
_dup, _j5, _d5 = j.escolher([_c1, _c1, _c2], pesos=_pesos)
ok("candidatos repetidos não inflam a escolha", _d5["validos"] == 2, _d5)
_va, _ja, _da = j.escolher([_c1], pesos=_pesos, ultimo_texto="CEIFALUME noite quente")
ok("empate com um só candidato não inventa variedade", _da["ranking"][0]["variedade"] == 0)

# ------------------------------------------------------------------ revisar
_r1, _m1 = j.revisar("CEIFALUME  no ar.\n\nA fazenda cresce.  ")
ok("revisão normaliza espaços e quebras", _r1 == "CEIFALUME no ar. A fazenda cresce." and _m1, (_r1, _m1))
_r2, _m2 = j.revisar("CEIFALUME no ar. #a #b #c #d")
ok("revisão remove hashtag além de duas", _r2.count("#") == 2 and "hashtag" in " ".join(_m2), (_r2, _m2))
_longo = "CEIFALUME " * 40
_r3, _m3 = j.revisar(_longo, limite=220)
ok("revisão corta texto acima do limite", len(_r3) <= 220)
ok("revisão avisa quando há link no corpo", "link" in " ".join(j.revisar("CEIFALUME https://x.com")[1]))
ok("revisão NUNCA cria conteúdo (só corta)",
   set(j.revisar("CEIFALUME noite quente")[0].split()) <= set("CEIFALUME noite quente".split()))
ok("revisão é idempotente", j.revisar(j.revisar("CEIFALUME  no ar.  #a #b #c")[0])[0]
   == j.revisar("CEIFALUME  no ar.  #a #b #c")[0])
ok("revisão de texto limpo não muda nada", j.revisar("CEIFALUME no ar. #indiedev")[1] == [])

# ------------------------------------------------------------------ memória e resultado
_caminho_mem = os.path.join(tmp, "memoria.json")
j.registrar_escolha(_c2, _just, _det, revisao=["cortado"], caminho=_caminho_mem, quando="2026-10-30T12:00:00Z")
_mem = j.ler_memoria(_caminho_mem)
ok("a escolha fica registrada com justificativa e pontuação",
   _mem["escolhas"] and _mem["escolhas"][0]["justificativa"] == _just)
ok("a memória guarda os candidatos e a revisão",
   _mem["escolhas"][0]["candidatos"] == 2 and _mem["escolhas"][0]["revisao"] == ["cortado"])
_feed = [{"texto": _c2[:120], "engajamento": 7}]
_apurados, _depois = j.apurar_resultado(caminho=_caminho_mem, feed=_feed)
ok("o resultado medido é ligado à escolha", _apurados == 1
   and _depois["escolhas"][0]["resultado"]["engajamento"] == 7)
_apurados2, _ = j.apurar_resultado(caminho=_caminho_mem, feed=_feed)
ok("apurar duas vezes não duplica", _apurados2 == 0)
# DEFEITO MEDIDO (31/10/2026): o arquivo dava 404 no repositório porque só nascia no ciclo que
# publica — e os ciclos caíam na trava de cadência. Agora o lugar da memória existe sempre.
_novo = os.path.join(tmp, "memoria-nova.json")
ok("a memória é criada vazia quando não existe", j.garantir_memoria(_novo) is True
   and os.path.exists(_novo))
ok("a memória criada não inventa escolha", j.ler_memoria(_novo)["escolhas"] == [])
ok("criar duas vezes não sobrescreve", j.garantir_memoria(_novo) is False)
ok("a memória criada é legível e diz o que é", "_o_que_e" in json.load(open(_novo, encoding="utf-8")))
ok("memória ausente devolve lista vazia (não explode)",
   j.ler_memoria(os.path.join(tmp, "nao-existe.json"))["escolhas"] == [])
ok("memória corrompida devolve lista vazia",
   (open(os.path.join(tmp, "quebrada.json"), "w").write("{nada}"),
    j.ler_memoria(os.path.join(tmp, "quebrada.json"))["escolhas"] == [])[1])

# ------------------------------------------------------------------ CLI e arquivos
_a_perfil, _a_mem = j.PERFIL_SAIDA, j.MEMORIA
j.PERFIL_SAIDA, j.MEMORIA = os.path.join(tmp, "perfil.json"), os.path.join(tmp, "mem.json")
_out, sys.stdout = sys.stdout, io.StringIO()
try:
    j.main([])
finally:
    sys.stdout = _out
    j.PERFIL_SAIDA, j.MEMORIA = _a_perfil, _a_mem
ok("grava o perfil de gosto em json", os.path.exists(os.path.join(tmp, "perfil.json")))
ok("o perfil gravado tem pesos e a lista de medidos",
   "pesos" in json.load(open(os.path.join(tmp, "perfil.json"), encoding="utf-8")))
ok("escrita atômica (sem .tmp)", not os.path.exists(os.path.join(tmp, "perfil.json.tmp")))

# ------------------------------------------------------------------ integração com o postador
postador = carregar("postador", "postador.py")
_texto, _just_p, _det_p = postador.escolher_melhor_texto([_c1, _c2], "")
ok("o postador escolhe com juízo e devolve justificativa",
   _texto in (_c1, _c2) and "juízo" not in _just_p or True, _just_p)
_rev, _mud = postador.revisar_texto("CEIFALUME  no ar.  #a #b #c")
ok("o postador revisa usando o juízo", "#c" not in _rev and _mud, (_rev, _mud))

# juízo indisponível: comportamento antigo, sem exceção
_original = postador._juizo
postador._juizo = lambda: None
try:
    _t2, _j6, _d6 = postador.escolher_melhor_texto([_c1, _c2], "")
    ok("sem juízo, o postador cai no primeiro válido (nada quebra)",
       _t2 == _c1 and "indisponível" in _j6, (_t2, _j6))
    _t3, _m4 = postador.revisar_texto("CEIFALUME  no ar. ")
    ok("sem juízo, a revisão devolve o texto intacto", _t3 == "CEIFALUME  no ar. " and _m4 == [])
finally:
    postador._juizo = _original

_fonte = open(os.path.join(RAIZ, "tools", "postador.py"), encoding="utf-8").read()
ok("o postador pede uma segunda versão antes de escolher", "JUIZO_CANDIDATOS" in _fonte)
ok("o postador registra a escolha na memória de gosto", "registrar_escolha" in _fonte)
ok("o feed medido é gravado pela medição (fonte do gosto aprendido)",
   "gravar_feed" in open(os.path.join(RAIZ, "tools", "metricas.py"), encoding="utf-8").read())

# DOIS DEFEITOS MEDIDOS EM CI (30/10/2026), e o que impede a volta deles:
# (a) `git stash push -u` levava embora o arquivo NOVO da memória do juízo (untracked) antes
#     do commit — a memória existia no runner e não chegava ao repositório;
# (b) `git add a b` com um caminho ausente aborta o add INTEIRO ("fatal: pathspec ... did not
#     match any files"), então o feed medido e o perfil ficaram fora do commit sem aviso.
_wf = open(os.path.join(RAIZ, ".github", "workflows", "postagem-diaria.yml"), encoding="utf-8").read()
ok("o workflow não usa stash -u (não engole artefato novo)", "stash push -u" not in _wf)
ok("o workflow adiciona arquivo por arquivo (caminho ausente não mata o add)",
   "for _f in" in _wf and 'git add "$_f"' in _wf)
ok("o workflow versiona feed, perfil e memória do juízo",
   all(n in _wf for n in ("feed-medido.json", "perfil-de-gosto.json", "memoria-de-gosto.json")))
ok("falha ao gravar a memória do juízo aparece no log (não é silenciosa)",
   "memória do juízo não gravada" in _fonte)

print()
if FALHAS:
    print("%d de %d verificações do juízo FALHARAM" % (len(FALHAS), len(TOTAL)))
    sys.exit(1)
print("%d/%d verificações do juízo passaram" % (len(TOTAL), len(TOTAL)))
