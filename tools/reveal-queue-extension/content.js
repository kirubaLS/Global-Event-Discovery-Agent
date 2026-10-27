// Runs on LinkedIn profile pages. Only does anything in the tab the queue
// opened: shows a control bar, watches for the phone/email the EasyLeadz
// extension reveals, saves it and moves on to the next profile.

(async () => {
  const info = await chrome.runtime.sendMessage({ type: 'whoami' });
  if (!info) return;

  const AUTO_SAVE_SECONDS = 3;
  // LinkedIn's own page regions; numbers in here (About section, chats) are
  // not EasyLeadz results.
  const LINKEDIN_REGIONS = 'main, header, #global-nav, #msg-overlay, .msg-overlay-container';

  // ---------- UI (closed shadow root so our own text is never scanned) ----------
  const host = document.createElement('div');
  host.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:2147483647;';
  const root = host.attachShadow({ mode: 'closed' });
  root.innerHTML = `
    <style>
      .bar { width: 340px; background: #fff; color: #1b1f24; border: 1px solid #d9dde3; border-radius: 10px;
             box-shadow: 0 6px 24px rgba(0,0,0,.18); padding: 12px; font: 13px/1.4 system-ui, sans-serif; }
      .top { display: flex; justify-content: space-between; color: #667085; font-size: 12px; }
      .label { font-weight: 600; margin: 4px 0; }
      .status { margin: 6px 0; padding: 6px 8px; border-radius: 6px; background: #f2f4f7; }
      .status.found { background: #e7f6ec; color: #157f3b; }
      .status.warn { background: #fef0e6; color: #b54708; }
      input { width: 100%; box-sizing: border-box; margin: 3px 0; padding: 6px; border: 1px solid #d9dde3;
              border-radius: 6px; font: inherit; }
      .row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
      button { flex: 1; padding: 6px 8px; border: 1px solid #d9dde3; border-radius: 6px; background: #fff;
               font: inherit; cursor: pointer; }
      button.primary { background: #0a66c2; border-color: #0a66c2; color: #fff; }
    </style>
    <div class="bar">
      <div class="top"><span id="pos"></span><span id="credits"></span></div>
      <div class="label" id="label"></div>
      <div class="status" id="status">Click Reveal in the EasyLeadz extension…</div>
      <input id="phone" placeholder="Mobile (auto-filled)">
      <input id="email" placeholder="Email (auto-filled)">
      <input id="paste" placeholder="…or paste EasyLeadz text here">
      <div class="row">
        <button class="primary" id="save">Save &amp; next</button>
        <button id="nodata">No data</button>
        <button id="skip">Skip</button>
      </div>
      <div class="row">
        <button id="clip">Read clipboard</button>
        <button id="pause">Pause</button>
      </div>
    </div>`;
  document.documentElement.appendChild(host);
  const $ = id => root.getElementById(id);

  $('pos').textContent = `#${info.position} of ${info.total} · ${info.pending} left`;
  $('credits').textContent = `credits today ${info.credits}/${info.cap}`;
  $('label').textContent = Object.values(info.item.orig)
    .filter(v => v && !rqNormalizeUrl(v)).slice(0, 3).join(' · ') || info.item.url;

  function setStatus(text, cls = '') {
    $('status').textContent = text;
    $('status').className = 'status ' + cls;
  }

  // ---------- detection ----------
  let userEdited = false, done = false, countdown = null;

  function scanText() {
    let text = document.body ? document.body.innerText : '';
    // EasyLeadz may render inside an open shadow root.
    for (const el of document.querySelectorAll('*')) {
      if (el.shadowRoot) text += '\n' + el.shadowRoot.textContent;
    }
    const excluded = [...document.querySelectorAll(LINKEDIN_REGIONS)].map(e => e.innerText).join('\n');
    const exPhones = new Set(rqExtractPhones(excluded)), exEmails = new Set(rqExtractEmails(excluded));
    return {
      phones: rqExtractPhones(text).filter(p => !exPhones.has(p)),
      emails: rqExtractEmails(text).filter(e => !exEmails.has(e)),
    };
  }

  function fill(phones, emails) {
    if (phones.length) $('phone').value = phones.join(' / ');
    if (emails.length) $('email').value = emails.join(' / ');
  }

  function scan() {
    if (done || userEdited) return;
    const { phones, emails } = scanText();
    fill(phones, emails);
    if (phones.length && !countdown) startAutoSave();
    else if (!phones.length && emails.length) setStatus('Email found. Reveal the phone, or Save if there is none.', 'warn');
  }

  function startAutoSave() {
    let left = AUTO_SAVE_SECONDS;
    const tick = () => {
      if (left <= 0) { clearInterval(countdown); finish('auto'); return; }
      setStatus(`Got it — saving in ${left}s (edit a field to stop)`, 'found');
      left--;
    };
    tick();
    countdown = setInterval(tick, 1000);
  }

  function stopAutoSave(msg) {
    if (countdown) clearInterval(countdown);
    countdown = null;
    if (msg) setStatus(msg);
  }

  let debounce = null;
  new MutationObserver(() => {
    clearTimeout(debounce);
    debounce = setTimeout(scan, 400);
  }).observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  // Mutations inside shadow roots don't reach the observer above.
  const poll = setInterval(scan, 2000);
  scan();

  // ---------- actions ----------
  async function finish(status) {
    if (done) return;
    done = true;
    stopAutoSave();
    clearInterval(poll);
    const res = await chrome.runtime.sendMessage({
      type: 'finish', status, phone: $('phone').value, email: $('email').value,
    });
    if (res?.next) {
      let left = Math.round(res.delay / 1000);
      const tick = () => {
        if (left <= 0) { location.href = res.next; return; }
        setStatus(`Saved. Next profile in ${left}s…`, 'found');
        left--;
      };
      tick();
      const t = setInterval(tick, 1000);
      $('pause').onclick = async () => {
        clearInterval(t);
        await chrome.runtime.sendMessage({ type: 'pause' });
        setStatus('Paused. Resume from the queue page.');
      };
    } else if (res?.reason === 'cap') {
      setStatus('Daily credit cap reached. Stopped — continue tomorrow.', 'warn');
    } else if (res?.reason === 'done') {
      setStatus('Queue finished 🎉 Export from the queue page.', 'found');
    } else {
      setStatus('Saved. Queue is paused.');
    }
  }

  for (const id of ['phone', 'email']) {
    $(id).addEventListener('input', () => { userEdited = true; stopAutoSave('Edited — press Save & next when ready.'); });
  }
  function fromPasted(text) {
    userEdited = true;
    stopAutoSave();
    fill(rqExtractPhones(text), rqExtractEmails(text));
    setStatus('Filled from pasted text — check and press Save & next.');
  }
  $('paste').addEventListener('input', e => fromPasted(e.target.value));
  $('clip').onclick = async () => {
    try { fromPasted(await navigator.clipboard.readText()); }
    catch (e) { setStatus('Could not read clipboard — paste into the box instead.', 'warn'); }
  };
  $('save').onclick = () => finish('auto');
  $('nodata').onclick = () => finish('no_data');
  $('skip').onclick = () => finish('skipped');
  $('pause').onclick = async () => {
    stopAutoSave();
    await chrome.runtime.sendMessage({ type: 'pause' });
    setStatus('Paused. You can still Save this one; resume from the queue page.');
  };
})();
