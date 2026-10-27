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
    url: '',
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
    if (a === '--url') o.url = valor();
    else if (a === '--rota') o.rota = valor();
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
// ---------------------------------------------------------------------------------------
// LEITURA DE ESTADO — o gravador deixou de ser cego em 27/10/2026.
//
// O build é Godot: não há DOM com o estado do jogo (o "save" vai para IndexedDB e só é
// sincronizado de tempo em tempo). O que existe sempre é a IMAGEM. Então o estado é lido
// do canvas, com regiões medidas no próprio jogo:
//   • botão amarelo "Entendi, jogar!"  → tutorial aberto
//   • caixa clara "Jogar"              → tela de título
//   • fração de verde em cada célula   → semente crescendo / pronta para colher / vazia
// Cada decisão daqui para baixo depende de uma dessas medidas — nenhuma é "tocar no escuro".
// ---------------------------------------------------------------------------------------

const TELA = { largura: 1280, altura: 720 };

// regiões (x, y, largura, altura) em coordenadas de 1280x720
const REGIAO_TUTORIAL = { x: 520, y: 298, w: 240, h: 56 };   // botão amarelo do tutorial
const REGIAO_TITULO = { x: 500, y: 445, w: 290, h: 66 };      // caixa "Jogar" da capa
const REGIAO_DIALOGO = { x: 330, y: 180, w: 620, h: 220 };    // caixa escura do tutorial
const CELULAS = [
  { id: 'A', x: 420, y: 205, w: 180, h: 130 },
  { id: 'B', x: 680, y: 205, w: 180, h: 130 },
  { id: 'C', x: 940, y: 205, w: 180, h: 130 },
  { id: 'D', x: 420, y: 435, w: 180, h: 130 },
  { id: 'E', x: 680, y: 435, w: 180, h: 130 }
];
const ALVO = {
  tutorial: { x: 640, y: 331 },
  titulo: { x: 640, y: 484 },
  semente: { x: 437, y: 120 },
  bico: { x: 100, y: 481 },
  vender: { x: 140, y: 400 },
  melhoria: { x: 100, y: 600 }
};
// limites de decisão — calibrados nos quadros de 27/10 (ver docs/VIDEO-GAMEPLAY.md)
const LIMIAR = {
  botao: 0.05,        // fração de amarelo/claro que já conta como botão visível
  verdeVazio: 0.02,   // abaixo disso a célula está vazia
  verdePronto: 0.085, // acima disso a planta já pode ser colhida
  esperaCrescimento: 14000 // ms em que uma célula semeada ainda pode parecer vazia
};

/** Conta, dentro de um recorte do canvas, quantos pixels são amarelos e quantos são claros. */
const MEDIDOR = (regioes) => {
  const cv = document.querySelector('canvas');
  const c2 = document.createElement('canvas');
  c2.width = cv.width;
  c2.height = cv.height;
  const g = c2.getContext('2d', { willReadFrequently: true });
  g.drawImage(cv, 0, 0);
  const sx = cv.width / 1280;
  const sy = cv.height / 720;
  const conta = (r, teste) => {
    const d = g.getImageData(Math.round(r.x * sx), Math.round(r.y * sy),
      Math.max(1, Math.round(r.w * sx)), Math.max(1, Math.round(r.h * sy))).data;
    let n = 0;
    let tot = 0;
    for (let i = 0; i < d.length; i += 4) {
      tot += 1;
      if (teste(d[i], d[i + 1], d[i + 2])) n += 1;
    }
    return n / tot;
  };
  const amarelo = (r, c, b) => c > 150 && c > b + 60 && b < 140;   // dourado do jogo
  const claro = (r, c, b) => r > 200 && c > 200 && b > 200;
  const verde = (r, c, b) => c > 90 && c > r + 30 && c > b + 30;
  const escuro = (r, c, b) => r < 40 && c < 45 && b < 60;
  // ⚠️ O botão do tutorial é amarelo, mas o brilho de colheita TAMBÉM é amarelo e cai nessa
  // mesma faixa da tela. Por isso o tutorial só conta quando a caixa escura dele está atrás
  // (medido: 0,75 da região é escura com o tutorial aberto; 0,00 sem ele).
  const dialogo = conta(regioes.dialogo, escuro);
  return {
    dialogo,
    tutorial: dialogo > 0.35 ? conta(regioes.tutorial, amarelo) : 0,
    titulo: conta(regioes.titulo, claro),
    celulas: regioes.celulas.map((c) => ({
      id: c.id,
      verde: conta(c, verde),
      centro: { x: Math.round(c.x + c.w / 2), y: Math.round(c.y + c.h / 2) }
    }))
  };
};

/**
 * Agente: decide a cada passo olhando o estado. Devolve { acao, motivo } — e o registro do que
 * foi decidido volta no relatório, para ninguém precisar acreditar na palavra do gravador.
 */
function decidir(estado, memoria = {}) {
  if (estado.tutorial > LIMIAR.botao) {
    return { tipo: 'toque', alvo: ALVO.tutorial, motivo: 'tutorial aberto (' + estado.tutorial.toFixed(2) + ')' };
  }
  if (estado.titulo > LIMIAR.botao) {
    return { tipo: 'toque', alvo: ALVO.titulo, motivo: 'tela de título (' + estado.titulo.toFixed(2) + ')' };
  }
  const agora = memoria.agora || 0;
  const ocupadas = memoria.ocupadas || {};
  // madura: a visão decide (o broto é verde e cresce na tela)
  const prontas = estado.celulas.filter((c) => c.verde >= LIMIAR.verdePronto);
  if (prontas.length) {
    const c = prontas[0];
    return { tipo: 'colher', alvo: c.centro, celula: c.id,
             motivo: 'célula ' + c.id + ' pronta (verde ' + c.verde.toFixed(3) + ')' };
  }
  // livre: a visão diz que não há verde E a memória diz que não semeei ali há pouco.
  // Sem a memória o robô replanta a mesma célula para sempre: a semente leva ~12 s para
  // aparecer como broto, e nesse tempo a célula parece vazia.
  const livres = estado.celulas.filter((c) =>
    c.verde <= LIMIAR.verdeVazio && (agora - (ocupadas[c.id] || -1e9)) > LIMIAR.esperaCrescimento);
  if (livres.length) {
    return { tipo: 'plantar', celula: livres[0], motivo: 'célula ' + livres[0].id + ' livre' };
  }
  const crescendo = estado.celulas.filter((c) => c.verde > LIMIAR.verdeVazio && c.verde < LIMIAR.verdePronto);
  if (crescendo.length || estado.celulas.every((c) => (agora - (ocupadas[c.id] || -1e9)) <= LIMIAR.esperaCrescimento)) {
    return { tipo: 'toque', alvo: ALVO.bico, motivo: 'tudo semeado ou crescendo: moeda no bico' };
  }
  return { tipo: 'toque', alvo: ALVO.vender, motivo: 'sem célula livre: vender' };
}

/** Toque que não depende do tipo de evento: clique de mouse E toque de dedo. */
async function acionar(pagina, alvo) {
  await pagina.mouse.click(alvo.x, alvo.y);
  await pagina.waitForTimeout(120);
  await pagina.touchscreen.tap(alvo.x, alvo.y);
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

/**
 * Acha a biblioteca do navegador. Devolve null quando não há nenhuma — é essa ausência que
 * vira código de erro 3, nunca um vídeo vazio. A lista é parâmetro para que a barreira possa
 * provar o caminho "sem navegador" sem depender do que está instalado na máquina.
 */
function carregarPlaywright(tentativas = [], incluirPadroes = true) {
  const padroes = incluirPadroes
    ? ['playwright-core', 'playwright', process.env.PLAYWRIGHT_CORE || '']
    : [];
  const caminhos = tentativas.concat(padroes).filter(Boolean);
  for (const caminho of caminhos) {
    try { return require(caminho); } catch (e) { /* tenta o próximo */ }
  }
  return null;
}

async function principal() {
  const op = argumentos(process.argv.slice(2));
  const playwright = carregarPlaywright();
  if (!playwright) {
    console.error('✘ falta playwright-core: npm i playwright-core && npx playwright install chromium-headless-shell');
    return 3;
  }

  // Com --url o build vem de fora (ex.: o PRANCHETA só existe publicado no itch.io);
  // sem --url o jogo é servido do próprio repositório, com COOP+COEP para as threads.
  const local = await subirServidor().catch(() => null);
  const servidor = local ? local.servidor : { close() {} };
  const base = op.url || ('http://127.0.0.1:' + local.porta + op.rota);
  const pastaTemp = fs.mkdtempSync(path.join(os.tmpdir(), 'gameplay-'));
  console.log((op.url ? 'abrindo build externo: ' : 'servindo o repositório em ') + base);

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

    // ------- MALHA FECHADA: olhar → decidir → agir, até o tempo acabar -------
    const decisoes = [];
    const ocupadas = {};
    const inicioAcoes = Date.now();
    const fimAcoes = inicioAcoes + op.segundos * 1000;
    let colhidas = 0;
    let plantadas = 0;
    let toquesTela = 0;
    while (Date.now() < fimAcoes) {
      let estado;
      try {
        estado = await pagina.evaluate(MEDIDOR, {
          tutorial: REGIAO_TUTORIAL, titulo: REGIAO_TITULO,
          dialogo: REGIAO_DIALOGO, celulas: CELULAS
        });
      } catch (e) {
        await pagina.waitForTimeout(400);
        continue;
      }
      const d = decidir(estado, { agora: Date.now() - inicioAcoes, ocupadas });
      let acao;
      if (d.tipo === 'plantar') {
        await pagina.mouse.click(ALVO.semente.x, ALVO.semente.y);
        await pagina.waitForTimeout(160);
        await pagina.touchscreen.tap(ALVO.semente.x, ALVO.semente.y);
        await pagina.waitForTimeout(260);
        await acionar(pagina, d.celula.centro);
        ocupadas[d.celula.id] = Date.now() - inicioAcoes;
        plantadas += 1;
        acao = 'semente + célula ' + d.celula.id;
        await pagina.waitForTimeout(420);
      } else if (d.tipo === 'colher') {
        await acionar(pagina, d.alvo);
        delete ocupadas[d.celula];
        colhidas += 1;
        acao = 'colher ' + d.celula;
        await pagina.waitForTimeout(400);
        await acionar(pagina, ALVO.vender);
        acao += ' + vender';
        await pagina.waitForTimeout(300);
      } else if (d.tipo === 'toque') {
        await acionar(pagina, d.alvo);
        acao = 'toque em ' + d.alvo.x + ',' + d.alvo.y;
        if (d.alvo === ALVO.tutorial || d.alvo === ALVO.titulo) toquesTela += 1;
        await pagina.waitForTimeout(320);
      }
      decisoes.push({
        t: +((Date.now() - inicioAcoes) / 1000).toFixed(1),
        tutorial: +estado.tutorial.toFixed(3),
        titulo: +estado.titulo.toFixed(3),
        verdes: estado.celulas.map((c) => +c.verde.toFixed(3)),
        motivo: d.motivo, acao
      });
    }
    const verdeFinal = (await pagina.evaluate(MEDIDOR, {
      tutorial: REGIAO_TUTORIAL, titulo: REGIAO_TITULO,
      dialogo: REGIAO_DIALOGO, celulas: CELULAS
    })).celulas.map((c) => c.id + ':' + c.verde.toFixed(3)).join(' ');

    // Um quadro de prova, salvo ao lado do vídeo: serve para conferir a olho o que foi gravado.
    const quadro = op.saida.replace(/\.mp4$/i, '-quadro.png');
    fs.mkdirSync(path.dirname(quadro), { recursive: true });
    await pagina.screenshot({ path: quadro });
    console.log('decisões: ' + decisoes.length + ' · plantadas: ' + plantadas +
      ' · colhidas: ' + colhidas + ' · telas de abertura: ' + toquesTela);
    console.log('últimas decisões: ' + JSON.stringify(decisoes.slice(-4)));
    console.log('verde final por célula: ' + verdeFinal);
    // o mesmo relatório vai num JSON, para o validador e o kit usarem sem depender do log
    try {
      fs.writeFileSync(op.saida.replace(/\.mp4$/i, '-decisoes.json'), JSON.stringify({
        decisoes, plantadas, colhidas, telas: toquesTela, verde_final: verdeFinal,
        limite: LIMIAR, celulas: CELULAS.map((c) => c.id)
      }, null, 1));
    } catch (e) { /* relatório é extra, não pode derrubar a captura */ }

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

module.exports = {
  subirServidor, argumentos, duracaoDoVideo, carregarPlaywright,
  decidir, LIMIAR, CELULAS, REGIAO_TUTORIAL, REGIAO_TITULO, REGIAO_DIALOGO, ALVO
};
