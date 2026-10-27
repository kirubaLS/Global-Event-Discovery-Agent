const SOURCE = 'EasyLeadz LinkedIn extension';
const $ = id => document.getElementById(id);
const send = msg => chrome.runtime.sendMessage(msg);
let state = null;

// ---------- import ----------
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

async function importText(text) {
  const table = parseDelimited(text);
  if (!table.length) return 0;
  // Header row = first row with no LinkedIn URL in it.
  const hasHeader = !table[0].some(v => rqNormalizeUrl(v));
  const header = hasHeader ? table[0].map(h => h.trim() || 'col') : table[0].map((_, i) => 'col' + (i + 1));
  const body = hasHeader ? table.slice(1) : table;
  const urlCol = header.findIndex((_, i) => body.some(r => rqNormalizeUrl(r[i] || '')));
  const rows = [];
  for (const r of body) {
    const url = rqNormalizeUrl(urlCol >= 0 ? r[urlCol] || '' : '') || r.map(rqNormalizeUrl).find(Boolean);
    if (!url) continue;
    const orig = {};
    header.forEach((h, i) => { orig[h] = (r[i] || '').trim(); });
    rows.push({ url, orig });
  }
  return send({ type: 'addRows', columns: header, rows });
}

// ---------- export ----------
function csvCell(v) {
  v = String(v ?? '');
  return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}
function exportCsv(onlyFound) {
  const cols = [...state.columns, 'linkedin_url', 'phone', 'email', 'status', 'revealed_at', 'source'];
  const lines = [cols.map(csvCell).join(',')];
  for (const r of state.rows) {
    if (onlyFound && !(r.phone || r.email)) continue;
    const vals = state.columns.map(c => r.orig[c] || '');
    vals.push(r.url, r.phone, r.email, r.status, r.revealed_at, r.revealed_at ? SOURCE : '');
    lines.push(vals.map(csvCell).join(','));
  }
  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `easyleadz-contacts-${rqToday()}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// ---------- render ----------
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function render() {
  state = await send({ type: 'getState' });
  const rows = state.rows;
  const credits = rows.filter(r => r.phone && r.revealed_day === rqToday()).length;
  $('stTotal').textContent = rows.length;
  $('stPending').textContent = rows.filter(r => r.status === 'pending').length;
  $('stFound').textContent = rows.filter(r => r.phone).length;
  $('stCredits').textContent = `${credits} / ${state.cap}`;
  if (document.activeElement !== $('cap')) $('cap').value = state.cap;
  $('runMsg').textContent = state.running ? 'Running — work in the LinkedIn tab.' : '';

  const done = rows.filter(x => x.revealed_at).sort((a, b) => b.revealed_at.localeCompare(a.revealed_at)).slice(0, 10);
  $('recent').innerHTML = done.map(x =>
    `<tr><td>${esc(x.url.replace('https://www.linkedin.com/in/', '').replace(/\/$/, ''))}</td>
     <td>${esc(x.phone)}</td><td>${esc(x.email)}</td><td class="s-${x.status}">${x.status.replace('_', ' ')}</td></tr>`).join('');
}

// ---------- wiring ----------
$('file').addEventListener('change', async e => {
  const f = e.target.files[0];
  if (!f) return;
  $('importMsg').textContent = `Added ${await importText(await f.text())} new profile(s).`;
  e.target.value = '';
});
$('loadBtn').onclick = async () => {
  $('importMsg').textContent = `Added ${await importText($('paste').value)} new profile(s).`;
  $('paste').value = '';
};
$('startBtn').onclick = async () => {
  const res = await send({ type: 'start' });
  if (res?.reason === 'cap') $('runMsg').textContent = 'Daily credit cap already reached.';
  else if (res?.reason === 'done') $('runMsg').textContent = 'Nothing pending.';
};
$('pauseBtn').onclick = () => send({ type: 'pause' });
$('cap').onchange = e => send({ type: 'setCap', cap: parseInt(e.target.value, 10) || 170 });
$('exportBtn').onclick = () => exportCsv(false);
$('exportFoundBtn').onclick = () => exportCsv(true);
$('retryBtn').onclick = () => send({ type: 'retrySkipped' });
$('clearBtn').onclick = () => {
  if (confirm('Delete the whole queue and all saved contacts? Export first if you need them.')) send({ type: 'clear' });
};

chrome.storage.onChanged.addListener(render);
render();
