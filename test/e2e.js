const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');

const root = path.join(__dirname, '..');
const ICON = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64'
);

function html(title, marker) {
  return `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title><link rel="icon" href="/icon.png"></head><body><h1 id="marker">${marker}</h1></body></html>`;
}

async function startServer() {
  const pages = {
    '/fixture': html('Fixture Video', 'Preview loaded'),
    '/other': html('Other Page', 'Other loaded'),
  };
  const server = http.createServer((req, res) => {
    const url = (req.url || '/').split('?')[0];
    if (url === '/icon.png' || url === '/favicon.ico') {
      res.writeHead(200, { 'content-type': 'image/png', 'cache-control': 'no-store' });
      res.end(ICON);
      return;
    }
    if (pages[url]) {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      res.end(pages[url]);
      return;
    }
    res.writeHead(404);
    res.end('missing');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  return {
    base: `http://127.0.0.1:${port}`,
    close: () => new Promise((resolve, reject) => server.close((err) => (err ? reject(err) : resolve()))),
  };
}

async function launch(userData) {
  const app = await electron.launch({
    args: [root],
    cwd: root,
    executablePath: require('electron'),
    env: {
      ...process.env,
      GROUPS_BROWSER_USER_DATA: userData,
      GROUPS_BROWSER_TEST: '1',
    },
    timeout: 30000,
  });
  const page = await app.firstWindow();
  page.setDefaultTimeout(12000);
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') console.log(`UI ${msg.type()}: ${msg.text()}`);
  });
  page.on('pageerror', (error) => console.log(`UI pageerror: ${error.message}`));
  await page.locator('[data-group-name="Video Editing"]').waitFor({ timeout: 20000 });
  return { app, page };
}

async function inspect(app) {
  return app.evaluate(async ({ webContents, app: electronApp }) => {
    const contents = webContents.getAllWebContents()
      .filter((contents) => !contents.isDestroyed())
      .map((contents) => ({ url: contents.getURL(), type: contents.getType() }));
    const metrics = electronApp.getAppMetrics().map((metric) => ({
      type: metric.type,
      pid: metric.pid,
      memoryKB: metric.memory.workingSetSize,
    }));
    return { contents, metrics };
  });
}

function httpContents(info) {
  return info.contents.filter((item) => /^https?:/i.test(item.url));
}

function tabCount(info) {
  return info.metrics.filter((metric) => metric.type === 'Tab').length;
}

async function waitForPreview(page, expected) {
  await page.getByTestId('preview').waitFor({ state: 'visible' });
  await page.waitForFunction(() => {
    const node = document.querySelector('[data-testid="preview"]');
    return node && (node.dataset.previewState === 'ready' || node.dataset.previewState === 'failed');
  });
  const phase = await page.getByTestId('preview').getAttribute('data-preview-state');
  if (phase === 'failed') {
    throw new Error(`Preview failed: ${await page.locator('#preview-failed').textContent()}`);
  }
  if (expected) {
    await page.waitForFunction((needle) => {
      const node = document.querySelector('[data-testid="preview-url"]');
      return Boolean(node && node.textContent.includes(needle));
    }, expected);
  }
}

async function groupNames(page) {
  return page.locator('#group-list [data-group-name]').evaluateAll((nodes) => nodes.map((node) => node.dataset.groupName));
}

async function main() {
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'groups-browser-e2e-'));
  const site = await startServer();
  let app;
  let page;
  try {
    ({ app, page } = await launch(userData));
    const baseline = await inspect(app);

    await page.getByTestId('new-group').click();
    await page.getByTestId('group-name').fill('Social Media');
    await page.locator('[data-icon="💬"]').click();
    await page.getByTestId('group-create').click();
    await page.locator('[data-group-name="Social Media"]').waitFor();
    await page.locator('#group-title', { hasText: 'Social Media' }).waitFor();

    await page.getByTestId('add-page').click();
    await page.getByTestId('page-url').fill(`${site.base}/fixture`);
    await page.getByTestId('page-name').waitFor();
    await page.waitForFunction(() => document.querySelector('[data-testid="page-name"]').value === 'Fixture Video');
    await page.getByTestId('page-add').click();
    await page.locator('[data-page-name="Fixture Video"]').waitFor();

    await page.getByTestId('add-page').click();
    await page.getByTestId('page-url').fill(`${site.base}/other`);
    await page.waitForFunction(() => document.querySelector('[data-testid="page-name"]').value === 'Other Page');
    await page.getByTestId('page-add').click();
    await page.locator('[data-page-name="Other Page"]').waitFor();

    await page.getByTestId('search').fill('vimeo');
    await page.locator('[data-page-name="Vimeo"]').waitFor();
    await page.locator('[data-page-name="Fixture Video"]').waitFor({ state: 'hidden' });
    await page.getByTestId('search').fill('');
    await page.locator('[data-page-name="Fixture Video"]').waitFor();

    await page.locator('[data-page-name="Fixture Video"]').click();
    await waitForPreview(page, '/fixture');
    const marker = await app.evaluate(async ({ webContents }) => {
      const preview = webContents.getAllWebContents().find((contents) => (contents.getURL() || '').includes('/fixture'));
      if (!preview) return '';
      return preview.executeJavaScript('document.querySelector("#marker").textContent');
    });
    assert.equal(marker, 'Preview loaded');
    const during = await inspect(app);
    assert.equal(httpContents(during).length, 1, `expected one live page, saw ${JSON.stringify(during.contents)}`);
    assert.ok(tabCount(during) > tabCount(baseline), 'opening a preview should add a renderer');
    const viewBounds = await app.evaluate(async ({ BrowserWindow }) => {
      const win = BrowserWindow.getAllWindows()[0];
      const [width, height] = win.getContentSize();
      return {
        width,
        height,
        views: win.contentView.children.map((view) => view.getBounds()),
      };
    });
    const previewBounds = viewBounds.views.find((box) => box.x > 200 && box.width > 100);
    assert.ok(previewBounds, `preview view was not placed beside the grid: ${JSON.stringify(viewBounds)}`);
    assert.ok(previewBounds.width < viewBounds.width * 0.85, `preview should not be fullscreen: ${JSON.stringify(viewBounds)}`);
    assert.ok(previewBounds.x >= 240, `preview overlaps the sidebar: ${JSON.stringify(viewBounds)}`);

    await page.locator('[data-page-name="Other Page"]').click();
    await waitForPreview(page, '/other');
    const replaced = httpContents(await inspect(app));
    assert.equal(replaced.length, 1);
    assert.match(replaced[0].url, /\/other$/);

    await page.getByTestId('preview-close').click();
    await page.getByTestId('preview').waitFor({ state: 'hidden' });
    await page.waitForFunction(() => document.querySelector('#group-title').textContent === 'Social Media');
    let closed = await inspect(app);
    const deadline = Date.now() + 8000;
    while (Date.now() < deadline && (httpContents(closed).length > 0 || tabCount(closed) > tabCount(baseline))) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      closed = await inspect(app);
    }
    assert.deepEqual(httpContents(closed), [], `preview web contents lingered: ${JSON.stringify(closed.contents)}`);
    assert.ok(
      tabCount(closed) <= tabCount(baseline),
      `renderer lingered after close: baseline ${tabCount(baseline)}, now ${tabCount(closed)}, ${JSON.stringify(closed.metrics)}`
    );
    const idleKB = closed.metrics.reduce((sum, metric) => sum + metric.memoryKB, 0);
    let pssKB = 0;
    for (const metric of closed.metrics) {
      try {
        const rollup = fs.readFileSync(`/proc/${metric.pid}/smaps_rollup`, 'utf8');
        const match = rollup.match(/^Pss:\s+(\d+)/m);
        if (match) pssKB += Number(match[1]);
      } catch {
        // The process may have exited between the sample and the read.
      }
    }
    console.log(`idle working set sum ${Math.round(idleKB / 1024)} MB, proportional ${Math.round(pssKB / 1024)} MB`);
    console.log(closed.metrics.map((metric) => `${metric.type} ${Math.round(metric.memoryKB / 1024)} MB`).join(', '));

    await page.locator('[data-page-name="Fixture Video"]').click();
    await waitForPreview(page, '/fixture');
    await page.keyboard.press('Escape');
    await page.getByTestId('preview').waitFor({ state: 'hidden' });
    const afterEsc = httpContents(await inspect(app));
    assert.deepEqual(afterEsc, []);

    await page.locator('[data-page-name="Fixture Video"]').click();
    await waitForPreview(page, '/fixture');
    const cookieWrite = await app.evaluate(async ({ webContents }) => {
      const preview = webContents.getAllWebContents().find((contents) => (contents.getURL() || '').includes('/fixture'));
      return preview.executeJavaScript('document.cookie = "gb_session=signed-in; path=/; max-age=31536000"; document.cookie');
    });
    assert.match(cookieWrite, /gb_session=signed-in/);
    await page.getByTestId('save-to-group').click();
    await page.locator('[data-testid="save-group"][data-group-name="Video Editing"]').click();
    await page.locator('#toast', { hasText: 'Saved to Video Editing' }).waitFor();
    await page.getByTestId('save-to-group').click();
    await page.getByTestId('save-new-group').click();
    await page.locator('[data-group-name="Fixture Video"]').waitFor();

    await page.keyboard.press('Escape');
    await page.getByTestId('preview').waitFor({ state: 'hidden' });
    await page.locator('[data-group-name="Video Editing"]').click();
    await page.locator('#group-title', { hasText: 'Video Editing' }).waitFor();
    await page.locator('[data-page-name="Fixture Video"]').waitFor();

    const beforeOrder = await groupNames(page);
    await page.locator('[data-group-name="Marketing"]').dragTo(page.locator('[data-group-name="Video Editing"]'));
    await page.waitForFunction((previous) => {
      const names = [...document.querySelectorAll('#group-list [data-group-name]')].map((node) => node.dataset.groupName);
      return names.join('|') !== previous.join('|');
    }, beforeOrder);
    const afterOrder = await groupNames(page);
    assert.ok(afterOrder.indexOf('Marketing') < beforeOrder.indexOf('Marketing'));

    await page.screenshot({ path: path.join(os.tmpdir(), 'groups-browser-library.png') });
    await app.close();
    app = null;

    ({ app, page } = await launch(userData));
    await page.locator('[data-group-name="Social Media"]').waitFor();
    const restored = await groupNames(page);
    assert.deepEqual(restored, afterOrder);
    await page.locator('[data-group-name="Social Media"]').click();
    await page.locator('[data-page-name="Fixture Video"]').click();
    await waitForPreview(page, '/fixture');
    const cookie = await app.evaluate(async ({ webContents }) => {
      const preview = webContents.getAllWebContents().find((contents) => (contents.getURL() || '').includes('/fixture'));
      return preview.executeJavaScript('document.cookie');
    });
    assert.match(cookie, /gb_session=signed-in/);
    console.log('e2e ok');
  } catch (error) {
    if (page) {
      await page.screenshot({ path: path.join(os.tmpdir(), 'groups-browser-fail.png') }).catch(() => {});
      console.log(`screenshot ${path.join(os.tmpdir(), 'groups-browser-fail.png')}`);
    }
    throw error;
  } finally {
    if (app) await app.close().catch(() => {});
    await site.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
