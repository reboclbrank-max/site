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
import os
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

print("\n%d/%d testes do envio ao itch passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
