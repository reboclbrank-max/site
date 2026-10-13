import json, os, sys, datetime, time, urllib.request, urllib.parse

URL_JOGO = "https://rebocl-brank.itch.io/prancheta"
UA = {"User-Agent": "rebocl-postador/2"}
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

def cerebro(pergunta):
    bruto = ""
    try:
        req = urllib.request.Request("https://text.pollinations.ai/openai",
            data=json.dumps({"model": "openai-fast", "messages": [{"role": "user", "content": pergunta[:1100]}]}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "rebocl/2"})
        j = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
        bruto = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
    except Exception:
        bruto = ""
    if not bruto:
        try:
            q = urllib.parse.quote(pergunta[:590])
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
    if not bruto or bruto.startswith("{") or '"reasoning"' in bruto or '"role"' in bruto or bruto.lower().startswith("we need"):
        return ""
    return bruto

def canal(nome, fn):
    try:
        resultados.append((nome, "OK", str(fn())[:60]))
    except Exception as e:
        resultados.append((nome, "FALHOU", str(e)[:70]))

def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    fila = json.load(open("posts/fila.json"))
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
        gerado = cerebro(pedido)
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

    bh, bp = os.environ.get("BLUESKY_HANDLE"), os.environ.get("BLUESKY_APPPASS")
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

    mu, mt = os.environ.get("MASTODON_URL"), os.environ.get("MASTODON_TOKEN")
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
    if thid and thtok:
        def _th():
            def _post(url, dados):
                return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(), headers=dict(UA)), timeout=30).read().decode())
            c = _post("https://graph.threads.net/v1.0/" + thid + "/threads", {"media_type": "TEXT", "text": mensagem[:480], "access_token": thtok})
            time.sleep(5)
            pub = _post("https://graph.threads.net/v1.0/" + thid + "/threads_publish", {"creation_id": c.get("id"), "access_token": thtok})
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
