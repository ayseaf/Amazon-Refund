const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('groupsBrowser', {
  getState: () => ipcRenderer.invoke('library:get'),
  createGroup: (payload) => ipcRenderer.invoke('groups:create', payload),
  updateGroup: (payload) => ipcRenderer.invoke('groups:update', payload),
  deleteGroup: (id) => ipcRenderer.invoke('groups:delete', { id }),
  reorderGroups: (ids) => ipcRenderer.invoke('groups:reorder', { ids }),
  selectGroup: (id) => ipcRenderer.invoke('groups:select', { id }),
  addPage: (payload) => ipcRenderer.invoke('pages:add', payload),
  updatePage: (payload) => ipcRenderer.invoke('pages:update', payload),
  deletePage: (id) => ipcRenderer.invoke('pages:delete', { id }),
  movePage: (id, groupId) => ipcRenderer.invoke('pages:move', { id, groupId }),
  reorderPages: (groupId, ids) => ipcRenderer.invoke('pages:reorder', { groupId, ids }),
  fetchMetadata: (url) => ipcRenderer.invoke('meta:fetch', { url }),
  openPreview: (payload) => ipcRenderer.invoke('preview:open', payload),
  closePreview: () => ipcRenderer.invoke('preview:close'),
  reloadPreview: () => ipcRenderer.invoke('preview:reload'),
  openExternal: () => ipcRenderer.invoke('preview:external'),
  setPreviewBounds: (bounds) => ipcRenderer.send('preview:bounds', bounds),
  setPreviewVisible: (visible) => ipcRenderer.send('preview:visible', visible),
  saveToGroup: (groupId) => ipcRenderer.invoke('preview:save', { groupId }),
  saveToNewGroup: () => ipcRenderer.invoke('preview:save-new'),
  exportBackup: () => ipcRenderer.invoke('backup:export'),
  importBackup: () => ipcRenderer.invoke('backup:import'),
  onPreviewEvent: (callback) => {
    const listener = (_event, data) => callback(data);
    ipcRenderer.on('preview:event', listener);
  },
});
