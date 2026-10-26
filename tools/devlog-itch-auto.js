// Posta o devlog do itch — rodando no navegador do dono, onde a sessão está viva.
//
// Por que assim (medido em 26/10/2026):
//   - a Cloudflare devolve 403 com desafio para o painel do itch vindo de datacenter,
//     com cookie e sem cookie;
//   - a API não tem devlog: api.itch.io/games/5017404/devlogs -> 404 invalid api endpoint.
//   O formulário só abre no navegador do dono.
//
// Regras deste arquivo:
//   - o texto vem embutido (gerado de posts/devlog-itch.json por tools/montar-bookmarklet.js):
//     nenhuma busca externa, então nada depende de CORS nem de cache;
//   - não adivinha nada: procura os links na página de edição, baixa o formulário real
//     e usa os campos QUE ELE TEM (o nome vem do HTML), trocando só título e corpo;
//   - envia para o action do próprio formulário, preservando csrf e o resto;
//   - sem campo de texto, não envia nada.
(async function () {
  var dados = /*CONTEUDO*/ null;
  var CHAVE = 'ceifalume:devlog:ultima';
  var ID = 'ceifalume:game-id';
  var DIAG = 'https://ntfy.sh/ceifalume-devlog-diag-2026';

  // Relata a estrutura do que aconteceu (endereço, nome de campo, código HTTP).
  // Nunca manda cookie, senha ou qualquer dado da conta. Se o site bloquear, segue.
  function relatar(m) {
    try {
      fetch(DIAG, { method: 'POST', mode: 'cors', cache: 'no-store', body: String(m).slice(0, 900) });
    } catch (e) {}
  }
  function dica(m) { console.log('[ceifalume devlog] ' + m); relatar(m); }
  function parar(m) { console.error('[ceifalume devlog] ' + m); relatar('PAROU: ' + m); alert('Devlog: ' + m); }

  function acharLink(doc, re) {
    var as = Array.prototype.slice.call(doc.querySelectorAll('a[href]'));
    var achado = as.filter(function (a) { return re.test((a.textContent || '').trim()); })[0];
    return achado ? achado.getAttribute('href') : null;
  }

  function campo(form, re) {
    var es = Array.prototype.slice.call(form.querySelectorAll('input[name], textarea[name]'));
    return es.filter(function (e) {
      return re.test(e.name) && (e.type || '').toLowerCase() !== 'hidden';
    })[0] || null;
  }

  async function buscarDoc(url) {
    var r = await fetch(url, { credentials: 'include', cache: 'no-store' });
    if (!r.ok) throw new Error(url + ' -> HTTP ' + r.status);
    var t = await r.text();
    return new DOMParser().parseFromString(t, 'text/html');
  }

  try {
    if (!dados || !dados.corpo) { parar('o texto do devlog não veio embutido — refaça o favorito'); return; }
    if (!/(^|\.)itch\.io$/.test(location.hostname)) {
      parar('a página precisa ser do itch.io — abra itch.io/game/edit/5017404 e clique de novo');
      return;
    }

    var id = (location.pathname.match(/\/game\/edit\/(\d+)/) || [])[1] || localStorage.getItem(ID);
    if (!id) { parar('abra uma vez https://itch.io/game/edit/5017404 e clique de novo'); return; }
    localStorage.setItem(ID, id);

    if (localStorage.getItem(CHAVE) === dados.versao) {
      dica('a versão ' + dados.versao + ' já foi postada neste navegador — nada a fazer');
      return;
    }
    dica('versão ' + dados.versao + ' · título: ' + dados.titulo + ' · corpo: ' + dados.corpo.length + ' caracteres');

    var docEdit = await buscarDoc('/game/edit/' + id);
    var hrefDevlog = acharLink(docEdit, /^devlog$/i) || acharLink(docEdit, /devlog/i);
    relatar('edit=ok aba-devlog=' + String(hrefDevlog));
    if (!hrefDevlog) { parar('não achei a aba Devlog na página de edição'); return; }

    var docDevlog = await buscarDoc(hrefDevlog);
    var candidatos = [];
    var criar = acharLink(docDevlog, /(new|novo|create|nova)\s*(post|postagem|devlog)/i);
    if (criar) candidatos.push(criar);
    candidatos.push('/game/' + id + '/devlog/new', '/game/edit/' + id + '/devlog/new', '/game/edit/' + id + '/devlog');

    var alvo = null, corpo = null, titulo = null, urlForm = null;
    for (var i = 0; i < candidatos.length && !alvo; i++) {
      var doc;
      try { doc = await buscarDoc(new URL(candidatos[i], 'https://itch.io').href); }
      catch (e) { relatar('candidato falhou: ' + candidatos[i] + ' -> ' + e.message); continue; }
      var forms = Array.prototype.slice.call(doc.querySelectorAll('form'));
      for (var j = 0; j < forms.length; j++) {
        var c = campo(forms[j], /body|content|text/i);
        if (!c || (c.tagName !== 'TEXTAREA' && !c.isContentEditable)) continue;
        alvo = forms[j]; corpo = c;
        titulo = campo(forms[j], /title|headline|subject|name/i);
        urlForm = candidatos[i];
        break;
      }
    }
    if (!alvo) { parar('achei a página do devlog, mas não o formulário de texto'); return; }

    dica('formulário: ' + urlForm + ' · corpo=' + corpo.name + (titulo ? ' · título=' + titulo.name : ' · sem campo de título'));

    var fd = new FormData(alvo);
    fd.set(corpo.name, dados.corpo);
    if (titulo) fd.set(titulo.name, dados.titulo);

    var acao = new URL(alvo.getAttribute('action') || location.href, 'https://itch.io');
    var r = await fetch(acao.href, { method: 'POST', body: fd, credentials: 'include', redirect: 'follow' });
    var resposta = await r.text();
    var pareceErro = /can't be blank|is invalid|is required|must be|errors?/i.test(resposta.slice(0, 4000));
    relatar('POST ' + acao.pathname + ' -> HTTP ' + r.status + ' | erro-no-corpo=' + pareceErro + ' | final=' + r.url);

    if (!r.ok) { parar('o itch respondeu HTTP ' + r.status + ' — nada confirmado'); return; }
    if (pareceErro) { parar('o itch respondeu 200, mas o corpo parece erro de validação'); return; }

    localStorage.setItem(CHAVE, dados.versao);
    dica('postado · versão ' + dados.versao);
    alert('Devlog postado no itch ✅\n\n' + dados.titulo);
  } catch (e) {
    parar(String(e && e.message ? e.message : e));
  }
})();
