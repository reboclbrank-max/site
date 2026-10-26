// Monta a versão de instalar do bookmarklet do itch (uma linha só) a partir da fonte única.
//   node tools/montar-bookmarklet.js --verificar   (não escreve; diz se está em dia)
//   node tools/montar-bookmarklet.js --escrever    (regrava itch/preencher-bookmarklet.txt)
const fs = require('fs');
const path = require('path');

const raiz = path.join(__dirname, '..');
const fonte = path.join(raiz, 'tools', 'bookmarklet-itch.js');
const destino = path.join(raiz, 'itch', 'preencher-bookmarklet.txt');

function minificar(codigo) {
  return codigo
    .split('\n')
    .map((linha) => linha.trim())
    .filter((linha) => linha && !linha.startsWith('//'))
    .join(' ')
    .replace(/\s+/g, ' ');
}

const codigo = fs.readFileSync(fonte, 'utf8');
const linha = 'javascript:' + minificar(codigo);

const modo = process.argv[2] || '--verificar';
if (modo === '--escrever') {
  fs.writeFileSync(destino, linha + '\n');
  console.log('✔ bookmarklet regravado (' + linha.length + ' caracteres) em itch/preencher-bookmarklet.txt');
  process.exit(0);
}

if (!fs.existsSync(destino)) {
  console.error('✘ itch/preencher-bookmarklet.txt não existe — rode --escrever');
  process.exit(1);
}
const atual = fs.readFileSync(destino, 'utf8').trim();
if (atual !== linha) {
  console.error('✘ itch/preencher-bookmarklet.txt fora de sincronia com tools/bookmarklet-itch.js');
  process.exit(1);
}
console.log('✔ bookmarklet em sincronia com a fonte única (' + linha.length + ' caracteres)');
