#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envio de build para o itch.io pela ferramenta oficial (butler).

POR QUE EXISTE (26/10/2026): o itch não tem API para criar página nem para devlog, mas TEM
uma ferramenta oficial e gratuita para subir build de jogo: `butler`. A chave que a casa já
usa para ler downloads serve também para o envio — não precisa de conta nova nem de chave
nova.

Regras que este arquivo respeita:
  * `status` é SOMENTE LEITURA: mostra o diff entre o que está no itch e o que está no
    repositório, sem enviar nada;
  * `push` exige a palavra de confirmação: build ao vivo é coisa séria (substitui o que o
    jogador baixa);
  * a chave nunca aparece: vai para um arquivo de identidade temporário, nunca em argumento
    de linha de comando (que apareceria em log de processo) e nunca em mensagem;
  * nada é inventado: sem butler, sem chave ou sem build, o script diz o motivo.
"""
import hashlib
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

URL_BUTLER = "https://broth.itch.zone/butler/linux-amd64/LATEST/archive/default"
PALAVRA_CONFIRMACAO = "PUBLICAR"

# Alvo de cada jogo no itch. O que NÃO estiver aqui não é enviado — lista fechada.
BUILDS = {
    "ceifalume": {
        "alvo": "rebocl-brank/ceifalume",
        "pasta": "ceifalume",              # export web do Godot, na raiz do repositório
        "canais": ["html5", "web", "default"],
        # id do jogo no itch (página /dashboard/game/5017404/edit). Serve para a leitura de
        # uploads, que é o que responde "o que o jogador REALMENTE abre na página".
        "jogo_id": 5017404,
        "precisa": ["index.html", "index.wasm", "index.pck"],
    },
    # PRANCHETA não aparece aqui de propósito: não existe build do PRANCHETA em nenhum
    # repositório da casa (conferido em 26/10/2026). Sem export do Godot não há o que subir.
}


def resumo_de_chave(chave):
    chave = str(chave or "")
    return "(ausente)" if not chave else "prefixo %s… · %d caracteres" % (chave[:4], len(chave))


def chave_do_ambiente(nome_env="ITCH_API_KEY"):
    """Primeira chave não vazia de ITCH_API_KEY / ITCH_API_KEYS (a casa usa plural)."""
    bruto = os.environ.get(nome_env) or os.environ.get("ITCH_API_KEYS") or ""
    for parte in bruto.split(","):
        if parte.strip():
            return parte.strip()
    return ""


def procurar_butler():
    caminho = os.environ.get("BUTLER_PATH") or shutil.which("butler")
    return caminho if caminho and os.path.exists(caminho) else None


def arquivo_de_identidade(chave, pasta_temp=None):
    """Escreve a chave num arquivo 0600 e devolve o caminho (só o butler lê)."""
    pasta = pasta_temp or tempfile.mkdtemp(prefix="itch-")
    caminho = os.path.join(pasta, "butler_creds")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(chave)
    os.chmod(caminho, 0o600)
    return caminho


def conferir_build(slug, raiz=RAIZ):
    """(erros, caminho_da_pasta). Recusa build incompleto antes de qualquer rede."""
    alvo = BUILDS.get(slug)
    if not alvo:
        return ["build não declarado para %r (lista fechada — PRANCHETA não tem build)" % slug], None
    pasta = os.path.join(raiz, alvo["pasta"])
    if not os.path.isdir(pasta):
        return ["pasta do build ausente: " + alvo["pasta"]], None
    erros = []
    for nome in alvo["precisa"]:
        caminho = os.path.join(pasta, nome)
        if not os.path.exists(caminho):
            erros.append("arquivo do build ausente: " + nome)
        elif os.path.getsize(caminho) == 0:
            erros.append("arquivo do build vazio: " + nome)
    return erros, pasta


def ambiente_do_butler(chave, base=None):
    """O butler recomenda BUTLER_API_KEY em CI (ele mesmo avisa isso)."""
    ambiente = dict(base or os.environ)
    if chave:
        ambiente["BUTLER_API_KEY"] = chave
    return ambiente


def rodar(argumentos, identidade=None, timeout=600, executar=None, chave=None):
    """Chama o butler. Devolve (codigo, saida). A chave vai só por arquivo de identidade."""
    executar = executar or subprocess.run
    butler = procurar_butler()
    if not butler:
        return 127, "butler não está instalado (baixe de " + URL_BUTLER + ")"
    cmd = [butler] + (["--identity", identidade] if identidade else []) + list(argumentos)
    try:
        r = executar(cmd, capture_output=True, text=True, timeout=timeout,
                     env=ambiente_do_butler(chave))
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "butler passou do tempo limite"


def alvo_do_canal(slug, canal):
    alvo = BUILDS.get(slug)
    return "%s:%s" % (alvo["alvo"], canal) if alvo else None


def interpretar_preview(saida):
    """Traduz `butler push-preview` em IGUAL ou DIFERENTE — com número, não com fé.

    O que NÃO compara com o itch, medido em 30/10:
      * `butler status alvo:canal` devolve a mesma tabela de canais (run 41083714746);
      * `butler diff` compara DUAS PASTAS LOCAIS — cmd/diff/diff.go recebe target/source/patch
        (runs 41084326374 e 41084610596).

    O que compara: `butler push-preview <pasta> <alvo:canal>` ("authenticated; doesn't modify
    anything on itch.io", cmd/push/preview.go). Ele termina com uma linha de texto estável:

        Comparison vs build 2217549: 0 new, 0 modified, 0 deleted, 13 unchanged

    Isso é o que se lê aqui. Zero em new/modified/deleted = o que o jogador baixa é esta pasta.
    Canal sem build anterior sai como "All N entries are new" e conta como DIFERENTE. Qualquer
    dúvida cai em DIFERENTE: erra para o lado que não esconde atualização.
    """
    texto = (saida or "").strip()
    if not texto:
        return "INDEFINIDO: o butler não respondeu nada"
    achado = re.search(r"Comparison vs build (\d+): (\d+) new, (\d+) modified, "
                       r"(\d+) deleted, (\d+) unchanged", texto)
    if achado:
        pai, novos, mudados, apagados, iguais = (int(g) for g in achado.groups())
        conta = "%d novos, %d modificados, %d apagados, %d iguais (contra o build %d)" % (
            novos, mudados, apagados, iguais, pai)
        if novos == 0 and mudados == 0 and apagados == 0:
            return "IGUAL: o itch já tem exatamente esta pasta (nada a enviar) — " + conta
        return "DIFERENTE: o envio mudaria o que o jogador baixa — " + conta
    if re.search(r"All (\d+) entries are new \(no previous build\)", texto):
        return ("DIFERENTE: o canal não tem build anterior (todo o conteúdo é novo) — "
                + re.search(r"All (\d+) entries are new", texto).group(0))
    # Reserva: se o butler for chamado com --json, o resultado vem em NDJSON e a linha útil é a
    # que tem "comparison" (o arquivo inteiro não é um JSON só).
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            objeto = json.loads(linha)
        except Exception:  # noqa: BLE001
            continue
        comp = objeto.get("comparison") if isinstance(objeto, dict) else None
        if isinstance(comp, dict):
            novos = int(comp.get("new") or 0)
            mudados = int(comp.get("modified") or 0)
            apagados = int(comp.get("deleted") or 0)
            conta = "%d novos, %d modificados, %d apagados, %d iguais" % (
                novos, mudados, apagados, int(comp.get("same") or 0))
            if novos == 0 and mudados == 0 and apagados == 0:
                return "IGUAL: o itch já tem exatamente esta pasta (nada a enviar) — " + conta
            return "DIFERENTE: o envio mudaria o que o jogador baixa — " + conta
    return "INDEFINIDO: não achei a linha de comparação na saída do butler\n" + texto[-600:]


def status(slug, canal=None, raiz=RAIZ, identidade=None, executar=None, chave=None):
    """SOMENTE LEITURA. Sem canal, o butler LISTA os canais que existem no jogo.

    Defeito corrigido no próprio teste (26/10/2026): `butler status` aceita apenas o alvo
    (`usuario/jogo`), não a pasta — passar a pasta devolve "unexpected <path>". Sem canal, o
    comando lista os canais e o estado do último build: é assim que se descobre o nome do
    canal em vez de adivinhar.
    """
    alvo_base = (BUILDS.get(slug) or {}).get("alvo")
    if not alvo_base:
        return False, "build não declarado para %r" % slug
    if canal is None:
        codigo, saida = rodar(["status", alvo_base], identidade=identidade, executar=executar,
                              chave=chave)
        # A tabela de canais diz QUAL build está no ar, mas não responde a pergunta que
        # importa: "o que está no itch é o que está no repositório?". Em 30/10 essa pergunta
        # ficou sem resposta e o status saiu vazio de sentido. Então, depois da tabela,
        # comparamos o primeiro canal declarado do jogo (html5) com a pasta local.
        linhas = [(saida or "(sem saída)")[:800]]
        declarados = [c for c in (BUILDS.get(slug) or {}).get("canais") or []]
        erros, _pasta = conferir_build(slug, raiz)
        if declarados and not erros:
            alvo_canal = alvo_do_canal(slug, declarados[0])
            # `butler status alvo:canal` devolve a mesma tabela de canais (medido em 30/10):
            # não é diff, então não respondia nada. Quem compara pasta local com o build no
            # ar é `butler diff <pasta> <alvo:canal>`.
            # ORDEM: `butler push-preview <pasta> <alvo:canal>` (o --json é global, vem antes
            # do subcomando). Autenticado, mas NÃO modifica nada no itch.
            cod, dif = rodar(["push-preview", _pasta, alvo_canal],
                             identidade=identidade, executar=executar, chave=chave)
            linhas.append("--- diferença de %s contra a pasta local ---" % alvo_canal)
            if cod == 0:
                linhas.append(interpretar_preview(dif or ""))
            else:
                linhas.append("não consegui comparar: " + (dif or "")[:300])
        elif erros:
            linhas.append("não consegui comparar (build local incompleto): " + "; ".join(erros))
        return (codigo == 0), "\n".join(linhas)[:2400]
    erros, _pasta = conferir_build(slug, raiz)
    if erros:
        return False, "; ".join(erros)
    codigo, saida = rodar(["status", alvo_do_canal(slug, canal)],
                          identidade=identidade, executar=executar, chave=chave)
    if codigo == 0:
        return True, (saida or "(sem diferença: o itch já tem este build)")[:800]
    return False, "status recusado (canal %r?): %s" % (canal, saida[:300])


def ensaio(slug, canal, raiz=RAIZ, identidade=None, executar=None, chave=None):
    """ENSAIO (butler push --dry-run): mostra o que subiria, sem subir nada.

    É o que faltava para provar build pronto sem mexer na página: a página do CEIFALUME tem
    upload feito pelo site (APK, upload_id 19268322) e o butler não enxerga canal nenhum, ou
    seja, o canal do export web seria NOVO — e canal novo é mudança visível na loja.
    """
    erros, pasta = conferir_build(slug, raiz)
    if erros:
        return False, "; ".join(erros)
    alvo = alvo_do_canal(slug, canal)
    codigo, saida = rodar(["push", pasta, alvo, "--dry-run", "--assume-yes"],
                          identidade=identidade, executar=executar, chave=chave)
    if codigo != 0:
        return False, "ensaio recusado: " + saida[:400]
    return True, saida[:1200]


def enviar(slug, canal, confirmacao, raiz=RAIZ, identidade=None, executar=None, chave=None):
    """Envia o build. Só com a palavra de confirmação."""
    if str(confirmacao or "").strip().upper() != PALAVRA_CONFIRMACAO:
        return False, ("faltou a confirmação (%s): build ao vivo substitui o que o jogador "
                       "baixa, então não vai sozinho" % PALAVRA_CONFIRMACAO)
    erros, pasta = conferir_build(slug, raiz)
    if erros:
        return False, "build recusado: " + "; ".join(erros)
    alvo = alvo_do_canal(slug, canal)
    # SEM `--hidden` — DEFEITO MEDIDO EM 31/10/2026 (run 41151339470):
    #   itch.io API error (400): /wharf/builds: hidden can only be set when creating a new channel
    # O itch só aceita `hidden` ao CRIAR canal; em canal existente a chamada é recusada com 400.
    # E o `hidden` esconderia justamente o que o dono pediu: o build com o selo do gameplay no ar.
    # Publicar é deixar visível — então o push vai sem a flag.
    argumentos = ["push", pasta, alvo, "--assume-yes"]
    # Carimbo de versão (opcional) vai como --userversion: é o que permite, depois, dizer QUAL
    # build está no ar em vez de só um id.
    #
    # DEFEITO MEDIDO EM 31/10/2026 (run 41151770746): o carimbo morava DENTRO da pasta enviada,
    # então o build no ar ficava com um arquivo a mais que o repositório não tem, e o
    # `push-preview` — a única comparação confiável com o itch — respondia "1 apagado" para
    # sempre. Ou seja, o status nunca conseguia dizer a verdade ("IGUAL"). O carimbo agora vive
    # fora do pacote (env VERSAO_BUILD ou posts/versao-build.json) e a pasta enviada é
    # exatamente a pasta do repositório, arquivo por arquivo.
    versao = str(os.environ.get("VERSAO_BUILD") or "").strip()
    if not versao:
        carimbo = os.path.join(raiz, "posts", "versao-build.json")
        if os.path.exists(carimbo):
            try:
                with open(carimbo, encoding="utf-8") as f:
                    versao = str(json.load(f).get("versao") or "").strip()
            except Exception:  # noqa: BLE001
                versao = ""
    if versao:
        argumentos += ["--userversion", versao]
        print("versão do envio:", versao)
    codigo, saida = rodar(argumentos, identidade=identidade, executar=executar, chave=chave)
    if codigo != 0:
        return False, "envio recusado: " + saida[:400]
    return True, "enviado para %s — https://%s.itch.io/%s" % (
        alvo, BUILDS[slug]["alvo"].split("/")[0], BUILDS[slug]["alvo"].split("/")[1])


def listar_jogos(chave, get=None):
    """Jogos da conta pela API oficial (somente leitura): slug e url exatos.

    Existe porque adivinhar slug/ canal custa rodada: `butler status` respondeu "No channel
    found" para o alvo que a página do site aponta, e sem a lista eu estaria chutando entre
    rebocl-brank, reboclbrank-max e variantes com versão no nome.
    """
    get = get or _get_json
    if not chave:
        return None, "sem chave"
    dados, erro = get("https://api.itch.io/profile/games", chave)
    if erro or not isinstance(dados, dict):
        return None, erro or "resposta inesperada"
    jogos = []
    for j in dados.get("games") or []:
        jogos.append({"id": j.get("id"),
                      "titulo": (j.get("title") or "")[:60],
                      "slug": j.get("url") or j.get("slug") or "",
                      "publicado": j.get("published"),
                      "downloads": j.get("downloads_count"),
                      "visitas": j.get("views_count")})
    return jogos, None


def uploads_do_jogo(chave, jogo_id, get=None):
    """SOMENTE LEITURA: os uploads que o itch tem do jogo, com canal e data.

    POR QUE EXISTE (31/10/2026): a página do itch embute UM upload específico
    (html-classic.itch.zone/html/19268311/index.html). O build que o butler empurrou pode não
    ser esse upload — e aí o selo do gameplay não chega a quem joga, mesmo com "push enviado" no
    log. Adivinhar isso é o erro que esta casa não quer: aqui a resposta vem da API oficial,
    upload por upload, com id, nome, canal e data.
    """
    get = get or _get_json
    if not chave:
        return None, "sem chave"
    dados, erro = get("https://api.itch.io/games/%s/uploads" % jogo_id, chave)
    if erro or not isinstance(dados, dict):
        return None, erro or "resposta inesperada"
    lista = []
    for u in dados.get("uploads") or []:
        build = u.get("build") or {}
        lista.append({"id": u.get("id"),
                      "nome": (u.get("filename") or u.get("display_name") or "")[:60],
                      "canal": build.get("channel") or u.get("channel") or "",
                      "build_id": build.get("id"),
                      "bytes": u.get("size"),
                      "atualizado": (u.get("updated_at") or "")[:19],
                      "plataforma": u.get("platform") or u.get("type") or "",
                      "tipo": u.get("type") or ""})
    return lista, None


def _get_texto(url, abrir=None):
    """GET simples, sem chave: a página pública do jogo não pede login."""
    if abrir:
        # injetável: aceita texto puro ou (texto, erro) — quem testa não precisa montar urllib
        r = abrir(url)
        return (r, None) if isinstance(r, str) else (r[0], r[1])
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8", "replace"), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:80]


def o_que_o_jogador_abre(slug, abrir=None):
    """QUAL upload a página do itch realmente abre — medido, não suposto.

    POR QUE EXISTE (31/10/2026): o log do butler dizia "✓ enviado" e o `status` dizia IGUAL,
    mas a página do jogo continuava embutindo `html-classic.itch.zone/html/19268311/index.html`
    — um upload de 16/09. Ou seja: o build novo existia num canal do itch e NÃO era o que o
    jogador abria. "Publicado" que não chega a ninguém é falso-verde com outro nome.

    Esta função lê a página pública e devolve o upload embutido (id e versão). É a única medida
    que responde a pergunta que importa: o que abre quando alguém clica em jogar?
    """
    alvo = (BUILDS.get(slug) or {}).get("alvo")
    if not alvo:
        return None, "build não declarado para %r" % slug
    usuario, jogo = alvo.split("/", 1)
    url = "https://%s.itch.io/%s" % (usuario, jogo)
    html, erro = _get_texto(url, abrir=abrir)
    if erro or not html:
        return None, erro or "página vazia"
    achado = re.search(r"html(?:-classic)?\.itch\.zone/html/(\d+)/index\.html(?:\?v=(\d+))?",
                       html)
    if not achado:
        return None, "a página respondeu, mas não achei o iframe do jogo"
    upload, versao = achado.group(1), achado.group(2) or ""
    embutido = "https://html-classic.itch.zone/html/%s/index.html" % upload
    return {"jogo": jogo, "pagina": url, "upload_id": upload, "versao": versao,
            "embutido": embutido}, None


def o_jogador_ve_o_selo(slug, marcador="rb-gameplay", abrir=None):
    """A pergunta que o log do butler NÃO responde: o upload que a página abre tem o selo?

    Se o build novo está num canal e a página abre outro upload, o jogador não vê nada do que
    foi enviado. Aqui isso vira número: baixa o index.html do upload embutido e procura o
    marcador (`rb-gameplay`, o selo do gameplay).
    """
    abre, erro = o_que_o_jogador_abre(slug, abrir=abrir)
    if erro:
        return None, erro
    pagina, erro2 = _get_texto(abre["embutido"] + (("?v=" + abre["versao"]) if abre["versao"] else ""),
                               abrir=abrir)
    if erro2 or not pagina:
        return None, erro2 or "index.html do upload embutido veio vazio"
    return dict(abre, tem_marcador=marcador in pagina, marcador=marcador,
                bytes_do_index=len(pagina)), None


ARQUIVOS_DO_JOGO = ["index.html", "index.js", "index.pck", "index.wasm"]


def _baixar(url, timeout=180):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def conferir_conteudo(slug, raiz=RAIZ, baixar=None, arquivos=None):
    """O JOGO que o visitante do itch recebe é o mesmo que está no repositório?

    POR QUE EXISTE (31/10/2026): o cofre dizia "o jogador NÃO abre este build" porque a página
    embute um upload antigo — conclusão certa e MEDIDA INCOMPLETA. Comparando arquivo por
    arquivo, o conteúdo do jogo (index.pck, index.js, index.wasm) é byte a byte IGUAL ao do
    repositório; o que difere é só a casca HTML (o itch injeta o htmlgame.js dele e a casca
    embutida não tem o selo). Sem essa comparação, a casa continuaria tratando como "antigo" um
    jogo que está atualizado. Cada linha aqui é sha256 do arquivo servido contra o do repo.
    """
    baixar = baixar or _baixar
    arquivos = arquivos or ARQUIVOS_DO_JOGO
    pasta = (BUILDS.get(slug) or {}).get("pasta")
    if not pasta:
        return None, "build não declarado para %r" % slug
    abre, erro = o_que_o_jogador_abre(slug)
    if erro:
        return None, erro
    base = abre["embutido"].rsplit("/", 1)[0] + "/"
    linhas = []
    for nome in arquivos:
        local = os.path.join(raiz, pasta, nome)
        if not os.path.exists(local):
            linhas.append({"arquivo": nome, "estado": "ausente no repositório", "repo": "",
                           "itch": "", "bytes": 0})
            continue
        with open(local, "rb") as f:
            conteudo_local = f.read()
        sha_local = hashlib.sha256(conteudo_local).hexdigest()
        try:
            conteudo_itch = baixar(base + nome)
        except Exception as e:  # noqa: BLE001
            linhas.append({"arquivo": nome, "estado": "não consegui baixar do itch (%s)" % str(e)[:60],
                           "repo": sha_local[:16], "itch": "", "bytes": len(conteudo_local)})
            continue
        sha_itch = hashlib.sha256(conteudo_itch).hexdigest()
        linhas.append({"arquivo": nome,
                       "estado": "IGUAL" if sha_itch == sha_local else "DIFERENTE",
                       "repo": sha_local[:16], "itch": sha_itch[:16],
                       "bytes": len(conteudo_local)})
    # O jogo é o conteúdo, não a casca: index.html é a única peça que o itch reescreve.
    nucleo = [l for l in linhas if l["arquivo"] != "index.html"
              and not l["estado"].startswith("não consegui") and l["estado"] != "ausente no repositório"]
    jogo_igual = bool(nucleo) and all(l["estado"] == "IGUAL" for l in nucleo)
    casca = [l for l in linhas if l["arquivo"] == "index.html"]
    return {"jogo": abre["jogo"], "pagina": abre["pagina"], "upload": abre["upload_id"],
            "base": base, "arquivos": linhas, "jogo_igual_ao_repo": jogo_igual,
            "casca_html_igual": bool(casca) and casca[0]["estado"] == "IGUAL",
            "o_que_difere": [l["arquivo"] for l in linhas if l["estado"] == "DIFERENTE"]}, None


def _get_json(url, chave):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + chave,
                                               "Accept": "application/json",
                                               "User-Agent": "rebocl-itch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode()), None
    except Exception as e:
        return None, str(e)[:80]


def main(argv):
    modo = argv[0] if argv else "status"
    slug = argv[1] if len(argv) > 1 else "ceifalume"
    chave = chave_do_ambiente()
    print("chave do itch:", resumo_de_chave(chave))
    if not chave and modo not in ("conferir", "jogador"):
        print("✗ sem chave: defina ITCH_API_KEYS nos segredos do repositório")
        return 1
    identidade = arquivo_de_identidade(chave)
    try:
        if modo == "api":
            jogos, erro = listar_jogos(chave)
            if erro:
                print("✗ não consegui listar os jogos:", erro)
                return 1
            for j in jogos:
                print("  id=%-9s %-28s slug=%-40s downloads=%s visitas=%s publicado=%s" % (
                    j.get("id") or "?", j["titulo"], j["slug"] or "?", j["downloads"],
                    j["visitas"], j["publicado"]))
            # O id é o que a edição de página (tools/itch-navegador.py) exige no caminho
            # /dashboard/game/<id>/edit. Sem imprimi-lo, cada rodada começava adivinhando.
            return 0
        if modo == "conferir":
            # SOMENTE LEITURA: baixa o que a página serve e compara sha256 com o repositório.
            resultado, erro = conferir_conteudo(slug)
            if erro:
                print("✗ não consegui conferir:", erro)
                return 1
            print("página %s — upload %s" % (resultado["pagina"], resultado["upload"]))
            for l in resultado["arquivos"]:
                print("  %-12s %-14s repo=%s itch=%s %8d B" % (
                    l["arquivo"], l["estado"], l["repo"] or "-", l["itch"] or "-", l["bytes"]))
            print("  jogo (conteúdo) igual ao repositório: %s" % (
                "SIM" if resultado["jogo_igual_ao_repo"] else "NÃO"))
            print("  casca html igual: %s" % ("SIM" if resultado["casca_html_igual"] else
                                              "NÃO (o itch reescreve e injeta o htmlgame.js dele)"))
            return 0
        if modo == "jogador":
            # SOMENTE LEITURA: o que abre quando alguém clica em jogar, e o que a API tem.
            abre, erro = o_que_o_jogador_abre(slug)
            if erro:
                print("✗ não consegui ler a página do jogo:", erro)
                return 1
            print("página %s" % abre["pagina"])
            print("  abre o upload %s%s — %s" % (
                abre["upload_id"], (" (v=%s)" % abre["versao"]) if abre["versao"] else "",
                abre["embutido"]))
            selo, erro_selo = o_jogador_ve_o_selo(slug)
            if erro_selo:
                print("  (não consegui abrir o upload embutido: %s)" % erro_selo)
            else:
                print("  o upload que o jogador abre %s o selo do gameplay (%s)" % (
                    "TEM" if selo["tem_marcador"] else "NÃO TEM", selo["marcador"]))
            jogo_id = str((BUILDS.get(slug) or {}).get("jogo_id") or "")
            if jogo_id:
                lista, erro2 = uploads_do_jogo(chave, jogo_id)
                if erro2:
                    print("  (não consegui cruzar com a API: %s)" % erro2)
                else:
                    for u in lista:
                        marca = "  ← é ESTE que o jogador abre" if str(u["id"]) == abre["upload_id"] else ""
                        print("  upload %-10s %-26s %10s B  %s%s" % (
                            u["id"], u["nome"], u["bytes"], u["atualizado"], marca))
            return 0
        if modo == "uploads":
            jogo = argv[2] if len(argv) > 2 else str((BUILDS.get(slug) or {}).get("jogo_id") or "")
            if not jogo:
                print("✗ cadê o id do jogo? passe como 3o argumento ou declare em BUILDS")
                return 2
            lista, erro = uploads_do_jogo(chave, jogo)
            if erro:
                print("✗ não consegui listar os uploads:", erro)
                return 1
            for u in lista:
                print("  id=%-10s canal=%-10s build=%-10s %8s B  %s  %s" % (
                    u["id"], u["canal"] or "-", u["build_id"] or "-", u["bytes"],
                    u["atualizado"] or "-", u["nome"]))
            return 0
        if modo == "status":
            ok_lista, lista = status(slug, None, identidade=None, chave=chave)
            print(("✓ " if ok_lista else "✗ ") + "canais no itch (alvo "
                  + (BUILDS.get(slug) or {}).get("alvo", "?") + "):")
            for linha in (lista or "").splitlines():
                print("   " + linha[:160])
            return 0 if ok_lista else 1
        if modo == "ensaio":
            canal = argv[2] if len(argv) > 2 else "html5"
            ok, msg = ensaio(slug, canal, identidade=None, chave=chave)
            print(("✓ " if ok else "✗ ") + "ensaio " + canal + ":")
            for linha in (msg or "").splitlines()[:20]:
                print("   " + linha[:160])
            return 0 if ok else 1
        if modo == "push":
            # a palavra vem do ambiente (o workflow passa CONFIRMACAO=PUBLICAR), nunca de uma
            # constante no código: publicar é decisão, e a decisão tem que aparecer no run
            confirmacao = os.environ.get("CONFIRMACAO", "")
            canal = argv[2] if len(argv) > 2 else "html5"
            ok, msg = enviar(slug, canal, confirmacao, identidade=identidade)
            print(("✓ " if ok else "✗ ") + msg)
            return 0 if ok else 1
        print("modo desconhecido:", modo)
        return 2
    finally:
        try:
            os.remove(identidade)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
