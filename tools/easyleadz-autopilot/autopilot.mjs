#!/usr/bin/env node
// Drives a Chrome started with --remote-debugging-port: opens each LinkedIn
// profile from a CSV, clicks "View contact" in the EasyLeadz (Mr. E) side
// panel, reads the phone/email and appends them to an output CSV.
//
//   node autopilot.mjs leads.csv [--out contacts.csv] [--max 170]
//        [--min-delay 8] [--max-delay 20] [--port 9222]
//
// Needs Node 22+ (built-in fetch and WebSocket). No npm install.

import fs from 'node:fs';
import path from 'node:path';

// ---------- args ----------
const argv = process.argv.slice(2);
const opt = (name, def) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 ? argv[i + 1] : def;
};
const input = argv.find(a => !a.startsWith('--') && !argv[argv.indexOf(a) - 1]?.startsWith('--'));
if (!input) {
  console.log('Usage: node autopilot.mjs leads.csv [--out contacts.csv] [--max 170] [--min-delay 8] [--max-delay 20] [--port 9222]');
  process.exit(1);
}
const OUT = opt('out', path.join(path.dirname(input), 'easyleadz-contacts.csv'));
const MAX = parseInt(opt('max', '170'), 10);
const MIN_DELAY = parseFloat(opt('min-delay', '8')) * 1000;
const MAX_DELAY = parseFloat(opt('max-delay', '20')) * 1000;
const PORT = opt('port', '9222');
const PANEL_TIMEOUT = 25000;
const REVEAL_TIMEOUT = 15000;
const SOURCE = 'EasyLeadz (Mr. E) side panel';

const sleep = ms => new Promise(r => setTimeout(r, ms));
const jitter = () => MIN_DELAY + Math.random() * (MAX_DELAY - MIN_DELAY);
const log = (...a) => console.log(new Date().toLocaleTimeString(), ...a);

// ---------- parsing ----------
function parseDelimited(text) {
  const first = text.split('\n')[0];
  const delim = (first.match(/\t/g) || []).length > (first.match(/,/g) || []).length ? '\t' : ',';
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === delim) { row.push(cell); cell = ''; }
    else if (c === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; }
    else if (c !== '\r') cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows.filter(r => r.some(v => v.trim()));
}

function normalizeUrl(u) {
  const m = String(u).match(/linkedin\.com\/in\/([^/?#\s"',]+)/i);
  if (!m) return null;
  let slug = m[1];
  try { slug = decodeURIComponent(slug); } catch (e) {}
  return 'https://www.linkedin.com/in/' + slug.toLowerCase() + '/';
}

const PHONE_RE = /(?<!\d)(?:\+?91[\s-]?|0)?([6-9]\d{4})[\s-]?(\d{5})(?!\d)/g;

function extractPhones(text) {
  const out = [];
  const re = new RegExp(PHONE_RE);
  let m;
  while ((m = re.exec(text))) {
    const p = '+91' + m[1] + m[2];
    if (!out.includes(p)) out.push(p);
  }
  return out;
}

function extractEmails(text) {
  // The panel header shows your own login email; never record that.
  const own = new Set([...text.matchAll(/Login id\s*\(([^)]+)\)/gi)].map(m => m[1].trim().toLowerCase()));
  // Drop phone numbers first so a number rendered right before an email isn't glued onto it.
  const all = (text.replace(PHONE_RE, ' ').match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) || []).map(e => e.toLowerCase());
  return [...new Set(all)].filter(e => !own.has(e));
}

const csvCell = v => {
  v = String(v ?? '');
  return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
};

// ---------- CDP ----------
class Cdp {
  static async connect(wsUrl) {
    const c = new Cdp();
    c.ws = new WebSocket(wsUrl);
    c.id = 0;
    c.pending = new Map();
    c.ws.onmessage = e => {
      const msg = JSON.parse(e.data);
      const p = c.pending.get(msg.id);
      if (!p) return;
      c.pending.delete(msg.id);
      msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
    };
    c.ws.onclose = () => { for (const p of c.pending.values()) p.reject(new Error('target closed')); c.pending.clear(); };
    await new Promise((res, rej) => { c.ws.onopen = res; c.ws.onerror = () => rej(new Error('cannot connect to ' + wsUrl)); });
    return c;
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  }
  close() { try { this.ws.close(); } catch (e) {} }
}

async function listTargets() {
  try {
    return await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  } catch (e) {
    throw new Error(`Can't reach Chrome on port ${PORT}. Start Chrome with --remote-debugging-port=${PORT} (see README).`);
  }
}

async function linkedinTab() {
  let t = (await listTargets()).find(t => t.type === 'page' && /linkedin\.com/.test(t.url));
  if (!t) t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?https://www.linkedin.com/feed/`, { method: 'PUT' })).json();
  return Cdp.connect(t.webSocketDebuggerUrl);
}

// The side panel's target id changes when it reloads, so look it up each time.
async function panelText() {
  for (const t of await listTargets()) {
    if (!t.url.startsWith('chrome-extension://') || !t.webSocketDebuggerUrl) continue;
    let c;
    try {
      c = await Cdp.connect(t.webSocketDebuggerUrl);
      const text = await c.eval('document.body ? document.body.innerText : ""');
      if (/Powered by Easyleadz|View contact/i.test(text) && !/reveal queue/i.test(text)) return { cdp: c, text };
      c.close();
    } catch (e) { c?.close(); }
  }
  return null;
}

// Finds the innermost visible "View contact" element and returns its centre,
// so we can click it with a real mouse event (works with React-style handlers).
const FIND_VIEW_CONTACT = `(() => {
  const els = [...document.querySelectorAll('button, a, div, span, p')]
    .filter(e => e.offsetParent !== null && (e.innerText || '').trim().toLowerCase() === 'view contact');
  const el = els.find(e => !els.some(o => o !== e && e.contains(o)));
  if (!el) return null;
  el.scrollIntoView({ block: 'center' });
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
})()`;

async function clickViewContact(cdp) {
  const pt = await cdp.eval(FIND_VIEW_CONTACT);
  if (!pt) return false;
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) {
    await cdp.send('Input.dispatchMouseEvent', { type, x: pt.x, y: pt.y, button: 'left', clickCount: 1 });
    await sleep(60 + Math.random() * 120);
  }
  return true;
}

const remainingCredits = text => {
  const m = text.match(/Credits[\s:]*?(\d+)/i);
  return m ? parseInt(m[1], 10) : null;
};

// ---------- main ----------
async function main() {
  const table = parseDelimited(fs.readFileSync(input, 'utf8').replace(/^﻿/, ''));
  const hasHeader = !table[0].some(v => normalizeUrl(v));
  const header = hasHeader ? table[0].map(h => h.trim() || 'col') : table[0].map((_, i) => 'col' + (i + 1));
  const body = hasHeader ? table.slice(1) : table;

  const leads = [], seen = new Set();
  for (const r of body) {
    const url = r.map(normalizeUrl).find(Boolean);
    if (!url || seen.has(url)) continue;
    seen.add(url);
    leads.push({ url, row: header.map((_, i) => (r[i] || '').trim()) });
  }

  // Resume: skip anything already in the output file.
  const done = new Set();
  if (fs.existsSync(OUT)) {
    for (const r of parseDelimited(fs.readFileSync(OUT, 'utf8').replace(/^﻿/, '')).slice(1)) {
      const u = r.map(normalizeUrl).find(Boolean);
      if (u) done.add(u);
    }
  } else {
    fs.writeFileSync(OUT, '﻿' + [...header, 'linkedin_url', 'phone', 'email', 'status', 'revealed_at', 'source'].map(csvCell).join(',') + '\n');
  }
  const todo = leads.filter(l => !done.has(l.url));
  log(`${leads.length} profiles in list, ${done.size} already done, ${todo.length} to go. Max this run: ${MAX}. Writing to ${OUT}`);

  const probe = await panelText();
  probe?.cdp.close();
  if (!probe) {
    throw new Error('EasyLeadz side panel not found. Open the Mr. E panel in that Chrome window and log in, then re-run.');
  }
  const tab = await linkedinTab();

  let phonesThisRun = 0, lastText = '';
  for (const [n, lead] of todo.entries()) {
    if (phonesThisRun >= MAX) { log(`Reached --max ${MAX}. Stopping.`); break; }
    log(`[${n + 1}/${todo.length}] ${lead.url}`);
    await tab.send('Page.navigate', { url: lead.url });

    // Wait for the panel to switch to this profile (its text changes from the last one).
    let panel = null;
    const until = Date.now() + PANEL_TIMEOUT;
    await sleep(3000);
    while (Date.now() < until) {
      panel?.cdp.close();
      panel = await panelText();
      if (panel && panel.text !== lastText && /View contact|\+\*|\d{5}/i.test(panel.text)) break;
      await sleep(1000);
    }
    if (!panel) throw new Error('Lost the EasyLeadz side panel — is it still open?');

    const credits = remainingCredits(panel.text);
    if (credits === 0) { log('EasyLeadz shows 0 credits. Stopping.'); panel.cdp.close(); break; }

    let text = panel.text;
    if (!extractPhones(text).length && await clickViewContact(panel.cdp)) {
      const revealUntil = Date.now() + REVEAL_TIMEOUT;
      while (Date.now() < revealUntil) {
        await sleep(1000);
        text = await panel.cdp.eval('document.body.innerText');
        if (extractPhones(text).length) break;
      }
    }
    panel.cdp.close();
    lastText = text;

    const phones = extractPhones(text), emails = extractEmails(text);
    const status = phones.length ? 'found' : emails.length ? 'email_only' : 'no_data';
    if (phones.length) phonesThisRun++;
    fs.appendFileSync(OUT, [...lead.row, lead.url, phones.join(' / '), emails.join(' / '), status,
      new Date().toISOString(), SOURCE].map(csvCell).join(',') + '\n');
    log(`   ${status}  ${phones.join(' / ')}  ${emails.join(' / ')}  (credits left: ${remainingCredits(text) ?? '?'})`);

    if (n < todo.length - 1) await sleep(jitter());
  }
  tab.close();
  log(`Done. ${phonesThisRun} phone numbers this run → ${OUT}`);
}

main().then(() => process.exit(0), e => { console.error('\n' + e.message); process.exit(1); });
