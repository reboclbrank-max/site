#!/usr/bin/env node
// Sonda o painel do itch com um navegador de verdade e diz o que encontrou, com data e hora.
//
//   node tools/sonda-itch-navegador.js --headless   (Chromium headless shell)
//   node tools/sonda-itch-navegador.js --completo   (Chromium completo, use sob Xvfb)
//
// Por que existe: o painel do itch não tem API para devlog nem para editar página. Se um
// navegador de servidor atravessasse o desafio da Cloudflare, o passo que hoje depende do dono
// poderia ser automatizado. Medido em 30/10/2026: não atravessa (reputação de IP). Este script
// serve para REPETIR a medida, não para publicar nada — ele só faz GET.
//
// Regra da casa: o cookie vem do ambiente e nunca é impresso; nada é enviado ao itch.
const fs = require('fs');
const { chromium } = require('playwright-core');

const modo = process.argv.includes('--completo') ? 'completo' : 'headless';
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
         + 'Chrome/128.0.0.0 Safari/537.36';
const DESAFIO = /just a moment|um momento|checking your browser|attention required|verificando|cf-challenge|challenge-platform/i;
const ALVOS = ['https://itch.io/dashboard', 'https://itch.io/game/edit/5017404'];

function biscoitosDoAmbiente() {
  const cru = (process.env.ITCH_COOKIE || '').trim();
  console.log('cookie:', cru ? `presente (${cru.length} caracteres)` : 'AUSENTE');
  return cru.split(';').map((p) => p.trim()).filter(Boolean).map((p) => {
    const i = p.indexOf('=');
    return { name: p.slice(0, i), value: p.slice(i + 1), domain: '.itch.io',
             path: '/', httpOnly: true, secure: true };
  });
}

(async () => {
  const biscoitos = biscoitosDoAmbiente();
  const navegador = await chromium.launch({
    headless: modo !== 'completo',
    args: modo === 'completo'
      ? ['--disable-blink-features=AutomationControlled', '--no-sandbox']
      : [],
  });
  const contexto = await navegador.newContext({
    userAgent: UA, locale: 'pt-BR', viewport: { width: 1366, height: 768 },
    timezoneId: 'America/Sao_Paulo',
  });
  if (modo === 'completo') {
    await contexto.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });
  }
  if (biscoitos.length) await contexto.addCookies(biscoitos);
  const pagina = await contexto.newPage();

  for (const alvo of ALVOS) {
    let status = 0;
    try {
      const r = await pagina.goto(alvo, { waitUntil: 'domcontentloaded', timeout: 90000 });
      status = r ? r.status() : 0;
    } catch (e) {
      console.log('erro ao abrir', alvo, String(e).slice(0, 140));
    }
    // dá tempo de o desafio resolver sozinho, se for resolver
    for (let i = 0; i < 10; i++) {
      const titulo = await pagina.title();
      const html = await pagina.content();
      const desafio = DESAFIO.test(titulo) || DESAFIO.test(html);
      console.log(`[${modo}] ${alvo} t+${i * 8}s · status ${status} · url ${pagina.url()}` +
                  ` · titulo "${titulo}" · ${html.length} bytes · desafio ${desafio ? 'SIM' : 'NAO'}`);
      if (!desafio) break;
      await pagina.waitForTimeout(8000);
    }
    const html = await pagina.content();
    console.log(`[${modo}] painel? ${/meus jogos|my games/i.test(html)}` +
                ` · login? ${/entrar|log in|sign in/i.test(html)}` +
                ` · ceifalume? ${/ceifalume/i.test(html)}`);
    if (modo === 'completo') {
      try { await pagina.screenshot({ path: '/tmp/itch.png' }); } catch (e) { /* segue */ }
      try { fs.writeFileSync('/tmp/itch.html', html); } catch (e) { /* segue */ }
    }
  }
  await navegador.close();
})();
