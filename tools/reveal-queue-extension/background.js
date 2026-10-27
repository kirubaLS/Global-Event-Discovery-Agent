// Owns the queue state. Every change goes through mutate() so the queue page
// and the LinkedIn tab never overwrite each other.

const KEY = 'state';
const DEFAULT = { rows: [], columns: [], cap: 170, running: false, workerTabId: null, currentIdx: -1 };

// Random pause before opening the next profile, so browsing stays human-paced.
const MIN_DELAY_MS = 4000;
const MAX_DELAY_MS = 10000;

const today = () => new Date().toLocaleDateString('en-CA');

async function getState() {
  const s = (await chrome.storage.local.get(KEY))[KEY];
  return Object.assign({}, DEFAULT, s || {});
}

let lock = Promise.resolve();
function mutate(fn) {
  const p = lock.then(async () => {
    const s = await getState();
    const result = await fn(s);
    await chrome.storage.local.set({ [KEY]: s });
    return result;
  });
  lock = p.catch(() => {});
  return p;
}

function creditsToday(s) {
  return s.rows.filter(r => r.phone && r.revealed_day === today()).length;
}

function nextPending(s, after) {
  const n = s.rows.length;
  for (let k = 1; k <= n; k++) {
    const i = (after + k + n) % n;
    if (s.rows[i].status === 'pending') return i;
  }
  return -1;
}

async function tabAlive(id) {
  if (id == null) return false;
  try { await chrome.tabs.get(id); return true; } catch (e) { return false; }
}

async function start() {
  return mutate(async s => {
    if (creditsToday(s) >= s.cap) return { reason: 'cap' };
    const idx = s.rows[s.currentIdx]?.status === 'pending' ? s.currentIdx : nextPending(s, s.currentIdx);
    if (idx < 0) return { reason: 'done' };
    s.currentIdx = idx;
    s.running = true;
    const url = s.rows[idx].url;
    if (await tabAlive(s.workerTabId)) {
      await chrome.tabs.update(s.workerTabId, { url, active: true });
    } else {
      s.workerTabId = (await chrome.tabs.create({ url })).id;
    }
    return { ok: true };
  });
}

async function finish(msg, sender) {
  return mutate(s => {
    if (!sender.tab || sender.tab.id !== s.workerTabId) return { reason: 'not-worker' };
    const r = s.rows[s.currentIdx];
    if (!r) return { reason: 'done' };

    if (msg.status === 'skipped') {
      r.status = 'skipped';
    } else {
      const phone = (msg.phone || '').trim(), email = (msg.email || '').trim();
      r.phone = phone;
      r.email = email;
      r.status = msg.status === 'no_data' ? 'no_data' : phone ? 'found' : email ? 'email_only' : 'no_data';
      r.revealed_at = new Date().toISOString();
      r.revealed_day = today();
    }

    if (!s.running) return { reason: 'paused' };
    if (creditsToday(s) >= s.cap) { s.running = false; return { reason: 'cap' }; }
    const next = nextPending(s, s.currentIdx);
    if (next < 0) { s.running = false; return { reason: 'done' }; }
    s.currentIdx = next;
    const delay = MIN_DELAY_MS + Math.floor(Math.random() * (MAX_DELAY_MS - MIN_DELAY_MS));
    return { next: s.rows[next].url, delay };
  });
}

async function whoami(sender) {
  const s = await getState();
  if (!sender.tab || sender.tab.id !== s.workerTabId || !s.running) return null;
  const item = s.rows[s.currentIdx];
  if (!item) return null;
  return {
    item,
    position: s.currentIdx + 1,
    total: s.rows.length,
    pending: s.rows.filter(r => r.status === 'pending').length,
    credits: creditsToday(s),
    cap: s.cap,
  };
}

async function handle(msg, sender) {
  switch (msg.type) {
    case 'getState': return getState();
    case 'start': return start();
    case 'pause': return mutate(s => { s.running = false; });
    case 'whoami': return whoami(sender);
    case 'finish': return finish(msg, sender);
    case 'setCap': return mutate(s => { s.cap = msg.cap; });
    case 'retrySkipped': return mutate(s => { s.rows.forEach(r => { if (r.status === 'skipped') r.status = 'pending'; }); });
    case 'clear': return mutate(s => { Object.assign(s, DEFAULT, { cap: s.cap }); });
    case 'addRows': return mutate(s => {
      for (const c of msg.columns) if (!s.columns.includes(c)) s.columns.push(c);
      const seen = new Set(s.rows.map(r => r.url));
      let added = 0;
      for (const r of msg.rows) {
        if (seen.has(r.url)) continue;
        seen.add(r.url);
        s.rows.push({ url: r.url, orig: r.orig, status: 'pending', phone: '', email: '', revealed_at: '', revealed_day: '' });
        added++;
      }
      return added;
    });
  }
}

chrome.runtime.onMessage.addListener((msg, sender, send) => {
  handle(msg, sender).then(send, e => send({ error: String(e) }));
  return true;
});

chrome.action.onClicked.addListener(() => chrome.tabs.create({ url: 'queue.html' }));

chrome.tabs.onRemoved.addListener(tabId => {
  mutate(s => { if (s.workerTabId === tabId) { s.running = false; s.workerTabId = null; } });
});
