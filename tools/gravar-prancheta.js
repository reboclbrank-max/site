#!/usr/bin/env node
// ⚽ GRAVADOR DO PRANCHETA — o segundo jogo da casa, que até 27/10/2026 não tinha roteiro.
//
// O que faltava: o build web do PRANCHETA existe publicado no itch.io (Godot html5 dentro de um
// iframe do itch), mas o repositório só tem a página de marketing. Sem o build aberto não havia
// como medir região nenhuma — e sem medir, "gravar o PRANCHETA" seria chute.
//
// O que este script faz, em ordem, com o fluxo MEDIDO no jogo rodando em 27/10/2026 (1280×720):
//   1. descobre o endereço do build atual na página do itch (o id do upload muda a cada versão);
//   2. abre o build num Chromium com WebGL por software e grava a tela;
//   3. atravessa: splash → menu → Nova carreira → Escolha do clube (aceitar convite)
//      → casa do clube → Passo 1 (sugestão do staff) → microciclo → Passo 2 (prancheta)
//      → Jogar com plano recomendado → partida;
//   4. confere cada passo POR IMAGEM (a tela mudou?) e registra o que aconteceu num JSON.
//
// Honestidade: se um passo não mudar a tela, o script tenta de novo uma vez e, se continuar igual,
// FALHA — não entrega vídeo parado numa tela só fingindo que jogou.
//
// Uso:
//   node tools/gravar-prancheta.js --saida media/gameplay/prancheta-cru.mp4 --segundos 75
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const RAIZ = path.resolve(__dirname, '..');
const PAGINA_ITCH = 'https://rebocl-brank.itch.io/prancheta';
// Endereço medido em 27/10/2026 — usado só se a descoberta falhar.
const BUILD_RESERVA = 'https://html-classic.itch.zone/html/19604665/index.html?v=1791321920';

// Coordenadas lidas do jogo rodando em 1280×720 (a tela do jogo ocupa a janela inteira).
const TELA = { largura: 1280, altura: 720 };
const ALVO = {
  novaCarreira: { x: 500, y: 87 },
  aceitarConvite: { x: 500, y: 179 },
  passoStaff: { x: 500, y: 232 },
  microciclo: { x: 500, y: 612 },
  passoPrancheta: { x: 500, y: 259 },
  jogar: { x: 500, y: 289 },
  // Depois de "Jogar", o jogo abre o INTERVALO da partida (placar no topo, escolha de instrução).
  // Coordenadas lidas do quadro de 27/10 às 1280x720.
  instrucao: { x: 110, y: 608 },          // "+ Pressionar"
  seguir: { x: 636, y: 573 },             // "Seguir sem mexer"
  velocidadeRapida: { x: 700, y: 685 },   // "Rápida"
  pularParaFim: { x: 900, y: 705 }        // "Pular para o fim"
};

function argumentos(argv) {
  const o = {
    saida: path.join(RAIZ, 'media', 'gameplay', 'prancheta-cru.mp4'),
    segundos: 75,
    url: '',
    largura: 1280,
    altura: 720,
    quadros: 24
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const valor = () => argv[++i];
    if (a === '--saida') o.saida = path.resolve(valor());
    else if (a === '--segundos') o.segundos = Number(valor());
    else if (a === '--url') o.url = valor();
    else if (a === '--largura') o.largura = Number(valor());
    else if (a === '--altura') o.altura = Number(valor());
    else if (a === '--quadros') o.quadros = Number(valor());
  }
  return o;
}

/** Acha o build atual: o iframe do itch aponta para html-classic.itch.zone/html/<id>/index.html. */
function descobrirBuild(pagina, buscar) {
  try {
    const html = buscar(pagina);
    // O endereço vem dentro de um iframe com HTML escapado (&amp; e &quot;), por isso o corte
    // não pode parar no & — senão a versão (?v=) é perdida.
    const achado = html.match(/https:\/\/html-classic\.itch\.zone\/html\/\d+\/index\.html[^"'\s<>]*/);
    if (achado) {
      return achado[0].replace(/&amp;/g, '&').replace(/&quot;?$/, '');
    }
  } catch (e) { /* cai na reserva */ }
  return BUILD_RESERVA;
}

function buscarTexto(url) {
  const r = spawnSync('curl', ['-sL', '--max-time', '30', '-A', 'Mozilla/5.0', url],
    { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
  if (r.status !== 0) throw new Error('curl falhou: ' + String(r.stderr || '').slice(0, 120));
  return r.stdout || '';
}

function carregarPlaywright(caminhos, padrao) {
  const lista = caminhos || [process.env.PLAYWRIGHT_CORE || '', 'playwright-core', 'playwright',
    path.join(RAIZ, 'node_modules', 'playwright-core')].filter(Boolean);
  for (const nome of lista) {
    try {
      return require(nome);
    } catch (e) { /* tenta o próximo */ }
  }
  if (padrao === false) return null;
  return null;
}

/** Quanto a tela mudou em relação ao quadro anterior (0 = idêntica). */
const MEDIDOR_DIFERENCA = (anterior) => {
  const cv = document.querySelector('canvas');
  if (!cv) return -1;
  const c2 = document.createElement('canvas');
  c2.width = 160;
  c2.height = 90;
  const g = c2.getContext('2d', { willReadFrequently: true });
  g.drawImage(cv, 0, 0, 160, 90);
  const d = g.getImageData(0, 0, 160, 90).data;
  let soma = 0;
  for (let i = 0; i < d.length; i += 4) {
    if (!anterior) { soma += d[i] + d[i + 1] + d[i + 2]; continue; }
    soma += Math.abs(d[i] - anterior[i]) + Math.abs(d[i + 1] - anterior[i + 1])
      + Math.abs(d[i + 2] - anterior[i + 2]);
  }
  return anterior ? soma / (d.length / 4) / 3 : 0;
};

(async () => {
  const op = argumentos(process.argv.slice(2));
  const pw = carregarPlaywright();
  if (!pw) {
    console.error('✘ sem playwright-core: rode npm install --no-save playwright-core@1');
    return 3;
  }
  const endereco = op.url || descobrirBuild(PAGINA_ITCH, buscarTexto);
  console.log('build do PRANCHETA: ' + endereco);

  const pasta = path.dirname(op.saida);
  fs.mkdirSync(pasta, { recursive: true });
  const navegador = await pw.chromium.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader',
      '--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--enable-webgl',
      '--mute-audio']
  });
  const contexto = await navegador.newContext({
    viewport: { width: op.largura, height: op.altura },
    hasTouch: true,
    recordVideo: { dir: pasta, size: { width: op.largura, height: op.altura } }
  });
  const pagina = await contexto.newPage();
  const passos = [];

  const lerTela = async () => pagina.evaluate((anterior) => {
    const cv = document.querySelector('canvas');
    if (!cv) return { temCanvas: false, pixels: null };
    const c2 = document.createElement('canvas');
    c2.width = 160; c2.height = 90;
    const g = c2.getContext('2d', { willReadFrequently: true });
    g.drawImage(cv, 0, 0, 160, 90);
    const d = g.getImageData(0, 0, 160, 90).data;
    return { temCanvas: true, pixels: Array.from(d) };
  }, null);

  const diferenca = (a, b) => {
    if (!a || !b) return 0;
    let soma = 0;
    for (let i = 0; i < a.length; i += 4) {
      soma += Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
    }
    return soma / (a.length / 4) / 3;
  };

  const acionar = async (alvo) => {
    await pagina.mouse.click(alvo.x, alvo.y);
    await pagina.waitForTimeout(120);
    await pagina.touchscreen.tap(alvo.x, alvo.y);
  };

  // Um passo = toque + espera + conferência de que a tela mudou.
  const passo = async (nome, alvo, esperaMs, minimoMudanca) => {
    const antes = (await lerTela()).pixels;
    await acionar(alvo);
    await pagina.waitForTimeout(esperaMs);
    const depois = (await lerTela()).pixels;
    const mudou = diferenca(antes, depois);
    const okPasso = mudou >= (minimoMudanca || 1.2);
    passos.push({
      t: +((Date.now() - inicio) / 1000).toFixed(1),
      motivo: nome,
      acao: 'toque em ' + alvo.x + ',' + alvo.y,
      mudanca: +mudou.toFixed(2),
      ok: okPasso
    });
    console.log((okPasso ? '✔ ' : '· ') + nome + ' (mudança ' + mudou.toFixed(2) + ')');
    return okPasso;
  };

  const inicio = Date.now();
  try {
    await pagina.goto(endereco, { waitUntil: 'load', timeout: 180000 });
    // O Godot baixa wasm de 38 MB: espera o canvas existir e o primeiro desenho aparecer.
    await pagina.waitForSelector('canvas', { timeout: 180000 });
    await pagina.waitForTimeout(9000);
    await pagina.screenshot({ path: op.saida.replace(/\.mp4$/i, '-abertura.png') });

    let jogando = false;
    jogando = await passo('abrir o menu do jogo', ALVO.novaCarreira, 2500, 1.2) || jogando;
    jogando = await passo('aceitar o convite do clube', ALVO.aceitarConvite, 3000, 1.2) || jogando;
    await passo('aplicar a sugestão do staff', ALVO.passoStaff, 2200, 0.8);
    await passo('aplicar o microciclo da semana', ALVO.microciclo, 2200, 0.8);
    await passo('abrir a prancheta', ALVO.passoPrancheta, 2600, 0.8);
    await pagina.screenshot({ path: op.saida.replace(/\.mp4$/i, '-prancheta.png') });
    await passo('jogar com o plano recomendado', ALVO.jogar, 3500, 0.5);

    // Partida: o jogo para no intervalo e pede uma instrução. A sequência abaixo é a que o
    // próprio jogo sugere ("escolha uma instrução... toque em Seguir sem mexer").
    await passo('dar instrução no intervalo', ALVO.instrucao, 1600, 0.3);
    await passo('seguir sem mexer', ALVO.seguir, 1800, 0.3);
    await passo('acelerar a partida', ALVO.velocidadeRapida, 1800, 0.3);

    // Resto do tempo: alterna as velocidade (deixa a partida correr) e, no fim, pula para o
    // resultado — cada toque registrado com a mudança que causou na tela.
    const fim = inicio + op.segundos * 1000;
    let toquesPartida = 0;
    const alvosPartida = [ALVO.velocidadeRapida, { x: 640, y: 360 }, ALVO.instrucao, ALVO.seguir];
    while (Date.now() - inicio < op.segundos * 1000 - 9000) {
      const alvo = alvosPartida[toquesPartida % alvosPartida.length];
      const antes = (await lerTela()).pixels;
      await acionar(alvo);
      await pagina.waitForTimeout(2400);
      const depois = (await lerTela()).pixels;
      passos.push({
        t: +((Date.now() - inicio) / 1000).toFixed(1),
        motivo: 'partida em andamento',
        acao: 'toque em ' + alvo.x + ',' + alvo.y,
        mudanca: +diferenca(antes, depois).toFixed(2),
        ok: true
      });
      toquesPartida += 1;
    }
    await passo('pular para o fim da partida', ALVO.pularParaFim, 3000, 0.3);
    void fim;
    await pagina.screenshot({ path: op.saida.replace(/\.mp4$/i, '-quadro.png') });

    const confirmados = passos.filter((p) => p.ok).length;
    console.log('passos: ' + passos.length + ' · confirmados por imagem: ' + confirmados);
    const essenciais = passos.slice(0, 6).filter((p) => p.ok).length;
    if (essenciais < 4) {
      console.error('✘ menos de 4 passos essenciais mudaram a tela: o vídeo não seria gameplay');
      await contexto.close();
      await navegador.close();
      return 8;
    }
    fs.writeFileSync(op.saida.replace(/\.mp4$/i, '-decisoes.json'), JSON.stringify({
      jogo: 'prancheta',
      endereco,
      decisoes: passos.map((p) => ({ t: p.t, motivo: p.motivo, acao: p.acao })),
      passos_confirmados: confirmados,
      toques_partida: toquesPartida
    }, null, 1));

    const video = pagina.video();
    await contexto.close();
    await navegador.close();
    if (!video) {
      console.error('✘ o navegador não devolveu vídeo');
      return 5;
    }
    const bruto = await video.path();
    fs.copyFileSync(bruto, op.saida);
    const tamanho = (fs.statSync(op.saida).size / 1048576).toFixed(1);
    console.log('vídeo cru: ' + op.saida + ' · ' + tamanho + ' MB');
    return 0;
  } catch (erro) {
    console.error('✘ falhou: ' + String((erro && erro.message) || erro).slice(0, 300));
    try { await contexto.close(); await navegador.close(); } catch (e) { /* já fechado */ }
    return 4;
  }
})();

module.exports = { descobrirBuild, ALVO, BUILD_RESERVA, PAGINA_ITCH };
