const { _electron: electron } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const root = path.join(__dirname, '..');

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
  page.setDefaultTimeout(20000);
  await page.locator('[data-group-name="Video Editing"]').waitFor();
  return { app, page };
}

async function openAndRead(app, page, name) {
  await page.locator(`[data-page-name="${name}"]`).click();
  await page.getByTestId('preview').waitFor({ state: 'visible' });
  await page.waitForFunction(() => {
    const node = document.querySelector('[data-testid="preview"]');
    return node && (node.dataset.previewState === 'ready' || node.dataset.previewState === 'failed');
  }, null, { timeout: 45000 });
  const phase = await page.getByTestId('preview').getAttribute('data-preview-state');
  const shown = await page.getByTestId('preview-url').textContent();
  await page.waitForTimeout(1500);
  const details = await app.evaluate(async ({ webContents }) => {
    const preview = webContents.getAllWebContents().find((contents) => /^https?:/i.test(contents.getURL() || ''));
    if (!preview) return { error: 'no live page' };
    const info = await preview.executeJavaScript(`({
      href: location.href,
      title: document.title,
      text: (document.body && document.body.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 240)
    })`);
    const image = await preview.capturePage();
    return { ...info, jpeg: image.toJPEG(60).toString('base64') };
  });
  return { phase, shown, details };
}

function saveShot(details, file) {
  if (!details?.jpeg) return;
  fs.writeFileSync(file, Buffer.from(details.jpeg, 'base64'));
}

async function main() {
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'groups-browser-sites-'));
  const { app, page } = await launch(userData);
  const outDir = fs.existsSync('/opt/cursor/artifacts') ? '/opt/cursor/artifacts' : os.tmpdir();
  try {
    const youtube = await openAndRead(app, page, 'YouTube');
    await page.screenshot({ path: path.join(outDir, 'preview-chrome.png') });
    saveShot(youtube.details, path.join(outDir, 'youtube-preview.jpg'));
    console.log('YouTube', JSON.stringify({ phase: youtube.phase, shown: youtube.shown, href: youtube.details.href, title: youtube.details.title, text: youtube.details.text }));
    if (youtube.phase === 'failed') throw new Error(`YouTube failed to load: ${youtube.shown}`);
    const host = new URL(youtube.details.href).hostname;
    if (!/youtube\.com$|youtu\.be$|google\.com$/.test(host)) {
      throw new Error(`YouTube opened an unexpected host: ${youtube.details.href}`);
    }

    await page.getByTestId('preview-close').click();
    await page.getByTestId('preview').waitFor({ state: 'hidden' });
    await page.locator('[data-group-name="Marketing"]').click();
    const instagram = await openAndRead(app, page, 'Instagram');
    saveShot(instagram.details, path.join(outDir, 'instagram-preview.jpg'));
    console.log('Instagram', JSON.stringify({ phase: instagram.phase, shown: instagram.shown, href: instagram.details.href, title: instagram.details.title, text: instagram.details.text }));
    if (instagram.phase === 'failed') throw new Error(`Instagram failed to load: ${instagram.shown}`);
    const igHost = new URL(instagram.details.href).hostname;
    if (!/instagram\.com$|facebook\.com$|fb\.com$/.test(igHost)) {
      throw new Error(`Instagram opened an unexpected host: ${instagram.details.href}`);
    }

    const lingering = await app.evaluate(async ({ webContents }) => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      return webContents.getAllWebContents().filter((contents) => !contents.isDestroyed()).map((contents) => contents.getURL());
    });
    await page.getByTestId('preview-close').click();
    await page.getByTestId('preview').waitFor({ state: 'hidden' });
    const after = await app.evaluate(async ({ webContents }) => {
      const deadline = Date.now() + 8000;
      let urls = [];
      while (Date.now() < deadline) {
        urls = webContents.getAllWebContents().filter((contents) => !contents.isDestroyed() && /^https?:/i.test(contents.getURL() || '')).map((contents) => contents.getURL());
        if (!urls.length) return urls;
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      return urls;
    });
    if (after.length) throw new Error(`Live page still open: ${after.join(', ')} (before close: ${lingering.join(', ')})`);
    console.log('live sites ok');
  } finally {
    await app.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
