#!/usr/bin/env node
/**
 * AÇÕES DOS ALERTAS — porque alerta que só aparece no JSON não é alerta, é diário.
 *
 * O DEFEITO QUE ESTE ARQUIVO FECHA (17/11/2026):
 * `alertas-proativos-marketing.js` detectava três tipos de problema e fazia `push` num array.
 * Nada acontecia. Um `token_expirando` de severidade `critica` ficava registrado no
 * `posts/marketing/alertas-proativos-marketing.json` e a publicação continuava tentando usar
 * o token morto, run após run, até alguém olhar o arquivo. O briefing chama isso de "alerta
 * acionável" e o pedido é explícito: pelo menos UMA ação automática provada.
 *
 * REGRAS DE DESENHO — o que este motor NÃO faz:
 *   • não inventa diagnóstico: só age sobre o que o alerta afirma;
 *   • não sai disparando post: as ações são as duas que são reversíveis e seguras —
 *     PAUSAR uma rede por tempo limitado, e AVISAR quem precisa saber;
 *   • não engole o que fez: toda ação fica registrada em `acoes_tomadas`, com data, motivo
 *     e o id do alerta que a causou, no mesmo arquivo de estado.
 *
 * A pausa é um ARQUIVO (`posts/marketing/redes-pausadas.json`) que o portão de publicação lê.
 * Pausar publicando dentro do código exigiria que o portão importasse este módulo, criando
 * dependência circular; um arquivo de estado é o contrato mais simples e auditável.
 */
'use strict';

const fs = require('fs');
const path = require('path');

// No chat-clone este módulo vive em tools/ (raiz: __dirname/../posts).
// No site repo vive em tools/marketing/ (raiz: __dirname/../../posts).
// POSTS_DIR vence quando definido (contratos); senão sobe um nível a partir de tools/.
const POSTS_DIR = process.env.POSTS_DIR || path.join(__dirname, '..', 'posts');
const ARQ_ALERTAS = path.join(POSTS_DIR, 'marketing', 'alertas-proativos-marketing.json');
const ARQ_PAUSAS = path.join(POSTS_DIR, 'marketing', 'redes-pausadas.json');

function lerJson(arq, padrao) {
  try {
    if (fs.existsSync(arq)) {
      const d = JSON.parse(fs.readFileSync(arq, 'utf8'));
      if (d && typeof d === 'object') return d;
    }
  } catch (e) { /* arquivo ilegível: usa o padrão e NÃO apaga o original */ }
  return padrao;
}

function salvarJson(arq, obj) {
  try {
    fs.mkdirSync(path.dirname(arq), { recursive: true });
    fs.writeFileSync(arq, JSON.stringify(obj, null, 2), 'utf8');
    return true;
  } catch (e) { return false; }
}

// ── Regras: cada tipo de alerta sabe o que fazer. Nada implícito. ────────────────────────
// `pausarHoras` curto de propósito: pausa é freio de mão, não desligamento. Se o problema
// persistir, o próximo alerta pausa de novo — e o dono vê um histórico de pausas, que é
// informação melhor que uma rede silenciosamente desligada.
const REGRAS = {
  token_expirando: {
    descricao: 'credencial vencida: pausa a rede afetada e avisa',
    // token ruim não melhora publicando; insistir só gasta tentativa e polui o feed de erro
    pausarHoras: 12,
    avisar: true,
  },
  fila_estagnada: {
    descricao: 'rede parada: pausa 1h para não empilhar tentativa em cima de fila travada',
    pausarHoras: 1,
    avisar: true,
  },
  engajamento_baixo: {
    descricao: 'audiência baixa: NÃO pausa (o problema é conteúdo, não disponibilidade); avisa',
    pausarHoras: 0,
    avisar: true,
  },
};

function redeDoAlerta(a) {
  // `rede` vem preenchido nos alertas de rede; nos de token vem o nome do arquivo
  const r = String(a.rede || 'geral').toLowerCase();
  for (const conhecida of ['instagram', 'youtube', 'x', 'nostr', 'gmail', 'threads',
                           'bluesky', 'mastodon', 'devto', 'tumblr', 'discord']) {
    if (r.includes(conhecida)) return conhecida;
  }
  return r;
}

/**
 * Executa as ações devidas para os alertas AINDA NÃO acionados.
 * Idempotente por `alertas_acionados`: rodar duas vezes não pausa duas vezes.
 * @param {object} opcoes - { agora: Date } para teste determinístico
 */
function executarAcoes(opcoes = {}) {
  const agora = opcoes.agora instanceof Date ? opcoes.agora : new Date();
  const estado = lerJson(ARQ_ALERTAS, { ativo: false, alertas: [], acoes_tomadas: [] });
  if (!Array.isArray(estado.alertas)) estado.alertas = [];
  if (!Array.isArray(estado.acoes_tomadas)) estado.acoes_tomadas = [];
  if (!Array.isArray(estado.alertas_acionados)) estado.alertas_acionados = [];

  const pausas = lerJson(ARQ_PAUSAS, { pausas: {} });
  if (!pausas.pausas || typeof pausas.pausas !== 'object') pausas.pausas = {};

  const acionados = new Set(estado.alertas_acionados);
  const tomadas = [];
  const ignorados = [];

  for (const a of estado.alertas) {
    if (!a || a.resolvido) continue;
    if (acionados.has(a.id)) continue;
    const regra = REGRAS[a.tipo];
    if (!regra) {
      // tipo sem regra NÃO é acionado em silêncio: fica visível no resultado
      ignorados.push({ id: a.id, tipo: a.tipo, motivo: 'sem regra de ação definida' });
      continue;
    }
    const rede = redeDoAlerta(a);
    const acao = {
      alerta_id: a.id,
      tipo_alerta: a.tipo,
      rede,
      quando: agora.toISOString(),
      pausou_ate: null,
      avisou: false,
      descricao: regra.descricao,
    };

    if (regra.pausarHoras > 0) {
      const ate = new Date(agora.getTime() + regra.pausarHoras * 3600 * 1000);
      // se já há pausa mais longa vigente, NÃO encurta — a mais conservadora manda
      const atual = pausas.pausas[rede] && pausas.pausas[rede].ate;
      const atualMs = atual ? new Date(atual).getTime() : 0;
      const escolhido = Math.max(ate.getTime(), atualMs);
      pausas.pausas[rede] = {
        ate: new Date(escolhido).toISOString(),
        motivo: a.tipo,
        alerta_id: a.id,
        desde: new Date(escolhido - regra.pausarHoras * 3600 * 1000).toISOString(),
      };
      acao.pausou_ate = new Date(escolhido).toISOString();
    }
    if (regra.avisar) acao.avisou = true;   // a notificação real é o resumo do run

    estado.acoes_tomadas.push(acao);
    acionados.add(a.id);
    tomadas.push(acao);
  }

  // histórico não cresce para sempre: mantém as 200 últimas (mesmo teto dos alertas)
  if (estado.acoes_tomadas.length > 200) estado.acoes_tomadas = estado.acoes_tomadas.slice(-200);
  estado.alertas_acionados = [...acionados].slice(-400);
  estado.acoes_atualizado_em = agora.toISOString();

  salvarJson(ARQ_ALERTAS, estado);
  salvarJson(ARQ_PAUSAS, pausas);

  return { ok: true, acoes: tomadas, ignorados, acionados_agora: tomadas.length };
}

/** Uma rede está pausada AGORA? Usado pelo portão de publicação. */
function redePausada(rede, opcoes = {}) {
  const agora = opcoes.agora instanceof Date ? opcoes.agora : new Date();
  const p = lerJson(ARQ_PAUSAS, { pausas: {} });
  const reg = p.pausas && p.pausas[rede];
  if (!reg || !reg.ate) return { pausada: false };
  const ms = new Date(reg.ate).getTime() - agora.getTime();
  if (!(ms > 0)) return { pausada: false, expirada: true, motivo: reg.motivo };
  return {
    pausada: true,
    motivo: reg.motivo,
    alerta_id: reg.alerta_id,
    restam_min: Math.round(ms / 60000),
    ate: reg.ate,
  };
}

function limparPausasVencidas(opcoes = {}) {
  const agora = opcoes.agora instanceof Date ? opcoes.agora : new Date();
  const p = lerJson(ARQ_PAUSAS, { pausas: {} });
  let removidas = 0;
  for (const rede of Object.keys(p.pausas || {})) {
    if (!(new Date(p.pausas[rede].ate).getTime() > agora.getTime())) {
      delete p.pausas[rede];
      removidas++;
    }
  }
  if (removidas) salvarJson(ARQ_PAUSAS, p);
  return { ok: true, removidas };
}

function resumo() {
  const estado = lerJson(ARQ_ALERTAS, { alertas: [], acoes_tomadas: [] });
  const p = lerJson(ARQ_PAUSAS, { pausas: {} });
  const agora = new Date();
  const vigentes = Object.entries(p.pausas || {})
    .filter(([, v]) => new Date(v.ate).getTime() > agora.getTime())
    .map(([rede, v]) => `${rede} até ${v.ate.slice(11, 16)}Z (${v.motivo})`);
  const linhas = [];
  linhas.push('| | |');
  linhas.push('| --- | --- |');
  linhas.push(`| alertas acionados | ${(estado.alertas_acionados || []).length} |`);
  linhas.push(`| ações registradas | ${(estado.acoes_tomadas || []).length} |`);
  linhas.push(`| redes pausadas agora | ${vigentes.length ? vigentes.join(' · ') : 'nenhuma'} |`);
  const ultimas = (estado.acoes_tomadas || []).slice(-3).reverse();
  if (ultimas.length) {
    linhas.push('');
    linhas.push('**últimas ações**');
    for (const a of ultimas) {
      linhas.push(`- ${a.quando.slice(0, 16).replace('T', ' ')}Z · ${a.tipo_alerta} (${a.rede})` +
                  (a.pausou_ate ? ` → pausa até ${a.pausou_ate.slice(11, 16)}Z` : ' → aviso'));
    }
  }
  return linhas.join('\n');
}

module.exports = { executarAcoes, redePausada, limparPausasVencidas, resumo, REGRAS };

if (require.main === module) {
  const r = executarAcoes();
  const limpo = limparPausasVencidas();
  if (process.argv.includes('--json')) {
    process.stdout.write(JSON.stringify(r, null, 1) + '\n');
  } else {
    console.log(`ações tomadas agora: ${r.acionados_agora}`);
    for (const a of r.acoes) {
      console.log(`  • ${a.tipo_alerta} (${a.rede}) → ` +
                  (a.pausou_ate ? `pausa até ${a.pausou_ate}` : 'aviso'));
    }
    for (const i of r.ignorados) {
      console.log(`  · ignorado ${i.id} (${i.tipo}): ${i.motivo}`);
    }
    if (!r.acionados_agora && !r.ignorados.length) console.log('  (nenhum alerta pendente)');
    if (limpo.removidas) console.log(`pausas vencidas removidas: ${limpo.removidas}`);
    console.log();
    console.log(resumo());
  }
}
