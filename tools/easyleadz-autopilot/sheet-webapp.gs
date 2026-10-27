// Google Sheet bridge for autopilot.mjs.
//
// Setup (once):
//   1. Open your leads sheet → Extensions → Apps Script. Paste this whole file.
//   2. Change TOKEN below to a long random string (it's the password for this web app).
//   3. Deploy → New deployment → type "Web app"
//        Execute as: Me    Who has access: Anyone
//      Authorise, then copy the Web app URL (ends in /exec).
//   4. Run:  node autopilot.mjs --sheet <that URL> --token <your TOKEN>
//
// The script reads every row of the tab, and for each result finds the row with
// the same LinkedIn URL and fills phone / email / status / revealed_at / source
// (adding those columns if missing). Profiles not in the sheet are appended.

const TOKEN = 'change-this-to-a-long-random-string';
const SHEET_NAME = ''; // blank = first tab
const OUT_COLS = ['phone', 'email', 'status', 'revealed_at', 'source'];

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = SHEET_NAME ? ss.getSheetByName(SHEET_NAME) : ss.getSheets()[0];
  if (!sh) throw new Error('No tab named ' + SHEET_NAME);
  return sh;
}

function norm_(u) {
  const m = String(u).match(/linkedin\.com\/in\/([^\/?#\s"',]+)/i);
  if (!m) return null;
  let slug = m[1];
  try { slug = decodeURIComponent(slug); } catch (e) {}
  return 'https://www.linkedin.com/in/' + slug.toLowerCase() + '/';
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// Returns {header, col(name)}; adds any missing columns to row 1.
function ensureCols_(sh, names) {
  const lastCol = sh.getLastColumn();
  const header = lastCol ? sh.getRange(1, 1, 1, lastCol).getDisplayValues()[0] : [];
  for (const n of names) {
    if (header.indexOf(n) < 0) {
      header.push(n);
      sh.getRange(1, header.length).setValue(n);
    }
  }
  return { header, col: n => header.indexOf(n) + 1 };
}

function doGet(e) {
  if (e.parameter.token !== TOKEN) return json_({ error: 'bad token' });
  return json_({ values: sheet_().getDataRange().getDisplayValues() });
}

function doPost(e) {
  let body;
  try { body = JSON.parse(e.postData.contents); } catch (err) { return json_({ error: 'bad JSON' }); }
  if (body.token !== TOKEN) return json_({ error: 'bad token' });

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const sh = sheet_();
    const url = norm_(body.url);
    if (!url) return json_({ error: 'no LinkedIn URL' });

    const values = sh.getDataRange().getDisplayValues();
    let row = -1;
    for (let r = 1; r < values.length; r++) {
      if (values[r].some(v => norm_(v) === url)) { row = r + 1; break; }
    }

    if (row < 0) {
      // Not in the sheet (CSV input): append it with the original CSV columns.
      const fields = body.fields || {};
      const existing = values.length ? values[0] : [];
      const urlCol = existing.findIndex(h => /linkedin/i.test(h));
      // Match CSV columns to sheet columns by name (any case); the URL goes in
      // the sheet's LinkedIn column whatever the CSV called it.
      const target = {};
      for (const k of Object.keys(fields)) {
        const i = existing.findIndex(h => h.trim().toLowerCase() === k.trim().toLowerCase());
        target[k] = i >= 0 ? existing[i] : (norm_(fields[k]) && urlCol >= 0 ? existing[urlCol] : k);
      }
      const urlTarget = urlCol >= 0 ? existing[urlCol] : 'linkedin_url';
      const { col } = ensureCols_(sh, [...Object.values(target), urlTarget, ...OUT_COLS]);
      row = Math.max(sh.getLastRow(), 1) + 1;
      for (const k of Object.keys(fields)) if (fields[k]) sh.getRange(row, col(target[k])).setValue(fields[k]);
      sh.getRange(row, col(urlTarget)).setValue(body.url);
    }

    const { col } = ensureCols_(sh, OUT_COLS);
    for (const c of OUT_COLS) {
      // Plain-text format so "+91…" isn't turned into a number or formula.
      sh.getRange(row, col(c)).setNumberFormat('@').setValue(body[c] == null ? '' : String(body[c]));
    }
    return json_({ ok: true, row });
  } finally {
    lock.releaseLock();
  }
}
