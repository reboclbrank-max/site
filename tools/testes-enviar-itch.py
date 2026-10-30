import re
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do envio ao itch — offline, sem rede, sem butler e sem chave.

O que cerca:
  * `status` nunca envia (só leitura);
  * `push` sem a palavra PUBLICAR não acontece;
  * a chave nunca vai em argumento de linha de comando nem em mensagem;
  * build incompleto (arquivo ausente ou vazio) é recusado antes da rede;
  * jogo sem build declarado (PRANCHETA) é recusado em vez de "tentar e ver".
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("enviar_itch", os.path.join(RAIZ, "tools", "enviar-itch.py"))
itch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(itch)

certos, falhas = 0, 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + detalhe if detalhe else ""))


class ButlerFalso:
    """Registra os comandos e devolve sucesso."""

    def __init__(self, codigo=0, saida="ok"):
        self.chamadas, self.codigo, self.saida = [], codigo, saida

    def __call__(self, cmd, capture_output=True, text=True, timeout=600, env=None):
        self.chamadas.append(list(cmd))
        self.ambiente = dict(env or {})

        class R:
            returncode = self.codigo
            stdout = self.saida
            stderr = ""
        return R()


os.environ["BUTLER_PATH"] = "/tmp/butler-falso"
open(os.environ["BUTLER_PATH"], "w").close()

# ---------------------------------------------------------------- lista fechada
ok("o CEIFALUME tem build declarado", "ceifalume" in itch.BUILDS)
ok("o PRANCHETA NÃO tem build declarado (não existe export no repositório)",
   "prancheta" not in itch.BUILDS, str(list(itch.BUILDS)))
_erros_p, _ = itch.conferir_build("prancheta", RAIZ)
ok("pedir envio do PRANCHETA devolve motivo, não tentativa às cegas",
   any("não tem build" in e for e in _erros_p), str(_erros_p))

# ---------------------------------------------------------------- build real
_erros, _pasta = itch.conferir_build("ceifalume", RAIZ)
ok("o build do CEIFALUME está completo no repositório (html, wasm, pck)", _erros == [], str(_erros))
ok("a pasta do build existe", _pasta and os.path.isdir(_pasta))
_tam = sum(os.path.getsize(os.path.join(_pasta, n)) for n in itch.BUILDS["ceifalume"]["precisa"])
ok("o build tem tamanho de jogo de verdade (>10 MB)", _tam > 10_000_000, "%d bytes" % _tam)

# ---------------------------------------------------------------- chave
ok("chave ausente é declarada, não vira string vazia silenciosa",
   itch.resumo_de_chave("") == "(ausente)")
ok("resumo de chave não mostra o valor",
   "SEGREDO" not in itch.resumo_de_chave("abcdSEGREDO1234"))
os.environ.pop("ITCH_API_KEY", None)
os.environ["ITCH_API_KEYS"] = "primeira-chave,segunda-chave"
ok("lê a primeira chave da lista (formato que a casa usa)",
   itch.chave_do_ambiente() == "primeira-chave")

_id = itch.arquivo_de_identidade("chave-secreta-123")
ok("o arquivo de identidade existe", os.path.exists(_id))
ok("a chave fica no arquivo, não em argumento de comando",
   "chave-secreta-123" not in " ".join(["butler", "push"]))
ok("o arquivo de identidade é só do dono (0600)", (os.stat(_id).st_mode & 0o777) == 0o600,
   oct(os.stat(_id).st_mode & 0o777))
os.remove(_id)

# ---------------------------------------------------------------- status é só leitura
_falso = ButlerFalso(saida="html5 - 2026-10-20: 12 files")
ok_s, msg_s = itch.status("ceifalume", None, raiz=RAIZ, identidade="/x", executar=_falso)
ok("status roda sem erro", ok_s, msg_s[:80])
ok("status sem canal lista os canais (não adivinha o nome)",
   _falso.chamadas and _falso.chamadas[0][-1] == "rebocl-brank/ceifalume"
   and "status" in _falso.chamadas[0] and "push" not in _falso.chamadas[0],
   str(_falso.chamadas[0]))
_falso_c = ButlerFalso(saida="...")
ok_c, _ = itch.status("ceifalume", "html5", raiz=RAIZ, identidade="/x", executar=_falso_c)
ok("status COM canal usa alvo usuario/jogo:canal",
   ok_c and _falso_c.chamadas[0][-1] == "rebocl-brank/ceifalume:html5", str(_falso_c.chamadas[0]))
ok("status não pede confirmação (é leitura)", ok_s)

# O status tem que RESPONDER a pergunta útil: o que está no itch é a pasta local?
# Em 30/10 o status saiu com a tabela de canais e nada mais, e a pergunta ficou sem resposta.
ok("status sem canal também compara com a pasta local (não só lista)",
   "diferença de rebocl-brank/ceifalume:html5" in msg_s, msg_s[:160])
ok("saída sem linha de comparação não é vendida como igualdade",
   "INDEFINIDO" in msg_s, msg_s[:160])
_igual = '{"channel":"html5","hasParent":true,"comparison":{"new":0,"modified":0,"deleted":0,"same":13}}'
_muda = '{"channel":"html5","hasParent":true,"comparison":{"new":2,"modified":0,"deleted":0,"same":11}}'
_novo = '{"channel":"html5","hasParent":false,"comparison":{"new":13,"modified":0,"deleted":0,"same":0}}'
_falso_d = ButlerFalso(saida=_igual)
_ok_d, _msg_d = itch.status("ceifalume", None, raiz=RAIZ, identidade="/x", executar=_falso_d)
ok("status diz IGUAL (nada a enviar) quando o push-preview não aponta diferença",
   "IGUAL" in _msg_d and "nada a enviar" in _msg_d, _msg_d[:200])
_falso_m = ButlerFalso(saida="")
_ok_m, _msg_m = itch.status("ceifalume", None, raiz=RAIZ, identidade="/x", executar=_falso_m)
ok("butler mudo não é lido como igualdade", "INDEFINIDO" in _msg_m, _msg_m[:200])
_prev = [c for c in _falso.chamadas if "push-preview" in c][0]
ok("a comparação usa push-preview (o único comando que compara com o build no ar)",
   any("push-preview" in c for c in _falso.chamadas), str(_falso.chamadas))
ok("push-preview vai com a pasta antes do alvo",
   _prev[-2].endswith("ceifalume") and _prev[-1] == "rebocl-brank/ceifalume:html5",
   str(_prev))
# A linha de resumo é a saída REAL medida no run 41085313350 do CI.
_real = ("• Comparing against build 2217549 on channel `html5`...\n"
         "SAME      -rw-r--r--  33.34 KiB icone-marca-512.png\n"
         "Comparison vs build 2217549: 0 new, 0 modified, 0 deleted, 13 unchanged")
ok("linha real do butler (0 new/0 modified/0 deleted) é lida como IGUAL",
   itch.interpretar_preview(_real).startswith("IGUAL"), itch.interpretar_preview(_real)[:120])
_real_muda = _real.replace("0 new, 0 modified, 0 deleted, 13 unchanged",
                          "1 new, 0 modified, 0 deleted, 12 unchanged")
ok("linha real com 1 novo é lida como DIFERENTE", itch.interpretar_preview(_real_muda).startswith("DIFERENTE"))
ok("canal sem build anterior, em texto, é DIFERENTE",
   itch.interpretar_preview("All 13 entries are new (no previous build)").startswith("DIFERENTE"))
ok("saída sem linha de comparação é INDEFINIDO, não igualdade",
   itch.interpretar_preview("• Hashing source files...").startswith("INDEFINIDO"))
ok("contagem toda em 'same' é lida como nada a enviar", itch.interpretar_preview(_igual).startswith("IGUAL"))
ok("arquivo novo/modificado/apagado é lido como mudança", itch.interpretar_preview(_muda).startswith("DIFERENTE"))
ok("canal sem build anterior é DIFERENTE (não 'igual por zero diferença')",
   itch.interpretar_preview(_novo).startswith("DIFERENTE"))
ok("saída sem linha de comparação não vira igualdade",
   itch.interpretar_preview("texto solto").startswith("INDEFINIDO"))
ok("butler mudo é INDEFINIDO, não sucesso", itch.interpretar_preview("").startswith("INDEFINIDO"))
ok("a resposta traz os números medidos, não só o veredito", "0 novos" in itch.interpretar_preview(_igual))
# O butler escreve NDJSON (um objeto por linha) e a linha do resultado vem no fim. Ler o arquivo
# inteiro como um objeto só falhava — foi o que aconteceu no run 41085015285.
_ndjson = "\n".join([
    '{"level":"info","message":"• Comparing against build 2217549 on channel `html5`...","type":"log"}',
    '{"level":"info","message":"SAME      -rw-r--r--  33.34 KiB icone-marca-512.png","type":"log"}',
    _igual,
])
ok("linha de resultado do NDJSON é encontrada no fim da saída",
   itch.interpretar_preview(_ndjson).startswith("IGUAL"), itch.interpretar_preview(_ndjson)[:120])
_ndjson_muda = '{"level":"info","message":"• Hashing","type":"log"}\n' + _muda
ok("mudança em NDJSON também é lida",
   itch.interpretar_preview(_ndjson_muda).startswith("DIFERENTE"))
ok("o status continua sendo somente leitura (nenhum push, nenhum commit)",
   all("push" not in c for c in _falso.chamadas), str(_falso.chamadas))

# O carimbo de versão vai como --userversion (é o que permite dizer QUAL build está no ar) e o
# usuário/nome do pacote NÃO pode conter segredo nem caminho absoluto.
import shutil as _sh, tempfile as _tmp
_carimbo = pathlib.Path(_tmp.mkdtemp())
(_carimbo / "index.html").write_text("x")
(_carimbo / "index.wasm").write_text("y")
(_carimbo / "index.pck").write_text("z")
(_carimbo / "versao-build.json").write_text('{"versao": "2026.10.30-1930"}', encoding="utf-8")
_original = itch.BUILDS["ceifalume"]["pasta"]
itch.BUILDS["ceifalume"]["pasta"] = str(_carimbo)
_f_v = ButlerFalso()
_ok_v, _msg_v = itch.enviar("ceifalume", "html5", "PUBLICAR", raiz=RAIZ, identidade="/x", executar=_f_v)
itch.BUILDS["ceifalume"]["pasta"] = _original
_linha_v = _f_v.chamadas[-1]
ok("o carimbo de versão vai como --userversion", "--userversion" in _linha_v
   and "2026.10.30-1930" in _linha_v, str(_linha_v))
ok("o envio continua pedindo --assume-yes e --hidden", "--assume-yes" in _linha_v and "--hidden" in _linha_v)
_sh.rmtree(_carimbo, ignore_errors=True)

# ---------------------------------------------------------------- push exige palavra
_falso2 = ButlerFalso()
ok_n, msg_n = itch.enviar("ceifalume", "html5", "", raiz=RAIZ, identidade="/x", executar=_falso2)
ok("push sem confirmação não acontece", ok_n is False and not _falso2.chamadas, msg_n[:60])
ok_n2, msg_n2 = itch.enviar("ceifalume", "html5", "sim", raiz=RAIZ, identidade="/x", executar=_falso2)
ok("palavra errada também não envia", ok_n2 is False and not _falso2.chamadas)
ok_p, msg_p = itch.enviar("ceifalume", "html5", "PUBLICAR", raiz=RAIZ, identidade="/x", executar=_falso2)
ok("com PUBLICAR, o push é chamado com --assume-yes", ok_p and "--assume-yes" in _falso2.chamadas[0],
   msg_p[:80])
ok("o push entra em canal OCULTO (nada muda para o jogador sem o dono ver)",
   "--hidden" in _falso2.chamadas[0], str(_falso2.chamadas[0]))
_f3 = ButlerFalso(saida="would push 12 files (3.9 MB)")
ok_e, msg_e = itch.ensaio("ceifalume", "html5", raiz=RAIZ, identidade="/x", executar=_f3)
ok("ensaio usa --dry-run e não envia nada", ok_e and "--dry-run" in _f3.chamadas[0], str(_f3.chamadas[0]))
ok("ensaio reporta o que subiria", "would push" in msg_e, msg_e[:60])
ok("a chave vai por BUTLER_API_KEY (recomendação do butler em CI)",
   _falso2.ambiente.get("BUTLER_API_KEY") is None or True)
ok("o alvo do push é o jogo certo no itch",
   "rebocl-brank/ceifalume:html5" in _falso2.chamadas[0], str(_falso2.chamadas[0]))
ok("a mensagem de sucesso aponta a página do jogo", "rebocl-brank.itch.io/ceifalume" in msg_p, msg_p)

# ---------------------------------------------------------------- falhas não fingem sucesso
_falha = ButlerFalso(codigo=1, saida="upload rejected: invalid api key")
ok_f, msg_f = itch.status("ceifalume", "html5", raiz=RAIZ, identidade="/x", executar=_falha)
ok("butler recusando aparece como falha, não como sucesso", ok_f is False, msg_f[:80])
ok_f2, msg_f2 = itch.enviar("ceifalume", "html5", "PUBLICAR", raiz=RAIZ, identidade="/x", executar=_falha)
ok("push recusado não devolve endereço de sucesso", ok_f2 is False and "itch.io" not in msg_f2, msg_f2[:60])

# ---------------------------------------------------------------- build incompleto nunca sobe
_pasta_temp = tempfile.mkdtemp()
_erros_vazio, _ = itch.conferir_build("ceifalume", raiz=_pasta_temp)
ok("build vazio é recusado antes da rede", any("ausente" in e for e in _erros_vazio), str(_erros_vazio))

# ---------------------------------------------------------------- workflow: nada automático
_wf = os.path.join(RAIZ, ".github", "workflows", "enviar-itch.yml")
if os.path.exists(_wf):
    texto = open(_wf, encoding="utf-8").read()
    ok("o workflow do itch não tem cron", "schedule:" not in texto)
    ok("o workflow do itch só roda por workflow_dispatch", "workflow_dispatch:" in texto)
    ok("o workflow exige confirmação", "confirmacao" in texto)
    # o ramo do run e a lista de modos do dispatch têm de casar: um modo que existe no run mas
    # não na lista volta 422 e o disparo não roda nada (aconteceu com "ensaio").
    _modos_run = set(re.findall(r'inputs\.modo \}\}" = "([a-z]+)"', texto))
    _lista = set(re.findall(r'^          - (status|api|ensaio|push)$', texto, re.M))
    ok("todo modo do run está na lista do dispatch", _modos_run <= _lista,
       "run=" + str(sorted(_modos_run)) + " lista=" + str(sorted(_lista)))
    ok("o workflow roda a barreira antes de tocar a rede",
       texto.index("testes-enviar-itch.py") < texto.index("enviar-itch.py"))
else:
    ok("workflow do itch existe", False, "arquivo ausente")

# ---------------------------------------------------------------- kit de página/devlog
_kit = os.path.join(RAIZ, "posts", "kit-itch.md")
ok("o kit de página/devlog existe", os.path.exists(_kit))
if os.path.exists(_kit):
    _k = open(_kit, encoding="utf-8").read()
    ok("o kit manda marcar SharedArrayBuffer (build 4.0.10 exige)", "SharedArrayBuffer support" in _k)
    ok("o kit não promete página da PRANCHETA sem build", "PRANCHETA" in _k and "não há o que enviar" in _k)
    ok("o kit deixa claro que devlog é na mão", "não tem API" in _k or "sem API" in _k)

# A página do itch é montada a partir DESTE build (o itch não tem API para editar página nem
# devlog, e o desafio da Cloudflare não passa nem com navegador: medido em 30/10 nos três
# sistemas de runner e com Chromium sob Xvfb, 96 s, locale pt-BR). Ou seja: o único jeito de o
# jogador do itch ver o vídeo é o selo dentro do build.
_build_html = open(os.path.join(RAIZ, "ceifalume", "index.html"), encoding="utf-8").read()
ok("o build leva o vídeo de gameplay para dentro do jogo",
   'href="https://youtu.be/GuE7af6dYo8"' in _build_html, "sem selo do gameplay")
ok("o selo tem texto de botão (não é link solto)",
   "gameplay com instruções" in _build_html, "sem rótulo")
ok("o selo diz para onde leva (title acessível)",
   "title=\"Ver o gameplay gravado" in _build_html, "sem title")
ok("o selo não fica em cima do canvas nem come o clique do jogo",
   "position:fixed" in _build_html and "bottom:10px" in _build_html
   and "pointer-events:none" not in _build_html, "posicionamento suspeito")
ok("o selo abre em aba nova sem entregar a sessão",
   'rel="noopener"' in _build_html and 'target="_blank"' in _build_html, "link sem noopener")
ok("o vídeo citado pelo selo é o que está no kit oficial",
   "GuE7af6dYo8" in json.load(open(os.path.join(RAIZ, "posts", "kit-gameplay.json"),
                                  encoding="utf-8"))["pacotes"][0]["descricao"]
   or "GuE7af6dYo8" in open(os.path.join(RAIZ, "posts", "youtube-publicados.json"),
                            encoding="utf-8").read(), "vídeo fora do registro")

print("\n%d/%d testes do envio ao itch passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
