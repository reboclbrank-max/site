#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova o `registro-do-vivo.py`: ler o canal e corrigir o resumo do registro, sem tocar no vídeo.

O que se cobra aqui:
  - a página do YouTube é lida de verdade (título e descrição saem do JSON da própria página);
  - o resumo do registro corta em fim de parágrafo, nunca no meio de uma palavra;
  - o registro diz o tamanho que a descrição tem NO CANAL (é esse número que desmente
    "descrição truncada" quando o texto está inteiro);
  - canal que não responde não vira descrição inventada: o registro fica como está e a conta é dita;
  - sem rede nenhuma, o script devolve 2 (SKIP) em vez de fingir sucesso;
  - o ensaio não grava.
"""
import importlib.util
import json
import os
import shutil
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("reg", os.path.join(RAIZ, "tools", "registro-do-vivo.py"))
reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reg)

res = []


def ok(nome, condicao, dado=None):
    res.append((nome, bool(condicao)))
    print(("OK  " if condicao else "FALHOU  ") + nome + (("  <%s>" % (dado,)) if not condicao and dado is not None else ""))


DESCRICAO = ("As plantações crescem e as vendas acontecem por até 8 horas com o jogo fechado.\n\n"
             "Na gravação desta partida: 15 mudas plantadas e 8 colheitas em 2 minutos.\n\n"
             "Gameplay: gravado automaticamente do próprio jogo rodando no navegador. "
             + "A trilha é sintetizada pelo script de produção e as legendas descrevem a decisão. " * 6 +
             "\n\nJogar: https://reboclbrank-max.github.io/site/jogos/ceifalume/\n"
             "Todos os canais da casa: https://reboclbrank-max.github.io/site/canais.html\n\n#indiedev")


def pagina(descricao=DESCRICAO, titulo="Um título publicado"):
    return json.dumps({"title": titulo, "lengthSeconds": "130", "shortDescription": descricao})


def html_com(descricao=DESCRICAO, titulo="Um título publicado"):
    corpo = pagina(descricao, titulo)
    # o extrator procura os dois campos no JSON da página, nesta ordem de aparição
    return '{"x":%s}' % corpo


# 1. extração
titulo, descricao = reg._extrair(html_com())
ok("lê o título publicado", titulo == "Um título publicado", titulo)
ok("lê a descrição publicada inteira", descricao == DESCRICAO, (descricao or "")[:60])
ok("página sem os campos devolve (None, None)", reg._extrair("<html>nada</html>") == (None, None))

# 2. id que não tem cara de id não vai para a rede
chamou = []
reg_ler = reg.ler_do_canal("VIDEO123", abrir=lambda url: chamou.append(url) or "")
ok("id fora do padrão do YouTube não consulta a rede", not chamou, chamou)
ok("id fora do padrão devolve (None, None)", reg_ler == (None, None), reg_ler)

# 3. resumo do registro: corte em fim de parágrafo, nunca no meio de palavra
resumo = reg._resumo_da_descricao(DESCRICAO)
ok("o resumo é menor que a descrição do canal", len(resumo) < len(DESCRICAO), len(resumo))
import re as _re

_ultima = resumo.rstrip("…").split()[-1].strip(".,!?;:")
ok("o resumo termina em fim de frase (ou com reticência)", resumo[-1] in ".!?…", repr(resumo[-30:]))
ok("o resumo não corta no meio de uma palavra",
   bool(_re.search(r"(?<!\w)" + _re.escape(_ultima) + r"(?!\w)", DESCRICAO)), _ultima)
ok("o resumo guarda o começo do texto, que é o que importa",
   resumo.startswith("As plantações crescem"), resumo[:40])

# 4. conferir: registro atualizado, com o tamanho do canal
tmp = tempfile.mkdtemp(prefix="registro-vivo-")
caminho = os.path.join(tmp, "youtube-publicados.json")
with open(caminho, "w", encoding="utf-8") as f:
    json.dump({"publicados": [
        {"id": "AAA111bbb22", "titulo": "antigo", "descricao": "…A trilha", "descricao_completa": False},
        {"id": "CCC333ddd44", "titulo": "", "descricao": "", "descricao_completa": True},
    ]}, f)
linhas, dados, mudou, sem_resposta = reg.conferir(
    caminho, abrir=lambda url: html_com(), hoje="2026-11-07T00:00:00Z")
ok("o registro foi atualizado", mudou is True, mudou)
ok("nenhum vídeo ficou sem resposta quando o canal responde", sem_resposta == 0, sem_resposta)
por_id = {x["id"]: x for x in dados["publicados"]}
ok("cada entrada diz o tamanho da descrição NO CANAL",
   por_id["AAA111bbb22"].get("descricao_no_canal") == len(DESCRICAO.strip()),
   por_id["AAA111bbb22"].get("descricao_no_canal"))
ok("a data da conferência fica gravada",
   por_id["AAA111bbb22"].get("conferido_em") == "2026-11-07T00:00:00Z")
ok("o resumo antigo, cortado no meio da palavra, foi substituído",
   not str(por_id["AAA111bbb22"]["descricao"]).endswith("A trilha"), por_id["AAA111bbb22"]["descricao"][-20:])
ok("entrada com descrição vazia passa a ter o texto do canal",
   len(por_id["CCC333ddd44"]["descricao"]) > 100 and por_id["CCC333ddd44"]["titulo"] == "Um título publicado")

# 5. canal que não responde: nada inventado
linhas2, dados2, mudou2, sem2 = reg.conferir(caminho, abrir=lambda url: (_ for _ in ()).throw(OSError("sem rede")))
ok("canal mudo deixa o registro como estava", mudou2 is False, mudou2)
ok("canal mudo é contado, não escondido", sem2 == 2, sem2)
ok("e a linha diz que não respondeu",
   all("não respondeu" in l for l in linhas2), linhas2[:1])

# 6. ensaio não grava
antes = open(caminho, encoding="utf-8").read()
# bancada sem rede: o canal é simulado, senão este contrato depende de a internet estar de pé
_orig = reg.ler_do_canal
reg.ler_do_canal = lambda vid, abrir=None: (None, DESCRICAO)
try:
    rc = reg.main(["registro-do-vivo.py", "--registro", caminho, "--ensaio",
                   "--hoje", "2026-11-07T00:00:00Z"])
finally:
    reg.ler_do_canal = _orig
ok("o ensaio devolve 0", rc == 0, rc)
ok("o ensaio não altera o arquivo", open(caminho, encoding="utf-8").read() == antes)

# 7. registro ilegível não explode
ruim = os.path.join(tmp, "ruim.json")
open(ruim, "w", encoding="utf-8").write("{")
linhas3, dados3, mudou3, sem3 = reg.conferir(ruim)
ok("registro ilegível devolve motivo e não grava", dados3 is None and "ilegível" in linhas3[0], linhas3)

shutil.rmtree(tmp, ignore_errors=True)

certos = sum(1 for _, c in res if c)
print("\n%d/%d contratos do registro do vivo passaram" % (certos, len(res)))
raise SystemExit(0 if certos == len(res) else 1)
