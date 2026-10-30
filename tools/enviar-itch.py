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
import json
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
        return (codigo == 0), (saida or "(sem saída)")[:800]
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
    # --hidden só vale para canal novo: o build fica no itch, mas não aparece como download
    # imediato. Assim nada muda para o jogador sem o dono ver primeiro.
    codigo, saida = rodar(["push", pasta, alvo, "--assume-yes", "--hidden"],
                          identidade=identidade, executar=executar, chave=chave)
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
    if not chave:
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
            canal = argv[2] if len(argv) > 2 else "html5"
            ok, msg = enviar(slug, canal, os.environ.get("CONFIRMACAO", ""), identidade=identidade)
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
