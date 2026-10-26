// Monta as versões de instalar (uma linha só, para colar como favorito) a partir
// das fontes únicas em tools/. O favorito é o único caminho que roda com a sessão viva
// do dono, dentro do navegador dele — sem credencial no repositório.
//
//   node tools/montar-bookmarklet.js --verificar   (não escreve; diz se está em dia)
//   node tools/montar-bookmarklet.js --escrever    (regrava as duas linhas)
const fs = require('fs');
const path = require('path');

const raiz = path.join(__dirname, '..');

const PARES = [
  { fonte: 'tools/bookmarklet-itch.js', destino: 'itch/preencher-bookmarklet.txt', rotulo: 'preencher a página' },
  { fonte: 'tools/entrar-itch.js', destino: 'itch/entrar-bookmarklet.txt', rotulo: 'entrar no itch' },
];

function minificar(codigo) {
  return codigo
    .split('\n')
    .map((linha) => linha.trim())
    .filter((linha) => linha && !linha.startsWith('//'))
    .join(' ')
    .replace(/\s+/g, ' ');
}

function linhaDe(par) {
  return 'javascript:' + minificar(fs.readFileSync(path.join(raiz, par.fonte), 'utf8'));
}

const modo = process.argv[2] || '--verificar';
let problema = 0;

PARES.forEach((par) => {
  const linha = linhaDe(par);
  const destino = path.join(raiz, par.destino);
  if (modo === '--escrever') {
    fs.writeFileSync(destino, linha + '\n');
    console.log('✔ ' + par.destino + ' regravado (' + linha.length + ' caracteres) — ' + par.rotulo);
    return;
  }
  if (!fs.existsSync(destino)) {
    console.error('✘ ' + par.destino + ' não existe — rode --escrever');
    problema += 1;
    return;
  }
  if (fs.readFileSync(destino, 'utf8').trim() !== linha) {
    console.error('✘ ' + par.destino + ' fora de sincronia com ' + par.fonte + ' — rode --escrever');
    problema += 1;
    return;
  }
  console.log('✔ ' + par.destino + ' em sincronia (' + linha.length + ' caracteres) — ' + par.rotulo);
});

if (modo !== '--escrever' && problema) { process.exit(1); }
