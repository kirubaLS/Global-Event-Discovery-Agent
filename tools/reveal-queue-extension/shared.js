// Helpers used by both the queue page and the LinkedIn content script.

// Local calendar day, so the credit counter resets at your midnight, not UTC's.
function rqToday() {
  return new Date().toLocaleDateString('en-CA');
}

function rqNormalizeUrl(u) {
  const m = String(u).match(/linkedin\.com\/in\/([^/?#\s"',]+)/i);
  if (!m) return null;
  let slug = m[1];
  try { slug = decodeURIComponent(slug); } catch (e) {}
  return 'https://www.linkedin.com/in/' + slug.toLowerCase() + '/';
}

// Indian mobiles: optional +91/91/0 prefix, 10 digits starting 6-9.
function rqExtractPhones(text) {
  const out = [];
  const re = /(?<!\d)(?:\+?91[\s-]?|0)?([6-9]\d{4})[\s-]?(\d{5})(?!\d)/g;
  let m;
  while ((m = re.exec(text))) {
    const p = '+91' + m[1] + m[2];
    if (!out.includes(p)) out.push(p);
  }
  return out;
}

function rqExtractEmails(text) {
  const all = text.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) || [];
  return [...new Set(all.map(e => e.toLowerCase()))];
}
