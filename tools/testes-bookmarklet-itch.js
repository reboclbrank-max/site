// Contratos do modo navegador do itch (offline, sem rede).
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const raiz = path.join(__dirname, '..');
const fonte = fs.readFileSync(path.join(raiz, 'tools', 'bookmarklet-itch.js'), 'utf8');
const derivada = fs.readFileSync(path.join(raiz, 'itch', 'preencher-bookmarklet.txt'), 'utf8').trim();

let passou = 0;
function ok(nome, fn) {
  fn();
  passou += 1;
  console.log('OK ' + nome);
}

ok('age só na página de edição do jogo', () => {
  assert(fonte.includes('/^\\/dashboard\\/game\\/[0-9]+\\/edit\\/?$/'), 'guarda de rota ausente');
});

ok('exige o formulário com csrf_token', () => {
  assert(fonte.includes('[name="csrf_token"]'), 'não confere o csrf do formulário');
});

ok('conhece exatamente os campos do MAPA do itch', () => {
  const esperado = ['title', 'short_text', 'description', 'genre', 'tags', 'min_price', 'classification'];
  const linha = fonte.split('\n').find((l) => l.includes('var CAMPOS ='));
  esperado.forEach((campo) => assert(linha.includes("'" + campo + "'"), 'campo ausente: ' + campo));
  const achados = (linha.match(/'[a-z_]+'/g) || []).map((s) => s.replace(/'/g, ''));
  assert.deepStrictEqual(achados, esperado, 'lista de campos fora do esperado');
});

ok('nunca lê o cookie da sessão', () => {
  assert(!/document\.cookie/.test(fonte), 'o script toca document.cookie');
});

ok('não usa eval nem Function construtor', () => {
  assert(!/\beval\s*\(/.test(fonte), 'usa eval');
  assert(!/new\s+Function/.test(fonte), 'usa new Function');
});

ok('só fala com o repositório (raw.githubusercontent.com)', () => {
  const hosts = fonte.match(/https?:\/\/[a-z0-9.-]+/gi) || [];
  const fora = hosts.filter((h) => !/^https:\/\/raw\.githubusercontent\.com$/.test(h));
  assert.deepStrictEqual(fora, [], 'host não previsto: ' + fora.join(', '));
});

ok('pede confirmação antes de enviar', () => {
  assert(fonte.includes('confirm('), 'não pede confirmação');
  assert(fonte.includes('location.reload()'), 'não cancela o rascunho ao recusar');
});

ok('não submete se nada mudou', () => {
  const trecho = fonte.slice(fonte.indexOf('if (!mudancas.length)'));
  assert(trecho.includes('return;'), 'segue adiante sem mudanças');
});

ok('o modo leitura não grava', () => {
  const trecho = fonte.slice(fonte.indexOf("indexOf('ler')"), fonte.indexOf('fetch(FONTE'));
  assert(trecho.includes('prompt('), 'modo ler não mostra o conteúdo atual');
  assert(!trecho.includes('submit'), 'modo ler submete o formulário');
});

ok('o one-liner é a fonte única minificada', () => {
  const minificado = 'javascript:' + fonte
    .split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('//')).join(' ').replace(/\s+/g, ' ');
  assert.strictEqual(derivada, minificado, 'a versão de instalar divergiu da fonte');
});

ok('cabe em um favorito de navegador', () => {
  assert(derivada.length < 8000, 'grande demais para bookmarklet: ' + derivada.length);
  assert(!derivada.includes('\n'), 'o one-liner tem quebra de linha');
  assert(derivada.startsWith('javascript:'), 'não começa com javascript:');
});

console.log('\n' + passou + '/' + passou + ' testes do modo navegador do itch passaram');
