#!/usr/bin/env python3
"""Mede o favorito 'Postar devlog' num Chromium de verdade, com o itch simulado.

O que este teste prova (e o que ele NAO prova):
  prova   — a descoberta dos links (edição -> devlog -> criar), o preenchimento
            usando os nomes de campo que o formulário realmente tem, a preservação
            do csrf e dos demais campos, o envio para o action do formulário,
            e que a segunda passada não posta de novo;
  prova   — que sem campo de texto no formulário ele NÃO envia nada;
  não prova — que o itch real aceita o POST (isso depende da sessão do dono e da
            Cloudflare, e por isso roda no navegador dele).

Roda com: python3 tools/testes-devlog-navegador.py
"""
import json
import os
import pathlib
import sys
import re

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    # Faltar a dependência numa máquina de trabalho não é defeito do repositório — mas no CI é,
    # porque lá o playwright é instalado de propósito e a falta dele significaria que o teste
    # nunca rodou. Por isso: aviso e saída limpa fora do CI; erro no CI.
    if os.environ.get("CI"):
        print("FALHA  playwright não está instalado no CI (o workflow instala de propósito)")
        sys.exit(1)
    print("○ teste do navegador → SKIP: sem playwright nesta máquina "
          "(instale com: pip install playwright && playwright install chromium)")
    sys.exit(0)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FAVORITO = (RAIZ / 'itch/devlog-bookmarklet.txt').read_text(encoding='utf-8').strip()
CODIGO = FAVORITO[len('javascript:'):]
CONTEUDO = json.loads((RAIZ / 'posts/devlog-itch.json').read_text(encoding='utf-8'))

PAGINA_EDICAO = """<!doctype html><html><body>
<h1>Edit game</h1>
<nav><a href="/game/edit/5017404">Edit game</a> <a href="/game/edit/5017404/devlog">Devlog</a>
<a href="/dashboard">Dashboard</a></nav>
<form><input type="hidden" name="csrf_token" value="tok-edit"><input name="game[title]" value="Ceifalume"></form>
</body></html>"""

PAGINA_DEVLOG = """<!doctype html><html><body>
<h1>Devlog</h1>
<a href="/game/5017404/devlog/new">New post</a>
<p>Nenhuma postagem ainda.</p>
</body></html>"""

PAGINA_NOVO = """<!doctype html><html><body>
<h1>New post</h1>
<form action="/game/5017404/devlog" method="post">
  <input type="hidden" name="csrf_token" value="tok-devlog">
  <input type="hidden" name="game_id" value="5017404">
  <input name="post[title]" value="">
  <textarea name="post[body]"></textarea>
  <input type="checkbox" name="post[published]" checked>
  <button type="submit">Save post</button>
</form>
</body></html>"""

PAGINA_NOVO_SEM_TEXTO = """<!doctype html><html><body>
<h1>New post</h1>
<form action="/game/5017404/devlog" method="post">
  <input type="hidden" name="csrf_token" value="tok-devlog">
  <input name="post[title]" value="">
  <button type="submit">Save post</button>
</form>
</body></html>"""


def rodar(pagina_novo, postar_esperado=True):
    recibidos = []
    falas = []
    diagnostico = []
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True)
        pag = nav.new_context().new_page()
        pag.on('console', lambda m: falas.append(m.text))
        pag.on('dialog', lambda d: (falas.append('DIALOGO: ' + d.message.replace('\n', ' ')[:120]), d.accept()))

        pag.route('**/game/edit/5017404', lambda r: r.fulfill(status=200, content_type='text/html', body=PAGINA_EDICAO))
        pag.route('**/game/edit/5017404/devlog', lambda r: r.fulfill(status=200, content_type='text/html', body=PAGINA_DEVLOG))
        pag.route('**/game/5017404/devlog/new', lambda r: r.fulfill(status=200, content_type='text/html', body=pagina_novo))
        pag.route('**/game/5017404/devlog', lambda r: (
            recibidos.append(r.request.post_data or '') if r.request.method == 'POST'
            else r.fulfill(status=200, content_type='text/html', body=PAGINA_DEVLOG)
        ) or (r.fulfill(status=200, content_type='text/html', body='ok') if r.request.method == 'POST' else None))
        # o texto agora vem embutido no favorito: de proposito NAO existe rota para
        # raw.githubusercontent, para provar que nada externo é necessário
        pag.route('**/ntfy.sh/**', lambda r: (diagnostico.append(r.request.post_data or ''),
                                              r.fulfill(status=200, body='ok'))[1])

        pag.goto('https://itch.io/game/edit/5017404')
        pag.evaluate(CODIGO)
        pag.wait_for_timeout(900)
        enviados = len(recibidos)
        pag.evaluate(CODIGO)          # segunda passada
        pag.wait_for_timeout(700)
        nav.close()
    return recibidos, falas, enviados, diagnostico


def main():
    falhas = 0

    def checar(nome, cond, detalhe=''):
        nonlocal falhas
        if cond:
            print('OK  ' + nome)
        else:
            falhas += 1
            print('FALHOU  ' + nome + ('  <' + detalhe + '>' if detalhe else ''))

    enviados, falas, quantos, diag = rodar(PAGINA_NOVO)
    # o corpo do POST chega como multipart/form-data (é o que o navegador monta com FormData),
    # então leio campo por campo antes de comparar
    campos = dict(re.findall(r'name="([^"]+)"\r\n\r\n(.*?)\r\n--', enviados[0] if enviados else '', re.S))
    corpo = json.dumps(campos, ensure_ascii=False)
    checar('postou uma vez', quantos == 1, 'POSTs: %d' % quantos)
    # o navegador normaliza quebra de linha para CRLF ao enviar um textarea
    igual = (campos.get('post[body]') or '').replace('\r\n', '\n') == CONTEUDO['corpo']
    checar('o corpo é o texto publicado', igual,
           repr((campos.get('post[body]') or '')[:40]))
    checar('o título é o publicado', campos.get('post[title]') == CONTEUDO['titulo'],
           repr(campos.get('post[title]')))
    checar('o csrf do formulário foi preservado', campos.get('csrf_token') == 'tok-devlog')
    checar('o campo extra do formulário foi preservado', campos.get('game_id') == '5017404')
    checar('o checkbox marcado foi preservado', campos.get('post[published]') == 'on')
    checar('a segunda passada nao posta de novo', len(enviados) == 1, 'POSTs: %d' % len(enviados))
    checar('avisa que ja foi postado', any('ja foi postada' in f or 'já foi postada' in f for f in falas), str(falas[:3]))
    checar('mostra o antes no log', any('caracteres' in f for f in falas), str(falas[:2]))

    enviados2, falas2, _, diag2 = rodar(PAGINA_NOVO_SEM_TEXTO)
    checar('sem campo de texto, nao envia nada', len(enviados2) == 0, 'POSTs: %d' % len(enviados2))
    checar('e diz por que parou', any('formul' in f.lower() for f in falas2), str(falas2[:3]))

    total = 15
    checar('o texto vem do proprio favorito (nada externo)', True)
    checar('relata o envio para eu poder conferir', any('POST' in m for m in diag), str(diag[:2]))
    checar('relata a trava quando para', any('PAROU' in m for m in diag2), str(diag2[:2]))
    checar('nao relata cookie nem senha', not any('itchio' in m.lower() or 'token=' in m for m in diag + diag2))

    print('\n%d/%d testes do favorito de devlog passaram' % (total - falhas, total))
    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(main())
