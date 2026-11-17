#!/usr/bin/env node
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🔐 VERIFICADOR DE TOKEN DO INSTAGRAM — responde de verdade se o token está vivo ou expirou.
// marketing Prancheta + Ceifalume. Prioridade igual para ambos os jogos.
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//
// POR QUE EXISTE (17/11/2026): o Instagram token expirou em produção. O alerta
// `token_expirando` era gravado num JSON e a publicação continuava tentando usar o token
// morto. Alerta que não impede a ação seguinte não é alerta, é anotação.
//
// Este módulo faz três perguntas separadas, exatamente como o verificador do Gmail:
//
//   1. a credencial existe?         (IG_TOKEN definido e não vazio)
//   2. o Graph API é alcançável?    (HTTP ao graph.facebook.com)
//   3. o Graph API ACEITA o token?  (requisição real de /me com o token)
//
// Códigos de saída:
//   0 = token válido
//   2 = falta credencial            → gerar/colar o secret IG_TOKEN
//   3 = não alcança o Graph API     → rede, não é o token
//   4 = alcança e RECUSA o token    → token expirado/revogado → pausar rede 12h
//
// Nunca imprime o token. Imprime só o tamanho e os últimos 4 caracteres mascarados.
'use strict';

const fs = require('fs');
const path = require('path');
const https = require('https');

const HOST = 'graph.facebook.com';
const CAMINHO_ME = '/v21.0/me?fields=id,name&access_token=';

const TOKEN = process.env.IG_TOKEN || '';

const resultado = {
  perguntas: [],
  codigo: 0,
  veredito: '',
  tokenExpirado: false,
};

function anota(pergunta, ok, detalhe) {
  resultado.perguntas.push({ pergunta, ok, detalhe });
  console.log((ok ? '✅' : '❌') + ' ' + pergunta + ' — ' + detalhe);
}

function httpGet(caminho, token, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    const opcoes = {
      hostname: HOST,
      port: 443,
      path: caminho,
      method: 'GET',
      timeout: timeoutMs,
      headers: { 'User-Agent': 'verificar-token-instagram/1.0' },
    };
    const req = https.request(opcoes, (res) => {
      let dados = '';
      res.on('data', (c) => { dados += c; });
      res.on('end', () => {
        resolve({ status: res.statusCode, body: dados });
      });
    });
    req.on('error', (e) => { reject(e); });
    req.on('timeout', () => { req.destroy(new Error('timeout ' + timeoutMs + 'ms')); });
    req.end();
  });
}

// ─── 1. credencial ───────────────────────────────────────────────────────────
if (!TOKEN) {
  anota('a credencial existe?', false, 'falta IG_TOKEN');
  resultado.codigo = 2;
  resultado.veredito = 'FALTA_CREDENCIAL';
} else {
  const tamanho = TOKEN.length;
  const ultimos = TOKEN.slice(-4);
  const mascarado = '*'.repeat(Math.max(0, tamanho - 4)) + ultimos;
  anota('a credencial existe?', true, 'IG_TOKEN com ' + tamanho + ' caracteres: ' + mascarado);
}

// ─── 2 e 3. alcança o Graph? ele aceita o token? ─────────────────────────────
async function main() {
  // Sem credencial não se testa conexão: a pergunta 1 já respondeu o que importa.
  if (resultado.codigo !== 0) {
    finalizar();
    return;
  }

  let alcançou = false;
  let loginOk = false;
  let motivo = '';

  try {
    const caminho = CAMINHO_ME + encodeURIComponent(TOKEN);
    const r = await httpGet(caminho, TOKEN);
    alcançou = true;
    if (r.status === 200) {
      try {
        const d = JSON.parse(r.body);
        if (d.id && !d.error) {
          loginOk = true;
          motivo = 'token aceito pelo Graph API (usuário: ' + (d.name || 'desconhecido') + ')';
        } else {
          motivo = 'Graph respondeu 200 mas sem id válido: ' + JSON.stringify(d).slice(0, 120);
        }
      } catch (e) {
        motivo = 'resposta 200 não é JSON: ' + r.body.slice(0, 120);
      }
    } else {
      try {
        const d = JSON.parse(r.body);
        const msg = (d.error && d.error.message) || '';
        const tipo = (d.error && d.error.type) || '';
        motivo = 'HTTP ' + r.status + ' — ' + tipo + ': ' + msg;
        if (/OAuth|token|expired|revoked|invalid/i.test(msg + tipo)) {
          resultado.tokenExpirado = true;
        }
      } catch (e) {
        motivo = 'HTTP ' + r.status + ' (corpo não é JSON)';
        if (r.status === 401) resultado.tokenExpirado = true;
      }
    }
  } catch (e) {
    alcançou = false;
    motivo = 'não conectou em ' + HOST + ':443 (' + (e.code || e.message) + ')';
  }

  if (alcançou) {
    if (loginOk) {
      anota('o servidor aceita o token?', true, motivo);
      resultado.codigo = 0;
      resultado.veredito = 'OK';
    } else {
      anota('o servidor aceita o token?', false, motivo);
      resultado.codigo = 4;
      resultado.veredito = 'TOKEN_EXPIRADO';
    }
  } else {
    anota('o servidor é alcançável?', false, motivo);
    resultado.codigo = 3;
    resultado.veredito = 'GRAPH_NAO_ALCANCADO';
  }

  finalizar();
}

function finalizar() {
  const acao = {
    0: 'nada a fazer — token válido',
    2: 'colar o secret IG_TOKEN (ver COMO-RESOLVER-IG.md, passo 2)',
    3: 'é rede, não o token — não gere token novo por causa disto',
    4: 'TOKEN EXPIRADO: gerar token novo e regravar IG_TOKEN; rede pausada 12h',
  }[resultado.codigo] || 'ver detalhe acima';

  console.log('');
  console.log('veredito: ' + resultado.veredito);
  console.log('próximo passo: ' + acao);
  process.exitCode = resultado.codigo;
}

main().catch((e) => {
  console.error('falha inesperada: ' + e.message);
  resultado.codigo = 3;
  resultado.veredito = 'ERRO_INESPERADO';
  finalizar();
});

module.exports = { verificar: main, resultado };
