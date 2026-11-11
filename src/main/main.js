const path = require('node:path');
const fs = require('node:fs');
const {
  app,
  BrowserWindow,
  Menu,
  dialog,
  ipcMain,
  protocol,
  session,
} = require('electron');
const { Library, ID_PATTERN } = require('../data/store');
const { PreviewSession, PARTITION } = require('./preview');
const { registerIpc } = require('./ipc');
const { CHROME_UA } = require('./user-agent');

if (process.env.GROUPS_BROWSER_USER_DATA) {
  app.setPath('userData', process.env.GROUPS_BROWSER_USER_DATA);
} else {
  app.setPath('userData', path.join(app.getPath('appData'), 'GroupsBrowser'));
}

app.userAgentFallback = CHROME_UA;
app.setName('GroupsBrowser');

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'gbthumb',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

const testing = process.env.GROUPS_BROWSER_TEST === '1';
const gotLock = testing || app.requestSingleInstanceLock();
if (!gotLock) app.quit();

let win = null;
let library = null;
let preview = null;
let uiLoadedOnce = false;

function installMenu() {
  const template = [
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    { role: 'editMenu' },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'togglefullscreen' },
        { type: 'separator' },
        { role: 'toggleDevTools' },
      ],
    },
    { role: 'windowMenu' },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function configureSession() {
  const ses = session.fromPartition(PARTITION);
  ses.setUserAgent(CHROME_UA, 'en-US,en');
  const allowed = new Set(['clipboard-sanitized-write', 'clipboard-read']);
  ses.setPermissionRequestHandler((_contents, permission, callback) => {
    callback(allowed.has(permission));
  });
}

function registerThumbProtocol() {
  protocol.handle('gbthumb', async (request) => {
    let url;
    try {
      url = new URL(request.url);
    } catch {
      return new Response('Bad address', { status: 400 });
    }
    const [kind, id] = url.pathname.split('/').filter(Boolean);
    if (!id || !ID_PATTERN.test(id)) return new Response('Bad id', { status: 400 });
    if (kind === 'thumb') {
      const file = library.thumbPath(id);
      if (!fs.existsSync(file)) return new Response('Missing', { status: 404 });
      const bytes = await fs.promises.readFile(file);
      return new Response(bytes, {
        headers: { 'content-type': 'image/jpeg', 'cache-control': 'no-cache' },
      });
    }
    if (kind === 'favicon') {
      const page = library.getState().pages.find((item) => item.id === id);
      const file = library.faviconPath(id);
      if (!page || !fs.existsSync(file)) return new Response('Missing', { status: 404 });
      const bytes = await fs.promises.readFile(file);
      return new Response(bytes, {
        headers: {
          'content-type': page.faviconMime || 'application/octet-stream',
          'cache-control': 'no-cache',
        },
      });
    }
    return new Response('Missing', { status: 404 });
  });
}

function hydrateMissingFavicons() {
  const { fetchPageMetadata, downloadFavicon } = require('./metadata');
  const pending = library.getState().pages.filter((page) => !page.hasFavicon);
  const queue = pending.slice(0, 24);
  const worker = async () => {
    while (queue.length) {
      const page = queue.shift();
      try {
        const meta = await fetchPageMetadata(page.url, { timeoutMs: 4000 });
        const icon = await downloadFavicon(meta.faviconUrls || [], { timeoutMs: 4000 });
        if (!icon) continue;
        if (!library.getState().pages.some((item) => item.id === page.id)) continue;
        library.setFavicon(page.id, icon);
        if (win && !win.isDestroyed() && !win.webContents.isDestroyed()) {
          win.webContents.send('preview:event', { type: 'thumbnail', pageId: page.id });
        }
      } catch {
        // The tile keeps its letter until a later preview.
      }
    }
  };
  worker();
  worker();
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 680,
    title: 'Groups Browser',
    backgroundColor: '#f3eee6',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload/preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });

  win.once('ready-to-show', () => win.show());
  win.on('closed', () => {
    preview?.close();
    win = null;
  });
  win.webContents.on('did-finish-load', () => {
    if (uiLoadedOnce) preview?.close();
    uiLoadedOnce = true;
  });
  win.loadFile(path.join(__dirname, '../renderer/index.html'));
}

if (gotLock) {
  app.on('second-instance', () => {
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();
  });

  app.whenReady().then(() => {
    try {
      library = Library.open(app.getPath('userData'));
    } catch (error) {
      dialog.showErrorBox('Groups Browser', error instanceof Error ? error.message : 'The library could not be opened.');
      app.quit();
      return;
    }
    configureSession();
    registerThumbProtocol();
    installMenu();
    preview = new PreviewSession({
      getWindow: () => win,
      library,
      emit: (event) => {
        if (win && !win.isDestroyed() && !win.webContents.isDestroyed()) {
          win.webContents.send('preview:event', event);
        }
      },
    });
    registerIpc({ ipcMain, library, preview, getWindow: () => win });
    if (testing) {
      app.on('child-process-gone', (_event, details) => {
        console.log(`child-process-gone ${details.type} ${details.reason}`);
      });
    }
    createWindow();
    if (!testing) hydrateMissingFavicons();
    app.on('before-quit', (event) => {
      if (app.__groupsBrowserFlushing) return;
      event.preventDefault();
      app.__groupsBrowserFlushing = true;
      const flush = session.fromPartition(PARTITION).cookies.flushStore().catch(() => {});
      const timeout = new Promise((resolve) => setTimeout(resolve, 1000));
      Promise.race([flush, timeout]).finally(() => app.quit());
    });
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
}
