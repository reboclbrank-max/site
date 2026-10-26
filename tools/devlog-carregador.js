// Carregador curto (para colar no celular): busca o script publicado e executa.
// O itch.io nao tem CSP restritiva (medido: so frame-ancestors), entao a busca
// externa passa; raw.githubusercontent.com responde com CORS liberado.
fetch('https://raw.githubusercontent.com/reboclbrank-max/site/main/itch/postar-devlog.js', { cache: 'no-store' })
  .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
  .then(function (t) { eval(t); })
  .catch(function (e) { alert('Devlog: nao consegui carregar o script (' + e.message + ')'); });
