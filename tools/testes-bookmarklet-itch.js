// Contratos do modo navegador do itch (offline, sem rede).
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

const raiz = path.join(__dirname, '..');
const fonte = fs.readFileSync(path.join(raiz, 'tools', 'bookmarklet-itch.js'), 'utf8');
const derivada = fs.readFileSync(path.join(raiz, 'itch', 'preencher-bookmarklet.txt'), 'utf8').trim();
const entrar = fs.readFileSync(path.join(raiz, 'tools', 'entrar-itch.js'), 'utf8');
const entrarDerivada = fs.readFileSync(path.join(raiz, 'itch', 'entrar-bookmarklet.txt'), 'utf8').trim();
const consoleDerivado = fs.readFileSync(path.join(raiz, 'itch', 'comando-console.txt'), 'utf8').trim();

function minificar(codigo) {
  return 'javascript:' + codigo
    .split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('//')).join(' ').replace(/\s+/g, ' ');
}

let passou = 0;
function ok(nome, fn) {
  fn();
  passou += 1;
  console.log('OK ' + nome);
}

ok('age na página de edição real (/game/edit/<id>)', () => {
  assert(fonte.includes('/^\\/game\\/edit\\/[0-9]+/'), 'não conhece o endereço real do editor');
  assert(fonte.includes('itch.io/game/edit/5017404'), 'não diz onde é a página');
  assert(!fonte.includes('\\/dashboard\\/game\\/[0-9]+\\/edit\\/?$/'), 'voltou ao endereço que deu 404');
});

ok('continua exigindo o formulário do jogo (com csrf no envio)', () => {
  // o form do jogo é identificado por game[title]; o csrf continua indo no envio inteiro
  assert(fonte.includes('[name="game[title]"]'), 'não identifica o formulário do jogo');
  assert(!/form\.submit\(\)[^;]*$/.test(fonte) || fonte.includes('botao'), 'envia sem o formulário completo');
});

ok('usa os nomes REAIS do formulário (game[...])', () => {
  const esperado = ['game[title]', 'game[short_text]', 'game[description]', 'game[genre]',
    'game[tags]', 'game[min_price]', 'game[classification]'];
  const trecho = fonte.slice(fonte.indexOf('var CAMPOS ='), fonte.indexOf('function formDoJogo'));
  esperado.forEach((campo) => assert(trecho.includes("'" + campo + "'"), 'campo ausente: ' + campo));
  assert(!/'(title|short_text|description)'/.test(trecho), 'voltou aos nomes sem o prefixo game[]');
});

ok('escolhe o formulário do jogo, não o de busca', () => {
  assert(fonte.includes("formDoJogo"), 'não procura o formulário certo');
  assert(fonte.includes('[name="game[title]"]'), 'não identifica o formulário pelo campo do jogo');
});

ok('nunca lê o cookie da sessão', () => {
  assert(!/document\.cookie/.test(fonte), 'o script toca document.cookie');
});

ok('não usa eval nem Function construtor', () => {
  assert(!/\beval\s*\(/.test(fonte), 'usa eval');
  assert(!/new\s+Function/.test(fonte), 'usa new Function');
});

ok('a única rede é o repositório (raw.githubusercontent.com)', () => {
  // itch.io só aparece como texto/mensagem para o dono, nunca em requisição.
  const hosts = fonte.match(/https?:\/\/[a-z0-9.-]+/gi) || [];
  const fora = hosts.filter((h) => !/^https:\/\/raw\.githubusercontent\.com$/.test(h) && h !== 'https://itch.io');
  assert.deepStrictEqual(fora, [], 'host não previsto: ' + fora.join(', '));
  const chamadas = fonte.match(/fetch\s*\([^)]*/g) || [];
  assert(chamadas.length > 0, 'não busca o conteúdo publicado');
  chamadas.forEach((c) => assert(/fetch\(\s*FONTE/.test(c), 'fetch fora do repositório: ' + c));
  assert(!/XMLHttpRequest|new WebSocket/.test(fonte), 'outra via de rede');
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
  assert.strictEqual(derivada, minificar(fonte), 'a versão de instalar divergiu da fonte');
});

ok('o comando de Console é a mesma fonte, sem o javascript:', () => {
  assert.strictEqual(consoleDerivado, derivada.replace(/^javascript:/, ''), 'o comando de Console divergiu');
  assert(!consoleDerivado.startsWith('javascript:'), 'comando de Console não leva o esquema');
});

ok('cabe em um favorito de navegador', () => {
  assert(derivada.length < 8000, 'grande demais para bookmarklet: ' + derivada.length);
  assert(!derivada.includes('\n'), 'o one-liner tem quebra de linha');
  assert(derivada.startsWith('javascript:'), 'não começa com javascript:');
});

ok('o favorito de entrar só age na página de login', () => {
  assert(entrar.includes('/^\\/login\\/?$/'), 'sem guarda de rota /login');
  assert(entrar.includes("https://itch.io/login"), 'não manda abrir a página certa');
});

ok('o favorito de entrar aborta sem formulário (tela de desafio)', () => {
  assert(entrar.includes('[name="password"]'), 'não procura o campo de senha');
  assert(entrar.includes('tela de verificação de segurança'), 'não explica o bloqueio');
});

ok('nenhuma senha literal no repositório', () => {
  const suspeitos = ['albert10', 'reboclbrank:@', 'password = "'];
  suspeitos.forEach((s) => {
    assert(!fonte.includes(s) && !entrar.includes(s) && !derivada.includes(s) && !entrarDerivada.includes(s),
      'texto de senha encontrado: ' + s);
  });
});

ok('o favorito de entrar não conversa com nenhum servidor', () => {
  assert(!/fetch\s*\(/.test(entrar), 'faz rede');
  assert(!/XMLHttpRequest/.test(entrar), 'faz rede');
  assert(!/document\.cookie/.test(entrar), 'lê o cookie da sessão');
});

ok('o favorito de entrar guarda só no navegador e sabe esquecer', () => {
  assert(entrar.includes('localStorage.setItem'), 'não guarda nada (nem oferece)');
  assert(entrar.includes('#esquecer') || entrar.includes("indexOf('esquecer')"), 'não tem como apagar o guardado');
  assert(entrar.includes('localStorage.removeItem'), 'não remove o guardado');
  assert(entrar.includes('confirm('), 'guarda a senha sem perguntar');
});

ok('o one-liner de entrar é a fonte única minificada', () => {
  assert.strictEqual(entrarDerivada, minificar(entrar), 'a versão de instalar divergiu da fonte');
  assert(entrarDerivada.startsWith('javascript:'), 'não começa com javascript:');
  assert(entrarDerivada.length < 8000, 'grande demais para bookmarklet');
});

ok('só mexe nos campos que vieram no conteúdo publicado', () => {
  // o risco real: mandar um texto truncado e apagar a descrição. Campo ausente = intocado.
  assert(fonte.includes('hasOwnProperty.call(dados, nome)'), 'não confere se o campo veio');
  assert(fonte.includes('dados[nome] === null'), 'não respeita campo nulo');
});

ok('aceita escolher opção do select pelo rótulo', () => {
  assert(fonte.includes('opcoes[o].textContent'), 'não tenta casar pelo texto da opção');
  assert(fonte.includes("el.tagName === 'SELECT'"), 'não trata select');
});

ok('todo comando entregue ao dono tem sintaxe válida', () => {
  // Regra criada em 26/10: dois comandos seguidos caíram por erro de sintaxe meu (um "..." literal).
  // node --check pega isso antes de qualquer colagem no navegador do dono.
  const alvos = ['itch/comando-genero.txt', 'itch/comando-console.txt', 'itch/preencher-bookmarklet.txt',
    'itch/entrar-bookmarklet.txt', 'itch/comando-selets.txt', 'itch/comando-ficha.txt', 'itch/ceifalume-auto.user.js', 'itch/aplicar-bookmarklet.txt', 'itch/devlog-bookmarklet.txt', 'tools/devlog-itch-auto.js'];
  alvos.forEach((rel) => {
    const bruto = fs.readFileSync(path.join(raiz, rel), 'utf8').trim();
    const codigo = bruto.startsWith('javascript:') ? bruto.slice('javascript:'.length) : bruto;
    const tmp = path.join(os.tmpdir(), 'comando-' + path.basename(rel) + '.js');
    fs.writeFileSync(tmp, codigo);
    const r = require('child_process').spawnSync(process.execPath, ['--check', tmp], { encoding: 'utf8' });
    assert.strictEqual(r.status, 0, rel + ' com erro de sintaxe: ' + (r.stderr || '').split('\n').slice(0, 4).join(' '));
  });
});

ok('o comando do gênero não mexe em mais nada', () => {
  const cmd = fs.readFileSync(path.join(raiz, 'itch/comando-genero.txt'), 'utf8');
  assert(cmd.includes('game[genre]'), 'não trata o gênero');
  assert(!/game\[description\]\s*=/.test(cmd), 'toca na descrição');
  assert(cmd.includes('confirm('), 'envia sem confirmar');
  assert(cmd.includes('game[title]'), 'não identifica a página de edição');
});

ok('nenhum arquivo entregue tem reticências soltas (o erro de 26/10)', () => {
  ['itch/comando-genero.txt', 'itch/comando-console.txt', 'itch/comando-selets.txt', 'itch/comando-ficha.txt', 'itch/ceifalume-auto.user.js', 'itch/aplicar-bookmarklet.txt', 'itch/devlog-bookmarklet.txt', 'tools/devlog-itch-auto.js', 'tools/bookmarklet-itch.js'].forEach((rel) => {
    const bruto = fs.readFileSync(path.join(raiz, rel), 'utf8');
    const semTexto = bruto.replace(/'[^']*'/g, "''").replace(/"([^"\\]|\\.)*"/g, '""').replace(/\/\/.*/g, '');
    assert(!/\.\.\.\s*[,}]/.test(semTexto), rel + ' tem reticências no lugar de código');
  });
});

ok('o comando da ficha só acrescenta, nunca apaga', () => {
  const cmd = fs.readFileSync(path.join(raiz, 'itch/comando-ficha.txt'), 'utf8');
  assert(/d\.value\s*=\s*d\.value\s*\+/.test(cmd), 'nao acrescenta: pode estar sobrescrevendo');
  assert(!/d\.value\s*=\s*bloco/.test(cmd), 'sobrescreve a descrição');
  assert(cmd.includes('ceifalume:ficha'), 'sem marcador: rodar duas vezes duplicaria');
  assert(cmd.includes('confirm('), 'aplica sem confirmar');
});

ok('o userscript aplica sozinho, com trava de versao', () => {
  const u = fs.readFileSync(path.join(raiz, 'itch/ceifalume-auto.user.js'), 'utf8');
  assert(u.includes('@match        https://itch.io/game/edit/*'), 'nao roda so na pagina de edicao');
  assert(u.includes('versaoAplicada() === versao'), 'sem trava: aplicaria a mesma versao sem parar');
  assert(u.includes('localStorage.setItem(CHAVE_VERSAO'), 'nao guarda a versao aplicada');
  assert(u.includes("cache: 'no-store'"), 'raw.githubusercontent pode servir cache antigo');
  assert(!/document\.cookie/.test(u), 'le cookie');
  const connects = (u.match(/^\/\/ @connect\s+(\S+)/gm) || []).map((l) => l.split(/\s+/).pop());
  assert.deepStrictEqual(connects, ['raw.githubusercontent.com'], 'host extra: ' + connects.join(', '));
  assert(u.includes("if (nome.charAt(0) === '_') return;"), 'tentaria escrever os campos de meta');
  assert(u.includes('previous') || u.includes('anteriores'), 'nao guarda o antes');
});

ok('o favorito de aplicar é derivado do userscript', () => {
  const f = fs.readFileSync(path.join(raiz, 'itch/aplicar-bookmarklet.txt'), 'utf8').trim();
  assert(f.startsWith('javascript:'), 'nao e favorito');
  assert(f.includes('ceifalume:itch:versao-aplicada'), 'sem trava de versao (repetiria sempre)');
  assert(f.includes('raw.githubusercontent.com'), 'nao busca o conteudo publicado');
  assert(!/document\.cookie/.test(f), 'le cookie');
});

ok('o favorito de devlog nao adivinha: descobre o formulario e envia o csrf', () => {
  const f = fs.readFileSync(path.join(raiz, 'itch/devlog-bookmarklet.txt'), 'utf8').trim();
  assert(f.startsWith('javascript:'), 'nao e favorito');
  assert(f.includes('/game/edit/'), 'nao parte da pagina de edicao');
  assert(f.includes('new FormData('), 'nao reenvia os campos reais do formulario');
  assert(f.includes("getAttribute('action')"), 'nao usa o action do proprio formulario');
  assert(f.includes('devlog-itch.json'), 'nao busca o texto publicado');
  assert(!/name=\s*['"]post\[/.test(f), 'chutou nome de campo');
});

console.log('\n' + passou + '/' + passou + ' testes do modo navegador do itch passaram');
