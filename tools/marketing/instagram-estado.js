#!/usr/bin/env node
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🚦 PORTÃO DO INSTAGRAM — decide se PODE publicar agora, e registra o que publicou.
//
// POR QUE EXISTE (16/11/2026):
// O `publicar-instagram.yml` publicava por cron a cada 30 minutos na janela 9-22h, sempre com
// a MESMA imagem e a MESMA legenda. Isso é duas coisas ruins ao mesmo tempo:
//   1. repetição — a Meta limita conta que repete mídia/conteúdo; e repetir é feio para quem
//      acompanha a conta;
//   2. volume — até 27 posts idênticos por dia, sem nenhum critério.
// O pedido do dono é publicação autônoma, não publicação infinita. Este portão é o critério:
//
//   • intervalo mínimo (padrão 120 min, igual ao YouTube) entre duas publicações;
//   • imagem JÁ publicada não repete (sha256 da URL + legenda);
//   • teto diário (padrão 3) e janela 9-22h de Brasília;
//   • registra media_id devolvido pelo `media_publish` — o registro é a memória.
//
// Uso:
//   node tools/marketing/instagram-estado.js --pode --imagem URL --legenda "texto"
//       → código 0 = PODE (imprime o motivo) · 1 = NÃO PODE (imprime por quê)
//   node tools/marketing/instagram-estado.js --registrar --media-id 123 --imagem URL \
//       --legenda "texto"
//   node tools/marketing/instagram-estado.js --resumo
//   node tools/marketing/instagram-estado.js --conferir   (usado pelos contratos)
//
// Estado: posts/marketing/instagram-publicados.json
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const RAIZ = path.resolve(__dirname, '..', '..');
const DIR = path.join(RAIZ, 'posts', 'marketing');
const ARQ = path.join(DIR, 'instagram-publicados.json');

const INTERVALO_MINIMO_MIN = Number(process.env.IG_INTERVALO_MINUTOS || 120);
const TETO_DIARIO = Number(process.env.IG_TETO_DIARIO || 3);
const JANELA = [9, 22];   // hora de Brasília (0-23)

function arg(nome, padrao = null) {
  const i = process.argv.indexOf('--' + nome);
  if (i === -1) return padrao;
  const v = process.argv[i + 1];
  return (v === undefined || v.startsWith('--')) ? padrao : v;
}
function flag(nome) { return process.argv.includes('--' + nome); }

function ler() {
  try {
    const d = JSON.parse(fs.readFileSync(ARQ, 'utf8'));
    d.publicados = d.publicados || [];
    return d;
  } catch (e) {
    return {
      _o_que_e: 'memória de publicações do Instagram (é o portão contra repetição)',
      intervalo_minimo_minutos: INTERVALO_MINIMO_MIN,
      teto_diario: TETO_DIARIO,
      publicados: [],
    };
  }
}
function gravar(d) {
  fs.mkdirSync(DIR, { recursive: true });
  d.atualizadoEm = new Date().toISOString();
  fs.writeFileSync(ARQ, JSON.stringify(d, null, 1) + '\n', 'utf8');
}

// Impressão da peça: URL da imagem + legenda. É o que a Meta recebe; é o que identifica.
function impressao(imagem, legenda) {
  const chave = String(imagem || '').trim() + '\u0000' + String(legenda || '').trim();
  return crypto.createHash('sha256').update(chave, 'utf8').digest('hex');
}

function horaBrasilia(agora = new Date()) {
  // Brasília é UTC-3 e hoje não tem horário de verão.
  return (agora.getUTCHours() + 24 - 3) % 24;
}
function diaBrasilia(agora = new Date()) {
  const t = new Date(agora.getTime() - 3 * 3600000);
  return t.toISOString().slice(0, 10);
}

// ───────────────────────────────────────────────────────────────────────────────
function podePublicar({ imagem, legenda, agora = new Date() }) {
  const d = ler();
  const motivos = [];

  const hora = horaBrasilia(agora);
  if (hora < JANELA[0] || hora >= JANELA[1]) {
    motivos.push('fora da janela: ' + String(hora).padStart(2, '0') +
      'h de Brasília (janela ' + JANELA[0] + 'h-' + JANELA[1] + 'h)');
  }

  const dia = diaBrasilia(agora);
  const hoje = d.publicados.filter(p => {
    try { return diaBrasilia(new Date(p.quando)) === dia; } catch (e) { return false; }
  });
  if (hoje.length >= TETO_DIARIO) {
    motivos.push('teto diário atingido: ' + hoje.length + '/' + TETO_DIARIO + ' em ' + dia);
  }

  if (d.publicados.length) {
    const ultimo = d.publicados[d.publicados.length - 1];
    const quandoUltimo = new Date(ultimo.quando);
    const minutos = (agora - quandoUltimo) / 60000;
    if (minutos < INTERVALO_MINIMO_MIN) {
      motivos.push('intervalo mínimo: ' + Math.round(minutos) + ' min desde o último post (' +
        INTERVALO_MINIMO_MIN + ' min exigidos)');
    }
  }

  if (imagem || legenda) {
    const imp = impressao(imagem, legenda);
    const repetida = d.publicados.find(p => p.impressao === imp);
    if (repetida) {
      motivos.push('peça repetida: já publicada em ' + repetida.quando +
        ' (media_id ' + repetida.media_id + ')');
    }
  }

  return {
    pode: motivos.length === 0,
    motivos,
    hora_brasilia: hora,
    dia_brasilia: dia,
    publicados_hoje: hoje.length,
    teto_diario: TETO_DIARIO,
    intervalo_minimo_minutos: INTERVALO_MINIMO_MIN,
    ultimo: d.publicados.length ? d.publicados[d.publicados.length - 1].quando : null,
    total: d.publicados.length,
  };
}

function registrar({ mediaId, imagem, legenda, agora = new Date() }) {
  if (!mediaId) return { ok: false, erro: 'sem media_id não há o que registrar' };
  const d = ler();
  const imp = impressao(imagem, legenda);
  if (d.publicados.some(p => p.impressao === imp)) {
    return { ok: false, erro: 'peça já registrada (repetição recusada)', impressao: imp };
  }
  if (d.publicados.some(p => p.media_id === String(mediaId))) {
    return { ok: false, erro: 'media_id já registrado', media_id: mediaId };
  }
  const item = {
    media_id: String(mediaId),
    quando: agora.toISOString(),
    hora_brasilia: horaBrasilia(agora),
    imagem: String(imagem || ''),
    legenda: String(legenda || '').slice(0, 300),
    impressao: imp,
  };
  d.publicados.push(item);
  if (d.publicados.length > 500) d.publicados = d.publicados.slice(-500);
  gravar(d);
  return { ok: true, registrado: item, total: d.publicados.length };
}

function resumo() {
  const d = ler();
  const linhas = ['## 🚦 Portão do Instagram', ''];
  linhas.push('| | |');
  linhas.push('| --- | --- |');
  linhas.push('| publicações registradas | ' + d.publicados.length + ' |');
  linhas.push('| intervalo mínimo | ' + INTERVALO_MINIMO_MIN + ' min |');
  linhas.push('| teto diário | ' + TETO_DIARIO + ' |');
  linhas.push('| janela | ' + JANELA[0] + 'h–' + JANELA[1] + 'h (Brasília) |');
  if (d.publicados.length) {
    linhas.push('| último | ' + d.publicados[d.publicados.length - 1].quando + ' |');
    linhas.push('');
    linhas.push('| quando | media_id | legenda |');
    linhas.push('| --- | --- | --- |');
    for (const p of d.publicados.slice(-8)) {
      linhas.push('| ' + p.quando + ' | `' + p.media_id + '` | ' +
        String(p.legenda || '').replace(/\|/g, '/').slice(0, 60) + ' |');
    }
  } else {
    linhas.push('');
    linhas.push('**nenhuma publicação registrada ainda.**');
  }
  return linhas.join('\n');
}

function main() {
  const imagem = arg('imagem');
  const legenda = arg('legenda');

  if (flag('resumo')) { console.log(resumo()); return 0; }

  if (flag('registrar')) {
    const r = registrar({ mediaId: arg('media-id'), imagem, legenda });
    console.log(r.ok ? '✅ registrado: media_id ' + r.registrado.media_id + ' (' + r.total + ' no total)'
                     : '❌ ' + r.erro);
    return r.ok ? 0 : 1;
  }

  if (flag('pode')) {
    const r = podePublicar({ imagem, legenda });
    if (r.pode) {
      console.log('✅ PODE publicar (' + r.dia_brasilia + ', ' + r.publicados_hoje + '/' +
        r.teto_diario + ' hoje, último: ' + (r.ultimo || 'nenhum') + ')');
      return 0;
    }
    console.log('⛔ NÃO publicar:');
    for (const m of r.motivos) console.log('   • ' + m);
    return 1;
  }

  if (flag('conferir')) {
    // autodiagnóstico usado pelo contrato: a matemática do portão está sã?
    const falsa = new Date('2026-11-16T22:30:00Z');   // 19:30 BRT: dentro da janela
    const r = podePublicar({ imagem: 'x', legenda: 'y', agora: falsa });
    console.log('portão responde: pode=' + r.pode + ' hora=' + r.hora_brasilia);
    return (r.hora_brasilia === 19) ? 0 : 1;
  }

  console.log(resumo());
  return 0;
}

if (require.main === module) process.exitCode = main();
module.exports = { podePublicar, registrar, impressao, horaBrasilia, respondeu: true };
