const { normalizeHttpUrl } = require('../shared/url');
const { siteLabel } = require('../shared/copy');
const { CHROME_UA } = require('./user-agent');

const FETCH_HEADERS = {
  'user-agent': CHROME_UA,
  accept: 'text/html,application/xhtml+xml,image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
};

function decodeEntities(text) {
  return text
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#0*39;|&#x0*27;/gi, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)));
}

function readTitle(html) {
  const patterns = [
    /<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["'][^>]*>/i,
    /<meta[^>]*content=["']([^"']+)["'][^>]*property=["']og:title["'][^>]*>/i,
  ];
  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match) return decodeEntities(match[1]).replace(/\s+/g, ' ').trim();
  }
  const title = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  if (!title) return '';
  return decodeEntities(title[1]).replace(/\s+/g, ' ').trim();
}

function readIcons(html, base) {
  const urls = [];
  const tags = html.match(/<link\b[^>]*>/gi) || [];
  for (const tag of tags) {
    const rel = /rel=["']([^"']+)["']/i.exec(tag)?.[1] || '';
    const href = /href=["']([^"']+)["']/i.exec(tag)?.[1] || '';
    if (!href || !/icon/i.test(rel)) continue;
    try {
      urls.push(new URL(href, base).toString());
    } catch {
      // Ignore a malformed icon href and keep looking.
    }
  }
  try {
    urls.push(new URL('/favicon.ico', base).toString());
  } catch {
    // No origin to guess from.
  }
  return [...new Set(urls)];
}

async function fetchPageMetadata(rawUrl, { fetchImpl = globalThis.fetch, timeoutMs = 8000 } = {}) {
  const url = normalizeHttpUrl(rawUrl);
  if (!url) throw new Error('Enter a full http or https address.');

  const fallback = (error) => ({
    ok: false,
    url,
    title: siteLabel(url, ''),
    faviconUrls: [],
    error,
  });

  try {
    const response = await fetchImpl(url, {
      redirect: 'follow',
      headers: FETCH_HEADERS,
      signal: AbortSignal.timeout(timeoutMs),
    });
    const finalUrl = normalizeHttpUrl(response.url || url) || url;
    if (!response.ok) {
      return {
        ok: false,
        url: finalUrl,
        title: siteLabel(finalUrl, ''),
        faviconUrls: [],
        error: 'The page did not respond. You can still name it yourself.',
      };
    }
    const type = response.headers.get('content-type') || '';
    if (!/html|xml/i.test(type)) {
      return {
        ok: true,
        url: finalUrl,
        title: siteLabel(finalUrl, ''),
        faviconUrls: readIcons('', finalUrl),
      };
    }
    const html = (await response.text()).slice(0, 500_000);
    const title = readTitle(html);
    return {
      ok: true,
      url: finalUrl,
      title: title || siteLabel(finalUrl, ''),
      faviconUrls: readIcons(html, finalUrl),
    };
  } catch (error) {
    if (error instanceof Error && /http or https/.test(error.message)) throw error;
    return fallback('The page did not respond. You can still name it yourself.');
  }
}

function looksLikeImage(bytes, contentType) {
  const type = (contentType || '').toLowerCase();
  if (type.includes('text/html') || type.includes('application/json')) return false;
  if (bytes.length < 8) return false;
  const head = bytes.subarray(0, 16).toString('utf8').trimStart().toLowerCase();
  if (head.startsWith('<!doctype') || head.startsWith('<html') || head.startsWith('<head')) return false;
  if (type.startsWith('image/')) return true;
  if (bytes[0] === 0x89 && bytes[1] === 0x50) return true;
  if (bytes[0] === 0xff && bytes[1] === 0xd8) return true;
  if (bytes[0] === 0x00 && bytes[1] === 0x00 && bytes[2] === 0x01 && bytes[3] === 0x00) return true;
  if (head.startsWith('<svg') || head.startsWith('<?xml')) return true;
  if (bytes.slice(0, 4).toString() === 'RIFF' && bytes.slice(8, 12).toString() === 'WEBP') return true;
  return false;
}

function mimeFrom(contentType, bytes) {
  const type = (contentType || '').split(';')[0].trim().toLowerCase();
  if (type.startsWith('image/')) return type;
  if (bytes[0] === 0x89) return 'image/png';
  if (bytes[0] === 0xff) return 'image/jpeg';
  if (bytes[0] === 0x00) return 'image/x-icon';
  const head = bytes.subarray(0, 16).toString('utf8').trimStart().toLowerCase();
  if (head.startsWith('<svg') || head.startsWith('<?xml')) return 'image/svg+xml';
  return 'application/octet-stream';
}

async function downloadFavicon(candidates, { fetchImpl = globalThis.fetch, timeoutMs = 8000 } = {}) {
  for (const candidate of candidates || []) {
    const url = normalizeHttpUrl(candidate);
    if (!url) continue;
    try {
      const response = await fetchImpl(url, {
        redirect: 'follow',
        headers: FETCH_HEADERS,
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!response.ok) continue;
      const buffer = Buffer.from(await response.arrayBuffer());
      if (buffer.length > 512 * 1024) continue;
      const contentType = response.headers.get('content-type') || '';
      if (!looksLikeImage(buffer, contentType)) continue;
      return { bytes: buffer, mime: mimeFrom(contentType, buffer) };
    } catch {
      // Try the next candidate.
    }
  }
  return null;
}

module.exports = { fetchPageMetadata, downloadFavicon };
