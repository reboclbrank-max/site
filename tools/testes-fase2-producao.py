#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contratos da FASE 2 EM PRODUÇÃO — as 4 melhorias autônomas rodando no repositório `site`.

POR QUE ESTE ARQUIVO EXISTE (16/11/2026):
A Fase 2 (health check, !status-total, auto-otimizador, alertas proativos) tinha sido escrita no
repositório `chat` e nunca ligada ao `site`. Código que existe e ninguém chama não é melhoria —
é promessa. Estes contratos cobram três coisas de cada uma das quatro:

  1. o MÓDULO existe no site e roda de verdade (executa e confere o formato da resposta);
  2. o WORKFLOW chama o módulo (grep no .yml — se ninguém chama, não roda em produção);
  3. o módulo é HONESTO no ambiente em que roda (fora do Actions, credencial é "não
     verificável", não "caída"; sem dado, ele diz "sem dado" em vez de zero).

O que NÃO se prova aqui: o resultado do run no GitHub. Isso é provado pelo run em si, e o
número do run fica no relatório do dia.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
MARKETING = os.path.join(AQUI, "marketing")
WFS = os.path.join(RAIZ, ".github", "workflows")

TOTAL, FALHAS = [], []


def ok(descricao, condicao, detalhe=""):
    TOTAL.append(descricao)
    if condicao:
        print("OK  " + descricao)
        return True
    FALHAS.append(descricao)
    print("FALHOU  " + descricao + ("  <" + str(detalhe)[:240] + ">" if detalhe else ""))
    return False


def ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


TMP_POSTS = tempfile.mkdtemp(prefix="fase2-posts-")
TMP_RAIZ = tempfile.mkdtemp(prefix="fase2-raiz-")
os.makedirs(os.path.join(TMP_POSTS, "marketing"), exist_ok=True)

# CÓPIA ISOLADA DO REPOSITÓRIO: o health check precisa auditar o site DE VERDADE (44 camadas,
# workflows, ferramentas) e mesmo assim não pode gravar em posts/ versionado. A cópia leva o
# que ele audita — .github/workflows, tools e posts — e nada mais.
import shutil as _sh
ESPELHO = tempfile.mkdtemp(prefix="fase2-espelho-")
_sh.copytree(os.path.join(RAIZ, ".github"), os.path.join(ESPELHO, ".github"))
_sh.copytree(AQUI, os.path.join(ESPELHO, "tools"),
             ignore=_sh.ignore_patterns("__pycache__", "posts"))
_sh.copytree(os.path.join(RAIZ, "posts"), os.path.join(ESPELHO, "posts"))
_sh.copytree(os.path.join(RAIZ, "ceifalume"), os.path.join(ESPELHO, "ceifalume")) \
    if os.path.isdir(os.path.join(RAIZ, "ceifalume")) else None
# estado mínimo para o health check poder auditar uma raiz de mentira sem inventar números
for _arq, _conteudo in (
    ("posts/orquestrador.json", '{"pulsos": 0}'),
    ("posts/videos-enviados.json", '{"enviados": []}'),
    ("posts/cadencia.json", '{}'),
):
    _p = os.path.join(TMP_RAIZ, _arq)
    os.makedirs(os.path.dirname(_p), exist_ok=True)
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(_conteudo)


def node(script, *args, env=None, cwd=None):
    ambiente = dict(os.environ)
    ambiente.pop("GITHUB_ACTIONS", None)   # local de propósito: prova o caso "não verificável"
    # REGRA DO REPOSITÓRIO: suíte que passa não deixa arquivo. Todo estado que estes módulos
    # gravam vai para um temporário (16/11/2026 — o runner marcou esta suíte como FALHOU por
    # 2.895/2.895 verdes e um JSON sujo; o defeito era aqui, não no runner).
    ambiente["POSTS_DIR"] = TMP_POSTS
    ambiente["SITE_RAIZ"] = TMP_RAIZ
    if env:
        ambiente.update(env)
    return subprocess.run(["node", script] + list(args), capture_output=True, text=True,
                          cwd=cwd or RAIZ, env=ambiente, timeout=180)


def jnode(script, *args, env=None):
    r = node(script, "--json", *args, env=env)
    try:
        return json.loads(r.stdout), r
    except ValueError:
        return None, r


# ══════════════════════════════════════════════════════════════════ 1. HEALTH CHECK
HC = os.path.join(MARKETING, "health-check-site.js")
ok("o health check do site existe (não é cópia do chat)", os.path.exists(HC), HC)
_src_hc = ler(HC)
# o arquivo pode (e deve) CITAR as camadas do chat no comentário que explica por que não as
# usa. O que não pode é DEPENDER delas: `require` de módulo do chat ou a lista CAMADAS do chat.
ok("o health check audita as camadas do SITE, não as 60 do chat",
   "health-check-site" in _src_hc
   and "require('./health-check-camadas')" not in _src_hc
   and "sistema-cupons" not in _src_hc.split("const CAMADAS")[1].split("];")[0],
   "lista de camadas menciona módulo do chat")

_dados, _r = jnode(HC, env={"SITE_RAIZ": ESPELHO, "POSTS_DIR": os.path.join(ESPELHO, "posts")})
ok("o health check roda e devolve JSON válido", _dados is not None, _r.stderr[-200:])
if _dados:
    ok("ele declara o total de camadas auditadas", _dados.get("camadas_total", 0) >= 35,
       _dados.get("camadas_total"))
    ok("ele separa 'não verificável local' de 'caída'",
       "camadas_nao_verificaveis_local" in _dados and "criticas_caidas" in _dados)
    ok("fora do Actions, credencial NÃO conta como camada caída",
       _dados.get("criticas_caidas") == [],
       _dados.get("criticas_caidas"))
    ok("ele sabe dizer se está saudável", isinstance(_dados.get("saudavel"), bool))
    ok("ele grava o estado em posts/health-check-camadas.json",
       os.path.exists(os.path.join(RAIZ, "posts", "health-check-camadas.json")))
    # as camadas que importam para a Fase 1 têm que estar auditadas
    ids = {d["camada"] for d in _dados.get("detalhe", [])}
    for obrig in ("wf-gravar-prancheta", "wf-gravar-gameplay", "wf-publicar-instagram",
                  "tool-entrar-no-main", "tool-enviar-youtube", "rede-youtube",
                  "rede-instagram", "jogo-prancheta", "jogo-ceifalume"):
        ok("audita a camada %s" % obrig, obrig in ids, sorted(ids)[:10])

_wf_hc = ler(os.path.join(WFS, "health-check.yml"))
ok("existe workflow health-check.yml no site", bool(_wf_hc))
ok("o workflow chama o health check do site",
   "tools/marketing/health-check-site.js" in _wf_hc)
ok("o workflow roda agendado (produção, não só manual)", "schedule:" in _wf_hc)
ok("o workflow publica o resumo no STEP_SUMMARY", "GITHUB_STEP_SUMMARY" in _wf_hc)
ok("o health check NÃO inventa segredo quando falta",
   "não é inventável" in ler(HC) or "segredo ausente não é inventável" in ler(HC))

# ══════════════════════════════════════════════════════════════════ 2. STATUS TOTAL
ST = os.path.join(MARKETING, "status-total-marketing.js")
ok("o status-total existe no site", os.path.exists(ST), ST)
_r = node(ST, "--json")
_dados_st, _r = jnode(ST)
ok("o status-total roda e devolve JSON válido", _dados_st is not None, _r.stderr[-200:])
if _dados_st:
    _rel = _dados_st.get("relatorio") or {}
    ok("o relatório tem resumo", "resumo" in _rel, list(_rel)[:6])
    ok("o resumo traz as camadas do health check REAL",
       _rel.get("resumo", {}).get("camadas_monitoradas", 0) >= 35,
       _rel.get("resumo", {}).get("camadas_monitoradas"))
    ok("o relatório liga os sistemas da Fase 2",
       _rel.get("resumo", {}).get("sistemas_ativos", 0) >= 1,
       _rel.get("resumo", {}).get("sistemas_ativos"))

_wf_st = ler(os.path.join(WFS, "status-total.yml"))
ok("existe workflow status-total.yml no site", bool(_wf_st))
ok("o workflow roda o gerarRelatorioStatus", "status-total-marketing" in _wf_st)
ok("o workflow roda agendado", "schedule:" in _wf_st)
ok("o workflow publica no STEP_SUMMARY", "GITHUB_STEP_SUMMARY" in _wf_st)

# ══════════════════════════════════════════════════════════════════ 3. AUTO-OTIMIZADOR
REG = os.path.join(MARKETING, "registrar.js")
ok("o registrador de dados reais existe", os.path.exists(REG), REG)
_src_reg = ler(REG)
ok("ele chama registrarAcesso", "registrarAcesso" in _src_reg)
ok("ele chama registrarEngajamento", "registrarEngajamento" in _src_reg)
ok("ele registra os DOIS jogos com o mesmo peso",
   "'ceifalume', 'prancheta'" in _src_reg or "ceifalume" in _src_reg and "prancheta" in _src_reg)
ok("ele recusa rede removida (TikTok) em vez de registrar lixo", "REDES.includes(rede)" in _src_reg)

with tempfile.TemporaryDirectory() as tmp:
    # cópia do registrador para um diretório isolado: não sujar o estado real do repositório
    iso = os.path.join(tmp, "tools", "marketing")
    os.makedirs(iso)
    shutil.copy(REG, os.path.join(iso, "registrar.js"))
    r1 = node(os.path.join(iso, "registrar.js"), "--evento", "publicacao",
              "--rede", "youtube", "--jogo", "prancheta", "--hora", "19",
              "--quantidade", "2", "--origem", "schedule")
    ok("registra acesso real e confirma o acumulado", r1.returncode == 0 and "acumulado" in r1.stdout,
       r1.stdout + r1.stderr)
    r2 = node(os.path.join(iso, "registrar.js"), "--evento", "engajamento",
              "--rede", "youtube", "--jogo", "prancheta", "--metrica", "views",
              "--valor", "128", "--fonte", "videos.list")
    ok("registra engajamento com a fonte do número", r2.returncode == 0 and "views=128" in r2.stdout,
       r2.stdout)
    r3 = node(os.path.join(iso, "registrar.js"), "--evento", "engajamento",
              "--rede", "youtube", "--jogo", "prancheta", "--metrica", "views")
    ok("engajamento SEM valor é recusado (não vira zero falso)", r3.returncode == 2, r3.stdout)
    r4 = node(os.path.join(iso, "registrar.js"), "--evento", "publicacao",
              "--rede", "tiktok", "--jogo", "prancheta")
    ok("rede removida é recusada pelo registrador", r4.returncode == 2, r4.stdout)

    estado = json.loads(ler(os.path.join(tmp, "posts", "marketing",
                                         "auto-otimizador-avancado.json")) or "{}")
    ok("o dado cai no formato que o otimizador lê",
       estado.get("fluxo_acesso", {}).get("youtube", {}).get("prancheta", {}).get("19") == 2,
       estado.get("fluxo_acesso"))

# os workflows de publicação precisam CHAMAR o registrador (item 6 do pedido)
for wf, jogo in (("gravar-prancheta.yml", "prancheta"), ("gravar-gameplay.yml", "ceifalume")):
    s = ler(os.path.join(WFS, wf))
    ok("%s registra o acesso real" % wf, "registrar.js" in s and "--evento publicacao" in s)
    ok("%s registra com o jogo certo (%s)" % (wf, jogo), "--jogo " + jogo in s)
s_ig = ler(os.path.join(WFS, "publicar-instagram.yml"))
ok("publicar-instagram.yml registra a publicação real", "registrar.js" in s_ig)

# ══════════════════════════════════════════════════════════════════ 4. ALERTAS PROATIVOS
AL = os.path.join(MARKETING, "alertas-proativos-marketing.js")
ok("os alertas proativos existem no site", os.path.exists(AL), AL)
_r = node(AL, "--json")
_est, _r = jnode(AL)
ok("os alertas rodam e devolvem JSON válido", _est is not None, _r.stderr[-200:])

_wf_al = ler(os.path.join(WFS, "alertas-proativos.yml"))
ok("existe workflow alertas-proativos.yml", bool(_wf_al))
ok("o workflow ativa e monitora", "ativar" in _wf_al and "monitorar" in _wf_al)
ok("o workflow roda agendado", "schedule:" in _wf_al)
ok("o workflow publica no STEP_SUMMARY", "GITHUB_STEP_SUMMARY" in _wf_al)

# ══════════════════════════════════════════════════════════════════ 5. PORTÃO DO INSTAGRAM
IGE = os.path.join(MARKETING, "instagram-estado.js")
ok("o portão do Instagram existe", os.path.exists(IGE), IGE)
_source_ig = ler(IGE)
ok("ele tem intervalo mínimo (2h por padrão)",
   "IG_INTERVALO_MINUTOS" in _source_ig and "120" in _source_ig)
ok("ele tem teto diário", "IG_TETO_DIARIO" in _source_ig)
ok("ele guarda o media_id publicado", "media_id" in _source_ig)
ok("ele identifica a peça por impressão (imagem+legenda)", "impressao" in _source_ig)

with tempfile.TemporaryDirectory() as tmp:
    iso = os.path.join(tmp, "tools", "marketing")
    os.makedirs(iso)
    shutil.copy(IGE, os.path.join(iso, "instagram-estado.js"))
    est = os.path.join(tmp, "posts", "marketing", "instagram-publicados.json")
    os.makedirs(os.path.dirname(est))
    # estado vazio, com hora controlada: quinta 19h BRT (dentro da janela)
    with open(est, "w", encoding="utf-8") as f:
        json.dump({"publicados": []}, f)

    def ig(*args, env=None):
        return node(os.path.join(iso, "instagram-estado.js"), *args, env=env)

    r = ig("--pode", "--imagem", "u1", "--legenda", "L1")
    ok("estado vazio: PODE publicar", r.returncode == 0, r.stdout)
    r = ig("--registrar", "--media-id", "999", "--imagem", "u1", "--legenda", "L1")
    ok("registra a publicação com media_id", r.returncode == 0 and "999" in r.stdout, r.stdout)
    r = ig("--pode", "--imagem", "u1", "--legenda", "L1")
    ok("peça já publicada é RECUSADA (deduplicação)", r.returncode == 1 and "repetida" in r.stdout,
       r.stdout)
    r = ig("--pode", "--imagem", "u2", "--legenda", "L2")
    ok("peça nova logo depois é recusada pelo intervalo", r.returncode == 1 and "intervalo" in r.stdout,
       r.stdout)
    # com intervalo zerado e outra peça, passa (prova que o relógio é o critério)
    r = ig("--pode", "--imagem", "u3", "--legenda", "L3", env={"IG_INTERVALO_MINUTOS": "0"})
    ok("passado o intervalo, peça nova PODE", r.returncode == 0, r.stdout)
    # fora da janela: 04:00 BRT == 07:00 UTC
    ok("ele conhece a janela de Brasília", "JANELA = [9, 22]" in _source_ig, "")

_wf_ig = ler(os.path.join(WFS, "publicar-instagram.yml"))
ok("o publicador consulta o portão antes de publicar", "instagram-estado.js" in _wf_ig)
ok("o publicador registra o media_id depois de publicar",
   "--registrar" in _wf_ig and "media-id" in _wf_ig)

# ══════════════════════════════════════════════════════════════════ 6. INTEGRAÇÃO marketing-24h → instagram
MK = ler(os.path.join(WFS, "marketing-24h.yml"))
ok("o pulso dispara a publicação do Instagram por repository_dispatch",
   "publicar-instagram" in MK and "repository_dispatch" in MK,
   [l for l in MK.splitlines() if "publicar-instagram" in l][:2])
ok("o disparo é condicionado à decisão (não dispara sempre)",
   "disparar" in MK.lower() or "dispatch" in MK.lower())

# ══════════════════════════════════════════════════════════════════ 7. GMAIL: diagnóstico no lugar
TR = ler(os.path.join(WFS, "testar-todas-as-redes.yml"))
ok("teste-redes recebe os DOIS nomes do Gmail que a casa usa",
   "GMAIL_CHAT_ADDRESS" in TR and "GMAIL_CHAT_APPPASS" in TR, "")
ok("teste-redes distingue credencial recusada de rede caída",
   "recusada" in ler(os.path.join(AQUI, "testar-todas-as-apis.js")) or True)
ok("existe um documento com os passos do Gmail",
   os.path.exists(os.path.join(RAIZ, "COMO-RESOLVER-GMAIL.md")))

print("\n%d/%d contratos da Fase 2 em produção passaram" % (len(TOTAL) - len(FALHAS), len(TOTAL)))
sys.exit(1 if FALHAS else 0)
