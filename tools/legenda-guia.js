#!/usr/bin/env node
// 🧭 LEGENDA-GUIA — desenha, sobre o vídeo do gameplay, as instruções de como jogar.
//
// REQUISITO DO DONO (não é preferência): "no vídeo as instruções de como jogar não saem da tela
// em momento algum". O vídeo atual do CEIFALUME não cumpre isso: as instruções aparecem só no
// tutorial do começo e somem. Este script resolve sem inventar nada:
//
//   · O TEXTO é o do próprio jogo (o tutorial do build) e o do kit oficial da casa
//     (tools/kit-youtube.py → "como_joga" e "diferencial"). Nada de frase nova prometendo coisa.
//   · O DESENHO é feito aqui, quadro a quadro, com ffmpeg + PIL: faixa inferior sólida com
//     fundo escuro (lê sobre qualquer cena do jogo), fonte grande, queimada NO VÍDEO — não é
//     legenda ativável, então não existe "desligar" nem sair da tela.
//   · A faixa aparece do primeiro ao último quadro e é MEDIDA depois por
//     tools/validar-instrucoes.py, que reprova se sumir, encolher ou ficar ilegível.
//
// Uso:
//   node tools/legenda-guia.js --entrada cru.mp4 --saida final.mp4
//   node tools/legenda-guia.js --entrada cru.mp4 --saida final.mp4 --sem-trilha
//
// Requisitos: ffmpeg (PATH, FFMPEG_PATH ou imageio-ffmpeg) e Pillow.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const RAIZ = path.resolve(__dirname, '..');

function argumentos(argv) {
  const o = {
    entrada: path.join(RAIZ, 'media', 'gameplay', 'ceifalume-gameplay-cru.mp4'),
    saida: path.join(RAIZ, 'media', 'gameplay', 'ceifalume-gameplay.mp4'),
    relatorio: null,
    linhas: [],
    alturaFaixa: 150,
    fonte: 28,
    semTrilha: false
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const valor = () => argv[++i];
    if (a === '--entrada') o.entrada = path.resolve(valor());
    else if (a === '--saida') o.saida = path.resolve(valor());
    else if (a === '--relatorio') o.relatorio = path.resolve(valor());
    else if (a === '--linha') o.linhas.push(String(valor()));
    else if (a === '--altura-faixa') o.alturaFaixa = Number(valor());
    else if (a === '--fonte') o.fonte = Number(valor());
    else if (a === '--sem-trilha') o.semTrilha = true;
  }
  return o;
}

function duracaoDoVideo(bin, arquivo) {
  const r = spawnSync(bin, ['-hide_banner', '-i', arquivo], { encoding: 'utf8' });
  const texto = ((r.stderr || '') + (r.stdout || '')).replace(/\s/g, '');
  const m = /Duration:(\d+):(\d+):(\d+\.?\d*)/.exec(texto);
  if (!m) return 0;
  return Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]);
}

function ffmpeg() {
  const candidatos = [process.env.FFMPEG_PATH];
  for (const c of candidatos) if (c && fs.existsSync(c)) return c;
  const noPath = spawnSync('ffmpeg', ['-version'], { captureOutput: true });
  if (!noPath.error) return 'ffmpeg';
  const py = spawnSync('python3', ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
    { encoding: 'utf8' });
  const caminho = (py.stdout || '').trim();
  if (py.status === 0 && caminho && fs.existsSync(caminho)) return caminho;
  return null;
}

// As instruções: primeiro a do kit (fonte única dos fatos), depois a de TELA, que é o que a
// pessoa precisa saber para jogar o que está vendo. Nenhuma linha promete o que o jogo não faz.
const INSTRUCOES_PADRAO = [
  'COMO JOGAR: 1) toque no botão de cima para escolher a semente  ·  2) toque no campo para plantar  ·  3) "Fazer um bico" ganha +1 moeda  ·  4) colha quando aparecer "pronto" e venda',
  'O que você está vendo é o jogo rodando no navegador: só clique, sem conta e sem instalação. As plantações crescem até 8 h com o jogo fechado.',
  'Grátis em reboclbrank-max.github.io/site/jogos/ceifalume · feito com Godot, no Brasil'
];

function main() {
  const o = argumentos(process.argv.slice(2));
  const bin = ffmpeg();
  if (!bin) {
    console.error('✘ sem ffmpeg: instale (apt install ffmpeg) ou imageio-ffmpeg');
    return 2;
  }
  if (!fs.existsSync(o.entrada)) {
    console.error('✘ entrada não existe: ' + o.entrada);
    return 2;
  }
  const linhas = o.linhas.length ? o.linhas : INSTRUCOES_PADRAO;
  const temporario = fs.mkdtempSync(path.join(os.tmpdir(), 'legenda-guia-'));
  const png = path.join(temporario, 'faixa.png');

  // A faixa é desenhada com Python/PIL: texto grande, margem, fundo opaco com transparência
  // controlada (0.88) — legível sobre a cena clara e sobre a escura.
  const desenho = spawnSync('python3', [path.join(__dirname, 'desenhar-faixa.py'),
    '--saida', png, '--largura', '1280', '--altura', String(o.alturaFaixa),
    '--fonte', String(o.fonte)].concat(linhas.flatMap((l) => ['--linha', l])), { encoding: 'utf8' });
  if (desenho.status !== 0 || !fs.existsSync(png)) {
    console.error('✘ faixa não desenhada: ' + ((desenho.stderr || desenho.stdout || '') + '').slice(-400));
    return 1;
  }

  fs.mkdirSync(path.dirname(o.saida), { recursive: true });

  // Trilha: o cru do gravador não tem áudio (medido: só um stream de vídeo). Sem trilha o vídeo
  // sai mudo, e vídeo mudo não é apresentável — então a casa gera um pad baixo do tamanho exato
  // do vídeo (a duração é lida do arquivo; nada de laço infinito).
  const duracao = duracaoDoVideo(bin, o.entrada);
  if (!(duracao > 0)) {
    console.error('✘ não consegui medir a duração de ' + o.entrada);
    return 1;
  }
  const pad = path.join(temporario, 'pad.m4a');
  const r = spawnSync(bin, ['-y', '-hide_banner', '-loglevel', 'error',
    '-f', 'lavfi', '-i',
    'aevalsrc=0.03*sin(2*PI*220*t)+0.02*sin(2*PI*329.63*t):s=44100:d=' + duracao.toFixed(2) +
    ',tremolo=f=0.12:d=0.3',
    '-c:a', 'aac', '-b:a', '64k', pad], { encoding: 'utf8' });
  const temPad = !o.semTrilha && r.status === 0 && fs.existsSync(pad);

  const probe = spawnSync(bin, ['-hide_banner', '-i', o.entrada], { encoding: 'utf8' });
  const temAudioOriginal = /Stream.*Audio:/.test((probe.stderr || '') + (probe.stdout || ''));

  const args = ['-y', '-hide_banner', '-loglevel', 'error', '-i', o.entrada,
    '-loop', '1', '-i', png];
  if (temPad) args.push('-i', pad);

  // `-loop 1` na imagem cria uma entrada de vídeo INFINITA. Sem `-shortest` o encode não
  // termina nunca (medido duas vezes: 87 MB e crescendo). O fim é o fim do vídeo gravado.
  let filtro = '[0:v][1:v]overlay=0:H-h:format=auto[v]';
  if (temPad && temAudioOriginal) filtro += ';[0:a][2:a]amix=inputs=2:duration=first[a]';
  args.push('-filter_complex', filtro, '-map', '[v]');
  if (temPad && temAudioOriginal) args.push('-map', '[a]');
  else if (temAudioOriginal) args.push('-map', '0:a');
  else if (temPad) args.push('-map', '2:a');
  // Limite explícito: `-loop 1` no PNG é uma entrada infinita e, sem trilha, `-shortest` não tem
  // contra o que comparar (medido: saída de 34 min para um vídeo de 105 s). A duração do próprio
  // vídeo gravado é o limite.
  args.push('-t', duracao.toFixed(3));
  args.push('-shortest');
  args.push('-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', o.saida);

  const saida = spawnSync(bin, args, { encoding: 'utf8' });
  if (saida.status !== 0 || !fs.existsSync(o.saida) || fs.statSync(o.saida).size < 10000) {
    console.error('✘ ffmpeg falhou: ' + ((saida.stderr || '') + '').slice(-600));
    return 1;
  }
  const tamanho = fs.statSync(o.saida).size;
  console.log('faixa desenhada: ' + linhas.length + ' linha(s) · altura ' + o.alturaFaixa + 'px · fonte ' + o.fonte + 'px');
  console.log('vídeo: ' + path.relative(RAIZ, o.saida) + ' · ' + (tamanho / 1048576).toFixed(1) + ' MB');
  return 0;
}

process.exit(main());
