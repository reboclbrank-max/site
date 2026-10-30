#!/usr/bin/env node
// Publica o devlog no itch SEM o clique — quando existir uma saída de rede limpa.
//
// O problema, medido três vezes (docs/sondagens/ITCH-403-CLOUDFLARE.json):
//   HTTP puro       -> 403 + desafio nos três sistemas de runner;
//   Chromium headless-> cai em /login?__cf_chl_rt_tk=…;
//   Chromium sob Xvfb, Chrome estável, perfil persistente -> 403 até o fim.
// Não é cookie, não é JavaScript, não é impressão digital: é reputação de IP. Por isso nenhum
// servidor de datacenter entra no painel.
//
// Este script NÃO usa proxy público (isso entregaria a sessão do dono a um terceiro) e não
// inventa identidade. Ele usa a ÚNICA saída limpa que pode existir legalmente: uma que o próprio
// dono controle (VPN, VPS, túnel em casa), informada no segredo ITCH_PROXY.
//
//   node tools/publicar-devlog-itch.js --verificar           (padrão; sem proxy, só leitura pública)
//   ITCH_PROXY=http://host:porta CONFIRMACAO=PUBLICAR \
//     node tools/publicar-devlog-itch.js --publicar
//
// Sem ITCH_PROXY o modo publicar explica o que falta e sai com código 3 — nunca tenta por
// caminho torto. A sessão nunca é impressa; o corpo do devlog vem do arquivo já testado do
// favorito, então o que roda aqui é o MESMO que o dono usa no 1 clique.
const fs = require('fs');
const path = require('path');

const RAIZ = path.join(__dirname, '..');
const FAVORITO = path.join(RAIZ, 'itch', 'devlog-gameplay-bookmarklet.txt');
const TEXTO = path.join(RAIZ, 'posts', 'devlog-itch-gameplay.json');
const DEVLOG_PUBLICO = 'https://rebocl-brank.itch.io/ceifalume/devlog';
const PALAVRA = 'PUBLICAR';

function estadoPublico() {
  return fetch(DEVLOG_PUBLICO, { headers: { 'user-agent': 'rebocl-devlog/1.0' } })
    .then((r) => r.text().then((corpo) => ({ status: r.status, corpo })))
    .then(({ status, corpo }) => {
      const baixo = corpo.toLowerCase();
      const saiu = /gue7af6dyo8|jogando sozinho|gameplay com as instru/.test(baixo);
      console.log(`devlog público: HTTP ${status} · post do vídeo: ${saiu ? 'SIM' : 'não'}`);
      return saiu;
    })
    .catch((e) => {
      console.log('não consegui ler o devlog público:', String(e).slice(0, 120));
      return null;
    });
}

async function publicar() {
  const proxy = (process.env.ITCH_PROXY || '').trim();
  const cookie = (process.env.ITCH_COOKIE || '').trim();
  const confirmacao = (process.env.CONFIRMACAO || '').trim().toUpperCase();

  if (!cookie) {
    console.log('✗ sem ITCH_COOKIE: a sessão do dono é o que autoriza o post');
    return 2;
  }
  if (confirmacao !== PALAVRA) {
    console.log(`✗ falta a palavra ${PALAVRA} (publicar é decisão, não rotina)`);
    return 2;
  }
  if (!proxy) {
    console.log('✗ sem ITCH_PROXY: nenhum IP de datacenter entra no painel do itch.');
    console.log('  medido: HTTP 403 + desafio nos 3 runners, Chromium headless e Chrome estável');
    console.log('  sob Xvfb (96 s). A saída limpa só pode ser uma que o dono controle — VPN, VPS');
    console.log('  ou túnel na própria casa — num segredo chamado ITCH_PROXY.');
    console.log('  Enquanto não existir, o caminho é o favorito de 1 clique');
    console.log('  (itch/devlog-gameplay-bookmarklet.txt) e este script só verifica o estado.');
    return 3;
  }

  const favorito = fs.readFileSync(FAVORITO, 'utf8').trim().replace(/^javascript:/, '');
  const texto = JSON.parse(fs.readFileSync(TEXTO, 'utf8'));
  console.log('proxy do dono: informado · sessão: presente · texto:', texto.titulo.slice(0, 60));

  const { chromium } = require('playwright-core');
  const biscoitos = cookie.split(';').map((p) => p.trim()).filter(Boolean).map((p) => {
    const i = p.indexOf('=');
    return { name: p.slice(0, i), value: p.slice(i + 1), domain: '.itch.io',
             path: '/', httpOnly: true, secure: true };
  });
  const navegador = await chromium.launch({ headless: true, proxy: { server: proxy } });
  const contexto = await navegador.newContext({ locale: 'pt-BR' });
  await contexto.addCookies(biscoitos);
  const pagina = await contexto.newPage();
  await pagina.goto('https://itch.io/dashboard', { waitUntil: 'domcontentloaded', timeout: 90000 });
  if (/just a moment|um momento/i.test(await pagina.title())) {
    console.log('✗ esta saída também é desafiada pela Cloudflare — nada foi publicado');
    await navegador.close();
    return 4;
  }
  await pagina.evaluate(favorito);                 // o MESMO código do favorito do dono
  await pagina.waitForTimeout(20000);              // tempo do formulário e do POST
  await navegador.close();
  const saiu = await estadoPublico();              // prova externa, sem painel
  console.log(saiu ? '✔ devlog no ar (confirmado na página pública)' : '… não confirmei a publicação');
  return saiu ? 0 : 5;
}

(async () => {
  const publicarAgora = process.argv.includes('--publicar');
  if (!publicarAgora) {
    const saiu = await estadoPublico();
    console.log(saiu ? 'nada a fazer: o post do vídeo já está no ar'
                     : 'o post do vídeo não está no ar (caminho: favorito de 1 clique)');
    process.exit(saiu ? 0 : 1);
  }
  process.exit(await publicar());
})();
