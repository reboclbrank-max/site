#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira da sondagem da trava do YouTube. Nenhum teste toca a rede nem envia vídeo."""
import importlib.util
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sonda", os.path.join(RAIZ, "tools", "sondar-trava-youtube.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

certos = [0]
falhas = [0]


def ok(nome, cond, det=""):
    if cond:
        certos[0] += 1; print("✔ " + nome)
    else:
        falhas[0] += 1; print("✗ " + nome + (" — " + str(det)[:200] if det else ""))


# a sondagem não pode publicar nada: pede sempre 'unlisted'
m = s.metadados("teste")
ok("a sondagem pede privacidade 'unlisted' (nunca public)", m["status"]["privacyStatus"] == "unlisted")
ok("a sondagem se identifica como sondagem na descrição", "Sondagem" in m["snippet"]["description"])
ok("a sondagem não pede 'public' em lugar nenhum", m["status"]["privacyStatus"] != "public")
ok("categoria declarada (exigida pelo YouTube)", bool(m["snippet"]["categoryId"]))

# veredito
ok("unlisted = sem trava", s.veredito("unlisted")[0] == "sem_trava")
ok("private = com trava", s.veredito("private")[0] == "com_trava")
ok("valor estranho = indefinido", s.veredito("weird")[0] == "indefinido")
ok("veredito sempre traz frase explicada", all(len(s.veredito(v)[1]) > 10 for v in ("unlisted", "private", "weird")))

# upload: o vídeo de sondagem existe e é pequeno
os.path.exists(os.path.join(RAIZ, s.ARQUIVO_PADRAO))
ok("o vídeo usado é o da casa", s.ARQUIVO_PADRAO == "media/reel.mp4")
ok("o vídeo existe e é menor que 10 MB",
   os.path.exists(os.path.join(RAIZ, s.ARQUIVO_PADRAO)) and os.path.getsize(os.path.join(RAIZ, s.ARQUIVO_PADRAO)) < 10_000_000)

# fluxo com dublês
class Post:
    def __init__(self, resp): self.resp = resp; self.chamadas = []
    def __call__(self, url, token, metodo="GET", corpo=None, timeout=45):
        self.chamadas.append((url, metodo, corpo))
        return self.resp, None


post = Post({"upload_url": "https://exemplo.invalido/sessao"})
sessao, erro = s.abrir_sessao("tok", 1000, s.metadados("t"), post=post)
ok("abre sessão de upload com POST", sessao.get("upload_url") and post.chamadas[0][1] == "POST")
ok("a URL da sessão vem do cabeçalho Location (não do corpo)", sessao.get("upload_url") == "https://exemplo.invalido/sessao")
ok("o corpo do POST não leva chave interna (_tamanho)", not any(k.startswith("_") for k in post.chamadas[0][2]))
ok("o corpo do POST leva snippet e status", "snippet" in post.chamadas[0][2] and "status" in post.chamadas[0][2])

class Put:
    def __init__(self, resp): self.resp = resp; self.conteudo = None
    def __call__(self, url, conteudo):
        self.conteudo = conteudo; return self.resp, None


put = Put({"id": "VID123"})
video, erro2 = s.subir("https://exemplo.invalido/sessao", "media/reel.mp4", put=put)
ok("envia o arquivo inteiro, não vazio", video and video["id"] == "VID123" and put.conteudo and len(put.conteudo) > 1000,
   len(put.conteudo or b""))

class Apagar:
    def __init__(self): self.url = None
    def __call__(self, url, token): self.url = url; return True, "apagado (204)"


ap = Apagar()
ok_del, _ = s.apagar("tok", "VID123", deletar=ap)
ok("apaga o vídeo de sondagem no fim", ok_del and ap.url.endswith("id=VID123") and "VID123" in ap.url, ap.url)

# nunca pedir privacidade 'public' no código-fonte
texto = open(os.path.join(RAIZ, "tools", "sondar-trava-youtube.py"), encoding="utf-8").read()
ok("o código da sondagem nunca usa privacyStatus public", '"privacyStatus": "public"' not in texto)

print("\n%d/%d testes da sondagem passaram" % (certos[0], certos[0] + falhas[0]))
sys.exit(1 if falhas[0] else 0)
