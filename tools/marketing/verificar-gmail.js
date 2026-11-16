#!/usr/bin/env node
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 📧 VERIFICADOR DO GMAIL — diz QUAL dos três problemas é, sem abrir cliente de e-mail.
//
// POR QUE EXISTE (16/11/2026):
// O diagnóstico antigo só sabia dizer "erro de conexão" para tudo: senha revogada, IMAP
// desligado na conta, porta 993 bloqueada e DNS quebrado davam a mesma frase. O dono não tinha
// o que corrigir. Este verificador faz três perguntas SEPARADAS:
//
//   1. a credencial existe?          (GMAIL_CHAT_ADDRESS/ADDR + PASS/APPPASS)
//   2. o servidor é alcançável?      (TCP 993 + banner IMAP)
//   3. o servidor ACEITA a senha?    (login IMAP real)
//
// A resposta é uma linha por pergunta, e o código de saída diz o que fazer:
//   0 = tudo certo
//   2 = falta credencial             → colar o secret (ver COMO-RESOLVER-GMAIL.md)
//   3 = não alcança imap.gmail.com   → é rede/porta, NÃO é a senha
//   4 = alcança e RECUSA a senha     → gerar senha de app nova
//
// Nunca imprime a senha. Imprime só o tamanho e o formato (quem lê precisa saber se colou o
// "abcd efgh ijkl mnop" com espaços, que é o erro mais comum).
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'use strict';

const net = require('net');

const ENDERECO = process.env.GMAIL_CHAT_ADDRESS || process.env.GMAIL_CHAT_ADDR || '';
const SENHA = process.env.GMAIL_CHAT_APPPASS || process.env.GMAIL_CHAT_PASS || '';
const HOST = 'imap.gmail.com';
const PORTA = 993;

const resultado = { perguntas: [], codigo: 0, veredito: '' };

function anota(pergunta, ok, detalhe) {
  resultado.perguntas.push({ pergunta, ok, detalhe });
  console.log((ok ? '✅' : '❌') + ' ' + pergunta + ' — ' + detalhe);
}

// ─── 1. credencial ───────────────────────────────────────────────────────────────
if (!ENDERECO || !SENHA) {
  anota('a credencial existe?', false,
    'falta ' + (!ENDERECO ? 'GMAIL_CHAT_ADDRESS/ADDR' : 'GMAIL_CHAT_PASS/APPPASS'));
  resultado.codigo = 2;
  resultado.veredito = 'FALTA_CREDENCIAL';
} else {
  const temEspaco = /\s/.test(SENHA);
  const tamanho = SENHA.replace(/\s/g, '').length;
  const pareceApp = tamanho === 16;
  anota('a credencial existe?', true,
    'endereço ' + ENDERECO.replace(/^(.).*(@.*)$/, '$1***$2') + ' · senha com ' + tamanho +
    ' caracteres' + (temEspaco ? ' (TEM ESPAÇO — senha de app é colada sem espaço)' : '') +
    (pareceApp ? '' : ' (senha de app do Google tem 16 caracteres; esta tem ' + tamanho + ')'));
}

// ─── 2 e 3. alcança o servidor? ele aceita a senha? ──────────────────────────────
// Sem credencial NÃO se testa conexão: a pergunta 1 já respondeu o que importa, e ficar 20s
// esperando um socket para depois dizer "falta secret" é ruído.
function finalizar() {
  const acao = {
    0: 'nada a fazer — credencial válida',
    2: 'colar o secret (COMO-RESOLVER-GMAIL.md, passo 2)',
    3: 'é rede/porta, não a senha — não gere senha nova por causa disto',
    4: 'gerar senha de app nova (COMO-RESOLVER-GMAIL.md, passo 1) e regravar o secret',
  }[resultado.codigo] || 'ver detalhe acima';
  console.log('');
  console.log('veredito: ' + resultado.veredito);
  console.log('próximo passo: ' + acao);
  process.exitCode = resultado.codigo;
}

if (resultado.codigo !== 0) {
  finalizar();
  return;
}

function conectar() {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: HOST, port: PORTA });
    let etapa = 'conexao';
    let buffer = '';
    const fim = (r) => { try { socket.destroy(); } catch (e) {} resolve(r); };

    socket.setTimeout(20000);
    socket.on('timeout', () => {
      // abriu o socket mas o servidor não falou: não é IMAP acessível.
      anota('o servidor é alcançável?', false,
        'a porta ' + PORTA + ' abriu, mas ' + HOST + ' não enviou o banner IMAP em 20s ' +
        '(saída de rede filtrada — não é a senha)');
      fim({ ok: false, alcançou: false, motivo: 'sem banner', etapa });
    });
    socket.on('error', (e) => {
      anota('o servidor é alcançável?', false,
        'não conectou em ' + HOST + ':' + PORTA + ' (' + (e.code || e.message) + ')');
      fim({ ok: false, alcançou: false, motivo: (e.code || e.message), etapa });
    });

    socket.on('close', () => {
      if (etapa === 'conexao') {
        anota('o servidor é alcançável?', false,
          'a conexão com ' + HOST + ':' + PORTA + ' abriu e foi FECHADA antes do banner IMAP ' +
          '(saída de rede filtrada ou proxy no caminho — não é a senha)');
        fim({ ok: false, alcançou: false, motivo: 'fechou antes do banner' });
      }
    });

    socket.on('data', (d) => {
      buffer += d.toString('utf8');
      // IMAP fala em linhas; o servidor manda o banner " * OK ..." / "* PREAUTH ..."
      if (etapa === 'conexao' && /\r?\n/.test(buffer)) {
        const banner = buffer.split(/\r?\n/).find(l => l.trim().length) || '';
        anota('o servidor é alcançável?', true, HOST + ':' + PORTA + ' respondeu: ' +
          banner.trim().slice(0, 70));
        if (!ENDERECO || !SENHA) return fim({ ok: true, alcançou: true });
        etapa = 'login';
        buffer = '';
        // LOGIN com aspas: a senha pode conter caracteres especiais. Não ecoamos nada.
        socket.write('a1 LOGIN "' + ENDERECO.replace(/"/g, '') + '" "' +
          SENHA.replace(/"/g, '') + '"\r\n');
        return;
      }
      if (etapa === 'login' && /a1 (OK|NO|BAD)/i.test(buffer)) {
        const linha = buffer.split(/\r?\n/).find(l => /a1 (OK|NO|BAD)/i.test(l)) || '';
        const aceitou = /a1 OK/i.test(linha);
        if (aceitou) {
          anota('o servidor aceita a senha?', true, 'LOGIN OK — credencial válida');
          socket.write('a2 LOGOUT\r\n');
          return fim({ ok: true, alcançou: true, login: true });
        }
        const recusa = /AUTHENTICATIONFAILED|Invalid credentials|Application-specific password/i
          .test(linha);
        anota('o servidor aceita a senha?', false,
          recusa ? 'AUTHENTICATIONFAILED — o Google recusou a senha de app'
                 : 'login recusado: ' + linha.replace(/^a1 /, '').slice(0, 90));
        return fim({ ok: true, alcançou: true, login: false });
      }
      if (buffer.length > 4000) fim({ ok: false, motivo: 'resposta inesperada do servidor', etapa });
    });
  });
}

// teto global: 45s e o processo sai de qualquer jeito. Verificador que trava o runner é
// pior do que verificador que não roda.
const TETO = setTimeout(() => {
  anota('o servidor é alcançável?', false, 'o teste passou de 45s sem resposta');
  resultado.codigo = 3;
  resultado.veredito = 'IMAP_NAO_ALCANCADO';
  finalizar();
  process.exit(3);
}, 45000);
TETO.unref && TETO.unref();

conectar().then((r) => {
  if (!r.alcançou) {
    // a pergunta 2 já foi anotada no evento que fechou o socket; aqui só se decide o código.
    if (resultado.codigo < 3) {
      resultado.codigo = 3;
      resultado.veredito = 'IMAP_NAO_ALCANCADO';
    }
  } else if (r.login === false && resultado.codigo < 4) {
    resultado.codigo = 4;
    resultado.veredito = 'SENHA_RECUSADA';
  } else if (r.login === true && resultado.codigo === 0) {
    resultado.veredito = 'OK';
  }

  clearTimeout(TETO);
  finalizar();
});
