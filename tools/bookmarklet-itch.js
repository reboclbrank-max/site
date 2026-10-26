// ☾ CEIFALUME — preencher a página do itch.io
//
// Roda DENTRO da página de edição, no navegador do dono, com a sessão viva dele.
// Não existe credencial aqui: nada é copiado, nada é guardado, nada expira.
// Se a sessão cair, o dono entra no itch de novo e clica outra vez — o mecanismo é o mesmo.
//
// Fonte única: este arquivo. A versão de instalar (uma linha só, para colar como
// favorito) é gerada por tools/montar-bookmarklet.js em itch/preencher-bookmarklet.txt.
// Rode: node tools/montar-bookmarklet.js --escrever
(function () {
  'use strict';

  // Campos que este script conhece — os mesmos nomes do formulário real de edição,
  // conferidos em tools/itch-navegador.py (MAPA). Qualquer outro campo é ignorado.
  var CAMPOS = ['title', 'short_text', 'description', 'genre', 'tags', 'min_price', 'classification'];

  // De onde vem o conteúdo publicado: arquivo público do repositório, sem credencial.
  var FONTE = 'https://raw.githubusercontent.com/reboclbrank-max/site/main/posts/pagina-itch.json';

  // Só age em uma página de jogo do dashboard (a edição e as abas dela). Fora disso, para.
  // O endereço exato do editor NÃO é chutado: o itch não documenta e fora da sessão ele dá 404.
  if (!/^\/dashboard\/game\/[0-9]+/.test(location.pathname)) {
    alert('Abra a página de edição do jogo (…/dashboard/game/<id>/edit) e clique no favorito de novo.');
    return;
  }

  // O formulário certo é o que tem csrf_token — o itch regrava todos os campos no envio.
  var form = null;
  var todos = document.querySelectorAll('form');
  for (var i = 0; i < todos.length; i += 1) {
    if (todos[i].querySelector('[name="csrf_token"]')) { form = todos[i]; break; }
  }
  if (!form) {
    alert('Não achei o formulário de edição (sem csrf_token). A página mudou — nada foi feito.');
    return;
  }

  function campo(nome) {
    return form.querySelector('[name="' + nome + '"]');
  }

  function ler() {
    var saida = {};
    for (var j = 0; j < CAMPOS.length; j += 1) {
      var el = campo(CAMPOS[j]);
      if (el) { saida[CAMPOS[j]] = el.value; }
    }
    return saida;
  }

  function corta(texto, limite) {
    texto = String(texto == null ? '' : texto);
    return texto.length > limite ? texto.slice(0, limite) + '…' : texto;
  }

  // Modo leitura: abre o conteúdo atual em uma caixa para copiar. Não grava nada.
  if ((location.hash || '').indexOf('ler') !== -1) {
    prompt('Conteúdo ATUAL da página (copie e mande para mim):', JSON.stringify(ler(), null, 2));
    return;
  }

  fetch(FONTE, { cache: 'no-store' }).then(function (resposta) {
    if (!resposta.ok) { throw new Error('o repositório respondeu ' + resposta.status); }
    return resposta.json();
  }).then(function (dados) {
    var antes = ler();
    var mudancas = [];
    var ignorados = [];

    for (var k = 0; k < CAMPOS.length; k += 1) {
      var nome = CAMPOS[k];
      if (!Object.prototype.hasOwnProperty.call(dados, nome)) { continue; }
      if (dados[nome] === null || dados[nome] === undefined) { continue; }
      var el = campo(nome);
      if (!el) { ignorados.push(nome); continue; }
      var novo = String(dados[nome]);
      if (String(el.value) === novo) { continue; }
      mudancas.push(nome + ':\n  antes: ' + corta(el.value, 90) + '\n  depois: ' + corta(novo, 90));
      if (el.tagName === 'SELECT') {
        el.value = novo;
        if (el.value !== novo) { ignorados.push(nome + ' (opção inexistente no select)'); }
      } else {
        el.value = novo;
      }
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    if (!mudancas.length) {
      alert('Nada a mudar: a página já está igual ao conteúdo publicado.' +
        (ignorados.length ? '\n\nIgnorados: ' + ignorados.join(', ') : ''));
      return;
    }

    var texto = 'Vai gravar na página do itch:\n\n' + mudancas.join('\n\n') +
      (ignorados.length ? '\n\nIgnorados: ' + ignorados.join(', ') : '') +
      '\n\nConfirmar o envio?';
    if (!confirm(texto)) { location.reload(); return; }

    var botao = form.querySelector('[type="submit"]') || form.querySelector('button[name="submit"]');
    if (botao) { botao.click(); } else { form.submit(); }
  }).catch(function (erro) {
    alert('Não consegui ler o conteúdo publicado: ' + (erro && erro.message ? erro.message : erro));
  });
}());
