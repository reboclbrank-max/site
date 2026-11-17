// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🚀 AUTO-OTIMIZADOR AVANÇADO — ajusta cadência de postagem com dados reais
// de acesso por rede e jogo. marketing Prancheta + Ceifalume.
// Prioridade igual para ambos os jogos. Zero intervenção humana.
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
const ARQ = path.join(MARKETING_DIR, 'auto-otimizador-avancado.json');

const JOGOS = ['ceifalume', 'prancheta'];
const REDES = ['instagram', 'x', 'nostr', 'gmail', 'threads', 'bluesky', 'youtube'];

let cache = null;

// 17/11/2026 — O DEFEITO QUE MATAVA O OTIMIZADOR EM SILÊNCIO.
// A versão anterior era:
//     try { if (fs.existsSync(ARQ)) cache = JSON.parse(...) } catch (e) {}
//     cache = { ativo: false, fluxo_acesso: {}, ... }      // ← RODAVA SEMPRE
// Ou seja: o arquivo era lido e, na linha seguinte, SOBRESCRITO pelo estado vazio padrão.
// Todo dado real era destruído na primeira leitura de cada processo. O sintoma era cruel:
// gravar e ler na MESMA execução funcionava (o `cache` em memória tinha o dado); num processo
// novo, o histórico sumia. Foi por isso que, em produção, `metricas_engajamento` continuava
// `{}` mesmo com o coletor rodando: o coletor gravava, e o otimizador apagava na leitura.
// O `try` sem `else` é uma armadilha: parece tratar o erro e na verdade descarta o sucesso.
function vazio() {
  return {
    ativo: false,
    fluxo_acesso: {}, // { rede: { jogo: { hora: acessos } } }
    metricas_engajamento: {}, // { rede: { jogo: { curtidas, compartilhamentos, comentarios, cliques } } }
    otimizacoes: [], // histórico de ajustes feitos
    proximoId: 1,
    criadoEm: new Date().toISOString(),
    atualizadoEm: new Date().toISOString()
  };
}

function carregar() {
  if (cache) return cache;
  if (fs.existsSync(ARQ)) {
    try {
      const lido = JSON.parse(fs.readFileSync(ARQ, 'utf8'));
      if (lido && typeof lido === 'object') {
        // completa o que faltar sem apagar o que existe
        cache = Object.assign(vazio(), lido);
        return cache;
      }
    } catch (e) {
      // arquivo ilegível: NÃO o apaga em silêncio — guarda ao lado, como o health check faz
      try { fs.copyFileSync(ARQ, ARQ + '.corrompido-' + Date.now()); } catch (e2) {}
    }
  }
  cache = vazio();
  return cache;
}
function salvar() {
  try { cache.atualizadoEm = new Date().toISOString(); fs.writeFileSync(ARQ, JSON.stringify(cache, null, 2), 'utf8'); } catch (e) {}
}

function ativarAutoOtimizador() {
  const c = carregar();
  const id = 'ao_' + c.proximoId++;
  c.ativo = true;
  salvar();
  return { ok: true, id };
}

function desativarAutoOtimizador() {
  const c = carregar();
  c.ativo = false;
  salvar();
  return { ok: true };
}

// Registra um acesso real (vindo do dashboard, analytics, ou qualquer fonte)
function registrarAcesso(rede, jogo, hora, quantidade) {
  const c = carregar();
  if (!JOGOS.includes(jogo)) return { ok: false, erro: 'Jogo inválido: ' + jogo };
  if (!REDES.includes(rede)) return { ok: false, erro: 'Rede inválida: ' + rede };
  if (!c.fluxo_acesso[rede]) c.fluxo_acesso[rede] = {};
  if (!c.fluxo_acesso[rede][jogo]) c.fluxo_acesso[rede][jogo] = {};
  const chaveHora = String(hora);
  c.fluxo_acesso[rede][jogo][chaveHora] = (c.fluxo_acesso[rede][jogo][chaveHora] || 0) + Number(quantidade || 1);
  salvar();
  return { ok: true, rede, jogo, hora, total: c.fluxo_acesso[rede][jogo][chaveHora] };
}

// Registra métrica de engajamento real
function registrarEngajamento(rede, jogo, metrica, valor) {
  const c = carregar();
  if (!JOGOS.includes(jogo)) jogo = 'ambos';
  if (!c.metricas_engajamento[rede]) c.metricas_engajamento[rede] = {};
  if (!c.metricas_engajamento[rede][jogo]) c.metricas_engajamento[rede][jogo] = {};
  c.metricas_engajamento[rede][jogo][metrica] = Number(valor) || 0;
  salvar();
  return { ok: true, rede, jogo, metrica, valor };
}

// Calcula o melhor horário para uma rede+jogo baseado em dados reais
function melhorHorario(rede, jogo) {
  const c = carregar();
  const dados = c.fluxo_acesso[rede] && c.fluxo_acesso[rede][jogo];
  if (!dados) return { ok: false, erro: 'Sem dados de acesso para ' + rede + '/' + jogo };
  let melhorHora = null;
  let melhorValor = -1;
  for (const [hora, acessos] of Object.entries(dados)) {
    if (acessos > melhorValor) {
      melhorValor = acessos;
      melhorHora = hora;
    }
  }
  return { ok: true, rede, jogo, melhor_horario: melhorHora, acessos: melhorValor, total_pontos: Object.keys(dados).length };
}

// Calcula cadência ideal (intervalo em minutos) baseado em engajamento e acesso
function calcularCadencia(rede, jogo) {
  const c = carregar();
  const fluxo = c.fluxo_acesso[rede] && c.fluxo_acesso[rede][jogo];
  const eng = c.metricas_engajamento[rede] && c.metricas_engajamento[rede][jogo];
  if (!fluxo) return { ok: false, erro: 'Sem dados de fluxo para ' + rede + '/' + jogo };
  const totalAcessos = Object.values(fluxo).reduce((s, v) => s + v, 0);
  const picos = Object.entries(fluxo).filter(([h, v]) => v > totalAcessos * 0.15).length;
  // Se há muitos picos de acesso, pode postar mais frequentemente
  let intervaloMinutos = 120; // padrão: 2h
  if (totalAcessos > 1000) intervaloMinutos = 60;
  else if (totalAcessos > 500) intervaloMinutos = 90;
  else if (totalAcessos < 100) intervaloMinutos = 240;
  // Ajusta baseado em engajamento
  if (eng) {
    const engajamentoTotal = Object.values(eng).reduce((s, v) => s + v, 0);
    if (engajamentoTotal > 500) intervaloMinutos = Math.max(30, intervaloMinutos - 30);
    else if (engajamentoTotal < 50) intervaloMinutos = Math.min(480, intervaloMinutos + 60);
  }
  return { ok: true, rede, jogo, intervalo_minutos: intervaloMinutos, total_acessos: totalAcessos, picos_detectados: picos };
}

// Executa otimização automática para todas as redes+jogos
function executarOtimizacao() {
  const c = carregar();
  if (!c.ativo) return { ok: false, erro: 'Auto-otimizador não ativo' };
  const resultados = [];
  for (const rede of REDES) {
    for (const jogo of JOGOS) {
      const cad = calcularCadencia(rede, jogo);
      if (cad.ok) {
        const mh = melhorHorario(rede, jogo);
        const otim = {
          id: 'opt_' + c.proximoId++,
          rede,
          jogo,
          intervalo_minutos: cad.intervalo_minutos,
          melhor_horario: mh.ok ? mh.melhor_horario : null,
          total_acessos: cad.total_acessos,
          picos: cad.picos_detectados,
          executadoEm: new Date().toISOString()
        };
        c.otimizacoes.push(otim);
        if (c.otimizacoes.length > 500) c.otimizacoes = c.otimizacoes.slice(-500);
        resultados.push(otim);
      }
    }
  }
  salvar();
  return { ok: true, total: resultados.length, otimizacoes: resultados };
}

// Lista todas as otimizações
function listarOtimizacoes(rede = null, jogo = null) {
  const c = carregar();
  let l = c.otimizacoes;
  if (rede) l = l.filter(x => x.rede === rede);
  if (jogo) l = l.filter(x => x.jogo === jogo);
  return l.sort((a, b) => new Date(b.executadoEm) - new Date(a.executadoEm));
}

// Estatísticas
function estatisticasAutoOtimizador() {
  const c = carregar();
  const totalFluxo = Object.values(c.fluxo_acesso).reduce((s, r) => s + Object.values(r).reduce((s2, j) => s2 + Object.values(j).reduce((s3, v) => s3 + v, 0), 0), 0);
  return {
    ativo: c.ativo,
    total_otimizacoes: c.otimizacoes.length,
    total_pontos_acesso: totalFluxo,
    redes_monitoradas: Object.keys(c.fluxo_acesso).length,
    jogos_monitorados: JOGOS,
    ultima_execucao: c.otimizacoes.length > 0 ? c.otimizacoes[c.otimizacoes.length - 1].executadoEm : null
  };
}

module.exports = { ativarAutoOtimizador, desativarAutoOtimizador, registrarAcesso, registrarEngajamento, melhorHorario, calcularCadencia, executarOtimizacao, listarOtimizacoes, estatisticasAutoOtimizador, JOGOS, REDES };
