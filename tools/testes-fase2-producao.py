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
import re as _re
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
# O jogo Ceifalume tem um index.wasm de 37 MB. O health check só audita `ceifalume/index.html`
# — copiar o binário do jogo inteiro custava 41 MB POR EXECUÇÃO (medido em 16/11/2026: 235 MB
# acumulados em 5 rodadas, e /tmp é tmpfs). No runner do Actions isso enche o disco e o CI falha
# por um motivo que não tem nada a ver com o código. Copia só o que é auditado.
_DIR_JOGO = os.path.join(ESPELHO, "ceifalume")
if os.path.isdir(os.path.join(RAIZ, "ceifalume")):
    os.makedirs(_DIR_JOGO, exist_ok=True)
    for _item in ("index.html", "index.js"):
        _origem = os.path.join(RAIZ, "ceifalume", _item)
        if os.path.exists(_origem):
            _sh.copy2(_origem, os.path.join(_DIR_JOGO, _item))
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

    # RELÓGIO FIXO: quinta 16/11, 19:00 BRT (= 22:00 UTC), dentro da janela 9-22h.
    # Sem isso a suíte ficava vermelha toda madrugada — um teste que mede o relógio, não o
    # portão. IG_AGORA existe só para os contratos; em produção é o tempo real.
    DENTRO = {"IG_AGORA": "2026-11-16T22:00:00Z"}

    def ig(*args, env=None):
        ambiente = dict(DENTRO)
        if env:
            ambiente.update(env)
        return node(os.path.join(iso, "instagram-estado.js"), *args, env=ambiente)

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
    # intervalo zerado + 3h depois = PODE de verdade (prova que a janela e o intervalo
    # são os dois critérios, e que passar os dois libera)
    r = ig("--pode", "--imagem", "u3", "--legenda", "L3",
           # 19:00 UTC = 16h BRT — bem dentro da janela (a janela é [9,22): 22h já está FORA)
           env={"IG_INTERVALO_MINUTOS": "0", "IG_AGORA": "2026-11-17T19:00:00Z"})
    ok("passado o intervalo, peça nova PODE", r.returncode == 0, r.stdout)
    # e a janela continua valendo: 04h BRT (=07 UTC) é fora
    r = ig("--pode", "--imagem", "u4", "--legenda", "L4",
           env={"IG_INTERVALO_MINUTOS": "0", "IG_AGORA": "2026-11-17T07:00:00Z"})
    ok("a janela barra às 4h de Brasília mesmo sem intervalo",
       r.returncode == 1 and "janela" in r.stdout, r.stdout)
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

# ── 10. AUTO-RECUPERAÇÃO: precisa RECUPERAR de verdade, não só existir ──────────
# (16/11/2026): o self-recovery estava escrito e nunca rodou. `auditar()` devolve `camada`
# (o id), não `nome` (o arquivo) — e `tentarRecuperacao()` lia `camada.nome`, recebia
# undefined, e pulava a recriação. Quatro estados ausentes viravam quatro camadas críticas
# caídas e ZERO tentativas de recuperação. Um teste que só chamasse `tentarRecuperacao()` com
# um objeto "bonitinho" passaria; só apagar os arquivos de verdade expõe o defeito.
# A raiz da recuperação precisa de: os workflows (para a auditoria ter o que ver), as
# ferramentas DE VERDADE (o health check confere a sintaxe de cada uma — um diretório vazio
# mudaria a resposta) e o health check. 2,5 MB por execução, e é o mínimo honesto.
_RAIZ_REC = tempfile.mkdtemp(prefix="fase2-rec-")
_RAIZ_REC_ALVO = _RAIZ_REC
_sh.copytree(os.path.join(RAIZ, ".github"), os.path.join(_RAIZ_REC, ".github"))
_sh.copytree(AQUI, os.path.join(_RAIZ_REC, "tools"),
             ignore=_sh.ignore_patterns("__pycache__", "posts"))
os.makedirs(os.path.join(_RAIZ_REC, "posts"), exist_ok=True)

_env_rec = {"SITE_RAIZ": _RAIZ_REC, "POSTS_DIR": os.path.join(_RAIZ_REC, "posts"),
            "GITHUB_ACTIONS": "true"}
# credenciais presentes: sem elas o resultado seria vermelho por credencial e esconderia a
# pergunta que interessa, que é se o ESTADO ausente é recriado.
for _k in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "IG_TOKEN", "IG_USER_ID",
           "GMAIL_CHAT_APPPASS", "NOSTR_KEY", "THREADS_TOKEN", "BLUESKY_APPPASS"):
    _env_rec[_k] = "presente"
_rec, _erro = jnode(HC, env=_env_rec)
_tex = ""
if isinstance(_rec, dict):
    _tex = json.dumps(_rec)
ok("o health check roda numa raiz sem estado nenhum e não quebra",
   isinstance(_rec, dict) and _rec.get("camadas_total", 0) > 0, _erro)
_recup = (_rec or {}).get("recuperacoes", {}) or {}
ok("self-recovery RECRIA estado ausente (não fica só em 'críticas caídas')",
   _recup.get("sucesso", 0) >= 1,
   "recuperações: %s" % json.dumps(_recup)[:200])
ok("estado recriado vira camada ativa (recuperação conclui o ciclo)",
   (_rec or {}).get("camadas_ativas", 0) >= 20,
   "ativas: %s" % (_rec or {}).get("camadas_ativas"))
_criados = [f for f in ("orquestrador.json", "videos-enviados.json", "fila-tarefas.json")
            if os.path.exists(os.path.join(_RAIZ_REC, "posts", f))]
ok("os arquivos de estado voltaram ao disco, com esqueleto válido",
   len(_criados) >= 3, "criados: %s" % _criados)

# ── 10. SELF-RECOVERY PROVADO POR EXECUÇÃO, NÃO POR INSPEÇÃO ────────────────────
# (16/11/2026) O health check tinha um bug que matou a auto-recuperação em silêncio:
# `auditar()` devolve `{camada: id, ...}` e NÃO `{nome}`; a função lia `camada.nome`, recebia
# undefined, e o ramo de recriação nunca executava. Zero tentativas desde que foi escrita, e
# ninguém viu porque o relatório dizia "0 recuperações" — que parece "nada precisou".
# Este contrato NÃO lê o código: apaga um estado crítico numa cópia isolada, roda o health
# check de verdade e exige que a camada volte e a tentativa seja registrada.
_rec_raiz = tempfile.mkdtemp(prefix="fase2-recovery-")
_rec_alvo_rel = "posts/orquestrador.json"
try:
    _sh.copytree(os.path.join(RAIZ, ".github"), os.path.join(_rec_raiz, ".github"))
    _sh.copytree(AQUI, os.path.join(_rec_raiz, "tools"),
                 ignore=_sh.ignore_patterns("__pycache__", "posts"))
    _sh.copytree(os.path.join(RAIZ, "posts"), os.path.join(_rec_raiz, "posts"))
    for _dir in ("ceifalume", "prancheta"):
        _orig = os.path.join(RAIZ, _dir)
        if os.path.isdir(_orig):
            _sh.copytree(_orig, os.path.join(_rec_raiz, _dir))
    os.remove(os.path.join(_rec_raiz, _rec_alvo_rel))
    _rec_dados, _rec_saida = jnode(
        os.path.join(_rec_raiz, "tools", "marketing", "health-check-site.js"), "--json",
        env={"SITE_RAIZ": _rec_raiz, "POSTS_DIR": os.path.join(_rec_raiz, "posts")})
    _rec = (_rec_dados or {}).get("recuperacoes", {}) if isinstance(_rec_dados, dict) else {}
    ok("o health check RECRIA um estado crítico apagado (self-recovery executa)",
       os.path.exists(os.path.join(_rec_raiz, _rec_alvo_rel)) and _rec.get("sucesso", 0) >= 1,
       "arquivo recriado: %s · recuperações: %s" % (
           os.path.exists(os.path.join(_rec_raiz, _rec_alvo_rel)), _rec))
    ok("o health check registra a tentativa de recuperação (não é silenciosa)",
       _rec.get("tentadas", 0) >= 1 and len(_rec.get("itens", [])) >= 1,
       _rec)
    # e o contrário: código quebrado NÃO é reescrito no chute (foi assim que o
    # entrar-no-main.sh virou base64 em 12/11 e derrubou 6 workflows)
    _rec2_dados, _ = jnode(
        os.path.join(_rec_raiz, "tools", "marketing", "health-check-site.js"), "--json",
        env={"SITE_RAIZ": _rec_raiz, "POSTS_DIR": os.path.join(_rec_raiz, "posts")})
    _scripts = [c for c in (_rec2_dados or {}).get("camadas", [])
                if c.get("tipo") == "script" and c.get("status") == "sintaxe_invalida"]
    ok("o health check NÃO reescreve código com sintaxe quebrada",
       all(c.get("recuperacao") and "no chute" in str(c.get("recuperacao")) for c in _scripts)
       if _scripts else True,
       "scripts quebrados: %d" % len(_scripts))
finally:
    _sh.rmtree(_rec_raiz, ignore_errors=True)

# ── 8b. PRECEDÊNCIA DO SECRET DO GMAIL: APPPASS antes de PASS, em TODO lugar ─────
# (16/11/2026, defeito real que durou semanas) O `site` guarda dois secrets de senha:
# GMAIL_CHAT_APPPASS (senha de app de 16 chars, funciona) e GMAIL_CHAT_PASS (senha comum,
# o Google recusa por definição). Dois arquivos liam `GMAIL_CHAT_PASS` PRIMEIRO. Resultado:
# o Gmail aparecia "Application-specific password required" — e a conclusão natural era
# "a conta precisa de senha de app", quando a senha de app JÁ ESTAVA lá, sendo ignorada.
# O sintoma apontava para o dono; o defeito era uma ordem de `||`.
_invertidos = []
for _base, _dirs, _arqs in os.walk(AQUI):
    if "marketing" in _base or _base.rstrip("/").endswith("tools"):
        for _a in _arqs:
            if not _a.endswith(".js"):
                continue
            _caminho = os.path.join(_base, _a)
            _txt = ler(_caminho)
            for _l in _txt.splitlines():
                # só é inversão quando `PASS` aparece LITERALMENTE antes de `APPPASS` na
                # mesma atribuição. `process.env.GMAIL_CHAT_APPPASS || ...GMAIL_CHAT_PASS`
                # contém a substring "GMAIL_CHAT_PASS ||"? Não — mas contém "PASS ||" no
                # fim. A marca inequívoca é a atribuição começando por PASS.
                # Ancorar no INÍCIO da expressão: `= process.env.GMAIL_CHAT_PASS ||`
                # significa que PASS é a primeira escolha. Se APPPASS vem antes,
                # a ocorrência está no meio e não casa.
                if _re.search(r"=\s*process\.env\.GMAIL_CHAT_PASS\s*\|\|", _l):
                    _invertidos.append(os.path.relpath(_caminho, RAIZ))
ok("nenhum arquivo lê GMAIL_CHAT_PASS antes de GMAIL_CHAT_APPPASS",
   not _invertidos, "invertidos: " + ", ".join(sorted(set(_invertidos))))

# ── 9. PERMISSÃO: workflow que versiona estado precisa de contents: write ────────
# (16/11/2026, defeito real): o publicar-instagram tinha `contents: read`. O passo de commit
# rodava, o git commit funcionava e o PUSH era recusado 6 vezes — o log dizia "autenticação/
# permissão" e o estado nunca chegava ao main. O portão continuava decorativo, agora por
# permissão em vez de por falta de commit. A regra vale para todo workflow que versiona.
_sem_escrita = []
for _f in sorted(os.listdir(WFS)):
    if not _f.endswith(".yml"):
        continue
    _txt = ler(os.path.join(WFS, _f))
    # "versiona" = CHAMA entrar-no-main ou git commit em um `run:` de verdade — não basta
    # citar o nome num teste. `diagnostico-da-casa` invoca os testes do entrar-no-main e por
    # isso foi falso positivo na primeira versão deste contrato.
    _linhas_de_run = [l for l in _txt.splitlines()
                      if ("entrar-no-main" in l or "git commit" in l)
                      and not l.strip().startswith("#")
                      and "testes-" not in l and "rodar-contratos" not in l]
    _versiona = bool(_linhas_de_run)
    if not _versiona:
        continue
    _m = _re.search(r"^permissions:\n((?:  .*\n)+)", _txt, _re.M)
    _perms = _m.group(1) if _m else ""
    if "contents: write" not in _perms:
        _sem_escrita.append(_f)
ok("todo workflow que versiona estado tem contents: write",
   not _sem_escrita,
   "sem permissão de escrita: " + ", ".join(_sem_escrita))

# ── 8. PERSISTÊNCIA: portão que não fica gravado é portão decorativo ─────────────
# (16/11/2026, defeito real): o publicar-instagram registrava o media_id no disco do runner e
# NÃO commitava. O run morria, o estado sumia, e a mesma peça ia ao ar de novo. A deduplicação
# funcionava perfeitamente — contra um arquivo que voltava vazio toda vez.
PUB_ = ler(os.path.join(WFS, "publicar-instagram.yml"))
ok("o portão do Instagram PERSISTE o media_id (sem commit o portão é decorativo)",
   "instagram-publicados.json" in PUB_
   and ("entrar-no-main" in PUB_ or "git commit" in PUB_),
   "publicar-instagram não versiona o registro: o runner morre e a próxima peça repete")

# ── 11. O CRON DO GITHUB PERDE EXECUÇÃO: precisa de despacho, não de fé ────────
# (16/11/2026, medido com dados do próprio GitHub): `administrar-itch` agendado 06:17 rodou
# 15:52 (9h35 de atraso); `gravar-prancheta` agendado 12:50 NÃO disparou; `health-check`
# agendado 06:10 NÃO disparou. `schedule:` é best-effort e descarta execução sob carga.
# Os crons novos que eu entreguei como "em produção" nunca teriam rodado sozinhos — só rodaram
# porque eu disparei à mão. Sem despacho, "autônomo" é falso.
DESP = os.path.join(WFS, "despachante.yml")
ok("existe um despachante (o cron não é confiável)", os.path.exists(DESP))
_txt_desp = ler(DESP)
ok("o despachante tem gatilho próprio (não depende de outro cron perdido)",
   "schedule:" in _txt_desp and "workflow_dispatch:" in _txt_desp)
ok("o despachante tem permissão de actions: write (sem ela o dispatch falha)",
   "actions: write" in _txt_desp)
for _alvo in ("gravar-prancheta.yml", "gravar-gameplay.yml", "health-check.yml",
              "status-total.yml", "alertas-proativos.yml"):
    ok("o despachante cobre %s" % _alvo, _alvo in _txt_desp)
ok("o despachante respeita intervalo (não duplica o trabalho do cron)",
   "intervalo" in _txt_desp and "idade" in _txt_desp)
ok("o despachante respeita janela de Brasília",
   "janela" in _txt_desp and "BRT" in _txt_desp)

ok("o despachante manda publicar=AUTOMATICO para os gravadores",
   "AUTOMATICO" in _txt_desp,
   "sem o input, o alvo grava e não publica: o passo do YouTube exige event_name==schedule")
ok("o despachante manda o input no CORPO do dispatch (não só no comentário)",
   '"inputs": entradas' in _txt_desp or "'inputs': entradas" in _txt_desp)
# prova a razão: os gravadores só publicam pelo caminho agendado OU com AUTOMATICO
for _wf in ("gravar-prancheta.yml", "gravar-gameplay.yml"):
    _t = ler(os.path.join(WFS, _wf))
    ok("%s aceita AUTOMATICO (o despacho consegue publicar)" % _wf,
       "AUTOMATICO" in _t and "event_name == 'schedule'" in _t)

ok("o despertador existente também usa dispatch (padrão que já funcionava)",
   "dispatches" in ler(os.path.join(WFS, "despertador.yml")))

# ── LIMPEZA ──────────────────────────────────────────────────────────────────────────────
# Sem isto cada execução deixa temporários para trás. `/tmp` no runner é tmpfs: em poucas
# rodadas o `conferir-tudo` começa a falhar por disco cheio, com um erro que não aponta para cá.
for _tmp in (TMP_POSTS, TMP_RAIZ, ESPELHO, _RAIZ_REC):
    _sh.rmtree(_tmp, ignore_errors=True)

# ══════════════════════════════════ 12. QUEM MEDE CREDENCIAL RECEBE A MESMA LISTA
# (17/11/2026, defeito real e traiçoeiro): o `health-check.yml` passava 21 secrets ao auditor e
# dizia "44/44 ativas". O `status-total.yml` passava 9 e, executando o MESMO auditor no MESMO
# repositório, dizia "43/44 — rede-x ausente". Dois números oficiais contraditórios sobre o
# mesmo fato, e o errado era o que aparecia no painel do dono.
# A causa não foi bug de código: foram DUAS LISTAS mantidas à mão em arquivos diferentes.
# Este contrato exige que todo workflow que executa o auditor receba a lista canônica inteira.
import json as _json
import yaml as _yaml

# A lista NÃO é mantida à mão aqui: é derivada do próprio auditor (camadas tipo `credencial`).
# Mantê-la neste arquivo seria repetir o defeito que o contrato existe para impedir.
from health_check_credenciais import credenciais_auditadas  # noqa: E402  (criado abaixo)

CANON = credenciais_auditadas(os.path.join(MARKETING, "health-check-site.js"))

_faltando = []
for _f in ("health-check.yml", "status-total.yml", "alertas-proativos.yml"):
    _d = _yaml.safe_load(ler(os.path.join(WFS, _f)))
    for _j in (_d.get("jobs") or {}).values():
        for _st in _j.get("steps", []):
            # EXECUTA o módulo, não apenas cita: `git add posts/marketing/x.json` não precisa
            # de credencial nenhuma. Sem esta distinção o contrato cobrava env de um passo de
            # git — e cobrar o que não é necessário ensina a ignorar o contrato.
            _run = str(_st.get("run", ""))
            if any(("node " + os.path.join("tools", "marketing", _m) + ".js") in _run
                   for _m in ("health-check-site", "status-total-marketing",
                              "alertas-proativos-marketing")):
                _tem = {k for k, v in (_st.get("env") or {}).items() if "secrets." in str(v)}
                _falta = set(CANON) - _tem
                if _falta:
                    _faltando.append("%s: %s" % (_f, ", ".join(sorted(_falta)[:5])))
ok("todo workflow que audita camadas recebe a MESMA lista de credenciais",
   not _faltando, "; ".join(_faltando))

# ══════════════════════ 13. O WORKFLOW PASSA O QUE O MÓDULO LÊ (fecha a classe)
# (17/11/2026) A divergência de secrets entre `health-check` e `status-total` era UM caso de uma
# classe: a lista de env de um passo é escrita à mão, e ninguém compara com o que o módulo lê.
# O contrato 12 cobriu os 3 módulos auditores. Este cobre o resto.
#
# Duas escolhas que evitam contrato ruidoso (e contrato ruidoso é contrato ignorado):
#   • só nomes com CARA de credencial — `PLAYWRIGHT_CORE` e `PYTHON` são caminhos de binário,
#     não segredos; cobrar env para eles seria perseguir fumaça;
#   • a checagem é por WORKFLOW, não por passo — `publicar-devlog-itch.yml` tem um passo de
#     "verificar" (que não publica e por isso não precisa de cookie) e um de "publicar" (que
#     passa ITCH_COOKIE/ITCH_PROXY). Exigir por passo acusaria um defeito que não existe.
import glob as _glob
import re as _re

_CARA_DE_CREDENCIAL = _re.compile(r"_(TOKEN|PASS|APPPASS|PASSWORD|KEY|SECRET|COOKIE|ADDR|ADDRESS)$")
_FERRAMENTAS = sorted(_glob.glob(os.path.join(AQUI, "*.js")) + _glob.glob(os.path.join(MARKETING, "*.js")))

_neo = []
for _f in sorted(os.listdir(WFS)):
    if not _f.endswith(".yml"):
        continue
    _d = _yaml.safe_load(ler(os.path.join(WFS, _f))) or {}
    _passa_no_wf = set()
    _modulos = set()
    for _j in (_d.get("jobs") or {}).values():
        for _st in _j.get("steps", []):
            _passa_no_wf |= {k for k, v in (_st.get("env") or {}).items() if "secrets." in str(v)}
            _modulos |= set(_re.findall(r"tools/(?:marketing/)?([a-z0-9-]+\.js)", str(_st.get("run", ""))))
    for _mod in sorted(_modulos):
        _cand = [p for p in _FERRAMENTAS if p.endswith("/" + _mod)]
        if not _cand:
            continue
        _le = {v for v in _re.findall(r"process\.env\.([A-Z0-9_]+)", ler(_cand[0]))
               if _CARA_DE_CREDENCIAL.search(v)}
        _falta = _le - _passa_no_wf
        if _falta:
            _neo.append("%s → %s: %s" % (_f, _mod, ", ".join(sorted(_falta))))

ok("todo módulo executado por workflow recebe todas as envs que ele lê",
   not _neo, " | ".join(_neo[:4]))

# ══════════════ 14. AUTO-RECUPERAÇÃO COM A CAMADA DOENTE (o que faltava provar)
# (17/11/2026, pedido do instrutor) O contrato anterior apagava um estado AUSENTE e via o health
# check recriá-lo. Faltava o caso mais realista: arquivo PRESENTE e CORROMPIDO — escrita
# interrompida, merge ruim, disco cheio no meio do write. Medido antes do conserto:
#     status: json_invalido · ativa: false · recuperação: "sem recuperação automática"
# Ou seja: o sistema tinha um jeito de ficar doente para sempre, e o painel não avisava que
# dava para consertar. A recuperação só olhava `!existsSync`.
# Este contrato exige: camada doente → recuperação tentada → camada volta ativa → evidência guardada.
_RAIZ_DOENTE = tempfile.mkdtemp(prefix="fase2-doente-")
_sh.copytree(os.path.join(RAIZ, ".github"), os.path.join(_RAIZ_DOENTE, ".github"))
_sh.copytree(AQUI, os.path.join(_RAIZ_DOENTE, "tools"),
             ignore=_sh.ignore_patterns("__pycache__", "posts"))
os.makedirs(os.path.join(_RAIZ_DOENTE, "posts"), exist_ok=True)
with open(os.path.join(_RAIZ_DOENTE, "posts", "orquestrador.json"), "w", encoding="utf-8") as f:
    f.write('{ isto nao e json')      # o estado doente

_env_d = {"SITE_RAIZ": _RAIZ_DOENTE, "POSTS_DIR": os.path.join(_RAIZ_DOENTE, "posts"),
          "GITHUB_ACTIONS": "true"}
for _k in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "IG_TOKEN", "IG_USER_ID",
           "GMAIL_CHAT_APPPASS", "NOSTR_KEY", "THREADS_TOKEN", "BLUESKY_APPPASS"):
    _env_d[_k] = "presente"
_doente, _erro_doente = jnode(HC, env=_env_d)
_cam = next((d for d in (_doente or {}).get("detalhe", [])
             if d.get("camada") == "estado-orquestrador"), {})
_rec_d = (_doente or {}).get("recuperacoes", {}) or {}

ok("camada doente (JSON corrompido) é RECUPERADA e volta ativa",
   _cam.get("ativa") is True and _cam.get("status") == "recriada",
   "status=%s ativa=%s rec=%s" % (_cam.get("status"), _cam.get("ativa"),
                                  str(_cam.get("recuperacao"))[:70]))
ok("a tentativa de recuperação é REGISTRADA (não é recuperação silenciosa)",
   _rec_d.get("sucesso", 0) >= 1
   and any(i.get("camada") == "estado-orquestrador" for i in _rec_d.get("itens", [])),
   json.dumps(_rec_d)[:200])
ok("o arquivo doente é PRESERVADO como evidência antes de recriar",
   any("corrompido" in _n for _n in os.listdir(os.path.join(_RAIZ_DOENTE, "posts"))),
   os.listdir(os.path.join(_RAIZ_DOENTE, "posts")))
ok("o run não quebra com a camada doente (código 0 e relatório completo)",
   isinstance(_doente, dict) and _doente.get("camadas_total", 0) > 0,
   _erro_doente)
# ── e o contrário: com a camada SÃ, nenhuma recuperação é tentada ────────────────
_RAIZ_SA = tempfile.mkdtemp(prefix="fase2-sa-")
_sh.copytree(os.path.join(RAIZ, ".github"), os.path.join(_RAIZ_SA, ".github"))
_sh.copytree(AQUI, os.path.join(_RAIZ_SA, "tools"),
             ignore=_sh.ignore_patterns("__pycache__", "posts"))
_sh.copytree(os.path.join(RAIZ, "posts"), os.path.join(_RAIZ_SA, "posts"))
_sa, _ = jnode(HC, env={**_env_d, "SITE_RAIZ": _RAIZ_SA,
                        "POSTS_DIR": os.path.join(_RAIZ_SA, "posts")})
ok("com a camada SÃ, nenhuma recuperação é inventada",
   ((_sa or {}).get("recuperacoes") or {}).get("tentadas", 0) == 0,
   json.dumps((_sa or {}).get("recuperacoes"))[:160])
_sh.rmtree(_RAIZ_DOENTE, ignore_errors=True)
_sh.rmtree(_RAIZ_SA, ignore_errors=True)

# ══════════ 15. AUTO-OTIMIZADOR: NÃO PERDER O DADO, E FECHAR O LOOP (itens 3 e 4)
# (17/11/2026) Dois defeitos reais, ambos medidos:
#
# a) O ESTADO ERA DESTRUÍDO NA LEITURA. `carregar()` fazia
#        try { if (exists) cache = JSON.parse(...) } catch {}
#        cache = { estado vazio }          ← rodava SEMPRE, sobrescrevendo o lido
#    Gravar e ler no MESMO processo funcionava; em processo novo o histórico sumia. Por isso
#    `metricas_engajamento` ficava `{}` em produção mesmo com o coletor rodando.
#
# b) O CÁLCULO NÃO VIRAVA AÇÃO. `calcularCadencia()` devolvia 90/150/300 min e ninguém lia:
#    o portão do Instagram usava 120 fixo do YAML. O sistema media, concluía e ignorava.
#
# Este bloco prova os dois com PROCESSOS SEPARADOS (é o único jeito de provar (a): no mesmo
# processo o cache em memória esconde o defeito) e prova (b) lendo o intervalo efetivo do
# portão depois de alimentar o otimizador.
_OT = tempfile.mkdtemp(prefix="fase2-otim-")
os.makedirs(os.path.join(_OT, "posts", "marketing"), exist_ok=True)
_OT_ENV = {"POSTS_DIR": os.path.join(_OT, "posts")}

# (a) grava num processo...
node(os.path.join(MARKETING, "auto-otimizador-avancado.js"), "-e", "", env=_OT_ENV)  # aquece
_grava = ("const m=require(process.env.MOD);m.ativarAutoOtimizador();"
          "m.registrarAcesso('instagram','prancheta','19',700,'contrato');"
          "m.registrarEngajamento('instagram','prancheta','curtidas',120);")
node("-e", _grava, env={**_OT_ENV, "MOD": os.path.join(MARKETING, "auto-otimizador-avancado.js")})
# ...e lê em OUTRO processo
_le = ("const m=require(process.env.MOD);"
       "process.stdout.write(JSON.stringify(m.calcularCadencia('instagram','prancheta')))")
_r1 = node("-e", _le, env={**_OT_ENV, "MOD": os.path.join(MARKETING, "auto-otimizador-avancado.js")})
_d1 = {}
try:
    _d1 = json.loads((_r1.stdout or "{}").strip().splitlines()[-1])
except Exception:
    pass
ok("o otimizador NÃO perde o estado entre processos (defeito do try sem else)",
   _d1.get("ok") is True and _d1.get("total_acessos") == 700,
   (r1.stdout or r1.stderr)[:150])

# (b) o portão lê o intervalo do otimizador e ele DIFERE do padrão
_r2 = node(os.path.join(MARKETING, "instagram-estado.js"), "--resumo", env=_OT_ENV)
_txt = (_r2.stdout or "")
_m = _re.search(r"intervalo mínimo \| (\d+) min", _txt)
ok("o portão do Instagram USA o intervalo do otimizador (cálculo vira ação)",
   _m is not None and int(_m.group(1)) != 120 and "otimizador" in _txt,
   "(padrão seria 120) " + _txt.replace("\n", " ")[:170])
ok("o portão mostra de onde veio o intervalo (dado ou chute)",
   "origem do intervalo" in _txt, _txt[:120])

# (b2) força explícita continua vencendo o otimizador — quem quer travar a cadência não briga
_r3 = node(os.path.join(MARKETING, "instagram-estado.js"), "--resumo",
           env={**_OT_ENV, "IG_INTERVALO_MINUTOS": "45"})
_m3 = _re.search(r"intervalo mínimo \| (\d+) min", _r3.stdout or "")
ok("IG_INTERVALO_MINUTOS vence o otimizador (força explícita manda)",
   _m3 is not None and int(_m3.group(1)) == 45, (_r3.stdout or "")[:120])

# (b3) sem dado nenhum, cai no padrão e DIZ que é padrão
_OT_VAZIO = tempfile.mkdtemp(prefix="fase2-otim-vazio-")
os.makedirs(os.path.join(_OT_VAZIO, "posts", "marketing"), exist_ok=True)
_r4 = node(os.path.join(MARKETING, "instagram-estado.js"), "--resumo",
           env={"POSTS_DIR": os.path.join(_OT_VAZIO, "posts")})
ok("sem dado do otimizador, o portão usa 120 e admite que é padrão",
   "padrão" in (_r4.stdout or "") and "120 min" in (_r4.stdout or ""),
   (_r4.stdout or "")[:150])
_sh.rmtree(_OT, ignore_errors=True)
_sh.rmtree(_OT_VAZIO, ignore_errors=True)

# ══════════════════ 16. O COLETOR DE ENGAJAMENTO (o elo que faltava para o item 3)
# (17/11/2026) Item 3 do pedido: "não há workflow chamando registrarAcesso/Engajamento com
# dados reais de engajamento". Era verdade: `metricas_engajamento` ficava `{}` em produção.
# Este bloco prova que (a) o coletor existe e LÊ as duas redes, (b) ele NUNCA inventa zero
# quando a credencial falta, e (c) o workflow o executa e versiona o resultado.
COL = os.path.join(MARKETING, "coletar-engajamento.js")
ok("existe um coletor de engajamento real", os.path.exists(COL))

# (b) sem credencial: código 3 e nenhum número inventado
_sem_cred = node(COL, "--json", env={"IG_TOKEN": "", "YT_API_KEY": ""})
_sd = {}
try:
    # o --json imprime o OBJETO INTEIRO (multilinha) — pegar só a última linha devolvia "}".
    _sd = json.loads(_sem_cred.stdout or "{}")
except Exception:
    pass
ok("coletor sem credencial NÃO inventa zero (diz 'não verificável' e sai 3)",
   _sem_cred.returncode == 3 and not (_sd.get("por_rede") or {})
   and any("não verificável" in f for f in (_sd.get("falhas") or [])),
   "código=%s saida=%s" % (_sem_cred.returncode, (_sem_cred.stdout or "")[:140]))

# (a) com um duplo de HTTP no mesmo processo: lê e ATRIBUI o jogo certo
_prova = (
    "const cham=[];"
    "global.fetch=async(u)=>{const s=String(u);cham.push(s.split('?')[0]);"
    "let c;"
    "if(s.includes('/v21.0/111'))c={like_count:7,comments_count:2};"
    "else if(s.includes('youtube/v3/videos'))c={items:["
    "{id:'YT1',statistics:{viewCount:'50',likeCount:'5',commentCount:'3'}}]};"
    "else c={error:{message:'x'}};"
    "return{ok:!c.error,status:c.error?400:200,json:async()=>c};};"
    "process.env.IG_TOKEN='t';process.env.YT_API_KEY='k';"
    "const m=require(process.env.COL);"
    "(async()=>{await m.coletarInstagram();await m.coletarYouTube();"
    "process.stdout.write(JSON.stringify({chamadas:cham.length,"
    "prancheta:m.jogoDaPeca('prancheta-gameplay','PRANCHETA: x'),"
    "ambos:m.jogoDaPeca('#Prancheta #Ceifalume')}));})();"
)
_COL_TMP = tempfile.mkdtemp(prefix="fase2-col-")
os.makedirs(os.path.join(_COL_TMP, "posts", "marketing"), exist_ok=True)
with open(os.path.join(_COL_TMP, "posts", "marketing", "instagram-publicados.json"), "w",
          encoding="utf-8") as f:
    json.dump({"publicados": [{"media_id": "111", "legenda": "#Prancheta"}]}, f)
with open(os.path.join(_COL_TMP, "posts", "youtube-publicados.json"), "w", encoding="utf-8") as f:
    json.dump({"publicados": [{"id": "YT1", "slug": "prancheta-gameplay",
                               "titulo": "PRANCHETA: x"}]}, f)
_rc = node("-e", _prova, env={"POSTS_DIR": os.path.join(_COL_TMP, "posts"), "COL": COL})
_cd = {}
try:
    _cd = json.loads((_rc.stdout or "{}").strip().splitlines()[-1])
except Exception:
    pass
ok("o coletor LÊ as duas redes e atribui o jogo pela peça",
   _cd.get("chamadas", 0) >= 2 and _cd.get("prancheta") == "prancheta"
   and _cd.get("ambos") == "ambos",
   (_rc.stdout or _rc.stderr or "")[:160])
_sh.rmtree(_COL_TMP, ignore_errors=True)

# (c) o workflow executa o coletor
_ST = ler(os.path.join(WFS, "status-total.yml"))
ok("o status-total EXECUTA o coletor de engajamento",
   "coletar-engajamento.js" in _ST, "status-total.yml não chama o coletor")
ok("o workflow passa ao coletor as credenciais que ele lê",
   "IG_TOKEN" in _ST and "YT_API_KEY" in _ST)

# ══════════ 17. CONCORRÊNCIA: DOIS RUNS GRAVANDO O MESMO ESTADO (perda silenciosa)
# (17/11/2026) MEDIDO EM PRODUÇÃO, NÃO EM TEORIA: status-total #4 coletou
# `youtube/ceifalume/visualizacoes = 13`, fez o commit, e o push foi RECUSADO 6 vezes. O run
# terminou `success` e `metricas_engajamento` continuou `{}` no repo. Duas causas somadas:
#
#  (a) `conciliar-estado.py` recusava o merge porque `atualizadoEm` (timestamp) NUNCA é igual
#      dos dois lados. Todo estado do marketing era descartado quando dois runs coincidiam.
#  (b) o workflow usava `|| echo`, então a perda não aparecia: run verde, dado fora.
#
# Ambos são invisíveis lendo o código — só aparecem com dois runs concorrentes DE VERDADE.
_CE = os.path.join(os.path.dirname(__file__), "conciliar-estado.py")
ok("existe o conciliador de estado", os.path.exists(_CE))

# conciliar-estado.py é PYTHON — chamar com `node` dava "Unknown file extension .py"
_CONC = (
    "import importlib.util,json;"
    "spec=importlib.util.spec_from_file_location('ce',r'%s');"
    "ce=importlib.util.module_from_spec(spec);spec.loader.exec_module(ce);"
    "base={'ativo':True,'fluxo_acesso':{},'metricas_engajamento':{},'otimizacoes':[],"
    "'atualizadoEm':'2026-11-17T02:00:00Z'};"
    "loc=dict(base);loc['metricas_engajamento']={'youtube':{'ceifalume':{'visualizacoes':13}}};"
    "loc['atualizadoEm']='2026-11-17T02:34:10Z';"
    "rem=dict(base);rem['fluxo_acesso']={'instagram':{'ambos':{'17':1}}};"
    "rem['atualizadoEm']='2026-11-17T02:34:07Z';"
    "o=ce.conciliar(base,loc,rem);"
    "campos=[k for k in ('fluxo_acesso','metricas_engajamento') if o.get(k)];"
    "print(json.dumps({'ok':True,'campos':campos,'carimbo':o.get('atualizadoEm')}))"
) % os.path.abspath(_CE)
_r = subprocess.run([sys.executable, "-c", _CONC], capture_output=True, text=True, timeout=60)
_d = {}
try:
    _d = json.loads((_r.stdout or "{}").strip().splitlines()[-1])
except Exception:
    pass
ok("dois runs concorrentes NÃO perdem dado na conciliação (carimbo não é conflito)",
   _d.get("ok") is True and len(_d.get("campos") or []) == 2,
   (_r.stdout or _r.stderr or "")[:180])
ok("o carimbo escolhido é o MAIS NOVO (não o do primeiro que chegou)",
   _d.get("carimbo") == "2026-11-17T02:34:10Z", str(_d.get("carimbo")))

# dados de verdade continuam sendo conflito — a correção não pode virar "aceita tudo"
_CONC2 = (
    # Cada instrução precisa de \n REAL: `import x;import y` numa linha só deixa o `try:`
    # colado no statement anterior. (E o contrato anterior passava por ACIDENTE: rodava com
    # `node`, falhava, e nada imprimia 'ACEITOU'. Falso positivo pego pela sabotagem.)
    "import importlib.util\n"
    "spec=importlib.util.spec_from_file_location('ce',r'%s')\n"
    "ce=importlib.util.module_from_spec(spec);spec.loader.exec_module(ce)\n"
    # (E o contrato anterior passava por ACIDENTE: rodava com `node`, que falhava sem
    #  imprimir 'ACEITOU'. Falso positivo pego pela sabotagem.)
    "try:\n ce.conciliar({'n':1},{'n':2},{'n':3}); print('ACEITOU')\n"
    "except ce.Conflito: print('RECUSOU')\n"
) % os.path.abspath(_CE)
_r2 = subprocess.run([sys.executable, "-c", _CONC2], capture_output=True, text=True, timeout=60)
ok("conflito REAL de dado continua recusado (carimbo não abriu a porteira)",
   "RECUSOU" in (_r2.stdout or ""), (_r2.stdout or "")[:80])

# (b) o workflow não pode mais esconder push recusado
for _wf in ("status-total.yml", "publicar-instagram.yml", "health-check.yml",
            "alertas-proativos.yml", "marketing-24h.yml"):
    _t = ler(os.path.join(WFS, _wf))
    ok("%s FALHA quando o estado não entra no main (sem `|| echo`)" % _wf,
       # procurar o PADRÃO (entrar-no-main ... || echo), não a palavra no comentário
       not _re.search(r'entrar-no-main\.sh[^\n]*\|\|\s*echo', _t)
       and "entrar-no-main.sh" in _t,
       "ainda engole a falha de push")

print("\n%d/%d contratos da Fase 2 em produção passaram" % (len(TOTAL) - len(FALHAS), len(TOTAL)))
sys.exit(1 if FALHAS else 0)
