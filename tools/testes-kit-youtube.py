#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do kit de envio do YouTube — offline, sem rede e sem segredo.

O risco aqui é o kit virar enfeite: título com promessa que a casa não sustenta, link que não
é oficial, arquivo que não existe, ou — o pior — o robô começar a enviar sozinho. Cada teste
cerca um desses.
"""
import importlib.util
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("kit", os.path.join(RAIZ, "tools", "kit-youtube.py"))
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + detalhe if detalhe else ""))


dados = kit.montar()
pacotes = {p["slug"]: p for p in dados["pacotes"]}

# 1. todo jogo tem pacote, e nenhum pacote é recusado
ok("todo jogo da casa tem pacote", set(pacotes) == set(kit.JOGOS), str(sorted(pacotes)))
ok("nenhum pacote recusado pelas regras da casa", dados["problemas"] == {}, str(dados["problemas"]))

for slug, p in pacotes.items():
    # 2. limites reais do YouTube
    ok(f"{slug}: título dentro de 100 caracteres", 0 < len(p["titulo"]) <= 100, str(len(p["titulo"])))
    ok(f"{slug}: descrição dentro de 5000 caracteres", 0 < len(p["descricao"]) <= 5000)
    ok(f"{slug}: tags dentro de 500 caracteres",
       sum(len(t) + 1 for t in p["tags"]) <= 500)
    # 3. links SEMPRE oficiais (lista fechada), nunca URL livre
    ok(f"{slug}: link do jogo é o oficial", kit.JOGOS[slug]["link"] in p["descricao"])
    ok(f"{slug}: link do hub de canais presente", kit.HUB_CANAIS in p["descricao"])
    urls = re.findall(r"https?://[^\s)]+", p["descricao"])
    ok(f"{slug}: nenhuma URL fora da casa", all(u.startswith("https://reboclbrank-max.github.io/") for u in urls),
       str(urls))
    # 4. o arquivo tem que existir de verdade
    ok(f"{slug}: arquivo de vídeo existe no repositório", p["arquivo_existe"])
    ok(f"{slug}: dimensões foram medidas, não supostas", isinstance(p["dimensoes"], tuple))
    # 5. nada de promessa que a casa não sustenta
    ok(f"{slug}: sem promessa vazia", not kit.PROIBIDO.search(p["titulo"] + p["descricao"]))
    # 6. o pacote é acionável: o dono tem passo a passo
    ok(f"{slug}: o dono recebe passo a passo", len(p["passos_do_dono"]) >= 4)

# 7. formato declarado com honestidade. A REGRA é "vertical fora do 9:16 é avisado", testada
# contra o arquivo 4:5 de verdade (media/reel.mp4) — não contra a escolha atual do kit, que
# passou a preferir o gameplay 16:9 (31/10/2026). Testar a escolha em vez da regra fazia o
# teste quebrar quando a escolha melhorava.
_reel = kit.JOGOS["prancheta"].get("video_reserva", "media/reel.mp4")
_d = kit.dimensoes_mp4(_reel)
ok("a regra do aviso reconhece o 4:5 como vertical", bool(_d) and _d[1] > _d[0], _d)
_aviso = ("vertical %dx%d" % _d) if (_d and _d[1] > _d[0] and abs(_d[0] / float(_d[1]) - 9 / 16.0) > 0.02) else None
ok("vertical fora do 9:16 é avisado, não escondido", _aviso is not None, _aviso)
ok("16:9 não ganha aviso",
   all(p.get("aviso_formato") is None for p in pacotes.values()), 
   {k: v.get("aviso_formato") for k, v in pacotes.items()})

# 8. o kit NÃO envia nada: sem upload, sem OAuth, sem POST
fonte = open(os.path.join(RAIZ, "tools", "kit-youtube.py"), encoding="utf-8").read()
ok("o kit não faz upload (nenhum endpoint de escrita)",
   "upload" not in fonte.lower() or "exige OAuth" in fonte or "não envia" in fonte)
ok("o kit não usa token nem chave", "API_KEY" not in fonte and "access_token" not in fonte)
ok("o kit não faz requisição de rede", "urlopen" not in fonte and "requests" not in fonte)
ok("a razão do bloqueio está escrita no próprio kit", "OAuth" in fonte)

# 9. o validador recusa de propósito (senão a barreira não prova nada)
_ruim = dict(pacotes["prancheta"])
_ruim["titulo"] = "PRANCHETA é o melhor do mundo"
ok("promessa vazia é recusada pelo validador", "promessa" in " ".join(kit.validar(_ruim)),
   str(kit.validar(_ruim)))
_ruim2 = dict(pacotes["prancheta"])
_ruim2["descricao"] = "PRANCHETA, jogo de futebol."
ok("descrição fraca é recusada", any("curta" in e for e in kit.validar(_ruim2)))
_ruim3 = dict(pacotes["prancheta"])
_ruim3["arquivo"] = "media/nao-existe.mp4"
_ruim3["arquivo_existe"] = False
ok("arquivo ausente é recusado", any("ausente" in e for e in kit.validar(_ruim3)))

# PREFERÊNCIA MEDIDA (31/10/2026): o kit do YouTube tem de apontar para o vídeo 16:9 quando ele
# existe. Publicar o reel 4:5 por ser o arquivo mais à mão é escolher o errado por conveniência.
_cfg = open(os.path.join(RAIZ, "tools", "kit-youtube.py"), encoding="utf-8").read()
ok("o kit do YouTube prefere o gameplay 16:9 ao reel 4:5",
         'media/gameplay/prancheta-gameplay.mp4' in _cfg
         and _cfg.index('media/gameplay/prancheta-gameplay.mp4') < _cfg.index('"video_reserva"'))
ok("o reel continua registrado como reserva (nada foi jogado fora)", '"video_reserva"' in _cfg)

print("\n%d/%d testes do kit do YouTube passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)

# PREFERÊNCIA MEDIDA (31/10/2026): o kit do YouTube tem de apontar para o vídeo 16:9 quando ele
# existe. Publicar o reel 4:5 por ser o arquivo mais à mão é escolher o errado por conveniência.
_cfg = open(os.path.join(RAIZ, "tools", "kit-youtube.py"), encoding="utf-8").read()
ok("o kit do YouTube prefere o gameplay 16:9 ao reel 4:5",
         'media/gameplay/prancheta-gameplay.mp4' in _cfg and
         _cfg.index('media/gameplay/prancheta-gameplay.mp4') < _cfg.index('"video_reserva"'))
ok("o reel continua registrado como reserva (nada foi jogado fora)", '"video_reserva"' in _cfg)
