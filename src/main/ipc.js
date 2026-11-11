const fs = require('node:fs');
const { dialog, shell } = require('electron');
const { fetchPageMetadata, downloadFavicon } = require('./metadata');
const { siteLabel } = require('../shared/copy');
const { normalizeHttpUrl } = require('../shared/url');

function registerIpc({ ipcMain, library, preview, getWindow }) {
  const publicState = () => ({
    ...library.getState(),
    dataDirectory: library.directory,
  });

  const ok = (extra = {}) => ({ ...extra, state: publicState() });

  async function rememberFavicon(pageId, url, faviconUrls) {
    try {
      let candidates = Array.isArray(faviconUrls) ? faviconUrls.slice(0, 6) : [];
      if (!candidates.length) {
        const meta = await fetchPageMetadata(url);
        candidates = meta.faviconUrls || [];
      }
      const icon = await downloadFavicon(candidates);
      if (icon) library.setFavicon(pageId, icon);
    } catch {
      // A missing icon falls back to a letter on the tile.
    }
  }

  function closePreviewIfOrphaned() {
    const openId = preview.pageId;
    if (!openId) return;
    if (!library.getState().pages.some((page) => page.id === openId)) preview.close();
  }

  ipcMain.handle('library:get', () => publicState());

  ipcMain.handle('groups:create', (_event, payload) => {
    try {
      library.createGroup({ name: payload?.name, icon: payload?.icon });
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('groups:update', (_event, payload) => {
    try {
      library.updateGroup(payload.id, { name: payload.name, icon: payload.icon });
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('groups:delete', (_event, payload) => {
    try {
      library.deleteGroup(payload.id);
      closePreviewIfOrphaned();
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('groups:reorder', (_event, payload) => {
    try {
      library.reorderGroups(payload.ids);
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('groups:select', (_event, payload) => {
    try {
      library.selectGroup(payload.id);
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('pages:add', async (_event, payload) => {
    try {
      const page = library.addPage({
        groupId: payload.groupId,
        name: payload.name,
        url: payload.url,
      });
      await rememberFavicon(page.id, page.url, payload.faviconUrls);
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('pages:update', async (_event, payload) => {
    try {
      const before = library.requirePage(payload.id);
      const page = library.updatePage(payload.id, {
        name: payload.name,
        url: payload.url,
        groupId: payload.groupId,
      });
      if (page.url !== before.url) {
        library.clearFavicon(page.id);
        await rememberFavicon(page.id, page.url);
      }
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('pages:delete', (_event, payload) => {
    try {
      library.deletePage(payload.id);
      closePreviewIfOrphaned();
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('pages:move', (_event, payload) => {
    try {
      library.movePage(payload.id, payload.groupId);
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('pages:reorder', (_event, payload) => {
    try {
      library.reorderPages(payload.groupId, payload.ids);
      return ok();
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('meta:fetch', async (_event, payload) => {
    try {
      return await fetchPageMetadata(payload?.url);
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('preview:open', async (_event, payload) => {
    try {
      await preview.open({ pageId: payload.pageId, bounds: payload.bounds });
      return { ok: true };
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('preview:close', () => {
    preview.close();
    return { ok: true };
  });

  ipcMain.handle('preview:reload', () => {
    preview.reload();
    return { ok: true };
  });

  ipcMain.handle('preview:external', async () => {
    const url = normalizeHttpUrl(preview.currentURL());
    if (!url) return fail(new Error('This page is still loading.'));
    await shell.openExternal(url);
    return { ok: true };
  });

  ipcMain.on('preview:bounds', (_event, bounds) => {
    if (!bounds || typeof bounds !== 'object') return;
    preview.setBounds(bounds);
  });

  ipcMain.on('preview:visible', (_event, visible) => {
    preview.setVisible(visible !== false);
  });

  ipcMain.handle('preview:save', async (_event, payload) => {
    try {
      const url = normalizeHttpUrl(preview.currentURL());
      if (!url) return fail(new Error('This page is still loading.'));
      const group = library.requireGroup(payload.groupId);
      const existing = library.getState().pages.find((page) => page.groupId === group.id && page.url === url);
      if (existing) {
        return ok({ already: true, page: existing, groupName: group.name });
      }
      const page = library.addPage({
        groupId: group.id,
        name: siteLabel(url, preview.currentTitle()),
        url,
      });
      await rememberFavicon(page.id, url);
      return ok({ already: false, page, groupName: group.name });
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('preview:save-new', async () => {
    try {
      const url = normalizeHttpUrl(preview.currentURL());
      if (!url) return fail(new Error('This page is still loading.'));
      const name = siteLabel(url, preview.currentTitle());
      const group = library.createGroup({ name, icon: '🔖', select: false });
      const page = library.addPage({ groupId: group.id, name, url });
      await rememberFavicon(page.id, url);
      return ok({ already: false, page, group, groupName: group.name });
    } catch (error) {
      return fail(error);
    }
  });

  ipcMain.handle('backup:export', async () => {
    const win = getWindow();
    const result = await dialog.showSaveDialog(win, {
      title: 'Export library',
      defaultPath: 'groups-browser-backup.json',
      filters: [{ name: 'JSON', extensions: ['json'] }],
    });
    if (result.canceled || !result.filePath) return { canceled: true };
    fs.writeFileSync(result.filePath, `${JSON.stringify(library.exportSnapshot(), null, 2)}\n`);
    return { canceled: false, filePath: result.filePath };
  });

  ipcMain.handle('backup:import', async () => {
    const win = getWindow();
    const picked = await dialog.showOpenDialog(win, {
      title: 'Import library',
      filters: [{ name: 'JSON', extensions: ['json'] }],
      properties: ['openFile'],
    });
    if (picked.canceled || !picked.filePaths[0]) return { canceled: true };
    const confirm = await dialog.showMessageBox(win, {
      type: 'warning',
      buttons: ['Replace library', 'Cancel'],
      defaultId: 1,
      cancelId: 1,
      message: 'Replace all groups and pages?',
      detail: 'This backup will replace the library on this Mac. This cannot be undone.',
    });
    if (confirm.response !== 0) return { canceled: true };
    try {
      const raw = fs.readFileSync(picked.filePaths[0], 'utf8');
      library.importSnapshot(JSON.parse(raw));
      preview.close();
      return ok({ canceled: false });
    } catch (error) {
      const message = error instanceof SyntaxError
        ? 'That file isn’t a Groups Browser backup.'
        : error.message;
      return fail(new Error(message));
    }
  });
}

function fail(error) {
  return { error: error instanceof Error ? error.message : 'Something went wrong.' };
}

module.exports = { registerIpc };
