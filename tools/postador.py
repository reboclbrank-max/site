import json, os, sys, datetime, time, urllib.request, urllib.parse
import base64
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

def salva_cofare(cofare, sha, msg):
    pat = os.environ.get("GHPAT")
    if not pat or not cofare:
        return
    body = {"message": msg, "content": base64.b64encode(json.dumps(cofare, ensure_ascii=False, indent=1).encode()).decode("ascii"), "branch": "main", "sha": sha}
    for tent in range(2):
        try:
            urllib.request.urlopen(urllib.request.Request(COFARE_URL.replace("?ref=main", ""), data=json.dumps(body).encode(), method="PUT", headers={"Authorization": "token " + pat, "Content-Type": "application/json", "User-Agent": "rebocl/2"}), timeout=30)
            return
        except Exception:
            try:
                req = urllib.request.Request(COFARE_URL, headers={"Authorization": "token " + pat, "User-Agent": "rebocl/2", "Accept": "application/vnd.github+json"})
                body["sha"] = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())["sha"]
            except Exception:
                return

URL_JOGO = "https://rebocl-brank.itch.io/prancheta"
UA = {"User-Agent": "rebocl-postador/2"}
PESQUISA_REDES = [
    ("lemmy.world", "https://lemmy.world/signup"), ("lemmy.ml", "https://lemmy.ml/signup"),
    ("meta.discourse", "https://meta.discourse.org/signup"), ("flarum", "https://discuss.flarum.org/signup"),
    ("bookwyrm", "https://bookwyrm.social/register"), ("tilvids-peertube", "https://tilvids.com/login"),
    ("writefreely", "https://write.as/register"), ("plume", "https://joinplu.me/"),
    ("diaspora*", "https://diasp.org/signup"), ("friendica", "https://libranet.de/register"),
    ("pixelfed", "https://pixelfed.social/register"), ("mastodon.social", "https://mastodon.social/auth/sign_up"),
]
FATOS = ("FATOS REAIS (use APENAS estes, NADA fora deles): PRANCHETA = manager de futebol 100% ficticio, "
         "voce desenha a bola parada na prancheta e ve a partida simular (ao vivo ou instantaneo), gratis no navegador ou APK, "
         "feito no Brasil com Godot. CEIFALUME = idle de fazenda noturna em desenvolvimento, \"a fazenda nao dorme\", "
         "plantacoes crescem mesmo com o jogo fechado. Link do estudio: https://rebocl-brank.itch.io")
resultados = []

def http_json(url, data=None, headers=None):
    h = dict(UA); h["Content-Type"] = "application/json"
    if headers: h.update(headers)
    d = json.dumps(data).encode() if isinstance(data, dict) else data
    r = urllib.request.urlopen(urllib.request.Request(url, data=d, headers=h), timeout=30)
    return r.status, r.read().decode()

def cerebro(pergunta, tentativas=3):
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
        time.sleep(20)
    return ""

def canal(nome, fn):
    try:
        resultados.append((nome, "OK", str(fn())[:60]))
    except Exception as e:
        resultados.append((nome, "FALHOU", str(e)[:70]))

def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    fila = json.load(open("posts/fila.json"))
    cofare, cofare_sha = le_cofare()
    dia = datetime.datetime.utcnow().timetuple().tm_yday
    if modo == "teste":
        texto = fila.get("teste", "teste da casa")
    else:
        temas = ["apresente o PRANCHETA pra quem curte manager de futebol", "conte expectativa do CEIFALUME (em desenvolvimento)",
                 "convide pra testar o PRANCHETA e contar qual modo prefere (lances ao vivo ou instantaneo)",
                 "explique por que o PRANCHETA ser 100% ficticio e um ponto forte", "dica tatica curta que funciona no PRANCHETA",
                 " converse sobre vida de dev solo no Brasil e cite os jogos", "pinte o clima do CEIFALUME: a fazenda nao dorme"]
        contexto = ""
        try:
            with open("posts/aulas.md") as fa:
                ultimas = [l.strip() for l in fa.readlines() if l.strip()][-3:]
            contexto = " APRENDIZADOS ANTERIORES DA CASA (use o que servir): " + " ".join(l[:120] for l in ultimas)
        except Exception:
            pass
        pedido = ("Voce e a voz da casa REBOCL BRANK, dev solo brasileiro, tom humano e caloroso. Escreva UM post de rede social, "
                  "ate 240 caracteres, portugues, no maximo 2 hashtags. " + FATOS + " TEMA DE HOJE: " + temas[dia % len(temas)] + "." + contexto)
        gerado = cerebro(pedido[:550])
        indice_reserva = (dia * 2 + (0 if datetime.datetime.utcnow().hour < 12 else 1)) % len(fila["posts"])
        texto = gerado[:280] if gerado and len(gerado) > 30 else fila["posts"][indice_reserva]["texto"]
        resultados.append(("cerebro", "OK", ("post novo criado" if gerado and len(gerado) > 30 else "fila de reserva")))
    mensagem = texto + "\n" + URL_JOGO

    def _ntfy():
        req = urllib.request.Request("https://ntfy.sh/" + os.environ.get("NTFY_TOPIC", "rebocl-enxame-x7k2"),
            data=("📣 A CASA POSTOU\n\n" + mensagem[:400]).encode(), headers=dict(UA))
        return "push " + str(urllib.request.urlopen(req, timeout=30).status)
    canal("ntfy (push do dono)", _ntfy)

    tt, tc = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if tt and tc:
        canal("telegram", lambda: "enviado " + str(http_json("https://api.telegram.org/bot" + tt + "/sendMessage", {"chat_id": tc, "text": mensagem})[0]))
    else:
        resultados.append(("telegram", "PULADO", "sem chave ainda"))

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
        resultados.append(("bluesky", "PULADO", "sem chave ainda"))

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
        resultados.append(("mastodon", "PULADO", "sem chave ainda (recuperacao na fila)"))

    thid, thtok = os.environ.get("THREADS_USER_ID"), os.environ.get("THREADS_TOKEN")
    if not (thid and thtok) and cofare.get("threads", {}).get("token"):
        thid, thtok = cofare["threads"].get("user_id"), cofare["threads"]["token"]
    if thid and thtok:
        def _th():
            def _post(url, dados):
                return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(), headers=dict(UA)), timeout=30).read().decode())
            c = _post("https://graph.threads.net/v1.0/" + thid + "/threads", {"media_type": "TEXT", "text": mensagem[:480], "access_token": thtok})
            time.sleep(5)
            pub = _post("https://graph.threads.net/v1.0/" + thid + "/threads_publish", {"creation_id": c.get("id"), "access_token": thtok})
            try:
                rr2 = json.loads(urllib.request.urlopen(urllib.request.Request("https://graph.threads.net/refresh_access_token?grant_type=threads_access_token&access_token=" + thtok, headers=dict(UA)), timeout=30).read().decode())
                novo = rr2.get("access_token")
                if novo and novo != thtok:
                    cofare.setdefault("threads", {})["token"] = novo
                    cofare["threads"]["atualizado"] = datetime.datetime.utcnow().strftime("%d/%m/%Y")
                    salva_cofare(cofare, cofare_sha, "robo renovou o token threads sozinho (nunca mais expira)")
            except Exception:
                pass
            return "publicado id " + str(pub.get("id"))[:12]
        canal("threads", _th)
    else:
        resultados.append(("threads", "PULADO", "sem chave ainda"))

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
            return "nota em %d relays" % len(aceitos)
        canal("nostr", _no)
    else:
        resultados.append(("nostr", "PULADO", "sem chave ainda"))

    dw = os.environ.get("DISCORD_WEBHOOK")
    if dw:
        canal("discord", lambda: "enviado " + str(http_json(dw, {"content": mensagem[:2000]})[0]))
    else:
        resultados.append(("discord", "PULADO", "sem chave ainda"))

    if modo != "teste":
        def _cacador():
            if not (bh and bp): return "sem chave bsky"
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
                if feitas >= 3: break
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
                corpo = {"repo": bh, "collection": "app.bsky.feed.post", "record": {"text": comentario[:300],
                    "createdAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "reply": {"root": {"uri": p["uri"], "cid": p["cid"]}, "parent": {"uri": p["uri"], "cid": p["cid"]}}}}
                pr = urllib.request.Request("https://bsky.social/xrpc/com.atproto.repo.createRecord", data=json.dumps(corpo).encode(),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer " + jwt, "User-Agent": "rebocl/1"})
                urllib.request.urlopen(pr, timeout=30)
                with open("posts/interacoes.md", "a") as fi:
                    fi.write(p["uri"] + "\n")
                feitas += 1
                time.sleep(3)
            return "%d interacoes (q=%s)" % (feitas, q)
        canal("cacador de oportunidades", _cacador)

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
                time.sleep(2)
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
                    except Exception:
                        return "commit falhou 2x"
            return "commit falhou"
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
                time.sleep(2)
            pat = os.environ.get("GHPAT")
            if not pat:
                return "sem GHPAT"
            alvo = "posts/censo-mundial.md"
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
                    except Exception:
                        return "commit falhou 2x"
            return "commit falhou"
        canal("censo mundial", _censo)

    if modo != "teste":
        def _vigia():
            gc = cofare.get("gmail_chat", {}) or {}
            endereco, apppass = gc.get("endereco"), gc.get("senha_de_app")
            if not (endereco and apppass):
                return "cofare sem gmail"
            import imaplib
            import email as ema
            import re as ree
            import http.cookiejar as hcj
            mi = imaplib.IMAP4_SSL("imap.gmail.com")
            mi.login(endereco, apppass)
            mi.select("INBOX")
            typ, dd = mi.search(None, "SINCE " + datetime.datetime.utcnow().strftime("%d-%b-%Y"))
            link = None
            for i in dd[0].split():
                typ, x = mi.fetch(i, "(RFC822)")
                msg = ema.message_from_bytes(x[0][1])
                if "mastodon" not in msg.get("From", "").lower():
                    continue
                corpo = ""
                for parte in (msg.walk() if msg.is_multipart() else [msg]):
                    if parte.get_content_type() in ("text/plain", "text/html"):
                        corpo += parte.get_payload(decode=True).decode("utf-8", "ignore")
                ls = ree.findall(r'https://mastodon\.social/auth/password/edit\?[^\s"<>]+', corpo.replace("=\r\n", "").replace("=\n", ""))
                if ls:
                    link = ls[0]
                    break
            mi.logout()
            if not link:
                return "sem link de recovery hoje (vigia volta no proximo ciclo)"
            nova_senha = os.urandom(12).hex()
            cj2 = hcj.CookieJar()
            opn = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj2))
            opn.addheaders = [("User-Agent", "Mozilla/5.0 rebocl/2")]
            pag = opn.open(link, timeout=30).read().decode("utf-8", "ignore")
            tk = ree.search(r'name="authenticity_token"\s+value="([^"]+)"', pag)
            if not tk:
                return "link sem formulario esperado"
            form = urllib.parse.urlencode({"authenticity_token": tk.group(1), "user[password]": nova_senha, "user[password_confirmation]": nova_senha}).encode()
            opn.open(urllib.request.Request(link, data=form), timeout=30)
            ma = cofare.get("mastodon", {}) or {}
            cid, csec = ma.get("client_id"), ma.get("client_secret")
            if not (cid and csec):
                cofare.setdefault("mastodon", {})["senha_atual"] = nova_senha
                salva_cofare(cofare, cofare_sha, "robo redefiniu a senha do mastodon sozinho (token no proximo passo)")
                return "senha do mastodon redefinida pelo robo (token: proximo ciclo)"
            ot = json.loads(urllib.request.urlopen(urllib.request.Request(ma.get("url", "https://mastodon.social") + "/oauth/token",
                data=urllib.parse.urlencode({"client_id": cid, "client_secret": csec, "grant_type": "password", "scope": "read write", "username": endereco, "password": nova_senha}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "rebocl/2"}), timeout=30).read().decode())
            tok = ot.get("access_token")
            if not tok:
                return "oauth sem token: " + str(ot)[:60]
            cofare.setdefault("mastodon", {})["token"] = tok
            cofare["mastodon"]["senha_atual"] = nova_senha
            cofare["mastodon"]["usuario"] = "ativado-pelo-robo"
            salva_cofare(cofare, cofare_sha, "MASTODON RECUPERADO PELO ROBO: 5o canal liga no proximo ciclo")
            return "mastodon recuperado pelo robo — canal 5 no ar no proximo ciclo"
        canal("vigia da caixa (auto-recovery)", _vigia)

    if "descobridor de redes" not in " ".join(n for n, _, _ in resultados):
        resultados.append(("descobridor de redes", "PULADO", "1 pesquisa por dia — volta no proximo ciclo"))
    agora = datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    with open("posts/posts-publicados.md", "a") as fp:
        fp.write("\n## %s\n%s\n" % (agora, texto.replace("\n", " ⏎ ")[:300]))
    linhas = ["\n## " + agora + (" — TESTE" if modo == "teste" else ""), "", "| canal | resultado |", "|---|---|"]
    for n, st, det in resultados:
        icone = "✅" if st == "OK" else ("➖" if st == "PULADO" else "❌")
        linhas.append("| " + n + " | " + icone + " " + det + " |")
    linhas += ["", "> " + texto.replace("\n", " · ")[:150], ""]
    with open("posts/log.md", "a") as f:
        f.write("\n".join(linhas))
    print("RESUMO:", " | ".join(n + "=" + st for n, st, _ in resultados))

main()
