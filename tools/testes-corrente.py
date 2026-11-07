#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da corrente de pulsos. Nenhum teste dorme nem chama a API: tudo injetado."""
import datetime
import importlib.util
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("corr", os.path.join(RAIZ, "tools", "corrente.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

certos, falhas = 0, 0
BRT = datetime.timezone(datetime.timedelta(hours=-3))
UTC = datetime.timezone.utc


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✗ " + nome + (" — " + str(detalhe)[:200] if detalhe else ""))


def local(h, m=0, dia=8):
    return datetime.datetime(2026, 11, dia, h, m, tzinfo=BRT)


# ------------------------------------------------------------------ quando acordar
_d = c.proximo_disparo(local(9, 7))
ok("às 09h07 acorda às 09h20 (alinhado ao passo de 20 min)",
   _d.astimezone(BRT).strftime("%H:%M") == "09:20", _d.astimezone(BRT))
ok("o horário de acordar está sempre no futuro", _d > local(9, 7).astimezone(UTC))
ok("o horário é múltiplo de 20 minutos", _d.astimezone(BRT).minute % 20 == 0,
   _d.astimezone(BRT).minute)

_d = c.proximo_disparo(local(21, 41))
ok("depois do último pulso da janela, acorda na pesquisa de amanhã (03h)",
   _d.astimezone(BRT).strftime("%d/%m %H:%M") == "09/11 03:00", _d.astimezone(BRT))

_d = c.proximo_disparo(local(23, 30))
ok("de madrugada fora das janelas, acorda às 03h", _d.astimezone(BRT).strftime("%H:%M") == "03:00",
   _d.astimezone(BRT))
_d = c.proximo_disparo(local(3, 30))
ok("às 03h30 (pesquisa) acorda às 03h40", _d.astimezone(BRT).strftime("%H:%M") == "03:40",
   _d.astimezone(BRT))
_d = c.proximo_disparo(local(4, 50))
ok("às 04h50 (fim do aprendizado) acorda às 09h", _d.astimezone(BRT).strftime("%H:%M") == "09:00",
   _d.astimezone(BRT))
_d = c.proximo_disparo(local(12, 0))
ok("meio da janela acorda 20 min depois", _d.astimezone(BRT).strftime("%H:%M") == "12:20",
   _d.astimezone(BRT))

# a janela do calendário manda: com 10-20, 09h não é hora de pulso
_d = c.proximo_disparo(local(9, 30), horas=c.horas_de_pulso(10, 20))
ok("horas de pulso respeitam a janela do calendário", _d.astimezone(BRT).hour == 10,
   _d.astimezone(BRT))

_todas_as_horas = c.horas_de_pulso()
ok("a janela 9-22 entra nas horas de pulso", {9, 15, 21} <= _todas_as_horas, sorted(_todas_as_horas))
ok("a janela de estudo entra", {3, 4} <= _todas_as_horas)
ok("22h não é hora de publicar", 22 not in _todas_as_horas)

# ------------------------------------------------------------------ motivo
ok("o motivo da janela aberta é dito", "janela aberta" in c.motivo(local(15, 0)))
ok("o motivo da janela de estudo é dito", "janela de estudo (3h)" in c.motivo(local(3, 20)))
ok("fora da janela não acontece (a conta mira só a janela)",
   "não deveria acontecer" in c.motivo(local(6, 0)))

# ------------------------------------------------------------------ o passo da corrente
_chamadas = []
_feito = c.ciclo(agora_fn=lambda: local(15, 5),
                 pulso_fn=lambda: _chamadas.append("pulso"),
                 si_fn=lambda: _chamadas.append("corrente"),
                 dormir=lambda s: _chamadas.append(("dormiu", s)),
                 token="x", parado_fn=lambda: False)
ok("a corrente acorda o pulso e se reagenda", _chamadas and _chamadas[-2:] == ["pulso", "corrente"],
   _chamadas)
ok("ela dorme antes de disparar", isinstance(_chamadas[0], tuple) and _chamadas[0][0] == "dormiu",
   _chamadas[:2])
ok("o sono é de 15 minutos quando faltam 15", _chamadas[0][1] == 15 * 60, _chamadas[0])
ok("o registro diz que disparou e quando", _feito["acao"] == "disparou" and _feito["em"], _feito)
ok("o registro diz o motivo", "janela aberta" in _feito["motivo"], _feito)

_chamadas_vazias = []
_parado = c.ciclo(agora_fn=lambda: local(15, 5),
                  pulso_fn=lambda: _chamadas_vazias.append("pulso"),
                  si_fn=lambda: _chamadas_vazias.append("corrente"),
                  dormir=lambda s: None, token="x", parado_fn=lambda: True)
ok("com posts/PARAR, nada é disparado", _chamadas_vazias == [], _chamadas_vazias)
ok("com posts/PARAR, a corrente diz que parou", _parado["acao"] == "parar" and "PARAR" in _parado["motivo"],
   _parado)

# PARAR que aparece durante a espera também para tudo
_estado = {"parado": False}


def _parado_depois(s):
    _estado["parado"] = True


_chamadas_durante = []
_meio = c.ciclo(agora_fn=lambda: local(15, 5),
                pulso_fn=lambda: _chamadas_durante.append("pulso"),
                si_fn=lambda: _chamadas_durante.append("corrente"),
                dormir=_parado_depois, token="x", parado_fn=lambda: _estado["parado"])
ok("se PARAR aparece durante a espera, não dispara", _chamadas_durante == [], _chamadas_durante)
ok("e diz por que parou", "durante a espera" in _meio["motivo"], _meio)

# ------------------------------------------------------- as diárias que o cron deixa passar
def run_em(instante):
    return {"created_at": instante.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}


_rodaram, _sem = c.rodaram_hoje(local(10, 5), ler_runs_fn=lambda wf: [run_em(local(9, 30))])
ok("rodou hoje é reconhecido por run do mesmo dia local",
   all(_rodaram[n] for n in _rodaram) and not _sem, (_rodaram, _sem))
_rodaram, _ = c.rodaram_hoje(local(10, 5), ler_runs_fn=lambda wf: [run_em(local(9, 30, dia=7))])
ok("run de ontem não conta como hoje",
   not any(_rodaram.values()), _rodaram)

_nada_rodou = {n: False for n, _h in c.DIARIAS_GARANTIDAS}
ok("às 08h50, antes da hora de preferência, nenhuma diária é cobrada",
   c.diarias_faltando(local(8, 50), _nada_rodou) == [])
ok("às 09h05 a corrente NÃO atropela o cron: a graça de uma passada ainda vale",
   c.diarias_faltando(local(9, 5), _nada_rodou) == [], c.diarias_faltando(local(9, 5), _nada_rodou))
ok("às 09h20, as diárias das 9h que não rodaram entram na conta",
   set(c.diarias_faltando(local(9, 20), _nada_rodou)) ==
   {n for n, h in c.DIARIAS_GARANTIDAS if h == 9},
   c.diarias_faltando(local(9, 20), _nada_rodou))
ok("às 09h20 a diária das 10h ainda não é cobrada",
   "medir-itch" not in c.diarias_faltando(local(9, 20), _nada_rodou))
ok("às 10h20 a das 10h entra", "medir-itch" in c.diarias_faltando(local(10, 20), _nada_rodou))
ok("a graça é de uma passada, não de uma hora",
   c.GRACA_MINUTOS == c.PASSO_MINUTOS, (c.GRACA_MINUTOS, c.PASSO_MINUTOS))
ok("diária que já rodou hoje não é disparada de novo",
   c.diarias_faltando(local(10, 5), {n: True for n, _h in c.DIARIAS_GARANTIDAS}) == [])
ok("fora da hora de pulso (05h) a corrente não dispara diária",
   c.diarias_faltando(local(5, 0), _nada_rodou) == [])
ok("a palavra de confirmação nunca é digitada: nenhuma diária garantida é de escrita",
   set(n for n, _h in c.DIARIAS_GARANTIDAS) ==
   {"medir-o-dia", "ler-comentarios", "pendencias-do-dono", "vigia-sessao-itch", "medir-itch"},
   c.DIARIAS_GARANTIDAS)
ok("administrar-itch e administrar-youtube ficam de fora (exigem palavra)",
   not ({"administrar-itch", "administrar-youtube"} &
        {n for n, _h in c.DIARIAS_GARANTIDAS}))

_disparadas = []
_feito_diarias = c.garantir(local(10, 25), token="x",
                            disparar_fn=lambda wf: _disparadas.append(wf),
                            ler_runs_fn=lambda wf: [])
ok("garantir dispara só o que falta", set(_disparadas) ==
   {n for n, h in c.DIARIAS_GARANTIDAS if h <= 10}, _disparadas)


def _falha(wf):
    raise RuntimeError("rede caiu")


_nao_lidas = c.garantir(local(10, 25), token="x", disparar_fn=lambda wf: None,
                        ler_runs_fn=_falha)
ok("leitura que falha não vira 'não rodou': não dispara às cegas",
   _nao_lidas["dispares"] == [] and _nao_lidas["sem_leitura"], _nao_lidas)

_ciclo_diarias = []
_feito_ciclo = c.ciclo(agora_fn=lambda: local(9, 5), pulso_fn=lambda: None,
                       si_fn=lambda: _ciclo_diarias.append("corrente"),
                       dormir=lambda s: None, token="x", parado_fn=lambda: False,
                       garantir_fn=lambda alvo: {"dispares": ["medir-o-dia"], "sem_leitura": {}})
ok("as diárias aparecem no registro do ciclo", _feito_ciclo["diarias"] == ["medir-o-dia"],
   _feito_ciclo)
ok("a corrente se reagenda mesmo depois de disparar diárias", _ciclo_diarias == ["corrente"])
_feito_erro = c.ciclo(agora_fn=lambda: local(9, 5), pulso_fn=lambda: None, si_fn=lambda: None,
                      dormir=lambda s: None, token="x", parado_fn=lambda: False,
                      garantir_fn=lambda alvo: (_ for _ in ()).throw(RuntimeError("boom")))
ok("diária que explode não derruba a corrente (e fica registrado)",
   _feito_erro["acao"] == "disparou" and _feito_erro["sem_leitura"], _feito_erro)

# ------------------------------------------------------------------ limites
_esperado = c.esperar(10 ** 6, dormir=lambda s: None)
ok("a espera nunca passa de 5h20 (job do GitHub morre em 6h)",
   _esperado == int(c.ESPERA_MAXIMA.total_seconds()), _esperado)

# ------------------------------------------------------------------ disparar de verdade (sem rede)
class _Resposta:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


_salvo = c.urllib.request.urlopen
c.urllib.request.urlopen = lambda req, timeout=None: _Resposta()
try:
    ok("disparo com HTTP 204 é sucesso", c.disparar("marketing-24h", "x") is True)

    class _Erro(_Resposta):
        status = 500

    c.urllib.request.urlopen = lambda req, timeout=None: _Erro()
    try:
        c.disparar("marketing-24h", "x")
        ok("HTTP diferente de 204/201 não é sucesso", False)
    except RuntimeError as erro:
        ok("HTTP diferente de 204/201 não é sucesso", "500" in str(erro), erro)
finally:
    c.urllib.request.urlopen = _salvo

# O PULSO VAI POR `repository_dispatch` (07/11/2026). O primeiro run de verdade morreu com
# HTTP 422: `marketing-24h` exige a entrada `confirmacao` e a corrente não a mandava. Mandar
# PUBLICAR daqui seria a automação digitando autorização de gente — então o pulso tem gatilho
# próprio, e o corpo enviado é provado abaixo.
_enviados = []


class _Captura(_Resposta):
    def __init__(self, status=204):
        self.status = status


def _capturar(req, timeout=None):
    _enviados.append({"url": req.full_url, "corpo": (req.data or b"").decode()})
    return _Captura()


_guarda = c.urllib.request.urlopen
c.urllib.request.urlopen = _capturar
try:
    c.disparar_pulso("x")
    c.disparar("corrente", "x")
finally:
    c.urllib.request.urlopen = _guarda
ok("o pulso é acordado pelo `repository_dispatch`",
   _enviados and _enviados[0]["url"].endswith("/repos/reboclbrank-max/site/dispatches"),
   _enviados[:1])
ok("o corpo do pulso diz o evento, não uma palavra de confirmação",
   '"event_type": "pulso"' in _enviados[0]["corpo"] and "PUBLICAR" not in _enviados[0]["corpo"],
   _enviados[0]["corpo"])
ok("a corrente se reagenda pelo `workflow_dispatch` (só ele dispara a si mesmo)",
   _enviados[1]["url"].endswith("/actions/workflows/corrente.yml/dispatches"), _enviados[1]["url"])
ok("a corrente nunca digita PUBLICAR por ninguém",
   all("PUBLICAR" not in e["corpo"] for e in _enviados), _enviados)

c.urllib.request.urlopen = lambda req, timeout=None: _Captura(422)
try:
    c.disparar_pulso("x")
    ok("HTTP 422 do pulso não é sucesso", False)
except RuntimeError as erro:
    ok("HTTP 422 do pulso não é sucesso", "422" in str(erro), erro)
finally:
    c.urllib.request.urlopen = _guarda

# o ciclo de verdade usa esses dois caminhos (não o `disparar('marketing-24h')` antigo)
_origem = c.disparar_pulso, c.disparar
_chamou = []
c.disparar_pulso = lambda token=None, **k: _chamou.append("pulso")
c.disparar = lambda wf, token=None, **k: _chamou.append(wf)
try:
    c.ciclo(agora_fn=lambda: local(15, 5), dormir=lambda s: None, token="x",
            parado_fn=lambda: False)
finally:
    c.disparar_pulso, c.disparar = _origem
ok("o ciclo padrao acorda o pulso pelo caminho novo e reagenda a corrente",
   _chamou == ["pulso", "corrente"], _chamou)

# sem token, a linha de comando não dispara às cegas
_salvo_token = {k: os.environ.pop(k, None) for k in ("GHPAT", "GITHUB_TOKEN")}
_codigo = c.main([])
for k, v in _salvo_token.items():
    if v is not None:
        os.environ[k] = v
ok("sem token a corrente para com código 3 (não finge que disparou)", _codigo == 3, _codigo)

# ------------------------------------------------- o workflow não pode mentir
_caminho_yaml = os.path.join(RAIZ, ".github", "workflows", "corrente.yml")
_yaml = open(_caminho_yaml, encoding="utf-8").read() if os.path.exists(_caminho_yaml) else ""


def _linha(chave):
    """Valor de uma chave do YAML, sem comentário à direita (o arquivo comenta muito)."""
    for linha in _yaml.splitlines():
        if linha.strip().startswith(chave):
            return linha.split(":", 1)[1].split("#", 1)[0].strip()
    return None


ok("o workflow da corrente existe no repositório", bool(_yaml))
ok("a corrente tem grupo de concorrência próprio (é o que impede dobrar)",
   _linha("group") == "corrente", _linha("group"))
ok("o grupo da corrente não cancela o run em andamento (só o pendente é substituído)",
   _linha("cancel-in-progress") == "false", _linha("cancel-in-progress"))
ok("a retaguarda do cron existe: se a corrente morrer, ela volta",
   '"0 */3 * * *"' in _yaml or "0 */3 * * *" in _yaml)
_teto = _linha("timeout-minutes")
ok("o job declara teto de tempo", _teto is not None and _teto.isdigit(), _teto)
ok("o teto cobre a espera máxima do código (senão o run morre dormindo)",
   _teto is not None and _teto.isdigit()
   and int(_teto) > c.ESPERA_MAXIMA.total_seconds() / 60.0,
   (_teto, c.ESPERA_MAXIMA))
ok("o teto fica abaixo do limite de 6h do GitHub",
   _teto is not None and _teto.isdigit() and int(_teto) < 360, _teto)
ok("o passo roda os contratos offline ANTES de iniciar a corrente",
   "testes-corrente.py" in _yaml
   and _yaml.index("testes-corrente.py") < _yaml.index("tools/corrente.py"),
   _yaml.find("testes-corrente.py"))
ok("o token que a corrente usa vem do segredo GHPAT", "GHPAT" in _yaml)
ok("o workflow conta a medição do concurrency (não é promessa, é run citado)",
   "42355781857" in _yaml and "pending" in _yaml)

print("\n%d/%d contratos da corrente passaram" % (certos, certos + falhas))
sys.exit(1 if falhas else 0)
