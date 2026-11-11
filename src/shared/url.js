/**
 * Canonical http(s) URL for anything the library is willing to store.
 * Returns null for empty values and for schemes other than http and https.
 * Userinfo is stripped so a pasted address cannot leave a password on disk.
 */
function normalizeHttpUrl(input) {
  let value = String(input ?? '').trim();
  if (!value) return null;
  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(value)) value = `https://${value}`;

  let url;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
  if (!url.hostname) return null;
  url.username = '';
  url.password = '';
  return url.toString();
}

function isHttpUrl(input) {
  return normalizeHttpUrl(input) != null;
}

module.exports = { normalizeHttpUrl, isHttpUrl };
