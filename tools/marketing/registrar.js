#!/usr/bin/env node
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 📈 REGISTRADOR — alimenta o auto-otimizador com dados REAIS de cada run do site.
//
// POR QUE EXISTE (16/11/2026):
// O auto-otimizador da Fase 2 sabe calcular melhor horário e cadência — mas ninguém chamava
// `registrarAcesso` nem `registrarEngajamento` fora do navegador do chat. Resultado: o
// otimizador rodava sobre estrutura vazia e "otimizava" o nada. Este arquivo é a ponte:
// os workflows de publicação chamam ele com o que REALMENTE aconteceu no run.
//
// O QUE É DADO REAL AQUI (e o que não é):
//   • acesso   → o horário em que a peça FOI PUBLICADA e quantas peças foram. É medido.
//   • engajamento → curtidas/views/comentários que a API da rede devolveu. Quando a API não é
//     consultada no run, NÃO se inventa número: `registrarEngajamento` só é chamado com o que
//     veio de resposta HTTP. Métrica ausente fica ausente — o otimizador já sabe lidar com
//     `sem_dados` e prefere isso a um zero falso.
//
// Uso (o workflow chama assim):
//   node tools/marketing/registrar.js \
//     --evento publicacao --rede youtube --jogo prancheta --hora 19 \
//     --quantidade 1 --origem schedule
//
//   node tools/marketing/registrar.js \
//     --evento engajamento --rede youtube --jogo prancheta \
//     --metrica views --valor 128 --fonte 'videos.list(part=statistics)'
//
//   node tools/marketing/registrar.js --evento metrica-extra --rede instagram \
//     --jogo prancheta --metrica curtidas --valor 12
//
//   node tools/marketing/registrar.js --resumo        # o que já foi registrado
//
// Códigos: 0 = registrado · 2 = dado inválido (não registra e explica) · 3 = sem módulo
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'use strict';

const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..');
const DIR_MKT = path.join(RAIZ, 'posts', 'marketing');
const ARQ_OPT = path.join(DIR_MKT, 'auto-otimizador-avancado.json');
const ARQ_REG = path.join(DIR_MKT, 'registros-reais.json');

const REDES = ['instagram', 'x', 'nostr', 'gmail', 'threads', 'bluesky', 'youtube',
               'mastodon', 'itch', 'devto', 'tumblr', 'discord', 'telegram'];
const JOGOS = ['ceifalume', 'prancheta', 'ambos'];

function arg(nome, padrao = null) {
  const i = process.argv.indexOf('--' + nome);
  if (i === -1) return padrao;
  const v = process.argv[i + 1];
  return (v === undefined || v.startsWith('--')) ? padrao : v;
}
function flag(nome) { return process.argv.includes('--' + nome); }

function garantirDir() {
  try { fs.mkdirSync(DIR_MKT, { recursive: true }); return true; } catch (e) { return false; }
}

// Lê/escreve o estado do auto-otimizador com o MESMO formato que o módulo usa.
// (Não fazemos require do módulo para não depender de `__dirname` dele; o formato é o contrato.)
function lerOpt() {
  try {
    const d = JSON.parse(fs.readFileSync(ARQ_OPT, 'utf8'));
    d.fluxo_acesso = d.fluxo_acesso || {};
    d.metricas_engajamento = d.metricas_engajamento || {};
    return d;
  } catch (e) {
    return { ativo: true, fluxo_acesso: {}, metricas_engajamento: {}, otimizacoes: [],
             proximoId: 1, criadoEm: new Date().toISOString() };
  }
}
function gravarOpt(d) {
  d.atualizadoEm = new Date().toISOString();
  fs.writeFileSync(ARQ_OPT, JSON.stringify(d, null, 1) + '\n', 'utf8');
}
function lerRegistros() {
  try { return JSON.parse(fs.readFileSync(ARQ_REG, 'utf8')); }
  catch (e) { return { _o_que_e: 'todo registro real já feito (auditoria do otimizador)', registros: [] }; }
}
function gravarRegistros(d) {
  // teto: o arquivo é auditoria, não contador infinito
  if (d.registros.length > 2000) d.registros = d.registros.slice(-2000);
  fs.writeFileSync(ARQ_REG, JSON.stringify(d, null, 1) + '\n', 'utf8');
}

function registrarAcesso(rede, jogo, hora, quantidade, origem) {
  const d = lerOpt();
  d.fluxo_acesso[rede] = d.fluxo_acesso[rede] || {};
  d.fluxo_acesso[rede][jogo] = d.fluxo_acesso[rede][jogo] || {};
  const h = String(hora);
  d.fluxo_acesso[rede][jogo][h] = (d.fluxo_acesso[rede][jogo][h] || 0) + Number(quantidade || 1);
  gravarOpt(d);
  return d.fluxo_acesso[rede][jogo][h];
}

function registrarEngajamento(rede, jogo, metrica, valor) {
  const d = lerOpt();
  d.metricas_engajamento[rede] = d.metricas_engajamento[rede] || {};
  d.metricas_engajamento[rede][jogo] = d.metricas_engajamento[rede][jogo] || {};
  d.metricas_engajamento[rede][jogo][metrica] = Number(valor) || 0;
  gravarOpt(d);
  return d.metricas_engajamento[rede][jogo][metrica];
}

function main() {
  if (!garantirDir()) { console.log('não consegui criar ' + path.relative(RAIZ, DIR_MKT)); return 3; }

  if (flag('resumo')) {
    const d = lerOpt();
    const regs = lerRegistros();
    const linhas = [];
    linhas.push('## 📈 Dados reais registrados');
    linhas.push('');
    const redes = Object.keys(d.fluxo_acesso);
    if (!redes.length) {
      linhas.push('**nenhum acesso registrado ainda** — os workflows de publicação registram no run.');
    } else {
      linhas.push('| rede | jogo | horas cobertas | acessos |');
      linhas.push('| --- | --- | --- | --- |');
      for (const rede of redes) {
        for (const jogo of Object.keys(d.fluxo_acesso[rede])) {
          const horas = d.fluxo_acesso[rede][jogo];
          const total = Object.values(horas).reduce((s, v) => s + Number(v || 0), 0);
          linhas.push('| ' + rede + ' | ' + jogo + ' | ' + Object.keys(horas).length + ' | ' + total + ' |');
        }
      }
    }
    const engRedes = Object.keys(d.metricas_engajamento);
    if (engRedes.length) {
      linhas.push('');
      linhas.push('| rede | jogo | métricas (da API, não estimadas) |');
      linhas.push('| --- | --- | --- |');
      for (const rede of engRedes) {
        for (const jogo of Object.keys(d.metricas_engajamento[rede])) {
          const m = d.metricas_engajamento[rede][jogo];
          linhas.push('| ' + rede + ' | ' + jogo + ' | ' +
            Object.entries(m).map(([k, v]) => k + '=' + v).join(' · ') + ' |');
        }
      }
    }
    linhas.push('');
    linhas.push('**total de registros auditáveis:** ' + (regs.registros || []).length);
    console.log(linhas.join('\n'));
    return 0;
  }

  const evento = arg('evento');
  const rede = arg('rede');
  const jogo = arg('jogo', 'ambos');
  const hora = arg('hora', String(new Date().getHours()));
  const quantidade = arg('quantidade', '1');
  const metrica = arg('metrica');
  const valor = arg('valor');
  const origem = arg('origem', 'run');
  const fonte = arg('fonte', '');

  if (!evento) { console.log('❌ falta --evento (publicacao|engajamento|metrica-extra|resumo)'); return 2; }
  if (!rede) { console.log('❌ falta --rede'); return 2; }
  if (!REDES.includes(rede)) {
    console.log('❌ rede inválida: ' + rede + ' (aceitas: ' + REDES.join(', ') + ')');
    return 2;
  }
  if (!JOGOS.includes(jogo)) {
    console.log('❌ jogo inválido: ' + jogo + ' (aceitos: ' + JOGOS.join(', ') + ')');
    return 2;
  }
  // 17/11/2026 — `ambos` É REGISTRO CEGO, NÃO REGISTRO DUPLO.
  // O otimizador itera `['ceifalume','prancheta']`. Um registro com jogo='ambos' entra em
  // `fluxo_acesso[rede]['ambos']` e NUNCA é lido por ninguém: medido em produção, 2 registros
  // de Instagram gravados e `otimizacoes: []` — o Instagram trabalhou e o otimizador não viu.
  // Pior: os dois jogos têm prioridade igual por regra do dono, então registrar "ambos" também
  // impede saber qual jogo o público procurou.
  // Agora a postagem em que os DOIS aparecem grava um registro PARA CADA JOGO. É honesto: a
  // peça falou dos dois, então os dois ganham o ponto de acesso naquela hora.

  const regs = lerRegistros();
  const registro = { quando: new Date().toISOString(), evento, rede, jogo, origem, fonte };

  if (evento === 'publicacao') {
    // peça que fala dos dois jogos conta para os dois (prioridade igual, registros separados)
    // ATENÇÃO: UMA chamada por jogo. A primeira versão chamava `registrarAcesso` no laço E
    // no `total`, contando 2× a mesma peça (o contrato pegou: esperava 2, viu 4). O total
    // vem do primeiro jogo só para a mensagem — não soma de novo.
    const jogos = jogo === 'ambos' ? ['ceifalume', 'prancheta'] : [jogo];
    let total = null;
    for (const j of jogos) {
      const r = registrarAcesso(rede, j, hora, quantidade, origem);
      if (total === null) total = r;
    }
    registro.tipo = 'acesso';
    registro.hora = Number(hora);
    registro.quantidade = Number(quantidade);
    registro.acumulado_na_hora = total;
    regs.registros.push(registro);
    gravarRegistros(regs);
    console.log('✅ acesso registrado: ' + rede + '/' + jogo + ' hora ' + hora +
      ' → acumulado ' + total + ' (origem: ' + origem + ')');
    return 0;
  }

  if (evento === 'engajamento' || evento === 'metrica-extra') {
    if (!metrica || valor === null) {
      console.log('❌ engajamento exige --metrica e --valor (número que veio da API)');
      return 2;
    }
    if (!/^-?\d+(\.\d+)?$/.test(String(valor))) {
      console.log('❌ --valor precisa ser número; veio "' + valor + '"');
      return 2;
    }
    const v = registrarEngajamento(rede, jogo, metrica, valor);
    registro.tipo = 'engajamento';
    registro.metrica = metrica;
    registro.valor = Number(valor);
    regs.registros.push(registro);
    gravarRegistros(regs);
    console.log('✅ engajamento registrado: ' + rede + '/' + jogo + ' ' + metrica + '=' + v +
      (fonte ? ' (fonte: ' + fonte + ')' : ''));
    return 0;
  }

  console.log('❌ evento desconhecido: ' + evento);
  return 2;
}

if (require.main === module) process.exitCode = main();
module.exports = { registrarAcesso, registrarEngajamento, REDES, JOGOS };
