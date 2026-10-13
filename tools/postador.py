import json, os, sys, datetime, urllib.request, urllib.parse

URL_JOGO = "https://rebocl-brank.itch.io/prancheta"
UA = {"User-Agent": "rebocl-postador/1"}
resultados = []

def http_json(url, data=None, headers=None):
    h = dict(UA); h["Content-Type"] = "application/json"
    if headers: h.update(headers)
    d = json.dumps(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=d, headers=h)
    r = urllib.request.urlopen(req, timeout=30)
    return r.status, r.read().decode()

def canal(nome, fn):
    try:
        resultados.append((nome, "OK", str(fn())[:40]))
    except Exception as e:
        resultados.append((nome, "FALHOU", str(e)[:70]))

def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    fila = json.load(open("posts/fila.json"))
    if modo == "teste":
        post = {"texto": fila.get("teste", "teste do postador"), "url": URL_JOGO}
    else:
        dia = datetime.datetime.utcnow().timetuple().tm_yday
        post = fila["posts"][dia % len(fila["posts"])]
    mensagem = post["texto"] + "\n" + post.get("url", URL_JOGO)

    def _ntfy():
        req = urllib.request.Request("https://ntfy.sh/" + os.environ.get("NTFY_TOPIC", "rebocl-enxame-x7k2"),
            data=("📣 A CASA POSTOU\n\n" + mensagem[:400]).encode(), headers=dict(UA))
        return "push " + str(urllib.request.urlopen(req, timeout=30).status)
    canal("ntfy (push do dono)", _ntfy)

    tt, tc = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if tt and tc:
        canal("telegram", lambda: "enviado " + str(http_json(f"https://api.telegram.org/bot{tt}/sendMessage", {"chat_id": tc, "text": mensagem})[0]))
    else:
        resultados.append(("telegram", "PULADO", "sem chave ainda"))

    bh, bp = os.environ.get("BLUESKY_HANDLE"), os.environ.get("BLUESKY_APPPASS")
    if bh and bp:
        def _bs():
            s, c = http_json("https://bsky.social/xrpc/com.atproto.server.createSession", {"identifier": bh, "password": bp})
            j = json.loads(c)
            agora = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            s2, _ = http_json("https://bsky.social/xrpc/com.atproto.repo.createRecord",
                {"repo": j["did"], "collection": "app.bsky.feed.post", "record": {"text": mensagem[:300], "createdAt": agora}},
                {"Authorization": "Bearer " + j["accessJwt"]})
            return "postado " + str(s2)
        canal("bluesky", _bs)
    else:
        resultados.append(("bluesky", "PULADO", "sem chave ainda"))

    mu, mt = os.environ.get("MASTODON_URL"), os.environ.get("MASTODON_TOKEN")
    if mu and mt:
        def _ma():
            form = urllib.parse.urlencode({"status": mensagem[:500]}).encode()
            req = urllib.request.Request(mu.rstrip("/") + "/api/v1/statuses", data=form,
                headers={"Authorization": "Bearer " + mt, "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "rebocl-postador/1"})
            return "toot " + str(urllib.request.urlopen(req, timeout=30).status)
        canal("mastodon", _ma)
    else:
        resultados.append(("mastodon", "PULADO", "sem chave ainda"))

    nk = os.environ.get("NOSTR_KEY")
    if nk:
        def _no():
            import hashlib, time as _t
            from coincurve import PrivateKey
            import websocket
            sk = PrivateKey(bytes.fromhex(nk))
            px = sk.public_key.format()[1:].hex()
            ev = {"pubkey": px, "created_at": int(_t.time()), "kind": 1,
                  "tags": [["t", "gamedev"], ["t", "indiedev"], ["t", "brazil"]],
                  "content": mensagem[:896]}
            ser = json.dumps([0, ev["pubkey"], ev["created_at"], ev["kind"], ev["tags"], ev["content"]], separators=(",", ":"), ensure_ascii=False).encode()
            ev["id"] = hashlib.sha256(ser).hexdigest()
            ev["sig"] = sk.sign_schnorr(bytes.fromhex(ev["id"]), os.urandom(32)).hex()
            aceitos = []
            for relay in ["wss://relay.damus.io", "wss://nos.lol"]:
                try:
                    ws = websocket.create_connection(relay, timeout=20)
                    ws.send(json.dumps(["EVENT", ev]))
                    fim, resp = _t.time() + 15, ""
                    while _t.time() < fim:
                        resp = ws.recv()
                        if '"OK"' in resp: break
                    ws.close()
                    r = json.loads(resp)
                    if r[0] == "OK" and r[2] is True: aceitos.append(relay)
                except Exception:
                    pass
            return "nota em %d relays (id %s)" % (len(aceitos), ev["id"][:10])
        canal("nostr", _no)
    else:
        resultados.append(("nostr", "PULADO", "sem chave ainda"))

    dw = os.environ.get("DISCORD_WEBHOOK")
    if dw:
        canal("discord", lambda: "enviado " + str(http_json(dw, {"content": mensagem[:2000]})[0]))
    else:
        resultados.append(("discord", "PULADO", "sem chave ainda"))

    agora = datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    linhas = ["\n## " + agora + (" — TESTE" if modo == "teste" else ""), "", "| canal | resultado |", "|---|---|"]
    for n, st, det in resultados:
        icone = "✅" if st == "OK" else ("➖" if st == "PULADO" else "❌")
        linhas.append("| " + n + " | " + icone + " " + det + " |")
    linhas += ["", "> " + post["texto"].replace("\n", " · ")[:150], ""]
    with open("posts/log.md", "a") as f:
        f.write("\n".join(linhas))
    print("POSTADO:", " | ".join(n + "=" + st for n, st, _ in resultados))

main()
