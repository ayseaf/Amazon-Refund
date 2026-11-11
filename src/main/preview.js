const { WebContentsView } = require('electron');
const { normalizeHttpUrl } = require('../shared/url');
const { shouldRefreshThumbnail } = require('../shared/thumbnail-policy');
const { CHROME_UA } = require('./user-agent');

const PARTITION = 'persist:groups-browser';

/**
 * One WebContentsView for the whole app. Opening a page replaces it.
 * Closing removes the view and destroys that web contents.
 */
class PreviewSession {
  constructor({ getWindow, library, emit }) {
    this.getWindow = getWindow;
    this.library = library;
    this.emit = emit;
    this.view = null;
    this.generation = 0;
    this.pageId = null;
    this.savedUrl = null;
    this.bounds = { x: 0, y: 0, width: 0, height: 0 };
  }

  async open({ pageId, bounds }) {
    const page = this.library.requirePage(pageId);
    const url = page.url;
    const gen = ++this.generation;
    this.destroyView();
    if (gen !== this.generation) return;

    const view = new WebContentsView({
      webPreferences: {
        partition: PARTITION,
        sandbox: true,
        contextIsolation: true,
        nodeIntegration: false,
        nodeIntegrationInSubFrames: false,
        webSecurity: true,
        allowRunningInsecureContent: false,
        spellcheck: false,
        backgroundThrottling: true,
      },
    });
    view.setBackgroundColor('#f3eee6');
    const wc = view.webContents;
    wc.setUserAgent(CHROME_UA);

    wc.setWindowOpenHandler(({ url: next }) => {
      const allowed = normalizeHttpUrl(next);
      if (allowed) {
        setImmediate(() => {
          if (!wc.isDestroyed() && gen === this.generation) {
            wc.loadURL(allowed, { userAgent: CHROME_UA }).catch(() => {});
          }
        });
      }
      return { action: 'deny' };
    });

    const blockUnsafe = (details) => {
      if (details.isMainFrame === false) return;
      if (!normalizeHttpUrl(details.url)) details.preventDefault();
    };
    wc.on('will-navigate', blockUnsafe);
    wc.on('will-redirect', blockUnsafe);
    wc.on('did-start-loading', () => {
      if (gen !== this.generation || wc.isDestroyed()) return;
      this.emitState('loading', wc);
    });
    wc.on('did-navigate', () => this.emitState('navigated', wc, gen));
    wc.on('did-navigate-in-page', () => this.emitState('navigated', wc, gen));
    wc.on('page-title-updated', () => this.emitState('navigated', wc, gen));
    wc.on('did-finish-load', () => {
      if (gen !== this.generation || wc.isDestroyed()) return;
      this.emitState('ready', wc, gen);
      this.captureLater(gen, wc, pageId, url);
    });
    wc.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
      if (!isMainFrame || errorCode === -3) return;
      if (gen !== this.generation || wc.isDestroyed()) return;
      this.emit({
        type: 'failed',
        url: validatedURL,
        title: '',
        pageId,
        message: 'This page didn’t load. Try Reload.',
        detail: errorDescription || '',
      });
    });
    wc.on('before-input-event', (event, input) => {
      if (input.type === 'keyDown' && input.key === 'Escape' && !input.alt && !input.control && !input.meta) {
        event.preventDefault();
        this.close();
      }
    });
    wc.on('render-process-gone', () => {
      if (gen !== this.generation) return;
      this.destroyView();
      this.emit({ type: 'crashed' });
    });
    wc.on('destroyed', () => {
      if (gen !== this.generation) return;
      if (this.view && this.view.webContents === wc) this.view = null;
      this.pageId = null;
      this.savedUrl = null;
      this.emit({ type: 'closed' });
    });

    this.view = view;
    this.pageId = pageId;
    this.savedUrl = url;
    this.setBounds(bounds);

    const win = this.getWindow();
    if (!win || win.isDestroyed()) {
      this.destroyView();
      throw new Error('The window is not available.');
    }
    win.contentView.addChildView(view);
    this.emitState('loading', wc, gen);
    try {
      await wc.loadURL(url, { userAgent: CHROME_UA });
    } catch {
      // did-fail-load reports the visible error. A close during load rejects too.
    }
  }

  setVisible(visible) {
    if (!this.view) return;
    this.view.setVisible(Boolean(visible));
  }

  setBounds(bounds) {
    this.bounds = sanitizeBounds(bounds);
    if (!this.view || this.bounds.width <= 0 || this.bounds.height <= 0) return;
    this.view.setBounds(this.bounds);
  }

  reload() {
    const wc = this.view?.webContents;
    if (wc && !wc.isDestroyed()) wc.reload();
  }

  currentURL() {
    const wc = this.view?.webContents;
    if (!wc || wc.isDestroyed()) return '';
    return wc.getURL() || '';
  }

  currentTitle() {
    const wc = this.view?.webContents;
    if (!wc || wc.isDestroyed()) return '';
    return wc.getTitle() || '';
  }

  close() {
    if (!this.view) {
      this.generation += 1;
      return;
    }
    this.generation += 1;
    this.destroyView();
    this.emit({ type: 'closed' });
  }

  destroyView() {
    const view = this.view;
    this.view = null;
    this.pageId = null;
    this.savedUrl = null;
    if (!view) return;
    const wc = view.webContents;
    const win = this.getWindow();
    try {
      if (win && !win.isDestroyed()) win.contentView.removeChildView(view);
    } catch {
      // The window may already have dropped the view.
    }
    if (wc && !wc.isDestroyed()) {
      try {
        wc.close({ waitForBeforeUnload: false });
      } catch {
        // Already going away.
      }
    }
  }

  emitState(type, wc, gen) {
    if (gen != null && gen !== this.generation) return;
    if (!wc || wc.isDestroyed()) return;
    this.emit({
      type,
      url: wc.getURL(),
      title: wc.getTitle(),
      pageId: this.pageId,
    });
  }

  captureLater(gen, wc, pageId, savedUrl) {
    setTimeout(async () => {
      if (gen !== this.generation || wc.isDestroyed()) return;
      const page = this.library.getState().pages.find((item) => item.id === pageId);
      if (!page) return;
      const currentUrl = wc.getURL();
      if (
        !shouldRefreshThumbnail({
          capturedAt: page.thumbnailCapturedAt,
          now: Date.now(),
          savedUrl,
          currentUrl,
        })
      ) {
        return;
      }
      try {
        const image = await wc.capturePage();
        if (gen !== this.generation || wc.isDestroyed()) return;
        const jpeg = cropToJpeg(image);
        if (!jpeg) return;
        this.library.setThumbnail(pageId, { bytes: jpeg, capturedAt: new Date().toISOString() });
        this.emit({ type: 'thumbnail', pageId });
      } catch {
        // The favicon tile stays until a later visit can be snapshotted.
      }
    }, 1100);
  }
}

function cropToJpeg(image) {
  if (!image || image.isEmpty()) return null;
  const size = image.getSize();
  if (!size.width || !size.height) return null;
  const target = 320 / 200;
  let cropW = size.width;
  let cropH = size.height;
  if (cropW / cropH > target) cropW = Math.round(cropH * target);
  else cropH = Math.round(cropW / target);
  cropW = Math.max(1, Math.min(size.width, cropW));
  cropH = Math.max(1, Math.min(size.height, cropH));
  const cropped = image.crop({
    x: Math.max(0, Math.round((size.width - cropW) / 2)),
    y: Math.max(0, Math.round((size.height - cropH) / 2)),
    width: cropW,
    height: cropH,
  });
  const resized = cropped.resize({ width: 320, height: 200, quality: 'good' });
  if (isMostlyBlank(resized)) return null;
  return resized.toJPEG(72);
}

function isMostlyBlank(image) {
  const { width, height } = image.getSize();
  if (!width || !height) return true;
  const bitmap = image.toBitmap();
  const pixels = width * height;
  const step = Math.max(4, Math.floor(pixels / 400) * 4);
  let count = 0;
  let sum = 0;
  let sumSq = 0;
  for (let i = 0; i + 2 < bitmap.length; i += step) {
    const lum = (bitmap[i] + bitmap[i + 1] + bitmap[i + 2]) / 3;
    sum += lum;
    sumSq += lum * lum;
    count += 1;
  }
  if (!count) return true;
  const mean = sum / count;
  const variance = sumSq / count - mean * mean;
  return mean > 245 && variance < 30;
}

function sanitizeBounds(bounds = {}) {
  const values = ['x', 'y', 'width', 'height'].map((key) => Number(bounds[key]));
  if (values.some((value) => !Number.isFinite(value))) return { x: 0, y: 0, width: 0, height: 0 };
  const [x, y, width, height] = values;
  return {
    x: Math.max(0, Math.round(x)),
    y: Math.max(0, Math.round(y)),
    width: Math.max(0, Math.round(width)),
    height: Math.max(0, Math.round(height)),
  };
}

module.exports = { PreviewSession, PARTITION, sanitizeBounds };
