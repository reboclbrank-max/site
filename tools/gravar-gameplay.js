#!/usr/bin/env node
// 🎮 GRAVADOR DE GAMEPLAY — transforma o jogo que roda no navegador em arquivo de vídeo.
//
// Por que existe: até 27/10/2026 a casa dizia "vídeo" e só tinha texto. O requisito do dono
// é vídeo de gameplay de verdade. Este script abre o build Godot (ceifalume/) num Chromium
// headless COM WebGL por software, joga sozinho por N segundos e grava a tela.
//
// Honestidade do que é medido: o script imprime o que conseguiu (segundos, quadros, bytes) e
// FALHA quando não há imagem — nunca entrega vídeo preto como se fosse gameplay. Quem confere
// se a imagem tem jogo (e não tela preta) é tools/validar-video.py.
//
// Uso:
//   node tools/gravar-gameplay.js --saida media/gameplay/ceifalume-gameplay.mp4 --segundos 24
//   node tools/gravar-gameplay.js --rota /ceifalume/ --largura 1280 --altura 720
//
// Requisitos: playwright-core (npm i playwright-core) + chromium baixado
// (`npx playwright install chromium-headless-shell`) + ffmpeg no PATH (usado para virar MP4).
// Nada de rede externa: o jogo é servido do próprio repositório, em 127.0.0.1.

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');

const RAIZ = path.resolve(__dirname, '..');

function argumentos(argv) {
  const o = {
    rota: '/ceifalume/',
    saida: path.join(RAIZ, 'media', 'gameplay', 'ceifalume-gameplay.mp4'),
    segundos: 24,
    largura: 1280,
    altura: 720,
    quadros: 24,
    manterBruto: false
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const valor = () => argv[++i];
    if (a === '--rota') o.rota = valor();
    else if (a === '--saida') o.saida = path.resolve(valor());
    else if (a === '--segundos') o.segundos = Number(valor());
    else if (a === '--largura') o.largura = Number(valor());
    else if (a === '--altura') o.altura = Number(valor());
    else if (a === '--quadros') o.quadros = Number(valor());
    else if (a === '--manter-bruto') o.manterBruto = true;
  }
  return o;
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.wasm': 'application/wasm',
  '.pck': 'application/octet-stream',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.css': 'text/css; charset=utf-8',
  '.webmanifest': 'application/manifest+json'
};

/**
 * Servidor estático mínimo do próprio repositório.
 * O build Godot usa threads (SharedArrayBuffer), e isso só liga com cross-origin isolation:
 * COOP same-origin + COEP require-corp. O GitHub Pages não manda esses cabeçalhos, então o
 * servidor local existe para que a captura aconteça no modo completo do jogo.
 */
function subirServidor({ porta = 0 } = {}) {
  const servidor = http.createServer((req, res) => {
    const url = decodeURIComponent((req.url || '/').split('?')[0]);
    let alvo = path.join(RAIZ, url);
    if (!alvo.startsWith(RAIZ)) { res.writeHead(403).end('fora do repositório'); return; }
    try {
      if (fs.statSync(alvo).isDirectory()) alvo = path.join(alvo, 'index.html');
    } catch (e) {
      res.writeHead(404).end('não achei'); return;
    }
    let dados;
    try { dados = fs.readFileSync(alvo); } catch (e) { res.writeHead(404).end('não achei'); return; }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(alvo).toLowerCase()] || 'application/octet-stream',
      'Content-Length': dados.length,
      'Cache-Control': 'no-store',
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Resource-Policy': 'same-origin'
    });
    res.end(dados);
  });
  return new Promise((ok, falha) => {
    servidor.on('error', falha);
    servidor.listen(porta, '127.0.0.1', () => ok({ servidor, porta: servidor.address().port }));
  });
}

/**
 * Roteiro de gameplay do Ceifalume — determinístico, em três fases medidas no jogo rodando:
 *
 *   1. AQUECIMENTO (0–14 s): o jogo tem três telas antes da fazenda (título "Jogar" →
 *      splash do estúdio → tutorial "COMO JOGAR"). Em vez de adivinhar o instante de cada
 *      uma, o roteiro toca nos dois botões principais em revezamento; toque em cenário não
 *      faz nada, então a sequência atravessa as três telas sozinha.
 *   2. CICLO DE FAZENDA: semente no topo (y≈120) → campo (y≈420-560) → bico (+1 moeda,
 *      y≈481) → colher → vender. É o ciclo que o próprio tutorial ensina.
 *   3. REFORÇO: a cada volta ele repete o toque nos botões de início, para o caso de o jogo
 *      ter voltado ao título (acontece quando a aba perde foco).
 *
 * Coordenadas lidas do build em 1280×720 (canvas ocupa a tela inteira).
 */
const BOTAO_JOGAR = { x: 640, y: 484 };
const BOTAO_ENTENDI = { x: 640, y: 331 };
const SEMENTES = [{ x: 437, y: 120 }, { x: 531, y: 120 }, { x: 620, y: 120 }];
const CAMPOS = [{ x: 300, y: 420 }, { x: 400, y: 500 }, { x: 500, y: 430 }, { x: 280, y: 560 }, { x: 560, y: 520 }, { x: 350, y: 470 }];
const BICO = { x: 100, y: 481 };
const VENDER = { x: 140, y: 400 };
const MELHORIA = { x: 100, y: 600 };

function roteiro(segundos) {
  const acoes = [];
  const push = (t, alvo, nota) => acoes.push({ t, tipo: 'clique', x: alvo.x, y: alvo.y, nota });

  // fase 1 — atravessa título, splash e tutorial
  const aquecimento = [BOTAO_JOGAR, BOTAO_ENTENDI, BOTAO_JOGAR, BOTAO_ENTENDI, BOTAO_JOGAR, BOTAO_ENTENDI, BOTAO_JOGAR, BOTAO_ENTENDI];
  aquecimento.forEach((alvo, i) => push(1.0 + i * 1.7, alvo, 'avançar tela'));

  // fase 2 — ciclo de fazenda, repetido até o fim do tempo pedido
  let t = 15.0;
  let volta = 0;
  while (t < segundos - 1.2) {
    const semente = SEMENTES[volta % SEMENTES.length];
    const campo = CAMPOS[volta % CAMPOS.length];
    const campo2 = CAMPOS[(volta + 1) % CAMPOS.length];
    push(t, semente, 'semente'); t += 0.7;
    push(t, campo, 'plantar'); t += 0.8;
    push(t, semente, 'semente'); t += 0.5;
    push(t, campo2, 'plantar'); t += 0.8;
    push(t, BICO, 'bico (+1 moeda)'); t += 0.9;
    push(t, BICO, 'bico (+1 moeda)'); t += 0.9;
    push(t, campo, 'colher'); t += 0.7;
    push(t, campo2, 'colher'); t += 0.7;
    push(t, VENDER, 'vender colheita'); t += 0.8;
    // a cada duas voltas, uma melhoria (comprar campo / ampliar celeiro)
    if (volta % 2 === 1) { push(t, MELHORIA, 'melhoria'); t += 0.8; }
    // a cada quatro voltas, um toque de reforço nas telas iniciais
    if (volta % 4 === 3) { push(t, BOTAO_JOGAR, 'reforço'); t += 0.6; push(t, BOTAO_ENTENDI, 'reforço'); t += 0.6; }
    volta += 1;
  }
  return acoes.filter((a) => a.t < segundos - 0.3);
}

function ffmpeg() {
  const doAmbiente = process.env.FFMPEG_PATH || '';
  if (doAmbiente && fs.existsSync(doAmbiente)) return doAmbiente;
  const r = spawnSync('ffmpeg', ['-version'], { encoding: 'utf8' });
  if (r.status === 0) return 'ffmpeg';
  // Reserva: o binário estático que o pip instala (imageio-ffmpeg) — usado quando o runner
  // não tem ffmpeg de sistema.
  const py = spawnSync('python3', ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'], { encoding: 'utf8' });
  const caminho = (py.stdout || '').trim();
  if (py.status === 0 && caminho && fs.existsSync(caminho)) return caminho;
  return null;
}

function duracaoDoVideo(binario, arquivo) {
  const r = spawnSync(binario, ['-hide_banner', '-i', arquivo], { encoding: 'utf8' });
  const texto = (r.stderr || '') + (r.stdout || '');
  const m = texto.match(/Duration:\s*(\d+):(\d+):(\d+\.\d+)/);
  if (!m) return null;
  return Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]);
}

async function principal() {
  const op = argumentos(process.argv.slice(2));
  const playwright = (() => {
    for (const caminho of ['playwright-core', 'playwright']) {
      try { return require(caminho); } catch (e) { /* tenta o próximo */ }
    }
    // Reserva: instalação fora do projeto (usada no meu teste local).
    const alternativa = process.env.PLAYWRIGHT_CORE || '/tmp/pw/node_modules/playwright-core';
    try { return require(alternativa); } catch (e) { return null; }
  })();
  if (!playwright) {
    console.error('✘ falta playwright-core: npm i playwright-core && npx playwright install chromium-headless-shell');
    return 3;
  }

  const { servidor, porta } = await subirServidor();
  const base = 'http://127.0.0.1:' + porta + op.rota;
  const pastaTemp = fs.mkdtempSync(path.join(os.tmpdir(), 'gameplay-'));
  console.log('servindo o repositório em ' + base);

  const navegador = await playwright.chromium.launch({
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--enable-unsafe-swiftshader',
      '--use-gl=angle',
      '--use-angle=swiftshader',
      '--ignore-gpu-blocklist',
      '--enable-webgl',
      '--mute-audio'
    ]
  });

  let codigo = 0;
  try {
    const contexto = await navegador.newContext({
      viewport: { width: op.largura, height: op.altura },
      deviceScaleFactor: 1,
      hasTouch: true,
      recordVideo: { dir: pastaTemp, size: { width: op.largura, height: op.altura } }
    });
    const pagina = await contexto.newPage();
    const erros = [];
    pagina.on('pageerror', (e) => erros.push(String(e && e.message || e).slice(0, 160)));
    pagina.on('console', (m) => { if (m.type() === 'error') erros.push('console: ' + m.text().slice(0, 160)); });

    const t0 = Date.now();
    await pagina.goto(base, { waitUntil: 'load', timeout: 60000 });

    // Espera o canvas do Godot existir e ter tamanho — sinal mínimo de que o jogo subiu.
    const canvas = await pagina.waitForFunction(() => {
      const c = document.querySelector('canvas');
      return c && c.width > 0 && c.height > 0 ? { w: c.width, h: c.height } : null;
    }, null, { timeout: 90000 }).then((h) => h.jsonValue()).catch(() => null);
    const carregouEm = ((Date.now() - t0) / 1000).toFixed(1);
    if (!canvas) {
      console.error('✘ o canvas do jogo não apareceu em 90 s — sem imagem, sem vídeo');
      erros.slice(0, 5).forEach((e) => console.error('   ' + e));
      await contexto.close();
      return 4;
    }
    console.log('canvas ' + canvas.w + 'x' + canvas.h + ' em ' + carregouEm + ' s');
    if (erros.length) console.log('avisos do navegador até aqui: ' + erros.slice(0, 3).join(' | '));

    // Deixa o jogo assentar (carregamento do .pck, primeira cena).
    await pagina.waitForTimeout(2500);

    const inicioAcoes = Date.now();
    for (const acao of roteiro(op.segundos)) {
      const esperar = acao.t * 1000 - (Date.now() - inicioAcoes);
      if (esperar > 0) await pagina.waitForTimeout(esperar);
      try {
        if (acao.tipo === 'clique') {
          // Toque, não mouse: medido em 27/10 — o build Godot responde ao evento de toque
          // de forma consistente no headless; o clique de mouse dependia de hover prévio.
          await pagina.touchscreen.tap(Math.round(acao.x), Math.round(acao.y));
        } else {
          await pagina.keyboard.press(acao.tecla);
        }
      } catch (e) { /* uma tecla perdida não invalida a captura */ }
    }
    const restante = op.segundos * 1000 - (Date.now() - inicioAcoes);
    if (restante > 0) await pagina.waitForTimeout(restante);

    // Um quadro de prova, salvo ao lado do vídeo: serve para conferir a olho o que foi gravado.
    const quadro = op.saida.replace(/\.mp4$/i, '-quadro.png');
    fs.mkdirSync(path.dirname(quadro), { recursive: true });
    await pagina.screenshot({ path: quadro });
    console.log('quadro de prova: ' + path.relative(RAIZ, quadro));

    // ⚠️ A ordem importa: o Playwright só entrega o arquivo depois que a página fecha, e
    // apaga o temporário quando o navegador fecha. Salvar aqui, fechar o navegador depois.
    const video = pagina.video();
    await contexto.close();
    if (!video) { console.error('✘ o navegador não devolveu vídeo'); return 5; }
    const bruto = path.join(pastaTemp, 'bruto.webm');
    await video.saveAs(bruto);
    await navegador.close();
    const bytes = fs.statSync(bruto).size;

    const binario = ffmpeg();
    if (!binario) { console.error('✘ falta ffmpeg para virar MP4'); return 6; }
    fs.mkdirSync(path.dirname(op.saida), { recursive: true });
    const conversao = spawnSync(binario, [
      '-y', '-i', bruto,
      '-vf', 'fps=' + op.quadros + ',scale=' + op.largura + ':' + op.altura + ':flags=lanczos',
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
      '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
      '-an', op.saida
    ], { encoding: 'utf8' });
    if (conversao.status !== 0) {
      console.error('✘ ffmpeg falhou: ' + String(conversao.stderr || '').slice(-400));
      return 7;
    }
    const duracao = duracaoDoVideo(binario, op.saida);
    const tamanho = fs.statSync(op.saida).size;
    if (!op.manterBruto) fs.rmSync(bruto, { force: true });
    console.log('vídeo: ' + path.relative(RAIZ, op.saida) + ' · ' + (tamanho / 1048576).toFixed(1) + ' MB' +
      ' · ' + (duracao ? duracao.toFixed(1) + ' s' : 'duração desconhecida') +
      ' · ' + op.largura + 'x' + op.altura + ' @ ' + op.quadros + ' fps');
    if (erros.length) console.log('avisos do navegador: ' + erros.slice(0, 3).join(' | '));

    // Barreira mínima aqui; a prova de que TEM JOGO na imagem é do validar-video.py.
    if (!duracao || duracao < Math.min(8, op.segundos * 0.5)) {
      console.error('✘ vídeo curto demais para valer (' + duracao + ' s)');
      codigo = 8;
    } else if (tamanho < 100_000) {
      console.error('✘ vídeo pequeno demais (' + tamanho + ' B) — provavelmente tela parada');
      codigo = 9;
    }
  } finally {
    try { await navegador.close(); } catch (e) { /* já fechado */ }
    servidor.close();
  }
  return codigo;
}

if (require.main === module) {
  principal().then((c) => process.exit(c)).catch((e) => {
    console.error('✘ ' + (e && e.stack || e));
    process.exit(1);
  });
}

module.exports = { subirServidor, roteiro, argumentos, duracaoDoVideo };
