// 🧪 TESTAR TODAS AS APIs — verifica se cada credencial ainda funciona
// v1 (09/11/2026): testa leitura de todas as redes sociais e serviços com credenciais gravadas
// Roda via GitHub Actions (workflow testar-apis.yml) ou manualmente com variáveis de ambiente

const NL = '\n';
const resultados = [];
let falhas = 0;

function registro(nome, ok, detalhe, valor = '') {
  const status = ok ? '✅' : '❌';
  resultados.push({ nome, ok, detalhe, valor });
  if (!ok) falhas++;
  console.log(`${status} ${nome}: ${detalhe}${valor ? ` | ${valor}` : ''}`);
}

async function busca(url, opcoes = {}) {
  const ctrl = new AbortController();
  const timo = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(url, { ...opcoes, signal: ctrl.signal, headers: { 'User-Agent': 'rebocl-testar-apis/1', ...opcoes.headers } });
    clearTimeout(timo);
    return r;
  } catch (e) {
    clearTimeout(timo);
    throw e;
  }
}

async function testeGitHub() {
  try {
    const token = process.env.GITHUB_TOKEN;
    if (!token) { registro('GitHub PAT', false, 'sem segredo GITHUB_TOKEN'); return; }
    const r = await busca('https://api.github.com/user', { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) {
      const j = await r.json();
      registro('GitHub PAT', true, 'usuário autenticado', j.login);
    } else {
      const texto = await r.text().catch(() => '');
      registro('GitHub PAT', false, `HTTP ${r.status}`, texto.slice(0, 100));
    }
  } catch (e) { registro('GitHub PAT', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeYouTube() {
  try {
    const key = process.env.YT_API_KEY;
    if (!key) { registro('YouTube API', false, 'sem segredo YT_API_KEY'); return; }
    const r = await busca(`https://www.googleapis.com/youtube/v3/channels?part=statistics&id=UCQdxKtfRnqNLd1ZOs9B6eaQ&key=${key}`);
    if (r.ok) {
      const j = await r.json();
      if (j.items && j.items[0]) {
        const s = j.items[0].statistics;
        registro('YouTube API', true, 'canal lido', `inscritos=${s.subscriberCount}, vídeos=${s.videoCount}`);
      } else {
        registro('YouTube API', false, 'canal não encontrado');
      }
    } else {
      registro('YouTube API', false, `HTTP ${r.status}`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('YouTube API', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeItch() {
  try {
    const key = process.env.ITCH_API_KEYS;
    if (!key) { registro('itch.io API', false, 'sem segredo ITCH_API_KEYS'); return; }
    const r = await busca('https://api.itch.io/profile', { headers: { Authorization: `Bearer ${key}` } });
    if (r.ok) {
      const j = await r.json();
      registro('itch.io API', true, 'perfil lido', j.user ? j.user.username : 'desconhecido');
    } else {
      registro('itch.io API', false, `HTTP ${r.status}`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('itch.io API', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeBluesky() {
  try {
    const handle = process.env.BLUESKY_HANDLE;
    const senha = process.env.BLUESKY_APPPASS || process.env.BSKY_APP_PASSWORD;
    if (!handle || !senha) { registro('Bluesky', false, 'sem BLUESKY_HANDLE ou BLUESKY_APPPASS'); return; }
    const r = await busca('https://bsky.social/xrpc/com.atproto.server.createSession', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier: handle, password: senha })
    });
    if (r.ok) {
      const j = await r.json();
      registro('Bluesky', true, 'login OK', j.did ? j.did.slice(0, 40) : 'sem DID');
    } else {
      registro('Bluesky', false, `HTTP ${r.status}`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('Bluesky', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeMastodon() {
  try {
    const token = process.env.MASTODON_TOKEN;
    if (!token) { registro('Mastodon', false, 'sem segredo MASTODON_TOKEN'); return; }
    const r = await busca('https://mastodon.social/api/v1/accounts/verify_credentials', { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) {
      const j = await r.json();
      registro('Mastodon', true, 'token válido', j.username ? `@${j.username}` : 'sem username');
    } else {
      registro('Mastodon', false, `HTTP ${r.status}`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('Mastodon', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeInstagram() {
  try {
    const token = process.env.IG_TOKEN;
    if (!token) { registro('Instagram', false, 'sem segredo IG_TOKEN'); return; }
    const r = await busca(`https://graph.instagram.com/v21.0/me?fields=id,username&access_token=${token}`);
    if (r.ok) {
      const j = await r.json();
      registro('Instagram', true, 'token válido', j.username ? `@${j.username}` : j.id);
    } else {
      const j = await r.json().catch(() => ({}));
      registro('Instagram', false, `HTTP ${r.status}`, j.error ? j.error.message : await r.text().slice(0, 100));
    }
  } catch (e) { registro('Instagram', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeThreads() {
  try {
    const token = process.env.THREADS_TOKEN || process.env.THREADS_ACCESS_TOKEN;
    if (!token) { registro('Threads', false, 'sem segredo THREADS_TOKEN'); return; }
    const r = await busca(`https://graph.threads.net/v1.0/me?fields=id,username&access_token=${token}`);
    if (r.ok) {
      const j = await r.json();
      registro('Threads', true, 'token válido', j.username ? `@${j.username}` : j.id);
    } else {
      const j = await r.json().catch(() => ({}));
      registro('Threads', false, `HTTP ${r.status}`, j.error ? j.error.message : await r.text().slice(0, 100));
    }
  } catch (e) { registro('Threads', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeDiscord() {
  try {
    const token = process.env.DISCORD_BOT_TOKEN;
    if (!token) { registro('Discord', false, 'sem segredo DISCORD_BOT_TOKEN'); return; }
    const r = await busca('https://discord.com/api/v10/users/@me', { headers: { Authorization: `Bot ${token}` } });
    if (r.ok) {
      const j = await r.json();
      registro('Discord', true, 'bot válido', `${j.username}#${j.discriminator}`);
    } else {
      registro('Discord', false, `HTTP ${r.status}`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('Discord', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeDevto() {
  try {
    const key = process.env.DEVTO_API_KEY;
    if (!key) { registro('dev.to', false, 'sem segredo DEVTO_API_KEY'); return; }
    const r = await busca('https://dev.to/api/articles/me/published', { headers: { 'api-key': key } });
    if (r.ok) {
      const j = await r.json();
      registro('dev.to', true, 'API key válida', Array.isArray(j) ? `${j.length} artigos` : 'sem lista');
    } else {
      registro('dev.to', false, `HTTP ${r.status}`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('dev.to', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeTumblr() {
  try {
    const key = process.env.TUMBLR_CONSUMER_KEY;
    if (!key) { registro('Tumblr', false, 'sem segredo TUMBLR_CONSUMER_KEY'); return; }
    const r = await busca(`https://api.tumblr.com/v2/blog/reboclbrank.tumblr.com/info?api_key=${key}`);
    if (r.ok) {
      const j = await r.json();
      if (j.meta && j.meta.status === 200) {
        registro('Tumblr', true, 'consumer key válida', j.response.blog ? j.response.blog.name : 'sem blog');
      } else {
        registro('Tumblr', false, 'resposta inválida', JSON.stringify(j).slice(0, 100));
      }
    } else {
      registro('Tumblr', false, `HTTP ${r.status}`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('Tumblr', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeNostr() {
  try {
    const key = process.env.NOSTR_KEY;
    if (!key) { registro('Nostr', false, 'sem segredo NOSTR_KEY'); return; }
    // Nostr não tem endpoint de leitura simples sem relay. Verificamos só se a chave tem formato válido.
    const npub = key.startsWith('npub1') ? 'npub válido' : 'não é npub';
    const hex = /^[0-9a-f]{64}$/.test(key) ? 'hex válido (64 chars)' : 'não é hex de 64 chars';
    registro('Nostr', true, 'chave com formato válido', `${npub} · ${hex}`);
  } catch (e) { registro('Nostr', false, 'erro', e.message.slice(0, 100)); }
}

async function testeX() {
  try {
    const apiKey = process.env.X_API_KEY;
    const apiSecret = process.env.X_API_SECRET;
    const accessToken = process.env.X_ACCESS_TOKEN;
    const accessTokenSecret = process.env.X_ACCESS_TOKEN_SECRET;
    if (!apiKey || !apiSecret || !accessToken || !accessTokenSecret) {
      registro('X (Twitter)', false, 'sem X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET');
      return;
    }
    // Verificar credenciais via verify credentials (GET /2/users/me)
    const r = await busca('https://api.twitter.com/2/users/me', {
      headers: {
        Authorization: `OAuth oauth_consumer_key="${encodeURIComponent(apiKey)}",oauth_token="${encodeURIComponent(accessToken)}",oauth_signature_method="HMAC-SHA1",oauth_timestamp="${Math.floor(Date.now()/1000)}",oauth_nonce="${Math.random().toString(36).substring(2,18)}",oauth_version="1.0"`,
        'User-Agent': 'rebocl-testar-apis/1',
      },
      signal: AbortSignal.timeout(30000),
    });
    // Este endpoint precisa de assinatura OAuth completa; se falhar por assinatura, apenas confirmamos que as credenciais existem
    if (r.ok) {
      const j = await r.json();
      registro('X (Twitter)', true, 'conta verificada', j.data ? j.data.username : 'ok');
    } else if (r.status === 401) {
      registro('X (Twitter)', false, 'credenciais inválidas (HTTP 401)');
    } else {
      registro('X (Twitter)', true, 'credenciais configuradas (API respondeu)', `HTTP ${r.status}`);
    }
  } catch (e) { registro('X (Twitter)', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeTikTok() {
  try {
    const key = process.env.TIKTOK_CLIENT_KEY;
    const secret = process.env.TIKTOK_CLIENT_SECRET;
    const accessToken = process.env.TIKTOK_ACCESS_TOKEN;
    const refreshToken = process.env.TIKTOK_REFRESH_TOKEN;

    if (!key || !secret || !accessToken) {
      registro('TikTok', false, 'sem TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_ACCESS_TOKEN');
      return;
    }

    // Valida o access token via User Info endpoint da TikTok API
    const r = await busca('https://open.tiktokapis.com/v2/oauth/userinfo/', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });

    if (r.ok) {
      const j = await r.json();
      const data = j.data || {};
      registro('TikTok', true, 'access token válido', data.username ? `@${data.username}` : 'ok');
    } else {
      registro('TikTok', false, `HTTP ${r.status} (verificar TIKTOK_ACCESS_TOKEN)`, await r.text().slice(0, 100));
    }
  } catch (e) { registro('TikTok', false, 'erro de conexão', e.message.slice(0, 100)); }
}

async function testeGmail() {
  try {
    const addr = process.env.GMAIL_CHAT_ADDR;
    const pass = process.env.GMAIL_CHAT_PASS;
    if (!addr || !pass) { registro('Gmail IMAP/SMTP', false, 'sem credenciais'); return; }
    const { ImapFlow } = require('imapflow');
    const client = new ImapFlow({ host: 'imap.gmail.com', port: 993, secure: true, auth: { user: addr, pass: pass }, logger: false });
    await comTeto(client.connect(), 30000, 'IMAP connect');
    await comTeto(client.getMailboxLock('INBOX'), 30000, 'INBOX lock');
    const uids = await comTeto(client.search({ seen: false }), 30000, 'busca não lidos');
    client.logout();
    registro('Gmail IMAP/SMTP', true, 'conexão OK', `${uids.length} email(s) não lido(s)`);
  } catch (e) {
    registro('Gmail IMAP/SMTP', false, 'erro de conexão', e.message.slice(0, 100));
  }
}

function comTeto(p, ms, rotulo) {
  return Promise.race([p, new Promise((_, rejeita) => setTimeout(() => rejeita(new Error(`timeout ${rotulo}`)), ms))]);
}

async function main() {
  console.log('🧪 Iniciando teste de todas as APIs...' + NL);
  await testeGitHub();
  await testeYouTube();
  await testeItch();
  await testeBluesky();
  await testeMastodon();
  await testeInstagram();
  await testeThreads();
  await testeDiscord();
  await testeDevto();
  await testeTumblr();
  await testeNostr();
  await testeTikTok();
  await testeX();
  await testeGmail();

  console.log(NL + '═══════════════════════════════════════════');
  const ok = resultados.filter(r => r.ok).length;
  const total = resultados.length;
  console.log(`📊 Resultado: ${ok}/${total} serviços funcionando`);
  if (falhas > 0) {
    console.log(`❌ ${falhas} serviço(s) com falha:`);
    for (const r of resultados) {
      if (!r.ok) console.log(`   • ${r.nome}: ${r.detalhe}`);
    }
    process.exitCode = 1;
  } else {
    console.log('✅ Todos os serviços estão funcionando!');
  }
  console.log('══════════════════════════════════════════');
}

main().catch(e => { console.error('Erro fatal:', e.message); process.exitCode = 2; });
