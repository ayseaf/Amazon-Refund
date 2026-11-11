const { describe, test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { fetchPageMetadata, downloadFavicon } = require('../src/main/metadata');

describe('page metadata', () => {
  /** @type {import('node:http').Server} */
  let server;
  let base;

  before(async () => {
    const png = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
      'base64'
    );
    server = http.createServer((req, res) => {
      if (req.url === '/page') {
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
        res.end(`<!doctype html><html><head>
          <meta property="og:title" content="Fixture &amp; Video">
          <link rel="icon" href="/icon.png">
          <title>Ignored</title>
        </head><body>Hi</body></html>`);
        return;
      }
      if (req.url === '/icon.png') {
        res.writeHead(200, { 'content-type': 'image/png' });
        res.end(png);
        return;
      }
      if (req.url === '/html-icon') {
        res.writeHead(200, { 'content-type': 'text/html' });
        res.end('<html>nope</html>');
        return;
      }
      if (req.url === '/down') {
        res.writeHead(503);
        res.end('nope');
        return;
      }
      res.writeHead(404);
      res.end('missing');
    });
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
    const { port } = server.address();
    base = `http://127.0.0.1:${port}`;
  });

  after(async () => {
    await new Promise((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));
  });

  test('reads the title and a site-relative icon', async () => {
    const meta = await fetchPageMetadata(`${base}/page`);
    assert.equal(meta.ok, true);
    assert.equal(meta.title, 'Fixture & Video');
    assert.equal(meta.url, `${base}/page`);
    assert.ok(meta.faviconUrls.includes(`${base}/icon.png`));

    const icon = await downloadFavicon(meta.faviconUrls);
    assert.equal(icon.mime, 'image/png');
    assert.ok(icon.bytes.length > 8);
  });

  test('rejects an icon response that is actually HTML', async () => {
    const icon = await downloadFavicon([`${base}/html-icon`, `${base}/missing.ico`]);
    assert.equal(icon, null);
  });

  test('keeps a usable title when the lookup fails', async () => {
    const meta = await fetchPageMetadata(`${base}/down`);
    assert.equal(meta.ok, false);
    assert.equal(meta.title, '127.0.0.1');
    assert.match(meta.error, /did not respond|name it yourself/i);
  });

  test('refuses a non-http address', async () => {
    await assert.rejects(() => fetchPageMetadata('javascript:alert(1)'), /http/);
  });
});
