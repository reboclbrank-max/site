import json, os, sys, datetime, time, urllib.request, urllib.parse
import base64, re
COFARE_URL = "https://api.github.com/repos/reboclbrank-max/base/contents/ferramentas/cofare.json?ref=main"

def le_cofare():
    pat = os.environ.get("GHPAT")
    if not pat:
        return {}, None
    try:
        req = urllib.request.Request(COFARE_URL, headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
        j = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        return json.loads(base64.b64decode(j["content"]).decode()), j["sha"]
    except Exception:
        return {}, None

# Destinos públicos, factuais e estáveis do funil editorial. O texto nunca escolhe
# URL livre: a rota é resolvida somente nesta lista, sem rastreador, encurtador ou
# parâmetro de atribuição. As páginas do produto mantêm os links para os canais
# oficiais já existentes; por isso um post pode levar ao jogo certo sem criar conta
# ou aumentar cadência.
DESTINOS_EDITORIAIS = {
    "prancheta": "https://reboclbrank-max.github.io/site/jogos/prancheta/",
    "ceifalume": "https://reboclbrank-max.github.io/site/jogos/ceifalume/",
    "catalogo": "https://reboclbrank-max.github.io/site/jogos.html",
    "canais": "https://reboclbrank-max.github.io/site/canais.html",
}
URLS_DE_DESTINO_PERMITIDAS = frozenset(DESTINOS_EDITORIAIS.values())
LIMITE_TEXTO_EDITORIAL = 220
# O menor limite vigente é o post textual do Bluesky. Reservar espaço para a URL
# impede que cada adaptador corte o destino no fim da mensagem.
LIMITE_MENSAGEM_MICROBLOG = 300
UA = {"User-Agent": "rebocl-postador/2"}

def codigo_erro(e):
    return "%s %s" % (getattr(e, "code", ""), str(e)[:50])
IG_ARTE = json.loads("""["https://img.itch.zone/aW1hZ2UvNTAxNzQwNC8zMDA0MDAyNy5wbmc=/original/sNW2uy.png",
"https://img.itch.zone/aW1hZ2UvNTAxNzQwNC8zMDA2NjgzMC5wbmc=/original/y4xru4.png",
"https://img.itch.zone/aW1hZ2UvNTAxNzQwNC8zMDA0MDAyOC5wbmc=/original/d7Kx0N.png",
"https://img.itch.zone/aW1hZ2UvNTAxNzQwNC8zMDA0MDAyOS5wbmc=/original/Mx7rpI.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDEzMy5wbmc=/original/njF2ij.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDEzMC5wbmc=/original/QPkTlF.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDEzMi5wbmc=/original/Wygen%2F.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDEzNC5wbmc=/original/r0Bsw9.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDEzMS5wbmc=/original/PsPCSV.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDY0Ni5wbmc=/original/K9%2F4UT.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDY0NC5wbmc=/original/s4YS93.png",
"https://img.itch.zone/aW1hZ2UvNTExMjc4OC8zMDYxMDY0NS5wbmc=/original/8WWfsP.png"]""")
# Espelhos estáveis e públicos do próprio repositório. Só entram se a arte de origem
# for recusada pela Meta; evitam que uma falha de CDN pare o canal inteiro.
IG_ARTE_RESERVA = [
    "https://raw.githubusercontent.com/reboclbrank-max/site/main/media/prancheta/capa-630x500.png",
    "https://raw.githubusercontent.com/reboclbrank-max/site/main/media/ceifalume/shot-dia9-chuva-1280x720.png",
    "https://raw.githubusercontent.com/reboclbrank-max/site/main/media/ceifalume/shot-jogo-1280x720.png",
    "https://raw.githubusercontent.com/reboclbrank-max/site/main/media/ceifalume/perfil-rb-itch-630x500.png",
]
PESQUISA_REDES = [
    ("lemmy.world", "https://lemmy.world/signup"), ("lemmy.ml", "https://lemmy.ml/signup"),
    ("meta.discourse", "https://meta.discourse.org/signup"), ("flarum", "https://discuss.flarum.org/signup"),
    ("bookwyrm", "https://bookwyrm.social/register"), ("tilvids-peertube", "https://tilvids.com/login"),
    ("writefreely", "https://write.as/register"), ("plume", "https://joinplu.me/"),
    ("diaspora*", "https://diasp.org/signup"), ("friendica", "https://libranet.de/register"),
    ("pixelfed", "https://pixelfed.social/register"), ("mastodon.social", "https://mastodon.social/auth/sign_up"),
]
FATOS = ("FATOS REAIS (use APENAS estes, NADA fora deles): PRANCHETA = simulador de gestao de futebol 100% ficticio, "
         "voce desenha a bola parada na prancheta e ve a partida simular (ao vivo ou instantaneo), gratis no navegador ou APK, "
         "feito no Brasil com Godot. CEIFALUME 0.1 = jogo idle de fazenda noturna ja lancado, \"a fazenda nao dorme\", "
         "onde plantacoes crescem por ate 8 horas mesmo com o jogo fechado; gratis no navegador ou Android, sem conta. "
         "O postador anexa sozinho apenas um destino oficial permitido.")
resultados = []
INTERVALO_MINIMO_ENTRE_CICLOS = datetime.timedelta(hours=2)
CABECALHO_CICLO = re.compile(r"^##\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s+UTC)\b")


def ultimo_ciclo_registrado(caminho="posts/log.md"):
    """Lê apenas o carimbo público do último ciclo produtivo registrado.

    Entradas de teste não contam para a trava. Estado ausente ou malformado não
    é convertido em um horário inventado; a agenda normal continua sendo a
    fonte de continuidade nesse caso.
    """
    encontrados = []
    try:
        linhas = open(caminho, encoding="utf-8").read().splitlines()
    except Exception:
        return None
    for linha in linhas:
        if "TESTE" in linha.upper():
            continue
        achado = CABECALHO_CICLO.match(linha)
        if not achado:
            continue
        try:
            encontrados.append(datetime.datetime.strptime(
                achado.group(1), "%d/%m/%Y %H:%M UTC"
            ).replace(tzinfo=datetime.timezone.utc))
        except ValueError:
            return None
    return max(encontrados) if encontrados else None


def ciclo_ainda_recente(agora=None, caminho="posts/log.md"):
    """Evita dois ciclos externos próximos quando cron atrasado encontra a retaguarda."""
    ultimo = ultimo_ciclo_registrado(caminho)
    if ultimo is None:
        return False
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=datetime.timezone.utc)
    else:
        agora = agora.astimezone(datetime.timezone.utc)
    idade = agora - ultimo
    return datetime.timedelta(0) <= idade < INTERVALO_MINIMO_ENTRE_CICLOS

def destino_editorial(texto, tema=""):
    """Escolhe a página oficial conforme o assunto, sem seguir instruções do texto.

    Quando os dois jogos (ou nenhum) aparecem, o catálogo é mais honesto que
    atribuir um produto arbitrariamente. Chamadas genéricas para acompanhar a
    casa podem apontar ao hub público de canais. Não há URLs de terceiros,
    parâmetros de rastreamento, redirecionamento ou efeito externo nesta função.
    """
    contexto = (str(texto or "") + " " + str(tema or "")).casefold()
    ceifalume = any(sinal in contexto for sinal in (
        "ceifalume", "fazenda", "plantação", "plantacoes", "lanterna", "colha", "colher", "mercado noturno",
    ))
    prancheta = any(sinal in contexto for sinal in (
        "prancheta", "futebol", "manager", "bola parada", "tática", "tatica", "técnico", "tecnico", "clube",
    ))
    acompanhar = any(sinal in contexto for sinal in (
        "seguir a conta", "siga a conta", "acompanhe a casa", "canais oficiais", "acompanhar a marca",
    ))
    if ceifalume and not prancheta:
        return DESTINOS_EDITORIAIS["ceifalume"]
    if prancheta and not ceifalume:
        return DESTINOS_EDITORIAIS["prancheta"]
    if acompanhar:
        return DESTINOS_EDITORIAIS["canais"]
    return DESTINOS_EDITORIAIS["catalogo"]


def destino_oficial(url_sugerida, texto, tema=""):
    """Aceita apenas uma URL exata da lista pública; o resto cai na rota semântica."""
    candidata = str(url_sugerida or "").strip()
    return candidata if candidata in URLS_DE_DESTINO_PERMITIDAS else destino_editorial(texto, tema)


def mensagem_editorial(texto, destino):
    """Monta uma mensagem íntegra para o menor canal, sem truncar o link final."""
    texto = str(texto or "").strip()
    destino = str(destino or "").strip()
    if destino not in URLS_DE_DESTINO_PERMITIDAS:
        raise ValueError("destino editorial fora da lista permitida")
    mensagem = texto + "\n" + destino
    if not texto or len(mensagem) > LIMITE_MENSAGEM_MICROBLOG:
        raise ValueError("texto editorial nao cabe com destino no menor canal")
    return mensagem


LIMITE_CONSECUTIVO_POR_PRODUTO = 2
CABECALHO_POST_PUBLICADO = re.compile(r"^##\s+\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s+UTC\b", re.I)


def produto_do_destino(destino):
    """Classifica somente os dois destinos de jogo que a diversidade pode equilibrar."""
    if destino == DESTINOS_EDITORIAIS["prancheta"]:
        return "prancheta"
    if destino == DESTINOS_EDITORIAIS["ceifalume"]:
        return "ceifalume"
    return None


def produto_editorial(texto="", url=""):
    """Retorna um jogo só quando o texto/rota não mistura ambos os produtos."""
    conteudo = (str(texto or "") + " " + str(url or "")).casefold()
    tem_prancheta = bool(re.search(r"\bprancheta\b", conteudo, re.I))
    tem_ceifalume = bool(re.search(r"\bceifalume\b", conteudo, re.I))
    if tem_prancheta == tem_ceifalume:
        return None
    return "prancheta" if tem_prancheta else "ceifalume"


def produtos_publicados_recentes(historico, limite=LIMITE_CONSECUTIVO_POR_PRODUTO):
    """Lê apenas blocos finais bem formados; histórico ambíguo não força uma troca."""
    blocos, atual = [], None
    for linha in str(historico or "").splitlines():
        if CABECALHO_POST_PUBLICADO.match(linha):
            if atual is not None:
                blocos.append("\n".join(atual))
            atual = []
        elif atual is not None:
            atual.append(linha)
    if atual is not None:
        blocos.append("\n".join(atual))
    recentes = []
    for bloco in reversed(blocos):
        produto = produto_editorial(bloco)
        if produto is None:
            break
        recentes.append(produto)
        if len(recentes) >= limite:
            break
    return recentes


def produto_exigido_por_diversidade(historico, reservas):
    """Após dois posts do mesmo jogo, pede o outro se a fila fechada o oferece."""
    recentes = produtos_publicados_recentes(historico)
    if len(recentes) != LIMITE_CONSECUTIVO_POR_PRODUTO or len(set(recentes)) != 1:
        return None
    alternativo = "ceifalume" if recentes[0] == "prancheta" else "prancheta"
    if any(produto_editorial(item.get("texto", ""), item.get("url", "")) == alternativo for item in (reservas or [])):
        return alternativo
    return None


def respeita_diversidade_editorial(texto, url_sugerida="", tema="", produto_exigido=None):
    """Aceita texto misto/genérico; bloqueia somente um terceiro destino igual seguido."""
    if produto_exigido not in {"prancheta", "ceifalume"}:
        return True
    destino = destino_oficial(url_sugerida, texto, tema)
    produto = produto_do_destino(destino)
    return produto is None or produto == produto_exigido


def seleciona_reserva_editorial(reservas, indice, historico="", produto_exigido=None):
    """Seleciona na rotação, priorizando a alternativa factual quando a guarda pede.

    A função não cria conteúdo, link ou cadência. Se todas as reservas já foram
    usadas, devolve a alternativa pedida (quando existir) para o chamador marcar
    a repetição com a data, preservando a deduplicação observável.
    """
    if not isinstance(reservas, list) or not reservas:
        raise ValueError("fila editorial sem reservas")
    ordem = [reservas[(int(indice) + passo) % len(reservas)] for passo in range(len(reservas))]
    memoria = str(historico or "").casefold()

    def nova(item):
        chave = str(item.get("texto", "")).strip()[:60].casefold()
        return bool(chave) and chave not in memoria

    def primeira(produto=None, somente_nova=False):
        for item in ordem:
            if produto is not None and produto_editorial(item.get("texto", ""), item.get("url", "")) != produto:
                continue
            if somente_nova and not nova(item):
                continue
            return item
        return None

    if produto_exigido in {"prancheta", "ceifalume"}:
        item = primeira(produto_exigido, somente_nova=True)
        if item is not None:
            return item, "diversidade", True
    item = primeira(somente_nova=True)
    if item is not None:
        return item, "rotacao", True
    if produto_exigido in {"prancheta", "ceifalume"}:
        item = primeira(produto_exigido)
        if item is not None:
            return item, "diversidade", False
    return ordem[0], "rotacao", False


# Alegações de plataforma, modo, preço ou prova social não aparecem nos fatos
# aprovados. A barreira é deliberadamente estreita: ela não tenta validar toda a
# linguagem natural, mas impede classes recorrentes de invenção e deixa a fila
# factual fechada assumir quando houver dúvida.
PADRAO_ALEGACAO_NAO_CONFIRMADA = re.compile(
    r"(?:\b(?:steam|epic(?: games)?|playstation|xbox|nintendo|switch|ios|app[ -]?store|google play)\b"
    r"|\b(?:multiplayer|multijogador|co[- ]?op(?:erativ[oa])?|pvp)\b"
    r"|\b(?:promo(?:[çc][aã]o)?|desconto|oferta|pr[ée][- ]?venda|beta|demo|early access|wishlist|lista de desejos)\b"
    r"|(?:r\$|us\$|€)\s*\d"
    r"|\b(?:viral|milhares|milh[oõ]es|mais jogad[oa]|recorde|\d+\s*(?:downloads?|seguidores?|avalia[çc][oõ]es?|reviews?))\b)",
    re.I,
)


# Barreira determinística para texto vindo de motor externo: o modelo sugere, a casa decide.
# Ela não tenta “provar” cada frase; reduz links inesperados, vazamento e promessas contraditórias
# antes de o postador cair na fila editorial já revisada.
def texto_gerado_seguro(texto, ja_publicados=""):
    texto = " ".join(str(texto or "").strip().split())
    baixo = texto.lower()
    if not (31 <= len(texto) <= LIMITE_TEXTO_EDITORIAL):
        return False
    if re.search(r"(?:https?://|www\.|(?:token|senha|password|api[ _-]?key|bearer)\b)", baixo, re.I):
        return False
    if re.search(r"(?:ignore|ignore as|esque[çc]a).{0,30}(?:instru|regra|prompt)", baixo, re.I):
        return False
    if len(re.findall(r"(?<!\w)#\w+", texto, re.UNICODE)) > 2:
        return False
    if PADRAO_ALEGACAO_NAO_CONFIRMADA.search(baixo):
        return False
    # Ambos os jogos 0.1 estão lançados. Só a versão futura permanece sem data;
    # portanto “em breve/em desenvolvimento” aplicado ao CEIFALUME inteiro é fato vencido.
    if (re.search(r"ceifalume.{0,45}\b(?:em breve|em desenvolvimento|ainda n[aã]o (?:lan[çc]ou|est[aá] dispon[ií]vel))\b", baixo, re.I)
            or re.search(r"\b(?:em breve|em desenvolvimento)\b.{0,45}ceifalume", baixo, re.I)):
        return False
    if re.search(r"prancheta.{0,45}\b(?:em breve|em desenvolvimento)\b", baixo, re.I):
        return False
    if not re.search(r"\b(?:prancheta|ceifalume|rebocl|fazenda|manager|futebol)\b", baixo, re.I):
        return False
    chave = texto[:60].lower()
    return chave not in str(ja_publicados or "").lower()

def cria_container_com_reserva(criar, primaria, reservas):
    """Tenta a arte principal uma vez e, se a plataforma a recusar, um espelho próprio.

    Não repete publicação: só repete a criação do container antes do publish. Se ambas
    falharem, preserva a falha original para o vigia registrar e tentar no próximo ciclo.
    """
    try:
        cid = criar(primaria)
        if not cid:
            raise RuntimeError("container sem id")
        return cid, primaria, False
    except Exception as erro_primario:
        for reserva in reservas:
            if reserva == primaria:
                continue
            try:
                cid = criar(reserva)
                if cid:
                    return cid, reserva, True
            except Exception:
                pass
        raise erro_primario

def espera_container_instagram(cid, token, consultar=None, pausar=time.sleep, tentativas=7, intervalo=10):
    """Espera a Meta terminar de preparar a mídia antes de chamar media_publish.

    A API pode aceitar o container e ainda responder 400 se o publish vier cedo.
    O token segue em cabeçalho HTTP, nunca na URL ou em log.
    """
    if not cid:
        raise RuntimeError("container instagram sem id")
    if consultar is None:
        def consultar(identificador, segredo):
            url = "https://graph.instagram.com/v21.0/" + urllib.parse.quote(str(identificador), safe="") + "?fields=status_code"
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + segredo, "User-Agent": UA["User-Agent"]})
            return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    ultimo = ""
    for tentativa in range(tentativas):
        estado = consultar(cid, token) or {}
        ultimo = str(estado.get("status_code") or "").upper()
        if ultimo in ("FINISHED", "PUBLISHED"):
            return
        if ultimo in ("ERROR", "EXPIRED"):
            raise RuntimeError("container instagram " + ultimo.lower())
        if tentativa + 1 < tentativas:
            pausar(intervalo)
    raise RuntimeError("container instagram nao ficou pronto" + (" (" + ultimo.lower() + ")" if ultimo else ""))

def http_json(url, data=None, headers=None):
    h = dict(UA); h["Content-Type"] = "application/json"
    if headers: h.update(headers)
    d = json.dumps(data).encode() if isinstance(data, dict) else data
    r = urllib.request.urlopen(urllib.request.Request(url, data=d, headers=h), timeout=30)
    return r.status, r.read().decode()

def cerebro(pergunta, tentativas=2):
    p = pergunta[:560]
    for tent in range(tentativas):
        bruto = ""
        try:
            req = urllib.request.Request("https://text.pollinations.ai/openai",
                data=json.dumps({"model": "openai-fast", "messages": [{"role": "user", "content": p}]}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "rebocl/2"})
            j = json.loads(urllib.request.urlopen(req, timeout=45).read().decode())
            bruto = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        except Exception:
            bruto = ""
        if not bruto:
            try:
                q = urllib.parse.quote(p)
                bruto = urllib.request.urlopen(urllib.request.Request("https://text.pollinations.ai/" + q, headers=dict(UA)), timeout=30).read().decode("utf-8", "ignore")
                try:
                    jj = json.loads(bruto)
                    bruto = jj.get("content") or ""
                except Exception:
                    pass
            except Exception:
                bruto = ""
        bruto = (bruto or "").strip()
        if bruto.startswith("```"):
            bruto = bruto.strip("`").lstrip()
        if bruto and not bruto.startswith("{") and '"reasoning"' not in bruto and '"role"' not in bruto and not bruto.lower().startswith("we need"):
            return bruto
        time.sleep(4)
    return ""

def canal(nome, fn):
    try:
        retorno = fn()
        # Algumas sondas não publicam: elas podem declarar explicitamente que a
        # leitura está indisponível, sem receber um selo verde por ter rodado.
        if isinstance(retorno, tuple) and len(retorno) == 2 and retorno[0] in {"OK", "PULADO", "INDISPONIVEL", "FALHOU"}:
            resultados.append((nome, retorno[0], str(retorno[1])[:220]))
        else:
            resultados.append((nome, "OK", str(retorno)[:60]))
    except Exception as e:
        msg = str(e)
        # janela de regra não é falha: fora do dia/hora previsto = PULADO (auditoria 14/10: o reel de sábado
        # aparecia como FALHOU em toda rodada, o que é falso alarme)
        # 14/10 noite: as TRAVAS também são regra, não falha (instagram 6h entre posts; reel 1x por semana) —
        # a postagem das 21:11 marcou "instagram=FALHOU" só porque a trava de 6h segurou, como deveria.
        if any(r in msg for r in ("janela", "sai no sabado", "ja postou ha", "ja saiu ha")):
            resultados.append((nome, "PULADO", msg[:60]))
        else:
            resultados.append((nome, "FALHOU", msg[:70]))


def indisponivel(nome, detalhe="configuracao de publicacao ausente"):
    """Separa credencial/capacidade ausente de uma trava anti-spam normal."""
    resultados.append((nome, "INDISPONIVEL", detalhe))


# Somente estes destinos entregam a mensagem editorial para fora. Sondas, motor,
# rota, push do dono, medição e interação não podem transformar uma tentativa em
# item do histórico de publicações.
CANAIS_DE_PUBLICACAO_EDITORIAL = frozenset((
    "telegram", "bluesky", "mastodon", "reel semanal", "instagram", "threads", "nostr", "discord",
))


def houve_aceite_tecnico_de_publicacao(registros):
    """Retorna se algum canal editorial devolveu aceitação técnica neste ciclo.

    Isto não prova entrega, alcance ou qualquer resultado humano. Apenas impede
    que texto sem aceite de canal seja usado como histórico de post publicado.
    """
    return any(
        nome in CANAIS_DE_PUBLICACAO_EDITORIAL and status == "OK"
        for nome, status, _ in registros
    )


def registra_historico_editorial(texto, registros, carimbo, caminho="posts/posts-publicados.md"):
    """Persiste texto somente após aceite técnico de canal editorial.

    A função não atribui entrega ou alcance; ela só preserva uma memória local
    coerente para a guarda de diversidade do próximo ciclo.
    """
    if not houve_aceite_tecnico_de_publicacao(registros):
        return False
    with open(caminho, "a", encoding="utf-8") as arquivo:
        arquivo.write("\n## %s\n%s\n" % (carimbo, str(texto).replace("\n", " ⏎ ")[:300]))
    return True


def resultado_nostr(aceitos):
    """Exige a confirmação de ao menos um relay antes de marcar Nostr como OK."""
    if not aceitos:
        raise RuntimeError("nenhum relay confirmou aceitacao tecnica")
    return "nota em %d relays" % len(aceitos)


LIMITE_INTERACOES_BSKY_POR_DIA = 3
CAMINHO_INTERACOES_BSKY_DIARIAS = "posts/interacoes-diarias.json"


def dia_utc(agora=None):
    """Converte o relógio de teste/runtime em dia UTC estável para a cota pública."""
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=datetime.timezone.utc)
    return agora.astimezone(datetime.timezone.utc).date().isoformat()


def estado_interacoes_bsky(caminho=CAMINHO_INTERACOES_BSKY_DIARIAS, agora=None):
    """Retorna ``(dia, usadas)``; estado malformado/futuro vira ``usadas=None``.

    O registro contém somente dia UTC e quantidade de tentativas reservadas, sem
    texto, autor, URI ou outro dado de terceiros. Falhar fechado evita transformar
    uma perda de estado em uma rajada de comentários.
    """
    caminho = os.fspath(caminho)
    hoje = dia_utc(agora)
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            estado = json.load(arquivo)
    except FileNotFoundError:
        return hoje, 0
    except Exception:
        return hoje, None
    if not isinstance(estado, dict):
        return hoje, None
    dia_registrado, usadas = estado.get("dia_utc"), estado.get("tentativas_bsky")
    if not isinstance(dia_registrado, str) or isinstance(usadas, bool) or not isinstance(usadas, int) or usadas < 0:
        return hoje, None
    try:
        data_registrada = datetime.date.fromisoformat(dia_registrado)
        data_hoje = datetime.date.fromisoformat(hoje)
    except (TypeError, ValueError):
        return hoje, None
    if data_registrada == data_hoje:
        return hoje, usadas
    if data_registrada < data_hoje:
        return hoje, 0
    return hoje, None


def reserva_interacao_bsky(caminho=CAMINHO_INTERACOES_BSKY_DIARIAS, agora=None):
    """Reserva uma das três tentativas diárias antes de qualquer envio externo.

    Reservar antes do request é intencional: se a rede ficar ambígua depois, o
    limite continua conservador e não tenta compensar com mais comentários.
    """
    caminho = os.fspath(caminho)
    hoje, usadas = estado_interacoes_bsky(caminho, agora)
    if usadas is None:
        return None, "estado-invalido"
    if usadas >= LIMITE_INTERACOES_BSKY_POR_DIA:
        return usadas, "limite-atingido"
    proxima = usadas + 1
    temporario = caminho + ".tmp"
    try:
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump({"dia_utc": hoje, "tentativas_bsky": proxima}, arquivo, ensure_ascii=False, sort_keys=True)
            arquivo.write("\n")
        os.replace(temporario, caminho)
    except Exception:
        try:
            os.unlink(temporario)
        except Exception:
            pass
        return None, "estado-invalido"
    return proxima, "reservada"


def recuperacao_credencial_pendente():
    """Mantém recuperação de conta fora do postador autônomo.

    Publicar nos canais já configurados não autoriza ler caixa de recuperação,
    redefinir senha, renovar/obter token ou escrever no cofre privado. Esses
    atos exigem revisão humana e configuração própria; a rotina só registra a
    fronteira sanitizada para não transformar ausência de credencial em sucesso.
    """
    return ("PULADO", "recuperação de credencial exige revisão humana; nenhuma caixa, senha, token ou cofre é alterado")


def main():
    argumentos = sys.argv[1:]
    if not argumentos:
        modo = ""
    elif argumentos == ["teste"]:
        modo = "teste"
    else:
        raise SystemExit("uso: python3 tools/postador.py [teste]")
    if modo != "teste" and ciclo_ainda_recente():
        print("RESUMO: cadencia=PULADO (intervalo minimo entre ciclos)")
        return
    fila = json.load(open("posts/fila.json"))
    cofare = {}
    dia = datetime.datetime.utcnow().timetuple().tm_yday
    if modo == "teste":
        texto = fila.get("teste", "teste da casa")
        tema_atual = "teste controlado"
        url_da_fila = ""
    else:
        cofare, _ = le_cofare()
        temas = ["apresente o PRANCHETA pra quem curte manager de futebol", "apresente o CEIFALUME 0.1 para quem curte idle de fazenda noturna",
                 "convide pra testar o PRANCHETA e contar qual modo prefere (lances ao vivo ou instantaneo)",
                 "explique por que o PRANCHETA ser 100% ficticio e um ponto forte", "dica tatica curta que funciona no PRANCHETA",
                 "converse sobre vida de dev solo no Brasil e cite os jogos", "pinte o clima do CEIFALUME: a fazenda nao dorme",
                 "curiosidade de bastidor: como e criar um jogo sozinho", "pergunte qual time o torcedor torce e provoque amistoso no PRANCHETA",
                 "explique o APK: por que tambem funciona no celular sem internet", "fale das plantacoes noturnas do CEIFALUME",
                 "compare gerir um clube real vs ficticio (sem citar clubes reais)", "pergunte: resultado ao vivo ou instantaneo, por que?",
                 "fale da arte pixelada e do clima de lanterna dos jogos", "convide pra seguir a conta pra acompanhar atualizacoes do CEIFALUME",
                 "conte que o PRANCHETA roda no navegador, sem baixar nada", "pergunte qual modo de jogo o publico prefere e por que",
                 "dica: como montar defesa no PRANCHETA", "fale do mercado noturno do CEIFALUME que muda de preco",
                 "agradeca aos que testaram e convide novos testadores", "explique o que e um manager de futebol pra quem nunca jogou",
                 "fale da liberdade de jogo 100% offline", "pergunte: qual ultimo jogo indie o publico jogou?",
                 "conte o passo a passo de como jogar o PRANCHETA agora", "pinte um cenario: noite de sexta, fazenda do CEIFALUME acesa",
                 "explique que a casa tambem ensina: devlogs abertos no itch", "pergunte o que falta num jogo de futebol pra ser perfeito",
                 "fale da rotina de estudar programacao todo dia", "compare jogar no navegador vs APK, vantagens de cada",
                 "peça sugestao de recurso pro CEIFALUME nos comentarios", "fale da alegria do primeiro jogador que nao e da familia",
                 "explique por que jogos pequenos tem alma", "pergunte: futebol com amigos ou gerir o clube sozinho?",
                 "fale dos sons e musicas que combinam com CEIFALUME", "convide pra apoiar seguindo e compartilhando", "retrospectiva rapida: o que a casa aprendeu essa semana"]
        contexto = ""
        try:
            with open("posts/aulas.md") as fa:
                ultimas = [l.strip() for l in fa.readlines() if l.strip()][-3:]
            contexto = " APRENDIZADOS ANTERIORES DA CASA (use o que servir): " + " ".join(l[:120] for l in ultimas)
        except Exception:
            pass
        indice_tema = 0
        url_da_fila = ""
        try:
            with open("posts/tema-contador.txt") as ft:
                indice_tema = int(ft.read().strip() or 0)
        except Exception:
            pass
        with open("posts/tema-contador.txt", "w") as ft:
            ft.write(str(indice_tema + 1))
        tema_atual = temas[indice_tema % len(temas)]
        pedido = ("Voce e a voz da casa REBOCL BRANK, dev solo brasileiro, tom humano e caloroso. Escreva UM post de rede social, "
                  "ate 220 caracteres, portugues, no maximo 2 hashtags. " + FATOS + " TEMA DE HOJE: " + tema_atual + "." + contexto)
        gerado = cerebro(pedido[:550])
        ciclo_do_dia = datetime.datetime.utcnow().hour // 3
        try:
            with open("posts/posts-publicados.md") as fpp:
                ja_publicados = fpp.read()
        except Exception:
            ja_publicados = ""
        produto_exigido = produto_exigido_por_diversidade(ja_publicados, fila["posts"])
        candidato_gerado = " ".join((gerado or "").strip().split())[:LIMITE_TEXTO_EDITORIAL]
        texto = candidato_gerado if (
            texto_gerado_seguro(candidato_gerado, ja_publicados)
            and respeita_diversidade_editorial(candidato_gerado, tema=tema_atual, produto_exigido=produto_exigido)
        ) else ""
        motivo_reserva = ""
        if not texto:
            indice_reserva = (dia + ciclo_do_dia) % len(fila["posts"])
            item, motivo_reserva, reserva_nova = seleciona_reserva_editorial(
                fila["posts"], indice_reserva, ja_publicados, produto_exigido)
            texto = item["texto"]
            if not reserva_nova:
                texto += " (" + datetime.datetime.utcnow().strftime("%d/%m") + ")"
            url_da_fila = item.get("url", "")
        detalhe_cerebro = "post novo validado" if texto == candidato_gerado and texto else (
            "fila de reserva (diversidade editorial)" if motivo_reserva == "diversidade"
            else "fila de reserva (gerado reprovado/indisponivel)"
        )
        resultados.append(("cerebro", "OK", detalhe_cerebro))
    destino = destino_oficial(url_da_fila, texto, tema_atual)
    mensagem = mensagem_editorial(texto, destino)
    nome_destino = next(nome for nome, url in DESTINOS_EDITORIAIS.items() if url == destino)
    if modo == "teste":
        # A simulação deve permanecer local: sem cofre, rede, canal, escrita de
        # arquivo ou contador. Ela só deixa visível a mensagem e a rota validadas.
        print("SIMULACAO OFFLINE: destino=%s | mensagem=%s" % (nome_destino, mensagem))
        return
    resultados.append(("destino editorial", "OK", "rota oficial " + nome_destino))

    def _ntfy():
        req = urllib.request.Request("https://ntfy.sh/" + os.environ.get("NTFY_TOPIC", "rebocl-enxame-x7k2"),
            data=("📣 A CASA POSTOU\n\n" + mensagem[:400]).encode(), headers=dict(UA))
        return "push " + str(urllib.request.urlopen(req, timeout=30).status)
    canal("ntfy (push do dono)", _ntfy)

    tt, tc = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if tt and tc:
        canal("telegram", lambda: "enviado " + str(http_json("https://api.telegram.org/bot" + tt + "/sendMessage", {"chat_id": tc, "text": mensagem})[0]))
    else:
        indisponivel("telegram")

    bh = os.environ.get("BLUESKY_HANDLE") or cofare.get("bluesky", {}).get("handle")
    bp = os.environ.get("BLUESKY_APPPASS") or cofare.get("bluesky", {}).get("senha_de_app")
    if bh and bp:
        def _bs():
            s, c = http_json("https://bsky.social/xrpc/com.atproto.server.createSession", {"identifier": bh, "password": bp})
            jwt = json.loads(c)["accessJwt"]
            agora = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            s2, _ = http_json("https://bsky.social/xrpc/com.atproto.repo.createRecord",
                {"repo": json.loads(c)["did"], "collection": "app.bsky.feed.post", "record": {"text": mensagem[:300], "createdAt": agora}},
                {"Authorization": "Bearer " + jwt})
            return "postado " + str(s2)
        canal("bluesky", _bs)
    else:
        indisponivel("bluesky")

    mu = os.environ.get("MASTODON_URL") or cofare.get("mastodon", {}).get("url")
    mt = os.environ.get("MASTODON_TOKEN") or cofare.get("mastodon", {}).get("token")
    if mu and mt:
        def _ma():
            form = urllib.parse.urlencode({"status": mensagem[:500]}).encode()
            req = urllib.request.Request(mu.rstrip("/") + "/api/v1/statuses", data=form,
                headers={"Authorization": "Bearer " + mt, "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "rebocl-postador/2"})
            return "toot " + str(urllib.request.urlopen(req, timeout=30).status)
        canal("mastodon", _ma)
    else:
        indisponivel("mastodon")

    igid, igtok = os.environ.get("IG_USER_ID"), os.environ.get("IG_TOKEN")
    if not (igid and igtok):
        ini = cofare.get("instagram", {}) or {}
        igid, igtok = ini.get("user_id"), ini.get("token")
    if igid and igtok:
        def _reel():
            agora = datetime.datetime.utcnow()
            dia_semana = agora.weekday()
            hora_utc = agora.hour
            # 14/10: cron atrasado podia cair fora da madrugada de sabado e perder a semana — agora aceita
            # sabado a partir das 21h UTC e a madrugada de domingo (ate 02h), alem do mesmo cuidado do IG.
            na_janela = (dia_semana == 5 and hora_utc >= 21) or (dia_semana == 6 and hora_utc <= 2)
            if not na_janela:
                raise RuntimeError("reel sai no sabado a noite BRT (um por semana — qualidade > quantidade)")
            ultimo_reel = None
            try:
                with open("posts/reel-quando.txt") as fr:
                    ultimo_reel = datetime.datetime.fromisoformat(fr.read().strip())
            except Exception:
                pass
            if ultimo_reel and (agora - ultimo_reel) < datetime.timedelta(days=6):
                raise RuntimeError("reel da semana ja saiu ha %.1f dias" % ((agora - ultimo_reel).total_seconds() / 86400.0))
            url_video = "https://raw.githubusercontent.com/reboclbrank-max/site/main/media/reel.mp4"
            form = urllib.parse.urlencode({"video_url": url_video, "caption": mensagem[:2000], "media_type": "REELS", "share_to_feed": "1", "access_token": igtok}).encode()
            reqc = urllib.request.Request("https://graph.instagram.com/v21.0/" + igid + "/media", data=form, headers=dict(UA))
            cid = json.loads(urllib.request.urlopen(reqc, timeout=120).read().decode()).get("id")
            time.sleep(2)
            formp = urllib.parse.urlencode({"creation_id": cid, "access_token": igtok}).encode()
            reqp = urllib.request.Request("https://graph.instagram.com/v21.0/" + igid + "/media_publish", data=formp, headers=dict(UA))
            pub = json.loads(urllib.request.urlopen(reqp, timeout=120).read().decode())
            try:
                with open("posts/reel-quando.txt", "w") as fr:
                    fr.write(agora.isoformat())
            except Exception:
                pass
            return "REEL publicado id " + str(pub.get("id"))[:14]
        canal("reel semanal", _reel)

    if igid and igtok:
        def _ig():
            hora_utc = datetime.datetime.utcnow().hour
            # 14/10: os crons do GitHub chegam atrasados (visto: 00:11, 04:05, 08:27, 11:19...), entao a hora
            # EXATA quase nunca batia e o instagram ficava sempre PULADO. Agora: janela com folga (dia 13h-16h,
            # noite 21h-02h UTC) + trava de 6h desde o ultimo post (segue no maximo 2-3 por dia, sem parecer bot).
            na_janela = (13 <= hora_utc <= 16) or hora_utc >= 21 or hora_utc <= 2
            if not na_janela:
                raise RuntimeError("fora da janela do instagram (dia 13h-16h / noite 21h-02h UTC) — conta nova nao pode parecer bot")
            ultimo_em = None
            try:
                with open("posts/ig-quando.txt") as fq:
                    ultimo_em = datetime.datetime.fromisoformat(fq.read().strip())
            except Exception:
                pass
            if ultimo_em and (datetime.datetime.utcnow() - ultimo_em) < datetime.timedelta(hours=6):
                raise RuntimeError("instagram ja postou ha %.1fh (minimo 6h entre posts)" % ((datetime.datetime.utcnow() - ultimo_em).total_seconds() / 3600.0))
            contador = 0
            try:
                with open("posts/ig-arte.txt") as fc:
                    contador = int(fc.read().strip() or 0)
            except Exception:
                pass
            arte = IG_ARTE[contador % len(IG_ARTE)]
            with open("posts/ig-arte.txt", "w") as fc:
                fc.write(str(contador + 1))
            def criar_container(url_arte):
                form = urllib.parse.urlencode({"image_url": url_arte, "caption": mensagem[:2000], "access_token": igtok}).encode()
                reqc = urllib.request.Request("https://graph.instagram.com/v21.0/" + igid + "/media", data=form, headers=dict(UA))
                cid = json.loads(urllib.request.urlopen(reqc, timeout=60).read().decode()).get("id")
                if not cid:
                    raise RuntimeError("instagram nao devolveu container")
                espera_container_instagram(cid, igtok)
                return cid
            reserva = [IG_ARTE_RESERVA[contador % len(IG_ARTE_RESERVA)]]
            cid, _, usou_reserva = cria_container_com_reserva(criar_container, arte, reserva)
            time.sleep(2)
            formp = urllib.parse.urlencode({"creation_id": cid, "access_token": igtok}).encode()
            reqp = urllib.request.Request("https://graph.instagram.com/v21.0/" + igid + "/media_publish", data=formp, headers=dict(UA))
            pub = json.loads(urllib.request.urlopen(reqp, timeout=60).read().decode())
            try:
                with open("posts/ig-quando.txt", "w") as fq:
                    fq.write(datetime.datetime.utcnow().isoformat())
            except Exception:
                pass
            return "postado id " + str(pub.get("id"))[:14] + (" (arte reserva)" if usou_reserva else "")
        canal("instagram", _ig)
    else:
        indisponivel("instagram")

    thid, thtok = os.environ.get("THREADS_USER_ID"), os.environ.get("THREADS_TOKEN")
    if not (thid and thtok) and cofare.get("threads", {}).get("token"):
        thid, thtok = cofare["threads"].get("user_id"), cofare["threads"]["token"]
    if thid and thtok:
        def _th():
            def _post(url, dados):
                return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(), headers=dict(UA)), timeout=30).read().decode())
            c = _post("https://graph.threads.net/v1.0/" + thid + "/threads", {"media_type": "TEXT", "text": mensagem[:480], "access_token": thtok})
            time.sleep(2)
            pub = _post("https://graph.threads.net/v1.0/" + thid + "/threads_publish", {"creation_id": c.get("id"), "access_token": thtok})
            # A postagem usa somente o token já configurado para este ciclo. Não
            # tenta renová-lo, substituí-lo ou persistir segredo em outro repo;
            # expiração/configuração ausente fica para revisão humana explícita.
            return "publicado id " + str(pub.get("id"))[:12]
        canal("threads", _th)
    else:
        indisponivel("threads")

    nk = os.environ.get("NOSTR_KEY")
    if nk:
        def _no():
            import hashlib
            from coincurve import PrivateKey
            import websocket
            sk = PrivateKey(bytes.fromhex(nk))
            px = sk.public_key.format()[1:].hex()
            ev = {"pubkey": px, "created_at": int(time.time()), "kind": 1,
                  "tags": [["t", "gamedev"], ["t", "indiedev"], ["t", "brazil"]], "content": mensagem[:896]}
            ser = json.dumps([0, ev["pubkey"], ev["created_at"], ev["kind"], ev["tags"], ev["content"]], separators=(",", ":"), ensure_ascii=False).encode()
            ev["id"] = hashlib.sha256(ser).hexdigest()
            ev["sig"] = sk.sign_schnorr(bytes.fromhex(ev["id"]), os.urandom(32)).hex()
            aceitos = []
            for relay in ["wss://relay.damus.io", "wss://nos.lol"]:
                try:
                    ws = websocket.create_connection(relay, timeout=20)
                    ws.send(json.dumps(["EVENT", ev]))
                    fim, resp = time.time() + 15, ""
                    while time.time() < fim:
                        resp = ws.recv()
                        if '"OK"' in resp: break
                    ws.close()
                    r = json.loads(resp)
                    if r[0] == "OK" and r[2] is True: aceitos.append(relay)
                except Exception:
                    pass
            return resultado_nostr(aceitos)
        canal("nostr", _no)
    else:
        indisponivel("nostr")

    dw = os.environ.get("DISCORD_WEBHOOK")
    if dw:
        canal("discord", lambda: "enviado " + str(http_json(dw, {"content": mensagem[:2000]})[0]))
    else:
        indisponivel("discord")

    if modo != "teste" and bh and bp:
        def _cacador():
            _, usadas = estado_interacoes_bsky()
            if usadas is None:
                return "PULADO", "estado diario de interacoes invalido; sem envio"
            if usadas >= LIMITE_INTERACOES_BSKY_POR_DIA:
                return "PULADO", "limite diario de %d interacoes ja atingido" % LIMITE_INTERACOES_BSKY_POR_DIA
            s, c = http_json("https://bsky.social/xrpc/com.atproto.server.createSession", {"identifier": bh, "password": bp})
            jwt = json.loads(c)["accessJwt"]
            q = ["#indiedev", "#gamedev", "#screenshotsaturday"][dia % 3]
            rq = urllib.request.Request("https://bsky.social/xrpc/app.bsky.feed.searchPosts?q=" + urllib.parse.quote(q) + "&limit=10",
                headers={"Authorization": "Bearer " + jwt, "User-Agent": "rebocl/1"})
            achados = json.loads(urllib.request.urlopen(rq, timeout=30).read().decode()).get("posts", [])
            ja_feitos = set()
            try:
                with open("posts/interacoes.md") as fi0:
                    ja_feitos = set(l.strip() for l in fi0 if l.strip().startswith("at://"))
            except Exception:
                pass
            feitas = 0
            for p in achados:
                if usadas >= LIMITE_INTERACOES_BSKY_POR_DIA: break
                rec = p.get("record") or {}
                if rec.get("reply"): continue
                if p.get("uri") in ja_feitos: continue
                autor = (p.get("author") or {}).get("handle", "")
                if not autor or "reboclbrank" in autor: continue
                txt_pai = (rec.get("text") or "")[:150]
                if not txt_pai or any(m2 in txt_pai.lower() for m2 in ["giveaway", "crypto", "nft", "politic", "election"]): continue
                pergunta = ("Voce e a voz da casa REBOCL BRANK, dev solo brasileiro amigavel. Escreva UM comentario genuino, generoso, "
                            "curto (ate 200 caracteres), sem link e sem spam, em portugues ou ingles conforme o post, para este post de outro dev: \"" + txt_pai + "\"")
                comentario = cerebro(pergunta)
                if not comentario or len(comentario) < 15: continue
                usadas, reserva = reserva_interacao_bsky()
                if reserva != "reservada":
                    detalhe = "estado diario indisponivel; sem envio" if reserva == "estado-invalido" else "limite diario de %d interacoes atingido" % LIMITE_INTERACOES_BSKY_POR_DIA
                    if feitas:
                        return ("OK", "%d interacoes (q=%s); %s" % (feitas, q, detalhe))
                    return ("PULADO", detalhe)
                corpo = {"repo": bh, "collection": "app.bsky.feed.post", "record": {"text": comentario[:300],
                    "createdAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "reply": {"root": {"uri": p["uri"], "cid": p["cid"]}, "parent": {"uri": p["uri"], "cid": p["cid"]}}}}
                pr = urllib.request.Request("https://bsky.social/xrpc/com.atproto.repo.createRecord", data=json.dumps(corpo).encode(),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer " + jwt, "User-Agent": "rebocl/1"})
                urllib.request.urlopen(pr, timeout=30)
                with open("posts/interacoes.md", "a") as fi:
                    fi.write(p["uri"] + "\n")
                feitas += 1
                time.sleep(1)
            return "%d interacoes (q=%s; cota UTC %d/%d)" % (feitas, q, usadas, LIMITE_INTERACOES_BSKY_POR_DIA)
        canal("cacador de oportunidades", _cacador)
    elif modo != "teste":
        indisponivel("cacador de oportunidades", "configuracao do canal ausente")

    if modo != "teste":
        def _aula():
            perguntas = ["Por que dev indie brasileiro deve postar nas redes quase todo dia?",
                         "Como conseguir os primeiros 100 jogadores de um jogo gratis?",
                         "O que fazer quando um post nao engaja?", "Como escrever titulo de post que atrai jogadores?",
                         "Que horas o publico gamer brasileiro mais engaja?", "Como transformar quem comenta em seguidor fiel?"]
            aula = cerebro("Responda em ate 350 caracteres, pratico e direto, sem introducao: " + perguntas[dia % len(perguntas)])
            if not aula: return "cerebro calado hoje"
            with open("posts/aulas.md", "a") as f:
                f.write("\n- **%s — %s**\n  %s" % (datetime.datetime.utcnow().strftime("%d/%m"), perguntas[dia % len(perguntas)], aula[:400].replace("\n", " ")))
            return "licao gravada (%d perguntas no ciclo)" % len(perguntas)
        canal("aula do cerebro", _aula)

    if modo != "teste":
        def _descobridor():
            import re as ree
            pat = os.environ.get("GHPAT")
            if not pat:
                return "sem GHPAT no ambiente"
            alvo = "posts/descobertas.md"
            ultimo_erro = ""
            cab = "\n## %s\n" % datetime.datetime.utcnow().strftime("%d/%m/%Y")
            existente = ""
            try:
                req0 = urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo + "?ref=main",
                    headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
                j0 = json.loads(urllib.request.urlopen(req0, timeout=30).read().decode())
                existente = base64.b64decode(j0["content"]).decode()
            except urllib.error.HTTPError as e0:
                if e0.code != 404:
                    return "erro lendo descobertas: " + str(e0.code)
            hoje_bloco = existente.split(cab, 1)[1] if cab in existente else None
            if hoje_bloco is not None:
                return "pesquisa de hoje ja registrada (1 ciclo por dia)"
            livres, muros = [], []
            for nome, url in PESQUISA_REDES:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) rebocl/2"})
                    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore").lower()
                    tem_muro = [m3 for m3 in ["recaptcha", "hcaptcha", "turnstile", "funcaptcha", "arkose", "geetest", "captcha", "anubis", "within.website", "making sure you"] if m3 in html]
                    if tem_muro:
                        muros.append(nome + "(" + tem_muro[0] + ")")
                    else:
                        livres.append(nome)
                except Exception:
                    muros.append(nome + "(inacessivel)")
                time.sleep(0.5)
            linha = "- pesquisei %d redes: LIVRES %s | MURO %s\n" % (len(livres), ", ".join(livres) if livres else "nenhuma", ", ".join(muros) if muros else "nenhuma")
            novo = existente + cab + linha
            body0 = {"message": "descobridor: pesquisa diaria de redes (lei do muro registrada)", "content": base64.b64encode(novo.encode()).decode("ascii"), "branch": "main", "sha": j0["sha"] if existente else None}
            if not body0["sha"]:
                body0.pop("sha")
            for _ in range(2):
                try:
                    urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo, data=json.dumps(body0).encode(), method="PUT", headers={"Authorization": "token " + pat, "Content-Type": "application/json", "User-Agent": "rebocl/2"}), timeout=30)
                    return "pesquisei %d redes → %d livre(s): %s" % (len(PESQUISA_REDES), len(livres), ", ".join(livres) if livres else "nenhuma")
                except Exception:
                    try:
                        req0 = urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo + "?ref=main", headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
                        j0 = json.loads(urllib.request.urlopen(req0, timeout=30).read().decode())
                        body0["sha"] = j0["sha"]
                    except Exception as e10:
                        return "commit-falhou 2x: " + codigo_erro(e10)
            return "commit-falhou: " + codigo_erro(e10)
        canal("descobridor de redes", _descobridor)

    if modo != "teste":
        def _censo():
            paginas = [("redes-ativas", "List_of_social_networking_services"), ("redes-mortas", "List_of_defunct_social_networking_services")]
            medicoes = []
            for rotulo, titulo in paginas:
                try:
                    import re as ree
                    req = urllib.request.Request("https://en.wikipedia.org/w/api.php?action=parse&page=" + titulo + "&prop=wikitext&format=json&formatversion=2", headers=dict(UA))
                    w = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())["parse"]["wikitext"]
                    medicoes.append("%s=%d" % (rotulo, len(ree.findall(r"^\|\s*\[\[", w, ree.M))))
                except Exception:
                    medicoes.append("%s=erro" % rotulo)
                time.sleep(0.5)
            pat = os.environ.get("GHPAT")
            if not pat:
                return "sem GHPAT"
            alvo = "posts/censo-mundial.md"
            ultimo_erro = ""
            cab = "\n## %s\n" % datetime.datetime.utcnow().strftime("%d/%m/%Y")
            existente, sha0 = "", None
            try:
                req0 = urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo + "?ref=main", headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
                j0 = json.loads(urllib.request.urlopen(req0, timeout=30).read().decode())
                existente = base64.b64decode(j0["content"]).decode(); sha0 = j0["sha"]
            except urllib.error.HTTPError as e0:
                if e0.code != 404:
                    return "erro lendo censo: " + str(e0.code)
            if cab in existente:
                return "censo de hoje ja registrado (1 por dia)"
            linha = "- mundo medido: %s (metodo: catalogo Wikipedia, contagem por tabela)\n" % " · ".join(medicoes)
            body0 = {"message": "censo mundial: contagem diaria de redes do mundo", "content": base64.b64encode((existente + cab + linha).encode()).decode("ascii"), "branch": "main"}
            if sha0:
                body0["sha"] = sha0
            for _ in range(2):
                try:
                    urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo, data=json.dumps(body0).encode(), method="PUT", headers={"Authorization": "token " + pat, "Content-Type": "application/json", "User-Agent": "rebocl/2"}), timeout=30)
                    return "mundo medido: " + " · ".join(medicoes)
                except Exception:
                    try:
                        req0 = urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo + "?ref=main", headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
                        body0["sha"] = json.loads(urllib.request.urlopen(req0, timeout=30).read().decode())["sha"]
                    except Exception as e10:
                        return "commit-falhou 2x: " + codigo_erro(e10)
            return "commit-falhou: " + codigo_erro(e10)
        canal("censo mundial", _censo)

    if modo != "teste":
        # Uma postagem autorizada não concede poder sobre contas ou credenciais.
        # Mantemos a fronteira visível no log, sem abrir caixa, seguir link de
        # recuperação, trocar senha, renovar/emitir token ou escrever na Base.
        canal("recuperação de credencial", recuperacao_credencial_pendente)

    def _regua():
        import re as ree
        medicoes, leituras_observadas = [], 0
        if bh and bp:
            try:
                sj2 = json.loads(urllib.request.urlopen(urllib.request.Request("https://bsky.social/xrpc/com.atproto.server.createSession", data=json.dumps({"identifier": bh, "password": bp}).encode(), headers={"Content-Type": "application/json", "User-Agent": "rebocl/2"}), timeout=30).read().decode())
                rq = urllib.request.Request("https://bsky.social/xrpc/app.bsky.actor.getProfile?actor=" + bh, headers={"User-Agent": "rebocl/2", "Authorization": "Bearer " + sj2["accessJwt"]})
                perfil = json.loads(urllib.request.urlopen(rq, timeout=30).read().decode())
                if "followersCount" not in perfil:
                    raise ValueError("perfil sem contador")
                medicoes.append("bsky_seguidores=%d(api)" % int(perfil["followersCount"]))
                leituras_observadas += 1
            except Exception:
                medicoes.append("bsky_seguidores=NAO_OBSERVAVEL")
        else:
            medicoes.append("bsky_seguidores=NAO_CONFIGURADO")
        if igid and igtok:
            try:
                cab = {"User-Agent": "rebocl/2", "Authorization": "Bearer " + igtok}
                rq = urllib.request.Request("https://graph.instagram.com/v21.0/" + igid + "?fields=followers_count,media_count", headers=cab)
                ji = json.loads(urllib.request.urlopen(rq, timeout=30).read().decode())
                if "followers_count" not in ji or "media_count" not in ji:
                    raise ValueError("contadores ausentes")
                medicoes.append("ig_seguidores=%d(api)" % int(ji["followers_count"]))
                medicoes.append("ig_posts=%d(api)" % int(ji["media_count"]))
                leituras_observadas += 1
            except Exception:
                medicoes.append("ig_seguidores=NAO_OBSERVAVEL")
                medicoes.append("ig_posts=NAO_OBSERVAVEL")
        else:
            medicoes.append("ig_seguidores=NAO_CONFIGURADO")
            medicoes.append("ig_posts=NAO_CONFIGURADO")
        # A página pública do itch não fornece uma leitura estável de downloads.
        # Não transformar scraping frágil ou ausência de API em zero/resultado.
        medicoes += [
            "itch_downloads=NAO_OBSERVAVEL",
            "alcance=NAO_OBSERVAVEL",
            "engajamento=NAO_OBSERVAVEL",
            "conversao=NAO_OBSERVAVEL",
            "youtube=NAO_OBSERVAVEL",
        ]
        status_medicao = "OK" if leituras_observadas else "INDISPONIVEL"
        pat = os.environ.get("GHPAT")
        if not pat:
            return status_medicao, " · ".join(medicoes)
        alvo = "posts/progresso-metas.md"
        cab = "\n## %s\n" % datetime.datetime.utcnow().strftime("%d/%m/%Y")
        existente, sha0 = "", None
        try:
            req0 = urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo + "?ref=main", headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
            j0 = json.loads(urllib.request.urlopen(req0, timeout=30).read().decode())
            existente = base64.b64decode(j0["content"]).decode(); sha0 = j0["sha"]
        except urllib.error.HTTPError as e0:
            if e0.code != 404:
                return "FALHOU", "historico da medicao indisponivel"
        if cab in existente:
            return status_medicao, " · ".join(medicoes) + " (fotografia ja registrada hoje)"
        linhas_antigas = [l for l in existente.split("\n") if l.strip().startswith("-")]
        ontem = linhas_antigas[-1] if linhas_antigas else ""
        delta = ""
        try:
            def num(s, chave):
                m5 = ree.search(chave + r"=(\d+)", s)
                return int(m5.group(1)) if m5 else None
            d_bsky = num(medicoes[0], "bsky_seguidores")
            o_bsky = num(ontem, "bsky_seguidores")
            if o_bsky is None:
                o_bsky = num(ontem, "bsky_seg")
            if d_bsky is not None and o_bsky is not None and d_bsky != o_bsky:
                delta = " | VARIACAO_OBSERVADA: bsky_seguidores %+d (sem atribuicao causal)" % (d_bsky - o_bsky)
        except Exception:
            pass
        linha = "- %s%s\n" % (" · ".join(medicoes), delta)
        body0 = {"message": "regua: fotografia diaria de sinais externos", "content": base64.b64encode((existente + cab + linha).encode()).decode("ascii"), "branch": "main"}
        if sha0:
            body0["sha"] = sha0
        for _ in range(2):
            try:
                urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo, data=json.dumps(body0).encode(), method="PUT", headers={"Authorization": "token " + pat, "Content-Type": "application/json", "User-Agent": "rebocl/2"}), timeout=30)
                return status_medicao, " · ".join(medicoes)
            except Exception:
                try:
                    req0 = urllib.request.Request("https://api.github.com/repos/reboclbrank-max/site/contents/" + alvo + "?ref=main", headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
                    body0["sha"] = json.loads(urllib.request.urlopen(req0, timeout=30).read().decode())["sha"]
                except Exception:
                    return "FALHOU", "fotografia da medicao nao foi gravada"
        return "FALHOU", "fotografia da medicao nao foi gravada"
    canal("regua de metas (medicao)", _regua)

    if "descobridor de redes" not in " ".join(n for n, _, _ in resultados):
        resultados.append(("descobridor de redes", "PULADO", "1 pesquisa por dia — volta no proximo ciclo"))
    agora = datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    if not registra_historico_editorial(texto, resultados, agora):
        resultados.append((
            "memoria editorial", "PULADO",
            "nenhum canal editorial confirmou aceitacao tecnica; texto nao entra no historico publicado",
        ))
    linhas = ["\n## " + agora + (" — TESTE" if modo == "teste" else ""), "", "| canal | resultado |", "|---|---|"]
    for n, st, det in resultados:
        icone = {"OK": "✅", "PULADO": "➖", "INDISPONIVEL": "⚪", "FALHOU": "❌"}.get(st, "❓")
        linhas.append("| " + n + " | " + icone + " " + det + " |")
    linhas += ["", "> " + texto.replace("\n", " · ")[:150], ""]
    with open("posts/log.md", "a") as f:
        f.write("\n".join(linhas))
    print("RESUMO:", " | ".join(n + "=" + st for n, st, _ in resultados))

if __name__ == "__main__":
    main()
