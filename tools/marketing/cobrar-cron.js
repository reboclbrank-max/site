#!/usr/bin/env node
/**
 * COBRA O CRON — a rede de segurança que o GitHub não oferece.
 *
 * POR QUE ISTO EXISTE (17/11/2026):
 * O briefing pede "3 runs por `schedule` de cada workflow". Medido no repositório `site`:
 * health-check, status-total e alertas-proativos estavam no main há 6h44 com ZERO runs por
 * `schedule`, enquanto o `despertador` (cron de 20 em 20 min) já tinha 99. Não era YAML
 * errado — os três declaravam cron válido e estado `active`.
 *
 * O que estava acontecendo é o que a própria documentação do GitHub diz: cron de Actions
 * NÃO É GARANTIDO. Agendamento em repositório com pouco movimento é enfileirado, atrasa em
 * horário de pico e pode ser descartado; e workflow sem atividade por 60 dias é desligado
 * pelo próprio GitHub. Medido neste repo, a latência entre "workflow existe" e "primeiro run
 * por schedule" variou de 5,4h a 458h.
 *
 * Ou seja: depender de `schedule` para autonomia é depender de um serviço que admite falhar.
 * Este script é o que fecha isso: o `despertador` roda a cada 20 min (e roda de verdade),
 * confere a idade do último run agendado de cada vigia e, se passou do limite, DISPARA.
 * Não inventa execução: só impede que a falta de um tick vire dias de silêncio.
 *
 * Códigos de saída: 0 = todos em dia ou cobrados com sucesso · 2 = alguma cobrança falhou.
 */
'use strict';

const TOKEN = process.env.GH_TOKEN || process.env.GHPAT || '';
const REPO = process.env.REPO_ALVO || 'reboclbrank-max/site';

// O limite é ~2× o intervalo do cron: atraso pequeno é normal e não se cobra.
// (workflow, horas máximas sem run agendado)
const ALVOS = [
  ['health-check.yml', 30],      // cron diário 06:10 UTC
  ['status-total.yml', 26],      // cron 00/13/18 UTC
  ['alertas-proativos.yml', 4],  // cron de hora em hora (00 e 12-23 UTC)
];

async function api(caminho, metodo = 'GET', corpo = null) {
  const r = await fetch('https://api.github.com' + caminho, {
    method: metodo,
    headers: {
      Authorization: 'Bearer ' + TOKEN,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'cobrar-cron-do-site',
      'Content-Type': 'application/json',
    },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const txt = await r.text();
  if (!r.ok) throw new Error(`${metodo} ${caminho} → ${r.status} ${txt.slice(0, 120)}`);
  return txt.trim() ? JSON.parse(txt) : {};
}

(async () => {
  if (!TOKEN) {
    console.log('sem GH_TOKEN: não dá para conferir nem cobrar (não é falha do cron)');
    process.exit(2);
  }
  let falhas = 0;
  let cobrados = 0;   // quantos precisaram de dispatch
  let todos;
  try {
    todos = (await api(`/repos/${REPO}/actions/workflows?per_page=100`)).workflows;
  } catch (e) {
    console.log('não consegui listar os workflows: ' + e.message);
    process.exit(2);
  }
  const porArquivo = {};
  for (const w of todos) porArquivo[w.path.split('/').pop()] = w;

  console.log('workflow                 último `schedule`        limite   ação');
  console.log('-'.repeat(72));
  for (const [arquivo, limiteH] of ALVOS) {
    const w = porArquivo[arquivo];
    if (!w) {
      console.log(`${arquivo.padEnd(24)} AUSENTE DO REPOSITÓRIO`);
      falhas++;
      continue;
    }
    const runs = (await api(`/repos/${REPO}/actions/workflows/${w.id}/runs?per_page=100`)).workflow_runs;
    const agendados = runs.filter((r) => r.event === 'schedule');
    let idade = null;
    if (agendados.length) {
      idade = (Date.now() - new Date(agendados[0].created_at).getTime()) / 3.6e6;
    }
    const idadeTxt = idade === null ? 'NUNCA' : `há ${idade.toFixed(1)}h`;
    let acao = 'em dia';
    if (idade === null || idade > limiteH) {
      try {
        await api(`/repos/${REPO}/actions/workflows/${w.id}/dispatches`, 'POST', { ref: 'main' });
        acao = 'COBRADO (dispatch enviado)';
        cobrados++;
      } catch (e) {
        // 422 = já há execução em andamento para este ref: não é falha
        if (String(e.message).includes('422')) acao = 'já em execução';
        else { acao = 'FALHOU: ' + e.message.slice(0, 40); falhas++; }
      }
    }
    console.log(`${arquivo.padEnd(24)} ${idadeTxt.padEnd(22)} ${String(limiteH + 'h').padEnd(7)}  ${acao}`);
  }
  console.log();
  // A mensagem final precisa refletir o que aconteceu. A primeira versão dizia sempre
  // "CRON EM DIA" mesmo tendo acabado de cobrar os três — resumo que contradiz a tabela
  // acima é pior que resumo nenhum, porque treina o dono a ler só a última linha.
  if (falhas) {
    console.log(`${falhas} pendência(s): a cobrança não pôde ser feita`);
  } else if (cobrados === ALVOS.length) {
    console.log(`NENHUM dos ${ALVOS.length} vigias tinha run agendado: todos foram cobrados agora`);
  } else if (cobrados) {
    console.log(`${cobrados} de ${ALVOS.length} vigias foram cobrados (os outros estão em dia)`);
  } else {
    console.log(`CRON EM DIA: os ${ALVOS.length} vigias rodaram dentro do esperado`);
  }
  process.exit(falhas ? 2 : 0);
})();
