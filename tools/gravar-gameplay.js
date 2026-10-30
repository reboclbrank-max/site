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
    // Linha de base para a comparação antes/depois: mesmo robô, mesmas leituras, mas sem as
    // decisões de dinheiro (melhoria/semente). Serve só para medir, não é o modo de produção.
    else if (a === '--sem-economia') o.semEconomia = true;
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
const REGIAO_TITULO = { x: 470, y: 445, w: 350, h: 80 };       // caixa "Jogar" da capa
const REGIAO_DIALOGO = { x: 330, y: 180, w: 620, h: 220 };     // painel do tutorial
const REGIAO_HUD = { x: 500, y: 0, w: 300, h: 50 };            // "Moedas: N" dourado do jogo
// Caixas dos campos, lidas da tela do jogo em 27/10/2026 (o build tem 4 campos: 3 em cima e
// 1 embaixo à esquerda). A quinta "célula" que existia antes media o telhado da casa.
const CELULAS = [
  { id: 'A', x: 400, y: 157, w: 220, h: 205 },
  { id: 'B', x: 640, y: 157, w: 240, h: 205 },
  { id: 'C', x: 884, y: 157, w: 235, h: 205 },
  { id: 'D', x: 400, y: 400, w: 220, h: 180 },
  // E: a quinta célula. Medida em 27/10 comprando "Comprar campo" (50 moedas): o save passou de
  // 4 para 5 entradas em `campos` e a caixa "Clique para plantar" apareceu embaixo, à direita da
  // D — em (640,372) 230×228, centro (755,486). Antes disso o robô comprava o campo e não
  // enxergava a célula nova: pagava 50 e continuava plantando em 4.
  { id: 'E', x: 640, y: 372, w: 230, h: 228 }
];
const ALVO = {
  tutorial: { x: 640, y: 331 },
  titulo: { x: 640, y: 484 },
  semente: { x: 437, y: 120 },
  bico: { x: 100, y: 481 },
  vender: { x: 140, y: 400 },
  melhoria: { x: 100, y: 600 }
};
// ECONOMIA — o jogo grava o estado em ceifalume-save.cfg (IndexedDB, "godot/app_userdata").
// Até 27/10/2026 o agente jogava só pela imagem: sabia colher, mas não sabia quanto tinha no
// bolso, qual semente estava escolhida nem que uma melhoria estava ao alcance. Com o save lido,
// as decisões de dinheiro passam a ser medidas no próprio jogo, não estimadas na tela.
const SAVE_CAMINHO = '/userfs/godot/app_userdata/Ceifalume/ceifalume-save.cfg';
const LEITOR_SAVE = async (caminho) => {
  const texto = await new Promise((resolver) => {
    const abrir = indexedDB.open('/userfs');
    abrir.onerror = () => resolver(null);
    abrir.onsuccess = () => {
      const pedido = abrir.result.transaction('FILE_DATA', 'readonly').objectStore('FILE_DATA')
        .get(caminho);
      pedido.onsuccess = () => {
        const v = pedido.result;
        if (!v || !v.contents) return resolver(null);
        const bytes = v.contents instanceof Uint8Array ? v.contents : new Uint8Array(v.contents);
        resolver(new TextDecoder('utf-8').decode(bytes));
      };
      pedido.onerror = () => resolver(null);
    };
  });
  if (!texto) return null;
  const numero = (campo) => {
    const achado = texto.match(new RegExp(campo + '=([^\\n]+)'));
    return achado ? Number(achado[1]) : null;
  };
  const celeiro = {};
  const bloco = texto.match(/celeiro=\{([\s\S]*?)\}/);
  if (bloco) {
    bloco[1].split(',').forEach((linha) => {
      const par = linha.match(/"([^"]+)"\s*:\s*(\d+)/);
      if (par) celeiro[par[1]] = Number(par[2]);
    });
  }
  const listaCampos = texto.match(/campos=\[([\s\S]*?)\]/);
  // `campos` é a lista de células na MESMA ordem da tela (medido em 27/10: plantar só na célula
  // A grava `planta` na primeira entrada). Cada entrada diz o que está plantado e se está pronto,
  // o que dispensa adivinhar colheita por cor: Trigo e Milho não têm a casca branca do Nabo e,
  // com a leitura só por pixel, ficavam maduros na tela e nunca eram colhidos.
  const camposLista = listaCampos
    ? listaCampos[1].split('}').filter((t) => t.indexOf('planta') >= 0).map((t) => ({
      planta: (t.match(/planta"?\s*:\s*"([^"]*)"/) || [, ''])[1],
      pronto: /pronto"?\s*:\s*true/.test(t),
      tempo: Number((t.match(/tempo"?\s*:\s*([\d.]+)/) || [, 0])[1]) || 0
    }))
    : null;
  return {
    moedas: numero('moedas'),
    campos: camposLista ? camposLista.length : null,
    camposLista,
    dia: numero('dia'),
    semente: numero('semente_selecionada'),
    niveis: {
      celeiro: numero('nivel_celeiro'),
      poco: numero('nivel_poco'),
      lanterna: numero('nivel_lanterna'),
      ajudante: numero('nivel_ajudante'),
      composteira: numero('nivel_composteira'),
      carroca: numero('nivel_carroca')
    },
    celeiro,
    tutorial_visto: /tutorial_visto=true/.test(texto)
  };
};
// Abas de semente e botões de melhoria, medidos na tela do jogo em 27/10/2026 (1280x720).
// Os custos são os que o jogo MOSTRA no painel; a compra é conferida no save (nível sobe e o
// dinheiro cai), então custo errado aparece como falha, não como sucesso imaginário.
// `responde`: medido em 27/10/2026 tocando a aba e conferindo `semente_selecionada` no save.
// O que parecia "aba que não funciona" era coordenada errada (y=112 em vez de y=121) e falta de
// dinheiro — o jogo só deixa escolher a semente que o bolso cobre. Medido com 21 moedas:
//   Nabo (440,121) já estava em 0 · Milho (562,121) trocou 0 -> 1 ✔
//   Trigo (690,121) · Tomate (817,121) · Abóbora (968,121) · Flor (1121,121) não trocaram
//   (custam 60 / 200 / 700 / 2500 — bem mais do que as 21 moedas da hora do teste)
// A conferência é sempre no save: aba que não trocar de verdade fica marcada como falha naquela
// captura e não é tentada de novo, então o robô não queima o vídeo insistindo numa aba travada.
const SEMENTES = [
  { indice: 0, nome: 'Nabo', custo: 5, venda: 8, alvo: { x: 440, y: 121 }, responde: true },
  { indice: 1, nome: 'Milho', custo: 20, venda: 35, alvo: { x: 562, y: 121 }, responde: true },
  { indice: 2, nome: 'Trigo', custo: 60, venda: 110, alvo: { x: 690, y: 121 }, responde: true },
  { indice: 3, nome: 'Tomate', custo: 200, venda: 380, alvo: { x: 817, y: 121 }, responde: true },
  { indice: 4, nome: 'Abóbora', custo: 700, venda: 1400, alvo: { x: 968, y: 121 }, responde: true },
  { indice: 5, nome: 'Flor de Lume', custo: 2500, venda: 5500, alvo: { x: 1121, y: 121 }, responde: true }
];
// ORDEM = PRIORIDADE DE COMPRA, e a ordem é por efeito MEDÍDO em moedas, não por preço:
//   1) Cavar Poço (40) — crescimento +10%: encurta o ciclo, e ciclo curto é mais colheita por
//      minuto. É o único efeito que ataca direto o numerador da conta (moedas/min).
//   2) Acender Lanterna (60) — +1 moeda em cada colheita: soma em toda venda, para sempre.
//   3) Composteira (80) — 8% de colheita dupla: ganho esperado, porém probabilístico.
//   4) Comprar campo (50) — +1 campo, mas o agente só enxerga as 4 células medidas; enquanto a
//      5ª não estiver mapeada, o campo novo rende zero. Fica atrás do que rende na hora.
//   5) Ampliar Celeiro (30) — capacidade 10 -> 20. O agente vende assim que colhe, então o
//      celeiro nunca é gargalo. Fica CATALOGADO (a compra existe e é conferida no save) mas
//      NÃO é comprado: gastar 30 moedas que atrasam o Poço é trocar efeito por nenhum.
const MELHORIAS = [
  { id: 'poco', nome: 'Cavar Poço', custo: 40, alvo: { x: 767, y: 606 },
    porque: 'crescimento +10% (colhe antes, mais ciclos)' },
  { id: 'lanterna', nome: 'Acender Lanterna', custo: 60, alvo: { x: 1120, y: 606 },
    porque: '+1 moeda por colheita' },
  { id: 'composteira', nome: 'Composteira', custo: 80, alvo: { x: 450, y: 688 },
    porque: '8% de colheita dupla' },
  { id: 'campo', nome: 'Comprar campo', custo: 50, alvo: { x: 170, y: 606 },
    porque: '+1 campo (só rende depois que a 5ª célula for mapeada)' },
  { id: 'celeiro', nome: 'Ampliar Celeiro', custo: 30, alvo: { x: 458, y: 606 },
    comprar: false,
    porque: 'capacidade 10 -> 20 (o agente vende logo, então não é gargalo)' }
];
// REGRA DE CAIXA PARA TROCAR DE SEMENTE (medida, não escolhida no gosto):
// o robô planta em até 4 células por rodada, então trocar de semente só faz sentido quando o
// caixa paga a rodada INTEIRA — custo × 4 — e ainda sobra um respiro. Teste de 27/10 que provou
// isso: com 25 moedas o robô subiu para Milho, plantou 1 vez, ficou sem caixa, desceu para Nabo
// e terminou o vídeo com 13,60 moedas/min (pior que o Nabo puro). Com a regra de 4× o caixa
// espera o momento de trocar sem se descapitalizar: 20×4+5 = 85 para o Milho, 205 para o Tomate.
const CELULAS_POR_RODADA = 4;
const FOLGA_SEMENTE = 5;
/** GANHO ≠ SALDO: comprar melhoria derruba o saldo e não é prejuízo. */
function ganhoDeMoedas(inicial, final, gasto) {
  if (typeof inicial !== 'number' || typeof final !== 'number') return null;
  return final - inicial + (gasto || 0);
}
// BICO — medido em 27/10/2026 (20 s por intervalo, moedas lidas no save):
//   60 ms → 525,0 moedas/min · 120 ms → 306,0 · 250 ms → 195,0 · 500 ms → 111,0 · 1000 ms → 57,0
// Ou seja: o botão "Fazer um bico (+1 moeda)" NÃO tem tempo de espera — cada toque paga 1 moeda.
// O agente antigo dava 1 toque a cada ~2,2 s (≈27/min) e por isso a fazenda inteira rendia menos
// que o dedo no bico. Agora o ócio entre colheitas vira rajada de bicos, que é o que um jogador
// de verdade faz neste jogo.
// Custo do toque medido no sandbox: ~58 ms de ida e volta + espera. A rajada é medida em TEMPO
// (não em número fixo de toques) para que o robô fique ~2,5 s no bico por vez e volte a olhar a
// fazenda: com 14 toques fixos o laço olhava a tela a cada 1,8 s e o overhead comia a renda.
const BICO = { intervalo: 45, rajadaMs: 8000 };

// limites de decisão — calibrados nos quadros de 27/10 (ver docs/VIDEO-GAMEPLAY.md)
const LIMIAR = {
  botao: 0.02,        // fração de branco que já conta como letra "Jogar" visível
  hud: 0.04,          // dourado de "Moedas" no topo: só existe com a fazenda na tela
  verdeVazio: 0.02,   // abaixo disso a célula está vazia (medido: 0,000 no campo vazio)
  verdeCrescendo: 0.03, // broto na tela (medido: 0,049 a 0,100)
  brancoPronto: 0.012,  // nabo maduro: casca branca no miolo (medido: 0,027 vs 0,000)
  barraOcupada: 0.02,   // barra dourada de progresso (medido: 0,046 já 3 s após semear; 0,000 vazia)
  carenciaColheita: 5000,  // ms em que a célula recém-colhida não é colhida de novo (save atrasa)
  esperaCrescimento: 9000  // ms de carência depois de semear (sob gravação o relógio do jogo anda
                           // devagar: a barra pode levar 6-8 s para aparecer; com 4 s o robô
                           // replantava em cima da semente e reiniciava o crescimento)
};

/** Conta, dentro de um recorte do canvas, quantos pixels são amarelos e quantos são claros. */
const MEDIDOR = (regioes) => {
  const cv = document.querySelector('canvas');
  const c2 = document.createElement('canvas');
  const g = c2.getContext('2d', { willReadFrequently: true });
  const sx = cv.width / 1280;
  const sy = cv.height / 720;
  // Só as regiões pedidas vão para o canvas auxiliar (antes o canvas inteiro era copiado a cada
  // leitura: 160-200 ms por olhada, e o laço perde ~1/4 do tempo só olhando). O resultado é o
  // mesmo pixel a pixel; muda só o custo.
  const conta = (r, teste) => {
    const x = Math.round(r.x * sx);
    const y = Math.round(r.y * sy);
    const w = Math.max(1, Math.round(r.w * sx));
    const h = Math.max(1, Math.round(r.h * sy));
    if (c2.width !== w || c2.height !== h) { c2.width = w; c2.height = h; }
    g.drawImage(cv, x, y, w, h, 0, 0, w, h);
    const d = g.getImageData(0, 0, w, h).data;
    let n = 0;
    let tot = 0;
    for (let i = 0; i < d.length; i += 4) {
      tot += 1;
      if (teste(d[i], d[i + 1], d[i + 2])) n += 1;
    }
    return n / tot;
  };
  const ouro = (r, c, b) => c > 140 && c > b + 50 && b < 150;      // dourado do jogo
  const brancoTexto = (r, c, b) => r > 200 && c > 200 && b > 200;  // letra "Jogar"
  const verde = (r, c, b) => c > 90 && c > r + 30 && c > b + 30;
  const brancoCasca = (r, c, b) => r > 190 && c > 185 && b > 170;   // casca do nabo maduro
  // ⚠️ CORRIGIDO EM 27/10/2026 — o vídeo entregue ao dono tinha o tutorial preso na tela do
  // começo ao fim. A causa foi medida quadro a quadro: o detector antigo exigia 35% de pixels
  // "escuros" (r<40,g<45,b<60) dentro do painel, mas o painel do tutorial é AZUL-ESCURO
  // (média rgb 44,52,65 → o azul passa de 60) e só dava 0,255 de "escuro". O tutorial nunca era
  // reconhecido, então o robô nunca tocou em "Entendi, jogar!" e ele ficou para sempre no quadro.
  // Agora o teste é o azul do painel + o dourado do botão — medidos nos dois estados:
  //   tutorial aberto: painel azul 0,878 · botão dourado 0,582
  //   jogando sem tutorial: painel azul 0,080 · botão dourado 0,000
  const azulPainel = (r, c, b) => b >= 45 && b <= 115 && b > r + 18 && b > c + 8 && r < 80;
  const dialogo = conta(regioes.dialogo, azulPainel);
  // 0,084 com a fazenda na tela (HUD "Moedas" em dourado) e 0,000 em splash/título: é o sinal
  // mais limpo para saber que o jogo já está sendo jogado.
  const hud = conta(regioes.hud, ouro);
  return {
    dialogo,
    tutorial: dialogo > 0.6 ? conta(regioes.tutorial, ouro) : 0,
    titulo: conta(regioes.titulo, brancoTexto),
    hud,
    celulas: regioes.celulas.map((c) => {
      // Faixas medidas nos quadros do jogo:
      //   crescendo → broto verde ocupa ~10% do miolo da caixa
      //   pronto    → o nabo fica BRANCO (verde cai para ~4% e aparece branco ~3%)
      //   colher    → botão dourado "Colher" na faixa de baixo da caixa
      const miolo = { x: c.x, y: c.y + 45, w: c.w, h: Math.max(20, c.h - 105) };
      const rodape = { x: c.x + 10, y: c.y + c.h - 45, w: c.w - 20, h: 40 };
      return {
        id: c.id,
        verde: conta(miolo, verde),
        branco: conta(miolo, brancoCasca),
        ouroBotao: conta(rodape, ouro),
        centro: { x: Math.round(c.x + c.w / 2), y: Math.round(c.y + c.h / 2) },
        // MEDIDO em 27/10: quem colhe é o clique no CORPO da planta (centro da caixa). O clique
        // na barra do rodapé (y + h − 25) NÃO colhe: ele planta uma semente nova na célula — era
        // por isso que o robô "colhia" e o save continuava com a planta madura no lugar.
        colher: { x: Math.round(c.x + c.w / 2), y: Math.round(c.y + c.h / 2) }
      };
    })
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
  // Ainda não há HUD de moedas na tela: é splash do estúdio ou outra tela de abertura.
  // Tocar no mesmo ponto do "Jogar" atravessa essa tela sem efeito colateral.
  if (estado.hud <= LIMIAR.hud) {
    return { tipo: 'toque', alvo: ALVO.titulo, motivo: 'tela de abertura (sem HUD)' };
  }
  const agora = memoria.agora || 0;
  const ocupadas = memoria.ocupadas || {};
  const economia = memoria.economia || null;

  // ---- decisões de DINHEIRO (medidas no save do próprio jogo) ----
  // Ordem de prioridade: primeiro o que aumenta a produção por ciclo (celeiro, poço, campo),
  // depois o que aumenta a receita (lanterna, composteira). A compra só acontece quando o
  // dinheiro cobre o custo, e o laço confere no save que o nível realmente subiu.
  if (economia && typeof economia.moedas === 'number') {
    const melhoriasFeitas = memoria.melhoriasFeitas || {};
    const compraveis = MELHORIAS.filter((m) => m.comprar !== false
      && economia.moedas >= m.custo && !melhoriasFeitas[m.id]);
    if (compraveis.length) {
      const m = compraveis[0];
      return { tipo: 'melhoria', melhoria: m, alvo: m.alvo,
               motivo: 'comprar ' + m.nome + ' (' + m.custo + ' moedas · ' + m.porque + ')' };
    }
    // SEMENTE: a mais cara que o bolso cobre com folga — é onde está o dinheiro de verdade
    // (Nabo vende 8, Milho 35, Tomate 380 por ciclo). Duas regras aprendidas na tela do jogo:
    //  • a aba só deixa a semente PENDENTE; `semente_selecionada` no save muda no primeiro
    //    plantio (medido: aba Milho em 562,121 + plantar em 760,259 → 0 -> 1). Por isso não se
    //    confere nada no instante do toque — quem confere é o plantio seguinte;
    //  • se o caixa não cobre mais a semente atual, o robô DESCE para a mais cara que cobre, em
    //    vez de ficar tentando plantar o que não pode pagar.
    const falhas = memoria.sementesFalhas || {};
    const pendente = memoria.sementePendente ? memoria.sementePendente.indice : null;
    const atual = SEMENTES.find((x) => x.indice === economia.semente) || null;
    // HISTERESE: subir exige caixa para 6 rodadas; descer só quando não paga nem UMA semente.
    // Sem essa faixa larga o robô ficava pulando Nabo → Trigo → Nabo a cada compra (medido em
    // 27/10: 4 trocas em 150 s, cada troca custando ~0,5 s de bico).
    const cobre = (x) => economia.moedas >= x.custo * (CELULAS_POR_RODADA + 2) + FOLGA_SEMENTE;
    // Caso de emergência: se o caixa não paga nem UMA semente da atual, o robô não pode ficar
    // travado (plantio recusado = célula vazia = zero de renda). Aí desce para a mais barata que
    // paga um plantio, mesmo sem cobrir a rodada inteira.
    const pagaUma = (x) => economia.moedas >= x.custo;
    const opcoes = SEMENTES.filter((x) => x.responde !== false && !falhas[x.indice] && cobre(x));
    const melhor = opcoes.length ? opcoes[opcoes.length - 1] : null;
    if (atual && !pagaUma(atual)) {
      const baratas = SEMENTES.filter((x) => pagaUma(x) && !falhas[x.indice]);
      if (baratas.length) {
        const barata = baratas[0];
        if (barata.indice !== economia.semente && barata.indice !== pendente) {
          return { tipo: 'semente', semente: barata, alvo: barata.alvo,
                   motivo: 'caixa curto: voltar para ' + barata.nome + ' (paga ' + barata.custo + ')' };
        }
      }
    }
    const desce = atual && !cobre(atual);
    if (melhor && melhor.indice !== economia.semente && melhor.indice !== pendente
      && (desce || melhor.custo > atual.custo || !atual)) {
      return { tipo: 'semente', semente: melhor, alvo: melhor.alvo,
               motivo: (desce ? 'caixa curto: descer para ' : 'subir para ') + melhor.nome
                 + ' (venda ' + melhor.venda + ' por ciclo)' };
    }
  }
  // ---- FAZENDA PELO SAVE (fonte da verdade) ----
  // O save diz, célula por célula, o que está plantado e se está pronto. Isso resolve o furo
  // medido em 27/10: com semente melhor (Milho/Trigo) a planta madura não tem a casca branca do
  // Nabo, a leitura por pixel não reconhecia a colheita e a célula ficava ocupada para sempre
  // (900 s: 14 plantios e 9 colheitas, contra 72 e 68 do robô sem economia).
  const centroDe = (c) => ({ x: Math.round(c.x + c.w / 2), y: Math.round(c.y + c.h / 2) });
  const colherDe = centroDe;   // quem colhe é o clique no corpo da planta (ver MEDIDOR)
  if (economia && Array.isArray(economia.camposLista) && economia.camposLista.length) {
    const prontasSave = [];
    const vaziasSave = [];
    // O save demora 1-2 s para refletir a colheita. Sem esta carência o robô colhia a MESMA
    // célula de novo na leitura velha (medido em 27/10: 169 colheitas em 900 s, a maioria clique
    // repetido na planta, e o tempo que ia para o bico virou toque perdido).
    const colhidasHaPouco = memoria.colhidasHaPouco || {};
    economia.camposLista.forEach((campo, i) => {
      const c = CELULAS[i];
      if (!c) return;
      if (campo.pronto && (agora - (colhidasHaPouco[c.id] || -1e9)) > LIMIAR.carenciaColheita) {
        prontasSave.push({ id: c.id, alvo: colherDe(c) });
      } else if (!campo.pronto && !campo.planta
        && (agora - (ocupadas[c.id] || -1e9)) > LIMIAR.esperaCrescimento) {
        vaziasSave.push({ id: c.id, centro: centroDe(c) });
      }
    });
    if (prontasSave.length) {
      return { tipo: 'colher', celula: prontasSave[0].id, alvo: prontasSave[0].alvo,
               prontas: prontasSave,
               motivo: 'save: ' + prontasSave.length + ' célula(s) pronta(s) ['
                 + prontasSave.map((x) => x.id).join(',') + ']' };
    }
    if (vaziasSave.length) {
      return { tipo: 'plantar', celula: { id: vaziasSave[0].id, centro: vaziasSave[0].centro },
               livres: vaziasSave,
               motivo: 'save: ' + vaziasSave.length + ' célula(s) vazia(s) ['
                 + vaziasSave.map((x) => x.id).join(',') + ']' };
    }
  }
  // SEM SAVE, a fazenda é decidida por pixel (reserva). COM save, NUNCA: a leitura por cor
  // inventava colheita na célula D (casca 0,015 fixa, acima do limiar 0,012) e o robô passava
  // minutos colhendo uma célula que estava só crescendo — 346 "colheitas" em 900 s e só 96
  // bicos/min. O save diz exatamente o que está pronto; pixel fica para quando não há save.
  const temSave = !!(economia && Array.isArray(economia.camposLista) && economia.camposLista.length);
  if (temSave) {
    // Nada pronto e nada vazio: a fazenda está crescendo. É bico, sem olhar cor nenhuma.
    return { tipo: 'toque', alvo: ALVO.bico, motivo: 'save: fazenda crescendo, moeda no bico' };
  }
  // PRONTA: o nabo maduro fica branco (medido: casca branca 0,027 no miolo, verde cai de 0,10
  // para 0,04). A leitura antiga exigia "verde alto" e por isso nunca colhia nada: no ponto de
  // colheita a planta deixa de ser verde.
  const prontas = estado.celulas.filter((c) => c.branco >= LIMIAR.brancoPronto);
  if (prontas.length) {
    const c = prontas[0];
    return { tipo: 'colher', alvo: c.colher, celula: c.id, celulaCentro: c.centro,
             prontas: prontas.map((x) => ({ id: x.id, alvo: x.colher })),
             motivo: 'célula ' + c.id + ' pronta (casca ' + c.branco.toFixed(3) + ')'
               + (prontas.length > 1 ? ' (+' + (prontas.length - 1) + ' prontas)' : '') };
  }
  // CRESCENDO: broto verde na tela — não replantar em cima, mas também não é hora de colher.
  const crescendo = estado.celulas.filter((c) => c.verde >= LIMIAR.verdeCrescendo);
  if (crescendo.length) {
    const c = crescendo[0];
    return { tipo: 'toque', alvo: ALVO.bico, celula: c.id,
             motivo: 'célula ' + c.id + ' crescendo (verde ' + c.verde.toFixed(3) + '): bico' };
  }
  // livre: nada plantado na célula. O sinal mais cedo é a BARRA DOURADA de progresso, que
  // aparece no rodapé da caixa no instante em que a semente cai (medido: 0,12 na célula com
  // semente e 0,00 na vazia). Antes o robô esperava o broto verde e nesse vão semeava a mesma
  // célula duas vezes ("Nabo crescendo" com dois toques de semente).
  const ocupada = (c) => c.ouroBotao > LIMIAR.barraOcupada
    || c.verde >= LIMIAR.verdeCrescendo || c.branco >= LIMIAR.brancoPronto;
  // Só planta quando a célula está livre em DUAS leituras seguidas: a barra dourada leva de 1 a
  // 3 s para aparecer e, com uma leitura só, o robô semeava de novo em cima da semente anterior,
  // reiniciando o crescimento (medido em 27/10: 4 campos, 8 sementes e nenhuma colheita em 75 s).
  const confirmacoes = memoria.confirmacoes || {};
  const livres = estado.celulas.filter((c) =>
    !ocupada(c) && (confirmacoes[c.id] || 0) >= 2
    && (agora - (ocupadas[c.id] || -1e9)) > LIMIAR.esperaCrescimento);
  if (livres.length) {
    return { tipo: 'plantar', celula: livres[0],
             livres: livres.map((c) => ({ id: c.id, centro: c.centro })),
             motivo: 'célula ' + livres[0].id + ' livre'
               + (livres.length > 1 ? ' (+' + (livres.length - 1) + ' livres)' : '') };
  }
  // Nada maduro, nada vazio para plantar: a fazenda está crescendo. Aqui é bico, SEMPRE — antes
  // este ramo devolvia "vender" e o robô passava 30 s tocando em "Vender toda a colheita" com o
  // celeiro vazio (medido no relatório de 27/10: 16 decisões seguidas de vender, zero moedas).
  return { tipo: 'toque', alvo: ALVO.bico, motivo: 'fazenda crescendo: moeda no bico' };
}

/** Toque que não depende do tipo de evento: clique de mouse E toque de dedo. */
/* ESCAPE DE TELA DE ABERTURA — conserto de 30/10/2026.
   Sintoma medido no sandbox: em duas de três gravações o robô passou 90 s decidindo
   "tela de abertura (sem HUD)" e tocando no mesmo ponto, sem chegar à fazenda; a gravação
   saía sem plantio e sem colheita (o pipeline recusava o vídeo, mas o robô perdia o run).
   Causa: o build às vezes não responde ao par clique+tap no mesmo ponto da capa (o canvas
   ainda não tem foco, ou a camada de entrada do Godot ainda está subindo).
   Correção: quando a abertura passa de ABERTURA_LIMITE segundos, alterna formas de entrada
   que o jogo aceita (foco no canvas, Enter/Espaço, clique no centro, clique no "Jogar"),
   sem tocar em nada que gaste dinheiro. E, se mesmo assim não sair, o run FALHA com motivo
   claro em vez de gravar 130 s de capa. */
const ABERTURA_LIMITE = 18;      // segundos aceitáveis na capa antes de escalar a entrada
const ABERTURA_MAXIMA = 45;      // segundos até desistir (aí o problema não é foco)

async function escaparDaAbertura(pagina, tentativa) {
  const vp = pagina.viewportSize() || { width: 1280, height: 720 };
  try { await pagina.bringToFront(); } catch (e) { /* sem janela visível: segue */ }
  try {
    await pagina.evaluate(() => {
      const c = document.querySelector('canvas');
      if (c) { c.setAttribute('tabindex', '0'); c.focus && c.focus(); }
      if (document.body) document.body.focus && document.body.focus();
    });
  } catch (e) { /* página pode estar no meio da troca de cena */ }
  // ordens diferentes a cada tentativa: o que não funcionou uma vez pode ser o que faltava
  const acoes = [
    async () => pagina.keyboard.press('Enter'),
    async () => pagina.keyboard.press('Space'),
    async () => pagina.mouse.click(Math.round(vp.width / 2), Math.round(vp.height / 2)),
    async () => pagina.touchscreen.tap(Math.round(vp.width / 2), Math.round(vp.height / 2)),
    async () => pagina.mouse.click(ponto(ALVO.titulo).x, ponto(ALVO.titulo).y),
    async () => pagina.mouse.down({ button: 'left' }) && pagina.mouse.up({ button: 'left' })
  ];
  for (let i = 0; i < acoes.length; i += 1) {
    const indice = (tentativa + i) % acoes.length;
    try { await acoes[indice](); } catch (e) { /* ação indisponível nesta versão do Playwright */ }
    await pagina.waitForTimeout(120);
  }
}

/* ESCALA DAS COORDENADAS — conserto de 30/10/2026.
   As regiões (MEDIDOR) já eram lidas em coordenadas de 1280×720 e escaladas pelo tamanho real do
   canvas; os CLIQUES não eram. Rodando com --largura 960 --altura 540 o robô tocava em pontos
   25% deslocados: ficava preso na capa ("tela de abertura (sem HUD)") ou tocava fora do botão do
   tutorial. Medido no sandbox: 3 de 3 gravações em 960×540 terminaram sem colheita, e 3 de 3 em
   1280×720 funcionaram. Aqui a mesma escala passa a valer para o clique. */
const ESCALA = { x: 1, y: 1 };

async function calibrarEscala(pagina) {
  // O canvas do Godot NASCE 300×150 e só depois é esticado para preencher a viewport (medido:
  // a primeira leitura dava 0,234 de escala e jogava todos os cliques para fora da tela).
  // Então: espera o canvas ficar do tamanho da viewport e só então fixa a escala.
  const vp = pagina.viewportSize() || { width: 1280, height: 720 };
  let caixa = null;
  for (let i = 0; i < 60; i += 1) {
    caixa = await pagina.evaluate(() => {
      const c = document.querySelector('canvas');
      if (!c) return null;
      const r = c.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height) };
    }).catch(() => null);
    if (caixa && caixa.w >= vp.width * 0.9 && caixa.h >= vp.height * 0.9) break;
    await pagina.waitForTimeout(250);
  }
  if (!caixa || !caixa.w || !caixa.h) return ESCALA;
  ESCALA.x = caixa.w / 1280;
  ESCALA.y = caixa.h / 720;
  return ESCALA;
}

function ponto(alvo) {
  return { x: Math.round(alvo.x * ESCALA.x), y: Math.round(alvo.y * ESCALA.y) };
}

async function acionar(pagina, alvo, duplo = true) {
  const p = ponto(alvo);
  await pagina.mouse.click(p.x, p.y);
  if (!duplo) return;
  await pagina.waitForTimeout(120);
  await pagina.touchscreen.tap(p.x, p.y);
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
    const escala = await calibrarEscala(pagina);
    console.log('escala dos cliques: ' + escala.x.toFixed(3) + ' x ' + escala.y.toFixed(3)
      + ' (1.000 = canvas em 1280x720)');
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
    let toquesTutorial = 0;
    let bicosDados = 0;
    let economiaCache = null;
    const colhidasHaPouco = {};
    let voltas = 0;
    let aberturaDesde = 0;      // ms em que a captura começou presa na abertura
    let escapes = 0;
    let tutorialFechado = false;
    let tutorialDesde = 0;
    let segundosComTutorial = 0;
    let confirmacoesAnteriores = {};
    let economiaInicial = null;
    let economiaAtual = null;
    const melhoriasFeitas = {};
    const sementesFalhas = {};
    let sementePendente = null;
    const melhoriasCompras = [];
    let gastoSementes = 0;   // semente também é despesa: sem isso o ganho sai subestimado
    let economiaResumo = null;
    const sementesTrocadas = [];
    while (Date.now() < fimAcoes) {
      let estado;
      try {
        estado = await pagina.evaluate(MEDIDOR, {
          tutorial: REGIAO_TUTORIAL, titulo: REGIAO_TITULO,
          dialogo: REGIAO_DIALOGO, hud: REGIAO_HUD, celulas: CELULAS
        });
      } catch (e) {
        await pagina.waitForTimeout(400);
        continue;
      }
      const confirmacoes = {};
      estado.celulas.forEach((c) => {
        const livre = c.ouroBotao <= LIMIAR.barraOcupada && c.verde < LIMIAR.verdeCrescendo
          && c.branco < LIMIAR.brancoPronto;
        confirmacoes[c.id] = livre ? ((confirmacoesAnteriores[c.id] || 0) + 1) : 0;
      });
      confirmacoesAnteriores = confirmacoes;
      // Estado de dinheiro lido do save (fonte da verdade do jogo, não da tela). A leitura custa
      // ~100 ms de ida e volta; com a rajada de bico valendo ~1 moeda a cada 130 ms, ler a cada
      // duas voltas é dinheiro no bolso e não muda nenhuma decisão (as compras são planejadas).
      voltas += 1;
      let economia = economiaCache;
      if (voltas % 2 === 1 || !economiaCache) {
        try {
          economia = await pagina.evaluate(LEITOR_SAVE, SAVE_CAMINHO);
          economiaCache = economia;
        } catch (e) { economia = economiaCache; }
      }
      if (economia) {
        if (!economiaInicial) economiaInicial = economia;
        economiaAtual = economia;
      }
      // Preso na abertura? Escala a forma de entrar (ver escaparDaAbertura).
      const semHud = estado.hud <= LIMIAR.hud && estado.tutorial <= LIMIAR.botao;
      if (semHud) {
        if (!aberturaDesde) aberturaDesde = Date.now();
        const preso = (Date.now() - aberturaDesde) / 1000;
        if (preso > ABERTURA_LIMITE && escapes < 12 && preso % 4 < 0.6) {
          escapes += 1;
          console.log('escape ' + escapes + ': ' + preso.toFixed(0) + ' s sem HUD — tentando outra forma de entrar');
          await escaparDaAbertura(pagina, escapes);
        }
        if (preso > ABERTURA_MAXIMA) {
          console.error('✘ o jogo não saiu da tela de abertura em ' + preso.toFixed(0)
            + ' s (o canvas existe, mas a fazenda nunca apareceu): gravação recusada');
          await contexto.close();
          return 9;
        }
      } else {
        aberturaDesde = 0;
      }
      const d = decidir(estado, { agora: Date.now() - inicioAcoes, ocupadas, confirmacoes,
        economia: op.semEconomia ? null : economia, melhoriasFeitas, sementesFalhas,
        sementePendente, colhidasHaPouco });
      let acao;
      if (d.tipo === 'plantar') {
        // Com troca de semente pendente, NÃO toca na sacola: o toque na sacola devolve a semente
        // salva e desfaz a aba escolhida (medido em 27/10 — a aba "funcionava" e o save continuava
        // em Nabo). Sem pendência, a sacola abre o plantio como antes.
        if (!sementePendente) {
          await pagina.mouse.click(ponto(ALVO.semente).x, ponto(ALVO.semente).y);
          await pagina.waitForTimeout(120);
        }
        // PLANTA EM LOTE: todas as células que a mesma olhada viu livres, num passo só. Antes era
        // uma por volta, e cada volta custa ~150 ms de leitura + 260 ms de espera.
        const alvosPlantio = (d.livres && d.livres.length ? d.livres : [{ id: d.celula.id, centro: d.celula.centro }]);
        // custo da semente usada neste plantio (tabela medida; o save mostra o índice escolhido)
        const sementeAtual = SEMENTES.find((x) => x.indice === (economia && economia.semente))
          || SEMENTES[0];
        gastoSementes += alvosPlantio.length * sementeAtual.custo;
        for (const alvo of alvosPlantio) {
          await pagina.mouse.click(ponto(alvo.centro).x, ponto(alvo.centro).y);
          ocupadas[alvo.id] = Date.now() - inicioAcoes;
          plantadas += 1;
          await pagina.waitForTimeout(150);
        }
        acao = 'semente + célula(s) ' + alvosPlantio.map((x) => x.id).join(',');
        // CONFERÊNCIA DA TROCA DE SEMENTE: só o plantio grava `semente_selecionada` no save.
        if (sementePendente) {
          const agoraSave = await pagina.evaluate(LEITOR_SAVE, SAVE_CAMINHO);
          const trocou = agoraSave && agoraSave.semente === sementePendente.indice;
          if (trocou || Date.now() - sementePendente.desde > 12000) {
            sementesTrocadas.push({ nome: sementePendente.nome, ok: !!trocou,
              t: +((Date.now() - inicioAcoes) / 1000).toFixed(1) });
            if (!trocou) sementesFalhas[sementePendente.indice] = true;
            sementePendente = null;
          }
        }
      } else if (d.tipo === 'colher') {
        // Um clique na planta colhe (medido: a barra do rodapé é o botão "Colher" e o corpo da
        // planta também colhe). A versão antiga dava 6 toques com 1,15 s de espera entre eles e
        // comia 2 s por colheita — tempo que agora vai para o bico.
        // COLHE EM LOTE: todas as células maduras da mesma olhada, e vende uma vez no fim.
        const alvosColheita = (d.prontas && d.prontas.length
          ? d.prontas : [{ id: d.celula, alvo: d.alvo }]);
        for (const alvo of alvosColheita) {
          await pagina.mouse.click(ponto(alvo.alvo).x, ponto(alvo.alvo).y);
          await pagina.waitForTimeout(160);
          delete ocupadas[alvo.id];
          colhidasHaPouco[alvo.id] = Date.now() - inicioAcoes;
          colhidas += 1;
        }
        await pagina.mouse.click(ponto(ALVO.vender).x, ponto(ALVO.vender).y);
        await pagina.waitForTimeout(150);
        acao = 'colher ' + alvosColheita.map((x) => x.id).join(',') + ' + vender';
      } else if (d.tipo === 'melhoria') {
        const antes = economiaAtual || {};
        await acionar(pagina, d.alvo);
        await pagina.waitForTimeout(700);
        const depois = await pagina.evaluate(LEITOR_SAVE, SAVE_CAMINHO);
        const nivel = (e) => (e && e.niveis && e.niveis[d.melhoria.id]) || 0;
        const comprou = depois && (nivel(depois) > nivel(antes)
          || (d.melhoria.id === 'campo' && depois.moedas < (antes.moedas || 0)));
        if (comprou) {
          melhoriasCompras.push({ id: d.melhoria.id, nome: d.melhoria.nome,
            custo: (antes.moedas || 0) - (depois.moedas || 0),
            t: +((Date.now() - inicioAcoes) / 1000).toFixed(1) });
          melhoriasFeitas[d.melhoria.id] = true;
          economiaAtual = depois;
          acao = 'comprar ' + d.melhoria.nome + ' (nível ' + nivel(depois) + ')';
        } else {
          // Se a compra não pegou, não insiste para sempre: marca e segue jogando.
          melhoriasFeitas[d.melhoria.id] = true;
          acao = 'tentei comprar ' + d.melhoria.nome + ' (não pegou)';
        }
      } else if (d.tipo === 'semente') {
        // UM toque só: clique + tap no mesmo lugar pode alternar a aba de volta.
        await acionar(pagina, d.alvo, false);
        sementePendente = { indice: d.semente.indice, nome: d.semente.nome, desde: Date.now() };
        acao = 'aba da semente ' + d.semente.nome;
      } else if (d.tipo === 'toque') {
        const noBico = d.alvo === ALVO.bico;
        if (noBico) {
          // RAJADA: um toque a cada BICO.intervalo, durante BICO.rajadaMs. `acionar` dá clique +
          // tap (dois eventos por toque), então aqui é só clique — o tap duplicaria o toque.
          const inicioRajada = Date.now();
          let naRajada = 0;
          while (Date.now() - inicioRajada < BICO.rajadaMs) {
            await pagina.mouse.click(ponto(ALVO.bico).x, ponto(ALVO.bico).y);
            naRajada += 1;
            await pagina.waitForTimeout(BICO.intervalo);
          }
          bicosDados += naRajada;
          acao = 'rajada de ' + naRajada + ' bicos (+' + naRajada + ' moedas)';
        } else {
          await acionar(pagina, d.alvo);
          acao = 'toque em ' + d.alvo.x + ',' + d.alvo.y;
        }
        if (d.alvo === ALVO.tutorial || d.alvo === ALVO.titulo) toquesTela += 1;
        // Abertura (splash do estúdio + capa) é só passagem: toque rápido, sem esperar 1 s por
        // toque. Antes o aquecimento comia 10 s dos 45 s de vídeo.
        const abertura = d.alvo === ALVO.titulo && estado.hud <= LIMIAR.hud;
        // O tutorial é um modal: depois do toque, confere se ele REALMENTE saiu da tela.
        // Antes (vídeo de 27/10) o robô achava que estava jogando com o "COMO JOGAR" aberto.
        if (d.alvo === ALVO.tutorial) {
          await pagina.waitForTimeout(600);
          const depois = await pagina.evaluate(MEDIDOR, {
            tutorial: REGIAO_TUTORIAL, titulo: REGIAO_TITULO,
            dialogo: REGIAO_DIALOGO, hud: REGIAO_HUD, celulas: CELULAS
          });
          tutorialFechado = depois.tutorial === 0 && depois.dialogo <= 0.6;
          acao += tutorialFechado ? ' · tutorial saiu da tela' : ' · tutorial AINDA na tela';
          toquesTutorial += 1;
          if (toquesTutorial > 8 && !tutorialFechado) {
            console.error('✘ o tutorial não fechou depois de ' + toquesTutorial + ' toques');
            await contexto.close();
            return 8;
          }
        }
        // Ritmo: a espera da plantação é longa (o tempo do jogo anda ~3x mais devagar sob
        // gravação). Alternar o bico a cada ~1 s mantém a tela viva e as moedas subindo, em vez
        // de 30 s de imagem praticamente parada.
        if (!noBico) await pagina.waitForTimeout(abertura ? 180 : 150);
      }
      const agoraS = Date.now() - inicioAcoes;
      if (estado.tutorial > 0) {
        if (!tutorialDesde) tutorialDesde = agoraS;
      } else if (tutorialDesde) {
        segundosComTutorial += (agoraS - tutorialDesde) / 1000;
        tutorialDesde = 0;
      }
      decisoes.push({
        t: +(agoraS / 1000).toFixed(1),
        tutorial: +estado.tutorial.toFixed(3),
        dialogo: +estado.dialogo.toFixed(3),
        titulo: +estado.titulo.toFixed(3),
        hud: +estado.hud.toFixed(3),
        moedas: economia ? economia.moedas : null,
        verdes: estado.celulas.map((c) => +c.verde.toFixed(3)),
        cascas: estado.celulas.map((c) => +c.branco.toFixed(3)),
        barras: estado.celulas.map((c) => +c.ouroBotao.toFixed(3)),
        motivo: d.motivo, acao
      });
    }
    const estadoFinal = await pagina.evaluate(MEDIDOR, {
      tutorial: REGIAO_TUTORIAL, titulo: REGIAO_TITULO,
      dialogo: REGIAO_DIALOGO, hud: REGIAO_HUD, celulas: CELULAS
    });
    const verdeFinal = estadoFinal.celulas.map((c) => c.id + ':' + c.verde.toFixed(3)).join(' ');
    if (tutorialDesde) segundosComTutorial += (Date.now() - inicioAcoes - tutorialDesde) / 1000;
    // PORTÃO DO TUTORIAL — o dono reprovou o vídeo de 27/10 porque o "COMO JOGAR" nunca saía
    // da tela. Enquanto esse portão existir, um vídeo com o tutorial aberto NÃO é entregue:
    // o gravador falha e o pipeline para aqui.
    // PORTÃO DO JOGO — gravação sem plantio é gravação da capa, não gameplay. Falha aqui, com
    // motivo, em vez de deixar o pipeline recusar depois (o custo é o mesmo; o diagnóstico não).
    if (plantadas === 0) {
      console.error('✘ nenhuma semente foi plantada em ' + op.segundos + ' s: a captura não chegou a jogar'
        + ' (escala dos cliques ' + ESCALA.x.toFixed(3) + 'x' + ESCALA.y.toFixed(3) + ')');
      await contexto.close();
      return 9;
    }
    if (estadoFinal.tutorial > 0) {
      console.error('✘ o tutorial ("COMO JOGAR") ainda está na tela no fim da captura');
      await contexto.close();
      return 8;
    }
    if (segundosComTutorial > op.segundos * 0.2) {
      console.error('✘ o tutorial ficou ' + segundosComTutorial.toFixed(1) + ' s na tela ('
        + Math.round(100 * segundosComTutorial / op.segundos) + '% da captura)');
      await contexto.close();
      return 8;
    }
    if (economiaInicial && economiaAtual) {
      // GANHO ≠ SALDO. Comprar melhoria derruba o saldo e não é prejuízo: o que se mede é
      // (saldo final - saldo inicial) + tudo o que foi gasto. Sem essa conta, o robô que
      // investe apareceria pior que o que não investe.
      const gasto = melhoriasCompras.reduce((s, m) => s + (m.custo || 0), 0);
      // Ganho = saldo final − saldo inicial + TUDO que saiu do bolso (melhorias + sementes).
      const ganho = ganhoDeMoedas(economiaInicial.moedas, economiaAtual.moedas, gasto + gastoSementes);
      console.log('economia: saldo ' + economiaInicial.moedas + ' -> ' + economiaAtual.moedas
        + ' · gasto ' + gasto + ' (melhorias) + ' + gastoSementes + ' (sementes) · GANHO '
        + ganho + ' moedas em ' + op.segundos + ' s ('
        + (ganho / (op.segundos / 60)).toFixed(2) + '/min) · melhorias: '
        + (melhoriasCompras.map((m) => m.nome).join(', ') || 'nenhuma')
        + ' · sementes: ' + (sementesTrocadas.map((s) => s.nome + (s.ok ? '' : '(falhou)')).join(', ') || 'nenhuma'));
      economiaResumo = { gasto, gasto_sementes: gastoSementes, ganho,
        ganho_por_minuto: +(ganho / (op.segundos / 60)).toFixed(2) };
    }
    console.log('tutorial: ficou ' + segundosComTutorial.toFixed(1) + ' s na tela · fechou: '
      + (tutorialFechado ? 'sim' : 'não precisou') + ' · toques nele: ' + toquesTutorial);

    // Um quadro de prova, salvo ao lado do vídeo: serve para conferir a olho o que foi gravado.
    const quadro = op.saida.replace(/\.mp4$/i, '-quadro.png');
    fs.mkdirSync(path.dirname(quadro), { recursive: true });
    await pagina.screenshot({ path: quadro });
    if (economiaResumo) {
      console.log('resumo da economia: ganho ' + economiaResumo.ganho + ' moedas · '
        + economiaResumo.ganho_por_minuto + '/min · gasto em melhorias ' + economiaResumo.gasto);
    }
    console.log('decisões: ' + decisoes.length + ' · plantadas: ' + plantadas +
      ' · colhidas: ' + colhidas + ' · telas de abertura: ' + toquesTela);
    console.log('bicos: ' + bicosDados + ' toques (+' + bicosDados + ' moedas) · '
      + (bicosDados / (op.segundos / 60)).toFixed(1) + ' bicos/min');
    console.log('últimas decisões: ' + JSON.stringify(decisoes.slice(-4)));
    console.log('verde final por célula: ' + verdeFinal);
    // o mesmo relatório vai num JSON, para o validador e o kit usarem sem depender do log
    try {
      fs.writeFileSync(op.saida.replace(/\.mp4$/i, '-decisoes.json'), JSON.stringify({
        decisoes, plantadas, colhidas, telas: toquesTela, bicos: bicosDados,
        bicos_por_minuto: +(bicosDados / (op.segundos / 60)).toFixed(1), verde_final: verdeFinal,
        tutorial_segundos: +segundosComTutorial.toFixed(1), tutorial_fechou: tutorialFechado,
        tutorial_toques: toquesTutorial,
        economia: {
          inicio: economiaInicial,
          fim: economiaAtual,
          resumo: economiaResumo,
          melhorias: melhoriasCompras,
          gasto_sementes: gastoSementes,
          sementes: sementesTrocadas
        },
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
  decidir, ganhoDeMoedas, MELHORIAS, SEMENTES, BICO, LIMIAR, CELULAS, MEDIDOR, REGIAO_HUD,
  REGIAO_TUTORIAL, REGIAO_TITULO, REGIAO_DIALOGO, ALVO
};
