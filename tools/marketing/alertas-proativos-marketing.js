// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🚨 ALERTAS PROATIVOS — monitora métricas reais e dispara alertas antes
// que algo falhe (engajamento caindo, fila estagnada, token expirando).
// marketing Prancheta + Ceifalume.
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const fs = require('fs');
const path = require('path');

const MARKETING_DIR = path.join(__dirname, '..', 'posts', 'marketing');
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

function adicionarAlerta(tipo, mensagem, severidade, rede) {
  const c = carregar();
  const alerta = {
    id: 'al_' + Date.now(),
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

  // Alerta: token expirando (verifica se há arquivo de tokens com datas)
  const regraToken = c.regras.find(r => r.nome === 'token_expirando');
  if (regraToken && regraToken.ativo) {
    // Verifica arquivos de registro de tokens no posts
    const tokensDir = path.join(__dirname, '..', 'posts');
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
    return 0;
  }
  console.log(resumoTexto(estatisticasAlertas(), null));
  return 0;
}

if (require.main === module) {
  process.exitCode = main(process.argv.slice(2));
}

module.exports = { ativarAlertasProativos, desativarAlertasProativos, adicionarAlerta, monitorarMetricas, listarAlertas, resolverAlerta, estatisticasAlertas, resumoTexto };
