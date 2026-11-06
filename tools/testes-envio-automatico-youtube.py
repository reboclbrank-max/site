#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos do portão do vídeo: o mesmo vídeo não sobe duas vezes.

O que se prova aqui, sem rede, sem segredo e sem subir nada:

  1. AUTOMÁTICO sem vídeo novo é recusado, com o id do anterior no motivo.
  2. AUTOMÁTICO com vídeo novo passa e registra a impressão (sha256) do que subiu.
  3. MANUAL (PUBLICAR) continua funcionando — e também registra a impressão.
  4. Palavra errada é recusada nos dois caminhos.
  5. Um envio que falha NÃO registra impressão (senão o vídeo ficaria "gasto" sem ter subido).

Contexto medido em 06/11/2026: o canal tinha 163 vídeos e o mesmo título de gameplay foi ao ar
três vezes. A palavra humana liberou a duplicata igualzinho ao primeiro envio.
"""
import importlib.util
import json
import os
import pathlib
import shutil
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("enviar_youtube", RAIZ / "tools" / "enviar-youtube.py")
enviar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enviar)

resultados = []


def checar(nome, condicao, detalhe=""):
    ok = bool(condicao)
    resultados.append((nome, ok))
    print(("PASS" if ok else "FAIL") + " — " + nome + (("  [" + str(detalhe)[:140] + "]") if detalhe and not ok else ""))


PACOTE = {"id": "ceifalume-gameplay", "slug": "ceifalume", "arquivo": "media/video.mp4",
          "titulo": "CEIFALUME 0.1 — gameplay gravado no navegador",
          "descricao": "descrição do vídeo", "tags": ["indie", "godot"],
          "capa": "media/capa.png", "dimensoes": [1280, 720],
          "formato": "vídeo normal (16:9)"}


def bancada(video_bytes=b"v" * 20_000, kit=None, publicados=None, impressos=None):
    """Um repositório descartável com kit, vídeo e registros."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bancada-youtube-"))
    (tmp / "media").mkdir(parents=True, exist_ok=True)
    (tmp / "posts").mkdir(parents=True, exist_ok=True)
    (tmp / "media" / "video.mp4").write_bytes(video_bytes)
    (tmp / "media" / "capa.png").write_bytes(b"x" * 1000)
    dados = kit if kit is not None else {"pacotes": [dict(PACOTE)]}
    (tmp / "posts" / "kit-gameplay.json").write_text(json.dumps(dados), encoding="utf-8")
    # o caminho do kit é variável de ambiente na casa (KIT_YOUTUBE); a bancada imita isso
    os.environ["KIT_YOUTUBE"] = str(tmp / "posts" / "kit-gameplay.json")
    os.environ["YT_REGISTRO"] = "1"
    if publicados is not None:
        (tmp / "posts" / "youtube-publicados.json").write_text(json.dumps(publicados), encoding="utf-8")
    if impressos is not None:
        (tmp / "posts" / "videos-enviados.json").write_text(json.dumps(impressos), encoding="utf-8")
    return tmp


def dublês(ok=True):
    chamadas = {"iniciar": 0, "enviar": 0}

    def renovar(*a, **k):
        return "token-de-teste", None

    def iniciar(token, meta, tamanho):
        chamadas["iniciar"] += 1
        return ("https://upload.exemplo/sessao", None) if ok else (None, "sem sessão")

    def enviar_bytes(url, caminho):
        chamadas["enviar"] += 1
        return ({"id": "VIDEO123"}, None) if ok else (None, "falhou no meio")

    return renovar, iniciar, enviar_bytes, chamadas


def validador_ok(pacote):
    return []


def rodar(raiz, confirmacao, ok=True, impressora=None, hora_local=12, publicacoes=(),
          aplicar_capa=None):
    """Roda o envio na bancada. `publicacoes` é o histórico do canal; vazio = canal novo.

    `hora_local=12` é o padrão de propósito: a janela do dono (09-22h) faz parte do portão, e um
    teste que dependesse da hora do relógio reprovaria de madrugada sem nada estar quebrado.
    """
    renovar, iniciar, enviar_bytes, chamadas = dublês(ok)
    enviou, msg = enviar.executar("ceifalume-gameplay", confirmacao, raiz=str(raiz),
                                  renovar=renovar, validador=validador_ok,
                                  iniciar=iniciar, enviar=enviar_bytes,
                                  escrever=lambda *a, **k: None, impressora=impressora,
                                  hora_local=hora_local, publicacoes=list(publicacoes),
                                  aplicar_capa=aplicar_capa)
    return enviou, msg, chamadas


# 1. palavra errada
with tempfile.TemporaryDirectory() as tmp:
    raiz = bancada()
    ok, msg, _ = rodar(raiz, "vai")
    checar("palavra errada é recusada", ok is False and "confirmação" in msg, msg)
    ok, msg, _ = rodar(raiz, "")
    checar("sem palavra nenhuma é recusada", ok is False, msg)
    shutil.rmtree(raiz, ignore_errors=True)

# 2. automático com vídeo novo
raiz = bancada()
ok, msg, _ = rodar(raiz, "AUTOMATICO")
checar("automático com vídeo novo envia", ok is True and "VIDEO123" in msg, msg)
registro = json.loads((raiz / "posts" / "videos-enviados.json").read_text(encoding="utf-8"))
checar("o envio grava a impressão sha256", len(registro["enviados"]) == 1
      and len(registro["enviados"][0]["sha256"]) == 64, registro.get("enviados"))
checar("a impressão aponta o vídeo que subiu", registro["enviados"][0]["id"] == "VIDEO123")
sha_primeiro = registro["enviados"][0]["sha256"]

# 3. o mesmo vídeo, de novo, no automático
ok, msg, _ = rodar(raiz, "AUTOMATICO")
checar("o MESMO vídeo não sobe duas vezes", ok is False and "já publicado" in msg, msg)
checar("e o motivo diz qual vídeo já existe", "VIDEO123" in msg, msg)
checar("recusar não apaga nem duplica a impressão existente",
      len(json.loads((raiz / "posts" / "videos-enviados.json").read_text())["enviados"]) == 1)

# 4. vídeo diferente (mesmo kit, outro arquivo) sobe
(raiz / "media" / "video.mp4").write_bytes(b"z" * 20_500)
ok, msg, _ = rodar(raiz, "AUTOMATICO")
checar("vídeo diferente é aceito como novo", ok is True, msg)
checar("agora são duas impressões distintas",
      len(json.loads((raiz / "posts" / "videos-enviados.json").read_text())["enviados"]) == 2)

# 5. manual continua valendo — e também registra
(raiz / "media" / "video.mp4").write_bytes(b"w" * 20_900)
ok, msg, _ = rodar(raiz, "PUBLICAR")
checar("manual (PUBLICAR) continua funcionando", ok is True, msg)
checar("manual também grava impressão",
      len(json.loads((raiz / "posts" / "videos-enviados.json").read_text())["enviados"]) == 3)
ok, msg, _ = rodar(raiz, "AUTOMATICO")
checar("depois do manual, o automático não repete o mesmo arquivo",
      ok is False and "já publicado" in msg, msg)
shutil.rmtree(raiz, ignore_errors=True)

# 6. envio que falha não gasta o vídeo
raiz = bancada()
ok, msg, _ = rodar(raiz, "AUTOMATICO", ok=False)
checar("falha no upload não é sucesso", ok is False, msg)
nao_existe = not (raiz / "posts" / "videos-enviados.json").exists()
checar("falha no upload NÃO registra impressão (o vídeo pode tentar de novo)", nao_existe)
ok, msg, _ = rodar(raiz, "AUTOMATICO", ok=True)
checar("depois da falha, o mesmo vídeo ainda pode subir", ok is True, msg)
shutil.rmtree(raiz, ignore_errors=True)

# 7. vídeo ausente e kit inválido
raiz = bancada()
(raiz / "media" / "video.mp4").unlink()
ok, msg, _ = rodar(raiz, "AUTOMATICO")
checar("vídeo ausente é recusado", ok is False and "ausente" in msg, msg)
shutil.rmtree(raiz, ignore_errors=True)

raiz = bancada(video_bytes=b"x" * 500)
ok, msg, _ = rodar(raiz, "AUTOMATICO")
checar("arquivo pequeno demais para ser vídeo é recusado", ok is False and "pequeno" in msg, msg)
shutil.rmtree(raiz, ignore_errors=True)

# 8. o registro é do repositório e começa vazio
if (RAIZ / "posts" / "videos-enviados.json").exists():
    dados = json.loads((RAIZ / "posts" / "videos-enviados.json").read_text(encoding="utf-8"))
    checar("o registro de impressões do repositório é uma lista", isinstance(dados.get("enviados"), list))
else:
    checar("o registro de impressões ainda não existe no repositório (nada foi enviado desde o portão)",
           True)

# 9. o workflow não publica vídeo por horário: só pelo portão
wf = (RAIZ / ".github" / "workflows" / "gravar-gameplay.yml").read_text(encoding="utf-8")
checar("o workflow passa AUTOMATICO (não PUBLICAR) no caminho agendado",
      "AUTOMATICO" in wf and "CONFIRMACAO: AUTOMATICO" in wf)
checar("o caminho manual do workflow continua existindo", "github.event.inputs.publicar == 'PUBLICAR'" in wf)
checar("o workflow versiona o registro de impressões", "posts/videos-enviados.json" in wf)
checar("o registro guarda o ângulo do vídeo (é o que faz o redator rodar)",
      "angulo=pacote.get(\"angulo\")" in open(RAIZ / "tools" / "enviar-youtube.py", encoding="utf-8").read())
# Medido no run 42248857217 (06/11/2026 16:08 UTC): o vídeo subiu, o registro entrou no main e o
# run terminou VERMELHO porque o resumo fazia `cat /tmp/envio.txt`, arquivo que só o caminho
# manual cria. Trabalho feito com run vermelho é o mesmo defeito de antes, só que ao contrário.
checar("o resumo do workflow não depende de arquivo que só o caminho manual cria",
      "cat /tmp/envio.txt 2>/dev/null" in wf and "envio-auto.txt 2>/dev/null" in wf)
checar("o passo do registro roda também no caminho automático",
      "github.event.inputs.publicar == 'AUTOMATICO'" in wf)

# 10. o arquivo novo NÃO basta: o mesmo título não sobe de novo
#     (medido em 06/11/2026: três uploads com o mesmo título, arquivos diferentes)
HISTORICO = [{"canal": "youtube", "id": "f5kQFOQs0To",
              "titulo": "CEIFALUME 0.1 — jogo idle de fazenda noturna (jogo indie brasileiro)"
                        " — gameplay gravado no navegador",
              "texto": "", "quando": "2026-11-04T05:17:32Z"}]
raiz = bancada()
kit_repetido = {"pacotes": [dict(PACOTE, titulo=HISTORICO[0]["titulo"])]}
(raiz / "posts" / "kit-gameplay.json").write_text(json.dumps(kit_repetido), encoding="utf-8")
ok, msg, chamadas = rodar(raiz, "AUTOMATICO", publicacoes=HISTORICO)
checar("título já publicado é recusado mesmo com arquivo novo",
       ok is False and "texto recusou" in msg, msg)
checar("e a recusa por forma não chama o upload", chamadas["enviar"] == 0, chamadas)
checar("a recusa por forma não grava impressão",
       not (raiz / "posts" / "videos-enviados.json").exists())
shutil.rmtree(raiz, ignore_errors=True)

# 11. título próprio (o da partida) passa contra o mesmo histórico
raiz = bancada()
kit_novo = {"pacotes": [dict(PACOTE, titulo="CEIFALUME 0.1: 9 colheitas, 14 mudas plantadas, "
                                            "728 toques em 2 min de jogo")]}
(raiz / "posts" / "kit-gameplay.json").write_text(json.dumps(kit_novo), encoding="utf-8")
ok, msg, _ = rodar(raiz, "AUTOMATICO", publicacoes=HISTORICO)
checar("título que descreve a partida passa contra o histórico", ok is True, msg)
shutil.rmtree(raiz, ignore_errors=True)

# 12. a janela do dono vale para o vídeo também
raiz = bancada()
ok, msg, chamadas = rodar(raiz, "AUTOMATICO", hora_local=3)
checar("vídeo às 3h de Brasília é recusado pela janela", ok is False and "janela" in msg, msg)
checar("e a recusa por horário não chama o upload", chamadas["enviar"] == 0, chamadas)
ok, msg, _ = rodar(raiz, "AUTOMATICO", hora_local=20)
checar("às 20h de Brasília o mesmo vídeo passa", ok is True, msg)
shutil.rmtree(raiz, ignore_errors=True)

# 13. o registro guarda a descrição — é o que o próximo portão de forma vai comparar
raiz = bancada()
rodar(raiz, "AUTOMATICO")
publicado = json.loads((raiz / "posts" / "youtube-publicados.json").read_text(encoding="utf-8"))
checar("o registro público guarda a descrição do que subiu",
       publicado["publicados"][0].get("descricao") == PACOTE["descricao"],
       publicado["publicados"][0].get("descricao"))
checar("o histórico do canal sai do mais novo para o mais antigo",
       [x["quando"] for x in enviar.historico_publicado(str(raiz))]
       == sorted([x["quando"] for x in enviar.historico_publicado(str(raiz))], reverse=True))
shutil.rmtree(raiz, ignore_errors=True)

# 14. o kit do gameplay monta o título a partir da PARTIDA, não de uma frase fixa
spec_kit = importlib.util.spec_from_file_location("kit_gameplay", RAIZ / "tools" / "kit-gameplay.py")
kitg = importlib.util.module_from_spec(spec_kit)
spec_kit.loader.exec_module(kitg)
spec_kit_yt = importlib.util.spec_from_file_location("kit_youtube", RAIZ / "tools" / "kit-youtube.py")
kityt = importlib.util.module_from_spec(spec_kit_yt)
spec_kit_yt.loader.exec_module(kityt)


def bancada_de_partida(plantadas, colhidas, toques, segundos):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bancada-partida-"))
    (tmp / "media" / "gameplay").mkdir(parents=True, exist_ok=True)
    caminho = tmp / "media" / "gameplay" / "ceifalume-gameplay-cru-decisoes.json"
    caminho.write_text(json.dumps({"decisoes": [{"t": segundos, "motivo": "colheu"}],
                                   "plantadas": plantadas, "colhidas": colhidas,
                                   "bicos": toques}), encoding="utf-8")
    return tmp


a = bancada_de_partida(14, 9, 728, 118)
b = bancada_de_partida(6, 2, 133, 96)
ta = kitg.titulo_da_partida("ceifalume", kityt, raiz=str(a))
tb = kitg.titulo_da_partida("ceifalume", kityt, raiz=str(b))
checar("o título do gameplay sai da partida medida", ta and "9 colheitas" in ta and "728 toques" in ta, ta)
checar("duas partidas diferentes dão dois títulos diferentes", ta != tb, (ta, tb))
checar("o título da partida é diferente do título fixo que repetiu três vezes",
      ta != "CEIFALUME 0.1 — jogo idle de fazenda noturna (jogo indie brasileiro)"
            " — gameplay gravado no navegador", ta)
checar("o título da partida cabe no limite do YouTube", 0 < len(ta) <= kityt.LIMITE_TITULO, len(ta))
checar("a descrição diz o que aconteceu naquela partida",
      "Esta partida: 14 mudas plantadas, 9 colheitas e 728 toques" in
      kitg.linha_da_partida("ceifalume", raiz=str(a)), kitg.linha_da_partida("ceifalume", raiz=str(a)))
checar("sem relatório da partida, o título próprio não é inventado",
      kitg.titulo_da_partida("ceifalume", kityt, raiz=str(tempfile.mkdtemp())) is None)
shutil.rmtree(a, ignore_errors=True)
shutil.rmtree(b, ignore_errors=True)


# ---- CAPA ÚNICA: os três vídeos de 06/11 subiram com o mesmo primeiro quadro ----------------
# A capa é desenhada na gravação e APLICADA aqui. Estes contratos cobram isso — e cobram também
# que uma falha de capa não esconda um vídeo que já subiu.
raiz = bancada()
capa = pathlib.Path(raiz) / "media" / "gameplay" / "ceifalume-capa.png"
capa.parent.mkdir(parents=True, exist_ok=True)
capa.write_bytes(b"PNG" + b"z" * 40_000)
chamadas_capa = []


def aplicar(token, vid, caminho):
    chamadas_capa.append((token, vid, caminho))
    return True, "capa aplicada no vídeo " + str(vid)


ok, msg, _ = rodar(raiz, "AUTOMATICO", aplicar_capa=aplicar)
checar("com capa desenhada, o envio aplica a capa", ok is True and len(chamadas_capa) == 1, msg)
checar("a capa vai para o vídeo que acabou de subir",
      bool(chamadas_capa) and chamadas_capa[0][1] == "VIDEO123", chamadas_capa)
checar("a capa aplicada é a capa daquele vídeo",
      bool(chamadas_capa) and chamadas_capa[0][2].endswith("ceifalume-capa.png"), chamadas_capa)

raiz_sem_capa = bancada()
chamadas_capa.clear()
ok, msg, _ = rodar(raiz_sem_capa, "AUTOMATICO", aplicar_capa=aplicar)
checar("sem capa desenhada, publica e não inventa capa",
      ok is True and chamadas_capa == [], (msg, chamadas_capa))

raiz_falha = bancada()
capa2 = pathlib.Path(raiz_falha) / "media" / "gameplay" / "ceifalume-capa.png"
capa2.parent.mkdir(parents=True, exist_ok=True)
capa2.write_bytes(b"PNG" + b"y" * 40_000)


def aplicar_quebrado(*a, **k):
    raise RuntimeError("thumbnails/set recusou")


ok, msg, _ = rodar(raiz_falha, "AUTOMATICO", aplicar_capa=aplicar_quebrado)
checar("capa que falha não derruba uma publicação que deu certo",
      ok is True and "publicado" in msg, msg)

for r in (raiz, raiz_sem_capa, raiz_falha):
    shutil.rmtree(r, ignore_errors=True)


# ---- o registro não pode guardar descrição cortada no meio da frase -------------------------
# Medido em 06/11/2026: quatro descrições em posts/youtube-publicados.json terminavam em
# "…A trilha". Registro quebrado mente sobre o que está no ar.
_longa = ("Linha curta.\n\n" + "Frase completa sobre a partida medida. " * 40)
_resumo = enviar._resumo_da_descricao(_longa)
checar("resumo da descrição não termina no meio de uma palavra",
      _resumo.endswith("…") or _resumo.endswith("."), _resumo[-25:])
checar("resumo da descrição cabe no registro", len(_resumo) <= 640, len(_resumo))
checar("descrição curta passa inteira", enviar._resumo_da_descricao("Texto curto.") == "Texto curto.")

certos = sum(1 for _, ok in resultados if ok)
print("%d/%d contratos do portão do vídeo passaram" % (certos, len(resultados)))
raise SystemExit(0 if certos == len(resultados) else 1)
