// ☾ CEIFALUME — entrar no itch.io com um clique
//
// Roda na página de login do itch, NO SEU NAVEGADOR. É o único lugar onde a senha
// funciona: a partir de datacenter o Cloudflare devolve 403 antes de existir formulário
// (medido em 26/10: POST /login -> 403, e fetch na própria origem do itch -> 403).
//
// A senha NUNCA entra no repositório: ela fica no localStorage deste navegador, no
// domínio itch.io, e só sai daqui para o formulário do próprio itch.
// Para apagar o que foi guardado: abra https://itch.io/login#esquecer e clique no favorito.
(function () {
  'use strict';

  var CHAVE_USUARIO = 'ceifalume:itch:usuario';
  var CHAVE_SENHA = 'ceifalume:itch:senha';

  if (!/^\/login\/?$/.test(location.pathname)) {
    alert('Abra https://itch.io/login e clique neste favorito de novo.');
    return;
  }

  if ((location.hash || '').indexOf('esquecer') !== -1) {
    localStorage.removeItem(CHAVE_USUARIO);
    localStorage.removeItem(CHAVE_SENHA);
    alert('Pronto: o usuário e a senha guardados neste navegador foram apagados.');
    return;
  }

  // O formulário certo é o que tem campo de senha. Se não houver, é a tela de desafio.
  var form = null;
  var todos = document.querySelectorAll('form');
  for (var i = 0; i < todos.length; i += 1) {
    if (todos[i].querySelector('[name="password"]')) { form = todos[i]; break; }
  }
  if (!form) {
    alert('Não há formulário de login nesta página — é a tela de verificação de segurança. ' +
      'Recarregue e tente de novo; se insistir, faça o login à mão uma vez.');
    return;
  }

  var campoUsuario = form.querySelector('[name="username"]') || form.querySelector('[name="email"]');
  var campoSenha = form.querySelector('[name="password"]');
  if (!campoUsuario || !campoSenha) {
    alert('O formulário mudou de formato — nada foi preenchido.');
    return;
  }

  var usuario = localStorage.getItem(CHAVE_USUARIO);
  if (!usuario) {
    usuario = prompt('Usuário ou e-mail do itch:');
    if (!usuario) { return; }
    localStorage.setItem(CHAVE_USUARIO, usuario);
  }

  var senha = localStorage.getItem(CHAVE_SENHA);
  if (!senha) {
    senha = prompt('Senha do itch (fica só neste navegador, não vai para o repositório):');
    if (!senha) { return; }
    if (confirm('Guardar a senha neste navegador para entrar com um clique nas próximas vezes?')) {
      localStorage.setItem(CHAVE_SENHA, senha);
    }
  }

  campoUsuario.value = usuario;
  campoSenha.value = senha;
  campoUsuario.dispatchEvent(new Event('input', { bubbles: true }));
  campoSenha.dispatchEvent(new Event('input', { bubbles: true }));
  campoSenha.dispatchEvent(new Event('change', { bubbles: true }));

  var botao = form.querySelector('[type="submit"]') || form.querySelector('button[name="submit"]');
  if (botao) { botao.click(); } else { form.submit(); }
}());
