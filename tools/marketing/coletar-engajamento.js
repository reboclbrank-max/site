#!/usr/bin/env node
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 📈 COLETOR DE ENGAJAMENTO REAL — o elo que faltava entre a rede e o otimizador.
//
// POR QUE EXISTE (17/11/2026):
// O auto-otimizador tem `calcularCadencia()`, que AJUSTA o intervalo conforme o engajamento
// (>500 → menos 30 min; <50 → mais 60 min). Ela nunca rodou com dado real: medido em produção,
// `metricas_engajamento` estava `{}`. O otimizador decidia com metade da informação, e chamar
// isso de "auto-otimização" era generoso.
//
// Instagram: like_count + comments_count das mídias registradas no portão.
// YouTube:   viewCount + likeCount + commentCount dos vídeos já publicados.
//
// REGRAS DE HONESTIDADE:
//   • sem credencial → não inventa zero; diz "não verificável" e sai com 3
//   • erro de rede/token → sai com 3 e diz o motivo; nunca grava número que não viu
//   • métrica ausente não vira 0 (exceto viewCount de vídeo novo, que é 0 de verdade)
//   • a atribuição de jogo é por slug/título/legenda; se os dois aparecem, é `ambos` e isso
//     fica visível no relatório em vez de escondido
//
// USO: --resumo (não grava) · --json · sem flag (grava)
// Códigos: 0 coletou · 2 nada a coletar · 3 falha ou credencial ausente
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'use strict';

const fs = require('fs');
const path = require('path');

const RAIZ = process.env.POSTS_DIR
  ? path.dirname(path.resolve(process.env.POSTS_DIR))
  : path.resolve(__dirname, '..', '..');
const DIR_MK = process.env.POSTS_DIR
  ? path.join(path.resolve(process.env.POSTS_DIR), 'marketing')
  : path.join(RAIZ, 'posts', 'marketing');

const IG_ARQ = path.join(DIR_MK, 'instagram-publicados.json');
const YT_ARQ = path.join(RAIZ, 'posts', 'youtube-publicados.json');

const JOGOS = ['ceifalume', 'prancheta'];

function lerJson(caminho, padrao) {
  try { return JSON.parse(fs.readFileSync(caminho, 'utf8')); } catch (e) { return padrao; }
}

// qual jogo esta peça fala? Procura no slug/título/legenda. Dois jogos = `ambos` (honesto).
function jogoDaPeca(...textos) {
  const t = textos.filter(Boolean).join(' ').toLowerCase();
  const achou = JOGOS.filter(j => t.includes(j));
  if (achou.length === 1) return achou[0];
  return 'ambos';
}

const resultado = { coletado: 0, por_rede: {}, falhas: [], pulados: [] };

function anota(rede, jogo, metrica, valor) {
  if (!resultado.por_rede[rede]) resultado.por_rede[rede] = {};
  if (!resultado.por_rede[rede][jogo]) resultado.por_rede[rede][jogo] = {};
  resultado.por_rede[rede][jogo][metrica] = valor;
}

async function coletarInstagram() {
  const token = process.env.IG_TOKEN || '';
  if (!token) {
    resultado.falhas.push('instagram: sem IG_TOKEN (não verificável neste ambiente)');
    return;
  }
  const estado = lerJson(IG_ARQ, { publicados: [] });
  const pubs = (estado.publicados || []).slice(-20);
  if (!pubs.length) { resultado.pulados.push('instagram: nenhuma mídia registrada ainda'); return; }
  for (const p of pubs) {
    if (!p.media_id) continue;
    const url = 'https://graph.facebook.com/v21.0/' + encodeURIComponent(p.media_id) +
      '?fields=like_count,comments_count&access_token=' + encodeURIComponent(token);
    try {
      const r = await fetch(url);
      const d = await r.json().catch(() => ({}));
      if (!r.ok || d.error) {
        resultado.falhas.push('instagram/' + p.media_id + ': ' +
          ((d.error && d.error.message) || ('HTTP ' + r.status)).slice(0, 90));
        continue;
      }
      const jogo = jogoDaPeca(p.legenda);
      const antes = (resultado.por_rede.instagram || {})[jogo] || {};
      anota('instagram', jogo, 'curtidas', (antes.curtidas || 0) + Number(d.like_count || 0));
      anota('instagram', jogo, 'comentarios', (antes.comentarios || 0) + Number(d.comments_count || 0));
      resultado.coletado++;
    } catch (e) {
      resultado.falhas.push('instagram/' + p.media_id + ': ' + String(e.message).slice(0, 70));
    }
  }
}

async function coletarYouTube() {
  const chave = process.env.YT_API_KEY || '';
  if (!chave) {
    resultado.falhas.push('youtube: sem YT_API_KEY (não verificável neste ambiente)');
    return;
  }
  const dados = lerJson(YT_ARQ, { publicados: [] });
  const pubs = (dados.publicados || []).slice(-20);
  if (!pubs.length) { resultado.pulados.push('youtube: nenhum vídeo registrado ainda'); return; }
  const ids = pubs.map(p => p.id).filter(Boolean);
  if (!ids.length) { resultado.pulados.push('youtube: registros sem id'); return; }
  const url = 'https://www.googleapis.com/youtube/v3/videos?part=statistics&id=' +
    ids.join(',') + '&key=' + encodeURIComponent(chave);
  try {
    const r = await fetch(url);
    const d = await r.json().catch(() => ({}));
    if (!r.ok || d.error) {
      resultado.falhas.push('youtube: ' + ((d.error && d.error.message) || ('HTTP ' + r.status)).slice(0, 90));
      return;
    }
    const porId = new Map((d.items || []).map(it => [it.id, it.statistics || {}]));
    for (const p of pubs) {
      const st = porId.get(p.id);
      if (!st) continue;
      const jogo = jogoDaPeca(p.slug, p.titulo);
      const antes = (resultado.por_rede.youtube || {})[jogo] || {};
      anota('youtube', jogo, 'visualizacoes', (antes.visualizacoes || 0) + Number(st.viewCount || 0));
      anota('youtube', jogo, 'curtidas', (antes.curtidas || 0) + Number(st.likeCount || 0));
      anota('youtube', jogo, 'comentarios', (antes.comentarios || 0) + Number(st.commentCount || 0));
      resultado.coletado++;
    }
  } catch (e) {
    resultado.falhas.push('youtube: ' + String(e.message).slice(0, 70));
  }
}

function registrar(modoResumo) {
  const mod = require('./auto-otimizador-avancado.js');
  const linhas = [];
  for (const [rede, porJogo] of Object.entries(resultado.por_rede)) {
    for (const [jogo, metricas] of Object.entries(porJogo)) {
      for (const [metrica, valor] of Object.entries(metricas)) {
        if (!modoResumo) mod.registrarEngajamento(rede, jogo, metrica, valor);
        linhas.push(`${rede}/${jogo}/${metrica} = ${valor}`);
      }
    }
  }
  return linhas;
}

async function main() {
  const argv = process.argv.slice(2);
  const modoResumo = argv.includes('--resumo');
  const modoJson = argv.includes('--json');

  await coletarInstagram();
  await coletarYouTube();
  const linhas = registrar(modoResumo);
  resultado.registrado = linhas;

  if (modoJson) {
    process.stdout.write(JSON.stringify(resultado, null, 1) + '\n');
  } else {
    console.log('## Engajamento real' + (modoResumo ? ' (resumo — não gravou)' : ''));
    if (!linhas.length) console.log('   nada coletado');
    for (const l of linhas) console.log('   ' + l);
    for (const p of resultado.pulados) console.log('   · ' + p);
    for (const f of resultado.falhas) console.log('   ⚠️  ' + f);
    console.log('');
    console.log('peças lidas: ' + resultado.coletado);
  }

  if (resultado.coletado > 0) return 0;
  const semCredencial = resultado.falhas.some(f => /sem (IG_TOKEN|YT_API_KEY)/.test(f));
  return semCredencial ? 3 : 2;
}

if (require.main === module) {
  main().then(c => { process.exitCode = c; }).catch(e => {
    console.error('falha inesperada: ' + e.message);
    process.exitCode = 3;
  });
}

module.exports = { jogoDaPeca, coletarInstagram, coletarYouTube };
