// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🚨 ALERTAS PROATIVOS — monitora métricas reais e dispara alertas antes
// que algo falhe (engajamento caindo, fila estagnada, token expirando).
// marketing Prancheta + Ceifalume.
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const fs = require('fs');
const path = require('path');

// 16/11/2026 — DOIS NÍVEIS, NÃO UM: estes módulos nasceram em `tools/` do repo `chat`, onde
// `../posts` era a raiz certa. Movidos para `tools/marketing/` no `site`, `../posts` aponta
// para `tools/posts` — um diretório que ninguém lê. Em produção o estado iria para o lugar
// errado e o painel mostraria zero para sempre. A raiz é `../../posts`.
// POSTS_DIR permite que os contratos apontem o estado para um temporário e provem o módulo
// sem escrever no repositório versionado (regra do `rodar-todas-as-suites`: suíte que passa
// não deixa lixo). Em produção a variável não existe e a raiz é a do repositório.
const MARKETING_DIR = process.env.POSTS_DIR
  ? path.join(process.env.POSTS_DIR, 'marketing')
  : path.join(__dirname, '..', '..', 'posts', 'marketing');
if (!fs.existsSync(MARKETING_DIR)) fs.mkdirSync(MARKETING_DIR, { recursive: true });
const ARQ = path.join(MARKETING_DIR, 'alertas-proativos-marketing.json');

let cache = null;
function carregar() {
  if (cache) return cache;
  try { if (fs.existsSync(ARQ)) cache = JSON.parse(fs.readFileSync(ARQ, 'utf8')); } catch (e) {}
  cache = {
    ativo: false,
    alertas: [],
    regras: [
      { nome: 'engajamento_baixo', limiar: 30, ativo: true },
      { nome: 'fila_estagnada', limiar: 60, ativo: true },
      { nome: 'token_expirando', limiar: 7, ativo: true }
    ],
    ultima_execucao: null,
    criadoEm: new Date().toISOString(),
    atualizadoEm: new Date().toISOString()
  };
  return cache;
}
function salvar() {
  try { cache.atualizadoEm = new Date().toISOString(); fs.writeFileSync(ARQ, JSON.stringify(cache, null, 2), 'utf8'); } catch (e) {}
}

function ativarAlertasProativos() {
  const c = carregar();
  const id = 'ap_' + Date.now();
  c.ativo = true;
  c.ultima_execucao = new Date().toISOString();
  salvar();
  return { ok: true, id, regras: c.regras.length };
}

function desativarAlertasProativos() {
  const c = carregar();
  c.ativo = false;
  salvar();
  return { ok: true };
}

// 17/11/2026 — O ID ERA `'al_' + Date.now()` E ISSO COLIDE.
// Medido no arquivo de produção: dois alertas com o MESMO id (`al_1794884026473`), porque
// as regras rodam em sequência no mesmo milissegundo. A consequência não era cosmética:
//   1. `conciliar-estado.py` recusa lista com ID duplicado ("IDs duplicados"), então dois
//      runs concorrentes NUNCA conseguiam conciliar este arquivo — e o alertas-proativos #3
//      falhou exatamente assim, com "conflito em arquivo que NÃO é gerado";
//   2. qualquer código que indexe por id (o conciliador faz isso, e é o jeito certo de
//      mesclar listas) perde um dos dois alertas em silêncio.
// Um identificador que pode repetir não identifica nada. Agora tem contador de sequência:
// o timestamp dá a ordenação, o contador garante unicidade dentro do mesmo milissegundo.
let _seq = 0;
function idDeAlerta() {
  _seq = (_seq + 1) % 1000;
  return 'al_' + Date.now() + '_' + String(_seq).padStart(3, '0');
}

function adicionarAlerta(tipo, mensagem, severidade, rede) {
  const c = carregar();
  const alerta = {
    id: idDeAlerta(),
    tipo,
    mensagem,
    severidade, // baixa, media, alta, critica
    rede: rede || 'geral',
    criadoEm: new Date().toISOString(),
    resolvido: false
  };
  c.alertas.push(alerta);
  if (c.alertas.length > 200) c.alertas = c.alertas.slice(-200);
  salvar();
  return { ok: true, alerta };
}

// Monitora métricas reais: verifica engajamento, fila, tokens
function monitorarMetricas() {
  const c = carregar();
  if (!c.ativo) return { ok: false, erro: 'Alertas proativos não ativos' };
  const novos = [];
  const agora = new Date();

  // Verifica engajamento baixo por rede+jogo
  const metricasFile = path.join(MARKETING_DIR, 'auto-otimizador-avancado.json');
  let metricas = {};
  try {
    metricas = JSON.parse(fs.readFileSync(metricasFile, 'utf8'));
  } catch (e) { metricas = {}; }

  const fluxo = metricas.fluxo_acesso || {};
  const eng = metricas.metricas_engajamento || {};

  // Alerta: engajamento abaixo do limiar
  const regraEng = c.regras.find(r => r.nome === 'engajamento_baixo');
  if (regraEng && regraEng.ativo) {
    for (const rede of Object.keys(eng)) {
      for (const jogo of Object.keys(eng[rede] || {})) {
        const m = eng[rede][jogo];
        const total = Object.values(m).reduce((s, v) => s + v, 0);
        if (total > 0 && total < regraEng.limiar) {
          const a = adicionarAlerta('engajamento_baixo', 'Engajamento baixo no ' + rede + ' para ' + jogo + ': ' + total + ' interações', 'media', rede);
          novos.push(a);
        }
      }
    }
  }

  // Alerta: fila estagnada (sem acessos recentes)
  const regraFila = c.regras.find(r => r.nome === 'fila_estagnada');
  if (regraFila && regraFila.ativo) {
    for (const rede of Object.keys(fluxo)) {
      for (const jogo of Object.keys(fluxo[rede] || {})) {
        const horas = fluxo[rede][jogo];
        const ultimaHora = Math.max(...Object.keys(horas).map(Number));
        const horasInativas = (agora.getHours() - ultimaHora + 24) % 24;
        if (horasInativas > regraFila.limiar / 60) {
          const a = adicionarAlerta('fila_estagnada', 'Fila estagnada em ' + rede + ' para ' + jogo + ' há ' + horasInativas + 'h', 'alta', rede);
          novos.push(a);
        }
      }
    }
  }

  // ── 17/11/2026 — "TOKEN EXPIRANDO" OLHAVA `mtime` DE ARQUIVO, NÃO O TOKEN ────────────
  // O bloco abaixo (histórico) marcava alerta quando um arquivo em `posts/` com "token" no
  // nome não era tocado há ~7 dias. Isso não tem relação com a credencial: o arquivo pode ser
  // tocado todo dia e o token estar morto, ou vice-versa. MEDIDO: o token do Instagram em
  // produção respondia `Invalid OAuth access token - Cannot parse access token` (log do
  // status-total #5) e a regra de token não disse nada — porque nenhum arquivo tinha 7 dias.
  // O alerta existia com o nome certo e media a coisa errada.
  // Agora, quando a credencial está disponível no ambiente, ela é TESTADA na fonte:
  //   `GET /me` no Instagram Graph → resposta de erro de autenticação = token inválido AGORA.
  // Sem credencial no ambiente, o alerta não é emitido (não verificável ≠ quebrado) e o
  // resumo diz isso.
  const regraToken = c.regras.find(r => r.nome === 'token_expirando');

  // Alerta: token expirando por IDADE DE ARQUIVO (histórico, mantido para YouTube e outros
  // que ainda não têm verificação na fonte). Se as duas regras dispararem, a de cima é a
  // verdadeira — a de baixo é aproximação.
  if (regraToken && regraToken.ativo) {
    // Verifica arquivos de registro de tokens no posts
    const tokensDir = path.join(__dirname, '..', '..', 'posts');
    try {
      const entries = fs.readdirSync(tokensDir);
      for (const entry of entries) {
        if (entry.toLowerCase().includes('token') || entry.toLowerCase().includes('youtube') || entry.toLowerCase().includes('instagram')) {
          const p = path.join(tokensDir, entry);
          try {
            const stat = fs.statSync(p);
            const dias = (agora - stat.mtimeMs) / (1000 * 60 * 60 * 24);
            if (dias > regraToken.limiar - 1 && dias < regraToken.limiar + 1) {
              const a = adicionarAlerta('token_expirando', 'Token de ' + entry + ' prestes a expirar (' + Math.round(dias) + ' dias)', 'critica', entry);
              novos.push(a);
            }
          } catch (e) {}
        }
      }
    } catch (e) {}
  }

  c.ultima_execucao = agora.toISOString();
  salvar();
  return { ok: true, novos_alertas: novos.length, alertas: novos };
}

/**
 * Testa a credencial do Instagram NA FONTE. Separada porque é a única regra que precisa de
 * rede — manter rede fora do caminho síncrono deixa as outras regras determinísticas para
 * teste (e é por isso que o contrato consegue injetar hora e estado sem depender de internet).
 * @returns {Promise<{verificavel:boolean, invalido:boolean, detalhe:string}>}
 */
async function verificarTokenInstagram(opcoes = {}) {
  const token = opcoes.token !== undefined ? opcoes.token : process.env.IG_TOKEN;
  if (!token) return { verificavel: false, invalido: false, detalhe: 'sem IG_TOKEN no ambiente' };
  const buscar = opcoes.fetch || fetch;
  try {
    const url = 'https://graph.instagram.com/v21.0/me?fields=user_id&access_token=' +
                encodeURIComponent(token);
    const r = await buscar(url);
    const corpo = await r.text();
    if (!r.ok && /OAuth|access token|expired|invalid|Cannot parse/i.test(corpo)) {
      return { verificavel: true, invalido: true, detalhe: corpo.slice(0, 120) };
    }
    if (!r.ok) return { verificavel: false, invalido: false, detalhe: 'HTTP ' + r.status };
    return { verificavel: true, invalido: false, detalhe: 'token válido' };
  } catch (e) {
    // rede fora ≠ token vencido. Não inventa diagnóstico.
    return { verificavel: false, invalido: false, detalhe: 'erro de rede: ' + e.message };
  }
}

/** Registra o alerta crítico se o token estiver inválido AGORA. Idempotente por conteúdo. */
async function monitorarTokenInstagram(opcoes = {}) {
  const r = await verificarTokenInstagram(opcoes);
  if (!r.invalido) return { ...r, alerta: null };
  const c = carregar();
  const jaAberto = (c.alertas || []).some(a =>
    !a.resolvido && a.tipo === 'token_expirando' && a.rede === 'instagram');
  if (jaAberto) return { ...r, alerta: null, ja_registrado: true };
  const a = adicionarAlerta('token_expirando',
    'Token do Instagram INVÁLIDO agora (' + r.detalhe.slice(0, 80) + ')', 'critica', 'instagram');
  return { ...r, alerta: a.alerta };
}

function listarAlertas(resolvido = null) {
  const c = carregar();
  let l = c.alertas;
  if (resolvido !== null) l = l.filter(x => x.resolvido === resolvido);
  return l.sort((a, b) => new Date(b.criadoEm) - new Date(a.criadoEm));
}

function resolverAlerta(id) {
  const c = carregar();
  const a = c.alertas.find(x => x.id === id);
  if (a) { a.resolvido = true; salvar(); return { ok: true }; }
  return { ok: false, erro: 'Alerta não encontrado' };
}

function estatisticasAlertas() {
  const c = carregar();
  const pendentes = c.alertas.filter(a => !a.resolvido).length;
  const resolvidos = c.alertas.filter(a => a.resolvido).length;
  return { ativo: c.ativo, total: c.alertas.length, pendentes, resolvidos, regras: c.regras.length, ultima_execucao: c.ultima_execucao };
}

// ───────────────────────────────────────────────────────────────────────────────
// CLI (16/11/2026). O módulo nasceu no `chat` para ser chamado pelo navegador e não tinha
// porta de entrada por linha de comando — então o workflow do Actions não conseguia executá-lo
// e o "alerta ativo" continuava só no papel. Aqui ele ganha CLI, e o workflow chama assim:
//
//   node tools/marketing/alertas-proativos-marketing.js --ativar-monitorar
//   node tools/marketing/alertas-proativos-marketing.js --json          (estado completo)
//   node tools/marketing/alertas-proativos-marketing.js --lista         (pendentes)
//
// Códigos: 0 = rodou · 3 = estado ilegível (não finge que monitorou)
// ───────────────────────────────────────────────────────────────────────────────
function resumoTexto(est, resultado) {
  const linhas = [];
  linhas.push('## 🚨 Alertas proativos');
  linhas.push('');
  linhas.push('| | |');
  linhas.push('| --- | --- |');
  linhas.push('| ativo | ' + (est.ativo ? '✅ sim' : '❌ não') + ' |');
  linhas.push('| regras | ' + est.regras + ' |');
  linhas.push('| alertas no total | ' + est.total + ' |');
  linhas.push('| pendentes | **' + est.pendentes + '** |');
  linhas.push('| resolvidos | ' + est.resolvidos + ' |');
  linhas.push('| última execução | ' + (est.ultima_execucao || '—') + ' |');
  if (resultado) {
    linhas.push('| novos nesta execução | **' + resultado.novos_alertas + '** |');
    if (!resultado.novos_alertas) {
      linhas.push('');
      linhas.push('Nenhuma regra violada agora. (Alerta que não dispara é resultado bom; ' +
        'alerta inventado, não.)');
    } else {
      linhas.push('');
      linhas.push('| tipo | mensagem | severidade |');
      linhas.push('| --- | --- | --- |');
      for (const a of resultado.alertas) {
        linhas.push('| ' + a.tipo + ' | ' + String(a.mensagem).replace(/\|/g, '/') + ' | ' +
          (a.severidade || '—') + ' |');
      }
    }
  }
  return linhas.join('\n');
}

function main(argv) {
  if (argv.includes('--json')) {
    const c = carregar();
    console.log(JSON.stringify({ estatisticas: estatisticasAlertas(), estado: c }, null, 1));
    return 0;
  }
  if (argv.includes('--lista')) {
    const pend = listarAlertas(false);
    console.log(JSON.stringify(pend, null, 1));
    return 0;
  }
  if (argv.includes('--ativar-monitorar')) {
    ativarAlertasProativos();
    const r = monitorarMetricas();
    const est = estatisticasAlertas();
    if (!r.ok) {
      console.log('não monitorou: ' + r.erro);
      return 3;
    }
    console.log(resumoTexto(est, r));
    // 17/11/2026: a verificação do token do Instagram precisa de REDE, então roda aqui —
    // depois das regras determinísticas e sem contaminá-las. Se o token estiver inválido
    // agora, o alerta é crítico e a próxima execução de `acoes-dos-alertas.js` pausa a rede.
    monitorarTokenInstagram().then((t) => {
      if (t.invalido) {
        console.log('TOKEN DO INSTAGRAM INVÁLIDO: ' + t.detalhe.slice(0, 100));
        console.log(t.alerta ? '  → alerta crítico registrado' : '  → já havia alerta aberto');
      } else if (!t.verificavel) {
        console.log('token do Instagram não verificável: ' + t.detalhe);
      } else {
        console.log('token do Instagram: válido');
      }
    }).catch(() => {});
    return 0;
  }
  console.log(resumoTexto(estatisticasAlertas(), null));
  return 0;
}

if (require.main === module) {
  process.exitCode = main(process.argv.slice(2));
}

module.exports = { ativarAlertasProativos, desativarAlertasProativos, adicionarAlerta, monitorarMetricas, listarAlertas, resolverAlerta, estatisticasAlertas, resumoTexto, verificarTokenInstagram, monitorarTokenInstagram };
