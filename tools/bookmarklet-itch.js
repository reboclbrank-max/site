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
  // Medido no formulário do dono em 26/10: o itch prefixa tudo com game[].
  var CAMPOS = ['game[title]', 'game[short_text]', 'game[description]', 'game[genre]',
    'game[tags]', 'game[min_price]', 'game[classification]', 'game[release_status]',
    'game[payment_mode]', 'game[type]', 'game[slug]'];
  // O formulário certo é o que tem estes campos (a página também tem o form de busca).
  function formDoJogo() {
    var forms = document.querySelectorAll('form');
    for (var i = 0; i < forms.length; i += 1) {
      if (forms[i].querySelector('[name="game[title]"]')) { return forms[i]; }
    }
    return null;
  }

  // De onde vem o conteúdo publicado: arquivo público do repositório, sem credencial.
  var FONTE = 'https://raw.githubusercontent.com/reboclbrank-max/site/main/posts/pagina-itch.json';

  // Só age na página de edição do jogo. Medido em 26/10 no navegador do dono: o endereço real
  // é https://itch.io/game/edit/<id> (o /dashboard/game/<id>/edit que eu tinha suposto é 404).
  if (!/^\/game\/edit\/[0-9]+/.test(location.pathname) && !/^\/dashboard\/game\/[0-9]+/.test(location.pathname)) {
    alert('Abra a página de edição: https://itch.io/game/edit/5017404');
    return;
  }

  // A página tem vários formulários (o de busca do topo também tem csrf_token): o do jogo é o
  // que tem game[title]. Sem ele, aborta em vez de mexer no formulário errado.
  var form = formDoJogo();
  if (!form) {
    alert('Não achei o formulário do jogo (sem game[title]). A página mudou — nada foi feito.');
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
        if (el.value !== novo) {
          // o itch usa valores curtos nas opções (ex.: "sim"); aceita escolher pelo rótulo
          var opcoes = el.options || [];
          for (var o = 0; o < opcoes.length; o += 1) {
            if (String(opcoes[o].textContent).trim().toLowerCase() === novo.trim().toLowerCase()) {
              el.value = opcoes[o].value;
              break;
            }
          }
        }
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
