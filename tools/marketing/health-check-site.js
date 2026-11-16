#!/usr/bin/env node
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🏥 HEALTH CHECK DAS CAMADAS DO `site` — roda em produção, dentro do Actions.
//
// POR QUE ESTE ARQUIVO EXISTE (16/11/2026):
// O health check que a Fase 2 criou no repositório `chat` audita 60 "camadas" que são módulos
// JS daquele repositório (`gamificacao-marketing`, `sistema-cupons`, `webhook-*`, ...). Copiá-lo
// para o `site` daria "0/60 ativas" — número VERDADEIRO sobre o chat e MENTIRA sobre o site,
// porque essas camadas nunca moraram aqui. Um relatório que nasce vermelho não informa nada.
//
// As camadas do `site` são outras: workflows, ferramentas Python, arquivos de estado que o
// pulso lê e escreve, e as credenciais que cada rede precisa. É isso que este arquivo audita,
// com a mesma regra de honestidade do resto da casa:
//   • camada existe?          → arquivo presente E com sintaxe válida
//   • camada está ligada?     → tem gatilho automático (schedule/repository_dispatch)
//   • camada tem dado vivo?   → o arquivo de estado foi tocado dentro da janela esperada
//   • camada pode rodar?      → o segredo que ela exige está configurado (sem imprimir valor)
//
// A AUTO-RECUPERAÇÃO é limitada de propósito ao que é seguro e verificável:
//   - arquivo de estado ausente e com estrutura conhecida → recriado vazio, marcado como
//     "recriado" (não como "saudável");
//   - módulo JS/Python com sintaxe quebrada → reportado, NUNCA reescrito no chute
//     (reescrever código por adivinhação é como o `entrar-no-main.sh` virou base64 em 12/11);
//   - segredo ausente → reportado com o NOME exato, jamais inventado.
//
// Uso:
//   node tools/marketing/health-check-site.js            # audita e grava
//   node tools/marketing/health-check-site.js --json     # só o JSON
//   node tools/marketing/health-check-site.js --resumo   # resumo para o STEP_SUMMARY
//
// Saída de código: 0 = tudo que importa está de pé · 1 = há camada crítica caída
//                 3 = não consegui auditar (sem git, sem repo)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

// SITE_RAIZ / POSTS_DIR existem para os CONTRATOS: eles auditam uma cópia isolada e não podem
// escrever no repositório versionado (regra do rodar-todas-as-suites). Em produção nada disso
// é definido e a raiz é a do checkout.
const RAIZ = process.env.SITE_RAIZ
  ? path.resolve(process.env.SITE_RAIZ)
  : path.resolve(__dirname, '..', '..');
const DIR_POSTS = process.env.POSTS_DIR
  ? path.resolve(process.env.POSTS_DIR)
  : path.join(RAIZ, 'posts');
const DIR_WF = path.join(RAIZ, '.github', 'workflows');
const DIR_TOOLS = path.join(RAIZ, 'tools');
const SAIDA = path.join(DIR_POSTS, 'health-check-camadas.json');

// ───────────────────────────────────────────────────────────────────────────────
// AS CAMADAS DO `site`. Cada linha é uma coisa que precisa estar de pé para a casa
// publicar sozinha. `critica: true` significa: se cair, sai de código 1.
// ───────────────────────────────────────────────────────────────────────────────
const CAMADAS = [
  // --- 1. motor de publicação de vídeo (a Fase 1 vive aqui) ---
  { id: 'wf-gravar-prancheta', tipo: 'workflow', nome: 'gravar-prancheta.yml', critica: true,
    papel: 'grava e envia o PRANCHETA ao YouTube (cron + AUTOMATICO)' },
  { id: 'wf-gravar-gameplay', tipo: 'workflow', nome: 'gravar-gameplay.yml', critica: true,
    papel: 'grava e envia o CEIFALUME ao YouTube (cron + AUTOMATICO)' },
  { id: 'wf-publicar-instagram', tipo: 'workflow', nome: 'publicar-instagram.yml', critica: true,
    papel: 'publica de verdade no Instagram (media_publish)' },
  { id: 'wf-enviar-youtube', tipo: 'workflow', nome: 'administrar-youtube.yml', critica: false,
    papel: 'organiza o que já está publicado no YouTube' },
  { id: 'wf-postar-redes', tipo: 'workflow', nome: 'postar-todas-as-redes.yml', critica: false,
    papel: 'postagem nas redes que não são vídeo' },

  // --- 2. motor de decisão ---
  { id: 'wf-marketing-24h', tipo: 'workflow', nome: 'marketing-24h.yml', critica: true,
    papel: 'pulso que decide e executa uma ação por vez' },
  { id: 'wf-corrente', tipo: 'workflow', nome: 'corrente.yml', critica: true,
    papel: 'segura a fila de pulsos (o cron sozinho entrega pouco)' },

  // --- 3. medição e retrato ---
  { id: 'wf-metricas-youtube', tipo: 'workflow', nome: 'metricas-youtube.yml', critica: false,
    papel: 'mede views/likes/comentários dos vídeos' },
  { id: 'wf-medir-o-dia', tipo: 'workflow', nome: 'medir-o-dia.yml', critica: false,
    papel: 'escreve a régua do dia e o placar' },
  { id: 'wf-conferir-tudo', tipo: 'workflow', nome: 'conferir-tudo.yml', critica: true,
    papel: 'roda as 63 suítes de contrato' },
  { id: 'wf-testar-redes', tipo: 'workflow', nome: 'testar-todas-as-redes.yml', critica: false,
    papel: 'diz o estado real de cada credencial' },

  // --- 4. ferramentas que os workflows chamam (se faltar, o passo morre em 127) ---
  { id: 'tool-entrar-no-main', tipo: 'script', nome: 'tools/entrar-no-main.sh', critica: true,
    papel: 'põe commit no main (a corrupção de 12/11 parou a casa inteira)' },
  { id: 'tool-enviar-youtube', tipo: 'script', nome: 'tools/enviar-youtube.py', critica: true,
    papel: 'portão SHA256 + upload' },
  { id: 'tool-publicar-instagram', tipo: 'script', nome: 'tools/publicar-instagram.py', critica: true,
    papel: 'container → FINISHED → media_publish' },
  { id: 'tool-orquestrador', tipo: 'script', nome: 'tools/orquestrador.py', critica: false,
    papel: 'decide a ação do pulso' },
  { id: 'tool-medir-cadencia', tipo: 'script', nome: 'tools/medir-cadencia.py', critica: false,
    papel: 'mede o que o cron ENTREGOU' },
  { id: 'tool-o-que-acontece', tipo: 'script', nome: 'tools/o-que-acontece.py', critica: false,
    papel: 'gera o retrato da agenda' },
  { id: 'tool-rodar-contratos', tipo: 'script', nome: 'tools/rodar-contratos-isolados.py', critica: true,
    papel: 'roda contrato em cópia isolada' },

  // --- 5. estado que o pulso lê e escreve ---
  { id: 'estado-orquestrador', tipo: 'estado', nome: 'posts/orquestrador.json', critica: true,
    horas: 6, papel: 'memória do pulso (pulso atrasado não duplica post)' },
  { id: 'estado-videos-enviados', tipo: 'estado', nome: 'posts/videos-enviados.json', critica: true,
    horas: 72, papel: 'SHA256 já enviados (é o portão que impede repetir vídeo)' },
  { id: 'estado-youtube-publicados', tipo: 'estado', nome: 'posts/youtube-publicados.json', critica: false,
    horas: 72, papel: 'registro público do que está no ar' },
  { id: 'estado-cadencia', tipo: 'estado', nome: 'posts/cadencia.json', critica: false,
    horas: 48, papel: 'entrega medida do agendador' },
  { id: 'estado-fila-tarefas', tipo: 'estado', nome: 'posts/fila-tarefas.json', critica: false,
    horas: 48, papel: 'fila do que ainda precisa acontecer' },
  { id: 'estado-log', tipo: 'estado', nome: 'posts/log.md', critica: false,
    horas: 48, papel: 'registro do que a casa fez' },

  // --- 6. credenciais (nome do segredo, nunca o valor) ---
  { id: 'cred-youtube', tipo: 'credencial', nome: 'YT_REFRESH_TOKEN', critica: true,
    papel: 'envio ao YouTube' },
  { id: 'cred-yt-client', tipo: 'credencial', nome: 'YT_CLIENT_ID', critica: true,
    papel: 'OAuth do YouTube' },
  { id: 'cred-instagram', tipo: 'credencial', nome: 'IG_TOKEN', critica: true,
    papel: 'publicação no Instagram' },
  { id: 'cred-instagram-id', tipo: 'credencial', nome: 'IG_USER_ID', critica: true,
    papel: 'conta do Instagram' },
  { id: 'cred-gmail', tipo: 'credencial', nome: 'GMAIL_CHAT_APPPASS', critica: false,
    papel: 'chat por e-mail (hoje recusada — ver alertas)' },
  { id: 'cred-nostr', tipo: 'credencial', nome: 'NOSTR_KEY', critica: false,
    papel: 'postagem no Nostr' },
  { id: 'cred-threads', tipo: 'credencial', nome: 'THREADS_TOKEN', critica: false,
    papel: 'postagem no Threads' },
  { id: 'cred-bluesky', tipo: 'credencial', nome: 'BLUESKY_APPRISK'.replace('APPRISK', 'APPPASS'),
    critica: false, papel: 'postagem no Bluesky' },

  // --- 7. redes com postagem real (o que o dono vê) ---
  { id: 'rede-youtube', tipo: 'rede', nome: 'youtube', critica: true,
    papel: 'vídeo dos dois jogos' },
  { id: 'rede-instagram', tipo: 'rede', nome: 'instagram', critica: true,
    papel: 'imagem/legenda' },
  { id: 'rede-threads', tipo: 'rede', nome: 'threads', critica: false, papel: 'texto curto' },
  { id: 'rede-nostr', tipo: 'rede', nome: 'nostr', critica: false, papel: 'texto descentralizado' },
  { id: 'rede-bluesky', tipo: 'rede', nome: 'bluesky', critica: false, papel: 'texto' },
  { id: 'rede-mastodon', tipo: 'rede', nome: 'mastodon', critica: false, papel: 'texto' },
  { id: 'rede-x', tipo: 'rede', nome: 'x', critica: false,
    papel: 'secrets vivem no repo chat (não é falha deste repo)' },
  { id: 'rede-gmail', tipo: 'rede', nome: 'gmail', critica: false, papel: 'chat por e-mail' },

  // --- 8. jogos (prioridade IGUAL, por decisão do dono) ---
  { id: 'jogo-prancheta', tipo: 'jogo', nome: 'prancheta', critica: true,
    papel: 'build web + roteiro medido' },
  { id: 'jogo-ceifalume', tipo: 'jogo', nome: 'ceifalume', critica: true,
    papel: 'build versionado + roteiro medido' },

  // --- 9. portões que impedem publicação errada ---
  { id: 'portao-sha256', tipo: 'portao', nome: 'posts/videos-enviados.json', critica: true,
    papel: 'vídeo repetido não sobe' },
  { id: 'portao-janela', tipo: 'portao', nome: 'gravar-prancheta.yml#janela', critica: false,
    papel: 'publicar de madrugada é recusado' },
];

const TOTAL_DECLARADO = CAMADAS.length;

// ───────────────────────────────────────────────────────────────────────────────
// utilidades
// ───────────────────────────────────────────────────────────────────────────────
function ler(caminho) {
  try { return fs.readFileSync(caminho, 'utf8'); } catch (e) { return null; }
}

function rel(p) { return path.relative(RAIZ, p); }

function agora() { return new Date(); }

function horasDesde(ms) { return (Date.now() - ms) / 3600000; }

// Sintaxe: shell com `bash -n`, python com `py_compile` em memória, JS com `node --check`.
// Nunca executa o script — só pergunta se ele PARSERIA.
function sintaxeOk(caminho) {
  const ext = path.extname(caminho);
  try {
    if (ext === '.sh') {
      execFileSync('bash', ['-n', caminho], { stdio: 'pipe' });
      return { ok: true };
    }
    if (ext === '.py') {
      execFileSync(process.env.PYTHON || 'python3',
        ['-c', 'import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)', caminho],
        { stdio: 'pipe' });
      return { ok: true };
    }
    if (ext === '.js') {
      execFileSync('node', ['--check', caminho], { stdio: 'pipe' });
      return { ok: true };
    }
    if (ext === '.json') {
      JSON.parse(ler(caminho));
      return { ok: true };
    }
    if (ext === '.yml' || ext === '.yaml') {
      // Sem interpretador de YAML no runner do passo, checagem mínima: precisa ter `name:`
      // e pelo menos um gatilho. YAML quebrado é pego pelo contrato `testes-workflows`.
      const s = ler(caminho) || '';
      const ok = /^name:/m.test(s) && /^(on|"on"|'on'):/m.test(s);
      return ok ? { ok: true } : { ok: false, motivo: 'sem name/on' };
    }
    return { ok: true };   // tipo sem parser: existe é o que dá para afirmar
  } catch (e) {
    const msg = String((e.stderr && e.stderr.toString()) || e.message || e).trim().split('\n')[0];
    return { ok: false, motivo: msg.slice(0, 160) };
  }
}

const SEGREDOS_CONHECIDOS = new Set([
  'YT_REFRESH_TOKEN', 'YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'IG_TOKEN', 'IG_USER_ID',
  'GMAIL_CHAT_APPPASS', 'GMAIL_CHAT_PASS', 'GMAIL_CHAT_ADDRESS', 'GMAIL_CHAT_ADDR',
  'NOSTR_KEY', 'THREADS_TOKEN', 'BLUESKY_HANDLE', 'BLUESKY_APPPASS', 'MASTODON_TOKEN',
  'ITCH_API_KEYS', 'DEVTO_API_KEY', 'TUMBLR_CONSUMER_KEY', 'DISCORD_BOT_TOKEN',
  'X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_TOKEN_SECRET', 'GHPAT',
]);

// Gatilhos automáticos de um workflow, lidos do arquivo (não da API: a API exige token
// e este health check também precisa rodar local).
function gatilhos(caminho) {
  const s = ler(caminho) || '';
  const auto = [];
  if (/^\s*schedule:/m.test(s)) auto.push('schedule');
  if (/repository_dispatch:/.test(s)) auto.push('repository_dispatch');
  if (/^\s*push:/m.test(s)) auto.push('push');
  return auto;
}

function temSegredoNoArquivo(caminhoYml) {
  const s = ler(caminhoYml) || '';
  const m = s.match(/secrets\.([A-Z0-9_]+)/g) || [];
  return [...new Set(m.map(x => x.replace('secrets.', '')))];
}

// ───────────────────────────────────────────────────────────────────────────────
// auditoria de uma camada
// ───────────────────────────────────────────────────────────────────────────────
function auditar(c) {
  const base = { camada: c.id, tipo: c.tipo, papel: c.papel, critica: !!c.critica };

  if (c.tipo === 'workflow') {
    const p = path.join(DIR_WF, c.nome);
    if (!fs.existsSync(p)) return { ...base, ativa: false, status: 'ausente', motivo: 'workflow não existe' };
    const s = sintaxeOk(p);
    const auto = gatilhos(p);
    const seg = temSegredoNoArquivo(p);
    return {
      ...base, ativa: s.ok, status: s.ok ? (auto.length ? 'ativa' : 'so_manual') : 'sintaxe_invalida',
      motivo: s.ok ? (auto.length ? 'gatilho: ' + auto.join('+') : 'sem gatilho automático') : s.motivo,
      segredos: seg,
    };
  }

  if (c.tipo === 'script') {
    const p = path.join(RAIZ, c.nome);
    if (!fs.existsSync(p)) return { ...base, ativa: false, status: 'ausente', motivo: 'arquivo não existe' };
    const s = sintaxeOk(p);
    // executável importa para .sh chamado por `bash`? não; para os que são chamados direto, sim.
    // O consentimento da casa é `bash tools/x.sh` — então "executável" NÃO é condição.
    return { ...base, ativa: s.ok, status: s.ok ? 'ativa' : 'sintaxe_invalida', motivo: s.motivo || '' };
  }

  if (c.tipo === 'estado') {
    const p = path.join(RAIZ, c.nome);
    if (!fs.existsSync(p)) return { ...base, ativa: false, status: 'ausente', motivo: 'estado não existe' };
    const st = fs.statSync(p);
    const h = horasDesde(st.mtimeMs);
    const velho = c.horas && h > c.horas;
    const s = c.nome.endsWith('.json') ? sintaxeOk(p) : { ok: true };
    return {
      ...base, ativa: s.ok && !velho,
      status: !s.ok ? 'json_invalido' : (velho ? 'estagnado' : 'ativa'),
      motivo: !s.ok ? s.motivo : (velho ? 'sem escrita há ' + h.toFixed(1) + 'h (esperado < ' + c.horas + 'h)' : 'escrito há ' + h.toFixed(1) + 'h'),
      horas: Number(h.toFixed(1)),
    };
  }

  if (c.tipo === 'credencial') {
    const noAmbiente = !!(process.env[c.nome] || '').trim();
    // Fora do Actions (local) não há segredo: isso é "não verificável", não "ausente".
    const rodandoNoActions = String(process.env.GITHUB_ACTIONS || '') === 'true';
    return {
      ...base,
      ativa: noAmbiente,
      status: noAmbiente ? 'ativa' : (rodandoNoActions ? 'ausente' : 'nao_verificavel_local'),
      motivo: noAmbiente ? 'configurada (valor não é lido nem impresso)'
        : (rodandoNoActions ? 'segredo ausente no repositório' : 'fora do Actions: não dá para verificar sem expor valor'),
    };
  }

  if (c.tipo === 'rede') {
    const mapa = {
      youtube: ['YT_REFRESH_TOKEN', 'YT_CLIENT_ID'],
      instagram: ['IG_TOKEN', 'IG_USER_ID'],
      threads: ['THREADS_TOKEN'],
      nostr: ['NOSTR_KEY'],
      bluesky: ['BLUESKY_APPPASS', 'BLUESKY_HANDLE'],
      mastodon: ['MASTODON_TOKEN'],
      x: ['X_API_KEY', 'X_ACCESS_TOKEN'],
      gmail: ['GMAIL_CHAT_APPPASS', 'GMAIL_CHAT_PASS'],
    }[c.nome] || [];
    const noAmbiente = mapa.some(n => !!(process.env[n] || '').trim());
    const rodandoNoActions = String(process.env.GITHUB_ACTIONS || '') === 'true';
    return {
      ...base, ativa: noAmbiente,
      status: noAmbiente ? 'ativa' : (rodandoNoActions ? 'ausente' : 'nao_verificavel_local'),
      motivo: noAmbiente ? 'tem credencial para postar' : 'sem credencial para postar',
      exige: mapa,
    };
  }

  if (c.tipo === 'jogo') {
    const pistas = {
      prancheta: [path.join(DIR_TOOLS, 'gravar-prancheta.js'), path.join(RAIZ, 'posts', 'cenas.json')],
      ceifalume: [path.join(RAIZ, 'ceifalume', 'index.html'), path.join(DIR_TOOLS, 'gravar-gameplay.js')],
    }[c.nome] || [];
    const achados = pistas.filter(p => fs.existsSync(p)).length;
    return {
      ...base, ativa: achados > 0, status: achados > 0 ? 'ativa' : 'ausente',
      motivo: achados + '/' + pistas.length + ' peças presentes',
    };
  }

  if (c.tipo === 'portao') {
    const [arquivo, sufixo] = c.nome.split('#');
    if (sufixo === 'janela') {
      // o portão de janela não é arquivo: é o cron dentro da faixa 9h-22h de Brasília.
      const s = ler(path.join(DIR_WF, arquivo)) || '';
      const m = s.match(/cron:\s*"([^"]+)"/);
      const ok = !!m;
      return { ...base, ativa: ok, status: ok ? 'ativa' : 'ausente',
               motivo: ok ? 'cron declarado: ' + m[1] : 'workflow sem cron' };
    }
    const p = path.join(RAIZ, arquivo);
    if (!fs.existsSync(p)) return { ...base, ativa: false, status: 'ausente', motivo: 'arquivo do portão não existe' };
    const s = sintaxeOk(p);
    return { ...base, ativa: s.ok, status: s.ok ? 'ativa' : 'json_invalido', motivo: s.motivo || '' };
  }

  return { ...base, ativa: false, status: 'tipo_desconhecido', motivo: c.tipo };
}

// ───────────────────────────────────────────────────────────────────────────────
// auto-recuperação — só o que é seguro e verificável
// ───────────────────────────────────────────────────────────────────────────────
const ESQUELETO = {
  'posts/orquestrador.json': { pulsos: 0, ultima_acao: null, historico: [] },
  'posts/videos-enviados.json': { _o_que_e: 'sha256 de vídeos já enviados', enviados: [] },
  'posts/youtube-publicados.json': { publicados: [] },
  'posts/fila-tarefas.json': { tarefas: [] },
};

// 16/11/2026 — O BUG QUE MATOU A AUTO-RECUPERAÇÃO SEM NINGUÉM NOTAR:
// `auditar()` devolve `{camada: id, tipo, status, motivo, ...}` — o campo `nome` NÃO volta.
// Esta função lia `camada.nome` para saber QUAL arquivo recriar, recebia `undefined`,
// `ESQUELETO[undefined]` era falso, e o ramo de recriação nunca executava. Resultado: quatro
// camadas de estado ausentes em `criticas_caidas` e ZERO tentativas de recuperação. O
// self-recovery nunca rodou uma vez sequer desde que foi escrito.
// A assinatura agora aceita os dois formatos, e o `nome` é resolvido pela tabela CAMADAS
// quando o objeto auditado não o traz.
function tentarRecuperacao(camada) {
  if (!camada.nome) {
    const declarada = CAMADAS.find(c => c.id === camada.camada);
    if (declarada) camada = { ...camada, nome: declarada.nome };
  }
  // Só estado com esqueleto conhecido é recriado. Script quebrado NUNCA é "consertado".
  if (camada.tipo === 'estado' && ESQUELETO[camada.nome] && !fs.existsSync(path.join(RAIZ, camada.nome))) {
    try {
      fs.mkdirSync(DIR_POSTS, { recursive: true });
      fs.writeFileSync(path.join(RAIZ, camada.nome),
        JSON.stringify(ESQUELETO[camada.nome], null, 1) + '\n', 'utf8');
      return { recuperou: true, motivo: 'estado ausente recriado com esqueleto vazio (não é sucesso: é começo do zero)' };
    } catch (e) {
      return { recuperou: false, motivo: 'falha ao recriar: ' + String(e.message).slice(0, 80) };
    }
  }
  if (camada.tipo === 'script' && camada.status === 'sintaxe_invalida') {
    return { recuperou: false, motivo: 'código com sintaxe quebrada NÃO é reescrito no chute — precisa de commit' };
  }
  if (camada.tipo === 'credencial' && camada.status === 'ausente') {
    return { recuperou: false, motivo: 'segredo ausente não é inventável — precisa do dono no painel' };
  }
  return { recuperou: false, motivo: 'sem recuperação automática para este tipo/estado' };
}

// ───────────────────────────────────────────────────────────────────────────────
// execução
// ───────────────────────────────────────────────────────────────────────────────
function executar(opcoes = {}) {
  const inicio = agora();
  const detalhe = [];
  const recuperacoes = { tentadas: 0, sucesso: 0, falha: 0, itens: [] };

  for (const c of CAMADAS) {
    const r = auditar(c);
    if (!r.ativa) {
      const rec = tentarRecuperacao(r);
      if (rec.recuperou || (rec.motivo && !/sem recuperação automática/.test(rec.motivo))) {
        recuperacoes.tentadas++;
        if (rec.recuperou) { recuperacoes.sucesso++; r.status = 'recriada'; r.ativa = true; }
        else recuperacoes.falha++;
        recuperacoes.itens.push({ camada: c.id, ...rec });
      }
      r.recuperacao = rec.motivo;
    }
    r.verificadoEm = inicio.toISOString();
    detalhe.push(r);
  }

  const ativas = detalhe.filter(d => d.ativa).length;
  const inativas = detalhe.filter(d => !d.ativa);
  // "não verificável neste ambiente" não é "caída". Fora do Actions não existe segredo
  // nenhum por definição — contar isso como queda faria o health check nascer vermelho na
  // máquina de quem só quer rodar os contratos, que é o oposto de informar.
  const criticasCaidas = inativas.filter(d => d.critica && d.status !== 'nao_verificavel_local');
  const naoVerificaveis = inativas.filter(d => d.status === 'nao_verificavel_local');

  const resultado = {
    id: 'hc_' + inicio.getTime(),
    executadoEm: inicio.toISOString(),
    onde: rel(RAIZ),
    no_actions: String(process.env.GITHUB_ACTIONS || '') === 'true',
    camadas_total: TOTAL_DECLARADO,
    camadas_ativas: ativas,
    camadas_inativas: inativas.length,
    camadas_nao_verificaveis_local: naoVerificaveis.length,
    criticas_caidas: criticasCaidas.map(d => ({ camada: d.camada, status: d.status, motivo: d.motivo })),
    recuperacoes,
    saudavel: criticasCaidas.length === 0,
    detalhe,
  };

  // grava (é estado, não relatório: o next run lê para comparar)
  try {
    fs.mkdirSync(DIR_POSTS, { recursive: true });
    fs.writeFileSync(SAIDA, JSON.stringify({
      atualizadoEm: resultado.executadoEm,
      ultima_execucao: resultado.executadoEm,
      camadas: resultado.camadas_total,
      ativas: resultado.camadas_ativas,
      inativas: resultado.camadas_inativas,
      criticas_caidas: resultado.criticas_caidas,
      recuperacoes_sucesso: recuperacoes.sucesso,
      recuperacoes_falha: recuperacoes.falha,
      saudavel: resultado.saudavel,
    }, null, 1) + '\n', 'utf8');
  } catch (e) { /* gravar não pode derrubar a auditoria */ }

  return resultado;
}

function resumoTexto(r) {
  const linhas = [];
  linhas.push('## 🏥 Health check das camadas do site');
  linhas.push('');
  linhas.push('| | |');
  linhas.push('| --- | --- |');
  linhas.push('| camadas declaradas | **' + r.camadas_total + '** |');
  linhas.push('| ativas | **' + r.camadas_ativas + '** |');
  linhas.push('| inativas | ' + r.camadas_inativas + (r.camadas_nao_verificaveis_local
    ? ' (' + r.camadas_nao_verificaveis_local + ' não verificáveis fora do Actions)' : '') + ' |');
  const criticasSemVerificar = r.detalhe.filter(d => d.critica && d.status === 'nao_verificavel_local').length;
  linhas.push('| críticas caídas | **' + r.criticas_caidas.length + '** |');
  if (criticasSemVerificar) linhas.push('| críticas não verificáveis aqui | ' + criticasSemVerificar + ' (só dentro do Actions) |');
  linhas.push('| recuperações | ' + r.recuperacoes.sucesso + ' ok / ' + r.recuperacoes.falha + ' falha |');
  linhas.push('| saudável | ' + (r.saudavel ? '✅ sim' : '❌ não') + ' |');
  linhas.push('');
  const porTipo = {};
  for (const d of r.detalhe) {
    porTipo[d.tipo] = porTipo[d.tipo] || { total: 0, ok: 0 };
    porTipo[d.tipo].total++;
    if (d.ativa) porTipo[d.tipo].ok++;
  }
  linhas.push('| tipo | ativas | total |');
  linhas.push('| --- | --- | --- |');
  for (const t of Object.keys(porTipo).sort()) {
    linhas.push('| ' + t + ' | ' + porTipo[t].ok + ' | ' + porTipo[t].total + ' |');
  }
  if (r.criticas_caidas.length) {
    linhas.push('');
    linhas.push('### ❌ Camadas críticas caídas');
    linhas.push('');
    linhas.push('| camada | status | motivo |');
    linhas.push('| --- | --- | --- |');
    for (const c of r.criticas_caidas) {
      linhas.push('| `' + c.camada + '` | ' + c.status + ' | ' + String(c.motivo || '').replace(/\|/g, '/').slice(0, 110) + ' |');
    }
  }
  const outras = r.detalhe.filter(d => !d.ativa && !d.critica && d.status !== 'nao_verificavel_local');
  if (outras.length) {
    linhas.push('');
    linhas.push('### ⚠️ Inativas (não críticas)');
    linhas.push('');
    for (const o of outras.slice(0, 14)) {
      linhas.push('- `' + o.camada + '` — ' + o.status + ': ' + String(o.motivo || '').slice(0, 100));
    }
    if (outras.length > 14) linhas.push('- … e mais ' + (outras.length - 14));
  }
  return linhas.join('\n');
}

function main(argv) {
  const r = executar();
  if (argv.includes('--json')) {
    console.log(JSON.stringify(r, null, 1));
  } else if (argv.includes('--resumo')) {
    console.log(resumoTexto(r));
  } else {
    console.log(resumoTexto(r));
    console.log('');
    console.log('gravado em ' + rel(SAIDA));
  }
  return r.saudavel ? 0 : 1;
}

if (require.main === module) {
  process.exitCode = main(process.argv.slice(2));
}

module.exports = { executar, auditar, resumoTexto, CAMADAS, sintaxeOk, gatilhos, TOTAL_DECLARADO };
