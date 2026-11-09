#!/usr/bin/env node
// Cartão final do vídeo — renderizado no navegador porque o ffmpeg do ambiente não tem
// drawtext (medido em 27/10: o build estático só traz libass/subtitles). Usa o mesmo
// Chromium da captura para desenhar o cartão e salva um PNG; o ffmpeg transforma em 3 s.
//
// Uso: node tools/cartao-final.js --saida media/gameplay/cartao.png
const fs = require('fs');
const path = require('path');
const { carregarPlaywright, argumentos } = require('./gravar-gameplay.js');

const RAIZ = path.resolve(__dirname, '..');

function pagina({ titulo, linha1, linha2, cor = '#0a0a0a', ouro = '#f0d97a' }) {
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><style>
    html,body{margin:0;width:1280px;height:720px;background:${cor};
      font-family:"DejaVu Sans",Segoe UI,Roboto,Arial,sans-serif;overflow:hidden}
    .c{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;
      justify-content:center;gap:18px}
    h1{color:${ouro};font-size:86px;letter-spacing:.06em;margin:0}
    p{color:#e8e6e1;font-size:32px;margin:0}
    small{color:#9d9a93;font-size:22px;margin-top:26px;letter-spacing:.04em}
  </style></head><body><div class="c">
    <h1>${titulo}</h1><p>${linha1}</p><p>${linha2}</p>
    <small>gravado do jogo rodando no navegador · feito no Brasil</small>
  </div></body></html>`;
}

async function principal() {
  const args = process.argv.slice(2);
  const mapa = {};
  for (let i = 0; i < args.length; i += 2) mapa[args[i]] = args[i + 1];
  const saida = path.resolve(mapa['--saida'] || path.join(RAIZ, 'media/gameplay/cartao.png'));
  const playwright = carregarPlaywright();
  if (!playwright) {
    console.error('✘ sem navegador para desenhar o cartão');
    return 3;
  }
  const nav = await playwright.chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const ctx = await nav.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    await p.setContent(pagina({
      titulo: mapa['--titulo'] || 'CEIFALUME',
      linha1: mapa['--linha1'] || 'jogue no navegador, de graça',
      linha2: mapa['--linha2'] || 'reboclbrank-max.github.io/site/'
    }), { waitUntil: 'load' });
    fs.mkdirSync(path.dirname(saida), { recursive: true });
    await p.screenshot({ path: saida });
    console.log('cartão: ' + path.relative(RAIZ, saida));
    return 0;
  } finally {
    await nav.close();
  }
}

if (require.main === module) {
  principal().then((c) => process.exit(c)).catch((e) => {
    console.error('✘ ' + (e && e.stack || e));
    process.exit(1);
  });
}
