#!/usr/bin/env node
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🔄 VERIFICAR E AGIR — TOKEN DO INSTAGRAM
// Verifica de verdade se o token do Instagram está vivo e, se expirou, dispara alerta
// e pausa a rede automaticamente (12h). Zero intervenção humana.
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'use strict';

const path = require('path');

// Carrega os módulos do próprio diretório
const verificarToken = require('./verificar-token-instagram.js');
const alertas = require('./alertas-proativos-marketing.js');
const acoes = require('./acoes-dos-alertas.js');

const REDE = 'instagram';

async function main() {
  // ─── 1. Ativa os alertas proativos (garante que o sistema está ligado) ───
  const ativo = alertas.ativarAlertasProativos();
  console.log('🚨 Alertas proativos: ' + (ativo.ok ? 'ativos (' + ativo.regras + ' regras)' : 'erro'));

  // ─── 2. Verifica de verdade se o token está vivo ───
  console.log('');
  console.log('🔐 Verificando token do Instagram...');
  await verificarToken.verificar();

  const r = verificarToken.resultado;
  console.log('');
  console.log('━ Resultado da verificação ━');
  console.log('   veredito: ' + r.veredito);
  console.log('   código:   ' + r.codigo);
  console.log('   token expirado: ' + r.tokenExpirado);

  // ─── 3. Se expirou, dispara alerta e executa ação automática ───
  if (r.codigo === 4 || r.tokenExpirado) {
    console.log('');
    console.log('🚨 TOKEN EXPIRADO — disparando alerta e ação automática...');

    const alerta = alertas.adicionarAlerta(
      'token_expirando',
      'Token do Instagram expirou/revogado pelo Graph API. Rede pausada automaticamente por 12h.',
      'critica',
      REDE
    );
    console.log('   alerta criado: id=' + alerta.alerta.id + ' severidade=' + alerta.alerta.severidade);

    const exec = acoes.executarAcoes({ agora: new Date() });
    console.log('   ações tomadas: ' + exec.acionados_agora);
    for (const a of exec.acoes) {
      console.log('   • ' + a.tipo_alerta + ' (' + a.rede + ') → ' +
        (a.pausou_ate ? 'pausa até ' + a.pausou_ate.slice(11, 16) + 'Z' : 'aviso'));
    }

    // ─── 4. Confirma que o portão vai bloquear ───
    const pausa = acoes.redePausada(REDE, { agora: new Date() });
    console.log('');
    console.log('🚦 Portão do Instagram — rede pausada agora: ' +
      (pausa.pausada ? 'SIM (' + pausa.motivo + ', ' + pausa.restam_min + ' min restantes)' : 'não'));

    process.exitCode = 0;
    return;
  }

  if (r.codigo === 2) {
    console.log('');
    console.log('⚠️  FALTA CREDENCIAL — IG_TOKEN não definido.');
    console.log('   Não é possível verificar se o token expirou sem a credencial.');
    process.exitCode = 2;
    return;
  }

  if (r.codigo === 3) {
    console.log('');
    console.log('⚠️  GRAPH API NÃO ALCANÇÁVEL — problema de rede, não de token.');
    console.log('   Não se gera token novo por causa disto.');
    process.exitCode = 3;
    return;
  }

  // ─── 5. Token válido ───
  console.log('');
  console.log('✅ Token do Instagram válido — nada a fazer.');
  process.exitCode = 0;
}

main().catch((e) => {
  console.error('❌ falha inesperada: ' + e.message);
  process.exitCode = 3;
});
