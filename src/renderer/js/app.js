const api = window.groupsBrowser;
const ICONS = window.GB_ICONS;
const GROUP_ICONS = ['💬', '🌐', '🎬', '✨', '📣', '📚', '🧪', '🎨', '🎵', '📷', '📰', '💼', '🏠', '✈️', '🛒', '💡', '📝', '🔖', '🎯', '🌿', '🧠', '📈', '🛠️', '🎧', '📌', '🗂️', '⭐', '🔥'];
const ACCENTS = ['sienna', 'ochre', 'olive', 'pine', 'sea', 'ink', 'plum', 'clay'];

let state = null;
let preview = blankPreview();
let popover = null;
let menu = null;
let closeDialog = null;
let dragPayload = null;
let toastTimer = 0;

function blankPreview() {
  return { open: false, pageId: null, url: '', title: '', phase: 'closed', message: '' };
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of [].concat(children)) {
    if (child == null || child === false) continue;
    node.append(child);
  }
  return node;
}

function iconEl(name) {
  const span = document.createElement('span');
  span.className = 'icon';
  span.setAttribute('aria-hidden', 'true');
  span.innerHTML = ICONS[name];
  return span;
}

function toast(message) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.classList.add('is-shown');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove('is-shown'), 2600);
}

function deleteGroupDetail(name, pageCount) {
  const count = Number(pageCount) || 0;
  if (count === 0) return `Delete “${name}”? This group is empty. This cannot be undone.`;
  const pages = count === 1 ? '1 page' : `${count} pages`;
  return `Delete “${name}” and its ${pages}? This cannot be undone.`;
}

function filterPages(pages, query) {
  const q = String(query || '').trim().toLowerCase();
  if (!q) return pages.slice();
  return pages.filter((page) => page.name.toLowerCase().includes(q) || page.url.toLowerCase().includes(q));
}

function reorderIdList(ids, sourceId, targetId, position) {
  if (sourceId === targetId) return ids.slice();
  const without = ids.filter((id) => id !== sourceId);
  let index = without.indexOf(targetId);
  if (index < 0) return ids.slice();
  if (position === 'after') index += 1;
  without.splice(index, 0, sourceId);
  return without;
}

function accentFor(name) {
  let hash = 0;
  for (const char of name || '?') hash = (hash * 33 + char.codePointAt(0)) >>> 0;
  return ACCENTS[hash % ACCENTS.length];
}

function letterFor(page) {
  const source = page.name || page.url || '?';
  const first = [...source][0] || '?';
  return first.toUpperCase();
}

function groupById(id) {
  return state.groups.find((group) => group.id === id) || null;
}

function pagesIn(groupId) {
  return state.pages
    .filter((page) => page.groupId === groupId)
    .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
}

async function commit(resultPromise) {
  const result = await resultPromise;
  if (!result) return null;
  if (result.error) {
    toast(result.error);
    return null;
  }
  if (result.state) applyState(result.state);
  return result;
}

function applyState(next) {
  state = next;
  renderGroups();
  renderStage();
}

function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

function renderGroups() {
  const list = document.getElementById('group-list');
  const scroll = list.scrollTop;
  list.replaceChildren();
  for (const group of state.groups) {
    const count = group.pageCount ?? pagesIn(group.id).length;
    const hit = el('div', { class: 'group-hit' }, [
      el('span', { class: 'group-icon', text: group.icon, 'aria-hidden': 'true' }),
      el('span', { class: 'group-copy' }, [
        el('span', { class: 'group-name', text: group.name }),
        el('span', { class: 'group-count', text: count === 1 ? '1 page' : `${count} pages` }),
      ]),
    ]);
    const more = el('button', {
      class: 'group-more',
      type: 'button',
      'aria-label': `Actions for ${group.name}`,
    }, [iconEl('more')]);
    more.addEventListener('click', (event) => {
      event.stopPropagation();
      openGroupMenu(group, more);
    });
    const row = el('div', {
      class: 'group',
      role: 'listitem',
      tabindex: '0',
      draggable: 'true',
      'data-group-name': group.name,
      'aria-current': group.id === state.selectedGroupId ? 'true' : 'false',
    }, [hit, more]);
    const select = () => {
      if (group.id !== state.selectedGroupId) commit(api.selectGroup(group.id));
    };
    row.addEventListener('click', (event) => {
      if (event.target.closest('.group-more')) return;
      select();
    });
    row.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        select();
      }
    });
    row.addEventListener('dragstart', (event) => {
      if (event.target.closest('.group-more')) {
        event.preventDefault();
        return;
      }
      dragPayload = { kind: 'group', id: group.id };
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', `group:${group.id}`);
      row.classList.add('is-dragging');
    });
    row.addEventListener('dragend', () => {
      dragPayload = null;
      row.classList.remove('is-dragging');
      clearDropStyles();
    });
    row.addEventListener('dragover', (event) => {
      if (!dragPayload) return;
      event.preventDefault();
      row.classList.add('is-drop-target');
    });
    row.addEventListener('dragleave', () => row.classList.remove('is-drop-target'));
    row.addEventListener('drop', (event) => onGroupDrop(event, group, row));
    list.append(row);
  }
  list.scrollTop = scroll;
}

function renderStage() {
  const query = document.getElementById('search').value.trim();
  const selected = groupById(state.selectedGroupId);
  const title = document.getElementById('group-title');
  const count = document.getElementById('group-count');
  const glyph = document.getElementById('group-glyph');
  if (query) {
    glyph.hidden = true;
    title.textContent = 'Matching pages';
    const matches = filterPages(state.pages, query);
    count.textContent = matches.length === 1 ? '1 page' : `${matches.length} pages`;
    if (!matches.length) {
      renderMessage('No pages match', `Nothing in the library matches “${query}”.`);
    } else {
      renderTiles(matches, { showGroup: true, draggable: false });
    }
    return;
  }
  if (!selected) {
    glyph.hidden = true;
    title.textContent = 'Your library';
    count.textContent = '';
    renderMessage('Create a group', 'Groups hold the pages you want to come back to. Add one to start.', {
      label: 'New group',
      onClick: () => openGroupDialog(),
    });
    return;
  }
  glyph.hidden = false;
  glyph.textContent = selected.icon;
  title.textContent = selected.name;
  const pages = pagesIn(selected.id);
  count.textContent = pages.length === 1 ? '1 page' : `${pages.length} pages`;
  if (!pages.length) {
    renderMessage('No pages in this group', 'Add a page you want to come back to. It stays a tile until you open it.', {
      label: 'Add page',
      onClick: () => openAddDialog(),
      testid: 'empty-add',
    });
    return;
  }
  renderTiles(pages, { showGroup: false, draggable: true });
}

function renderMessage(heading, copy, action) {
  const grid = document.getElementById('grid');
  const mark = document.createElement('div');
  mark.className = 'empty-mark';
  mark.innerHTML = ICONS.pages;
  const children = [mark, el('h2', { text: heading }), el('p', { text: copy })];
  if (action) {
    children.push(el('button', {
      class: 'primary',
      type: 'button',
      text: action.label,
      'data-testid': action.testid || 'empty-action',
      onclick: action.onClick,
    }));
  }
  grid.replaceChildren(el('div', { class: 'empty' }, children));
}

function renderTiles(pages, { showGroup, draggable }) {
  const grid = document.getElementById('grid');
  const wrap = el('div', { class: 'tiles' });
  for (const page of pages) {
    wrap.append(renderTile(page, { showGroup, draggable }));
  }
  grid.replaceChildren(wrap);
}

function renderTile(page, { showGroup, draggable }) {
  const thumbChildren = [];
  if (page.hasThumbnail) {
    const img = el('img', {
      class: 'shot',
      alt: '',
      src: `gbthumb://asset/thumb/${page.id}?v=${encodeURIComponent(page.thumbnailCapturedAt || '')}`,
    });
    img.addEventListener('error', () => img.remove());
    thumbChildren.push(img);
  } else if (page.hasFavicon) {
    const img = el('img', { class: 'mark', alt: '', src: `gbthumb://asset/favicon/${page.id}` });
    img.addEventListener('error', () => {
      img.replaceWith(el('span', { class: 'letter', text: letterFor(page) }));
    });
    thumbChildren.push(img);
  } else {
    thumbChildren.push(el('span', { class: 'letter', text: letterFor(page) }));
  }
  const thumb = el('span', { class: `thumb accent-${accentFor(page.name)}` }, thumbChildren);
  const open = el('button', {
    class: 'tile-open',
    type: 'button',
    draggable: draggable ? 'true' : 'false',
    'data-page-name': page.name,
    'data-page-id': page.id,
  }, [
    thumb,
    el('span', { class: 'tile-name', text: page.name }),
    showGroup ? el('span', { class: 'tile-group', text: groupById(page.groupId)?.name || '' }) : null,
  ]);
  open.addEventListener('click', () => openPreview(page.id));
  const more = el('button', {
    class: 'tile-more',
    type: 'button',
    'aria-label': `Actions for ${page.name}`,
  }, [iconEl('more')]);
  more.addEventListener('click', (event) => {
    event.stopPropagation();
    openPageMenu(page, more);
  });
  const tile = el('div', { class: 'tile' }, [open, more]);
  if (draggable) {
    open.addEventListener('dragstart', (event) => {
      dragPayload = { kind: 'page', id: page.id };
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', `page:${page.id}`);
      tile.classList.add('is-dragging');
    });
    open.addEventListener('dragend', () => {
      dragPayload = null;
      tile.classList.remove('is-dragging');
      clearDropStyles();
    });
    open.addEventListener('dragover', (event) => {
      if (!dragPayload || dragPayload.kind !== 'page') return;
      event.preventDefault();
      const before = event.offsetX <= open.clientWidth / 2;
      tile.classList.toggle('drop-before', before);
      tile.classList.toggle('drop-after', !before);
    });
    open.addEventListener('dragleave', () => {
      tile.classList.remove('drop-before', 'drop-after');
    });
    open.addEventListener('drop', (event) => onTileDrop(event, page, open));
  }
  return tile;
}

function clearDropStyles() {
  for (const node of document.querySelectorAll('.is-drop-target, .drop-before, .drop-after')) {
    node.classList.remove('is-drop-target', 'drop-before', 'drop-after');
  }
}

async function onGroupDrop(event, group, row) {
  event.preventDefault();
  row.classList.remove('is-drop-target');
  const payload = dragPayload;
  dragPayload = null;
  if (!payload) return;
  if (payload.kind === 'page') {
    await commit(api.movePage(payload.id, group.id));
    return;
  }
  if (payload.kind === 'group' && payload.id !== group.id) {
    const ids = state.groups.map((item) => item.id);
    const position = event.offsetY <= row.clientHeight / 2 ? 'before' : 'after';
    await commit(api.reorderGroups(reorderIdList(ids, payload.id, group.id, position)));
  }
}

async function onTileDrop(event, page, tile) {
  event.preventDefault();
  event.stopPropagation();
  const payload = dragPayload;
  dragPayload = null;
  tile.closest('.tile')?.classList.remove('drop-before', 'drop-after');
  if (!payload || payload.kind !== 'page' || payload.id === page.id) return;
  const source = state.pages.find((item) => item.id === payload.id);
  if (!source) return;
  if (source.groupId !== page.groupId) {
    await commit(api.movePage(source.id, page.groupId));
    return;
  }
  const ids = pagesIn(page.groupId).map((item) => item.id);
  const position = event.offsetX <= tile.clientWidth / 2 ? 'before' : 'after';
  await commit(api.reorderPages(page.groupId, reorderIdList(ids, source.id, page.id, position)));
}

function coverPreview(covered) {
  if (document.getElementById('preview').hidden) return;
  api.setPreviewVisible(!covered);
}

function openMenu(anchor, children, testid) {
  closeMenu();
  const node = el('div', { class: 'menu', role: 'menu', 'data-testid': testid || 'menu' }, children);
  document.body.append(node);
  placeNear(node, anchor, 'end');
  menu = node;
}

function closeMenu() {
  menu?.remove();
  menu = null;
}

function openGroupMenu(group, anchor) {
  openMenu(anchor, [
    el('button', { class: 'menu-item', type: 'button', role: 'menuitem', text: 'Edit group', onclick: () => { closeMenu(); openGroupDialog(group); } }),
    el('button', { class: 'menu-item danger', type: 'button', role: 'menuitem', text: 'Delete group', onclick: () => { closeMenu(); confirmDeleteGroup(group); } }),
  ]);
}

function openPageMenu(page, anchor) {
  const items = [
    el('button', { class: 'menu-item', type: 'button', role: 'menuitem', text: 'Edit page', onclick: () => { closeMenu(); openPageDialog(page); } }),
  ];
  const others = state.groups.filter((group) => group.id !== page.groupId);
  if (others.length) {
    items.push(el('div', { class: 'menu-label', text: 'Move to' }));
    for (const group of others) {
      items.push(el('button', {
        class: 'menu-item',
        type: 'button',
        role: 'menuitem',
        text: `${group.icon}  ${group.name}`,
        onclick: async () => {
          closeMenu();
          const result = await commit(api.movePage(page.id, group.id));
          if (result) toast(`Moved to ${group.name}.`);
        },
      }));
    }
  }
  items.push(el('button', {
    class: 'menu-item danger',
    type: 'button',
    role: 'menuitem',
    text: 'Remove page',
    onclick: () => { closeMenu(); confirmDeletePage(page); },
  }));
  openMenu(anchor, items);
}

function confirmDeleteGroup(group) {
  openConfirm({
    title: 'Delete this group',
    detail: deleteGroupDetail(group.name, group.pageCount ?? pagesIn(group.id).length),
    confirmLabel: 'Delete group',
    onConfirm: () => commit(api.deleteGroup(group.id)),
  });
}

function confirmDeletePage(page) {
  openConfirm({
    title: 'Remove this page',
    detail: `Remove “${page.name}” from ${groupById(page.groupId)?.name || 'this group'}?`,
    confirmLabel: 'Remove page',
    onConfirm: () => commit(api.deletePage(page.id)),
  });
}

function openConfirm({ title, detail, confirmLabel, onConfirm }) {
  openDialog(() => {
    const form = el('form', { class: 'dialog', role: 'alertdialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title' });
    form.append(
      el('h3', { id: 'dialog-title', text: title }),
      el('p', { class: 'dialog-copy', text: detail }),
      el('div', { class: 'dialog-actions' }, [
        el('button', { class: 'ghost', type: 'button', text: 'Cancel', onclick: () => dismissDialog() }),
        el('button', {
          class: 'danger',
          type: 'button',
          text: confirmLabel,
          'data-testid': 'confirm-delete',
          onclick: async () => {
            dismissDialog();
            await onConfirm();
          },
        }),
      ]),
    );
    form.addEventListener('submit', (event) => event.preventDefault());
    return form;
  });
}

function openGroupDialog(existing) {
  openDialog(() => {
    let icon = existing?.icon || '💬';
    const choices = GROUP_ICONS.includes(icon) ? GROUP_ICONS : [icon, ...GROUP_ICONS];
    const name = el('input', {
      type: 'text',
      required: 'true',
      maxlength: '80',
      value: existing?.name || '',
      'data-testid': 'group-name',
      autocomplete: 'off',
      spellcheck: 'false',
    });
    const grid = el('div', { class: 'icon-grid', 'data-testid': 'icon-grid' });
    for (const choice of choices) {
      const button = el('button', {
        class: 'icon-choice',
        type: 'button',
        text: choice,
        'data-icon': choice,
        'aria-label': `Icon ${choice}`,
        'aria-pressed': choice === icon ? 'true' : 'false',
      });
      button.addEventListener('click', () => {
        icon = choice;
        for (const item of grid.querySelectorAll('button')) {
          item.setAttribute('aria-pressed', item.getAttribute('data-icon') === icon ? 'true' : 'false');
        }
      });
      grid.append(button);
    }
    const form = el('form', { class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title' }, [
      el('h3', { id: 'dialog-title', text: existing ? 'Edit group' : 'New group' }),
      el('p', { class: 'dialog-copy', text: existing ? 'Change the name or the icon.' : 'Name the group and pick an icon.' }),
      el('label', { class: 'field' }, [el('span', { text: 'Name' }), name]),
      el('div', { class: 'field' }, [el('span', { text: 'Icon' }), grid]),
      el('div', { class: 'dialog-actions' }, [
        el('button', { class: 'ghost', type: 'button', text: 'Cancel', onclick: () => dismissDialog() }),
        el('button', { class: 'primary', type: 'submit', text: existing ? 'Save' : 'Create group', 'data-testid': 'group-create' }),
      ]),
    ]);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const result = existing
        ? await commit(api.updateGroup({ id: existing.id, name: name.value, icon }))
        : await commit(api.createGroup({ name: name.value, icon }));
      if (result) dismissDialog();
    });
    return form;
  });
}

function openAddDialog() {
  const group = groupById(state.selectedGroupId);
  if (!group) {
    openGroupDialog();
    return;
  }
  openDialog(() => {
    let pendingUrl = '';
    let pendingFavicons = [];
    let nameDirty = false;
    let timer = 0;
    const url = el('input', {
      type: 'text',
      required: 'true',
      placeholder: 'https://youtube.com',
      inputmode: 'url',
      'data-testid': 'page-url',
      autocomplete: 'off',
      spellcheck: 'false',
    });
    const name = el('input', {
      type: 'text',
      maxlength: '80',
      placeholder: 'Site name',
      'data-testid': 'page-name',
      autocomplete: 'off',
      spellcheck: 'false',
    });
    const status = el('p', { class: 'field-status', 'data-testid': 'page-status' });
    const submit = el('button', { class: 'primary', type: 'submit', text: 'Add page', 'data-testid': 'page-add' });
    name.addEventListener('input', () => { nameDirty = true; });
    url.addEventListener('input', () => {
      pendingUrl = '';
      pendingFavicons = [];
      clearTimeout(timer);
      const typed = url.value.trim();
      if (typed.length < 3) {
        status.textContent = '';
        return;
      }
      status.textContent = 'Looking up the title…';
      status.classList.remove('is-error');
      timer = setTimeout(async () => {
        const meta = await api.fetchMetadata(typed);
        if (url.value.trim() !== typed) return;
        if (meta?.error && !meta.title) {
          status.textContent = meta.error;
          status.classList.add('is-error');
          return;
        }
        if (!nameDirty && meta.title) name.value = meta.title;
        pendingUrl = meta.url || '';
        pendingFavicons = meta.faviconUrls || [];
        status.classList.toggle('is-error', meta.ok === false);
        status.textContent = meta.ok
          ? 'Title and icon found. Edit the name if you want.'
          : meta.error;
      }, 280);
    });
    const form = el('form', { class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title' }, [
      el('h3', { id: 'dialog-title', text: 'Add page' }),
      el('p', { class: 'dialog-copy', text: `Paste an address. It will be saved in ${group.name}.` }),
      el('label', { class: 'field' }, [el('span', { text: 'Address' }), url]),
      status,
      el('label', { class: 'field' }, [el('span', { text: 'Display name' }), name]),
      el('div', { class: 'dialog-actions' }, [
        el('button', { class: 'ghost', type: 'button', text: 'Cancel', onclick: () => dismissDialog() }),
        submit,
      ]),
    ]);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      submit.disabled = true;
      const typed = url.value.trim();
      const address = pendingUrl || typed;
      let label = name.value.trim();
      if (!label) {
        try {
          const parsed = new URL(/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(address) ? address : `https://${address}`);
          label = parsed.hostname.replace(/^www\./, '');
        } catch {
          label = address;
        }
      }
      const result = await commit(api.addPage({
        groupId: group.id,
        name: label,
        url: address,
        faviconUrls: pendingFavicons,
      }));
      submit.disabled = false;
      if (result) dismissDialog();
    });
    return form;
  });
}

function openPageDialog(page) {
  openDialog(() => {
    const name = el('input', { type: 'text', required: 'true', maxlength: '80', value: page.name, 'data-testid': 'edit-name' });
    const url = el('input', { type: 'url', required: 'true', value: page.url, 'data-testid': 'edit-url' });
    const select = el('select', { 'data-testid': 'edit-group' });
    for (const group of state.groups) {
      const option = el('option', { value: group.id, text: `${group.icon}  ${group.name}` });
      if (group.id === page.groupId) option.selected = true;
      select.append(option);
    }
    const form = el('form', { class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title' }, [
      el('h3', { id: 'dialog-title', text: 'Edit page' }),
      el('label', { class: 'field' }, [el('span', { text: 'Display name' }), name]),
      el('label', { class: 'field' }, [el('span', { text: 'Address' }), url]),
      el('label', { class: 'field' }, [el('span', { text: 'Group' }), select]),
      el('div', { class: 'dialog-actions' }, [
        el('button', {
          class: 'danger',
          type: 'button',
          text: 'Remove',
          onclick: () => {
            dismissDialog();
            confirmDeletePage(page);
          },
        }),
        el('button', { class: 'ghost', type: 'button', text: 'Cancel', onclick: () => dismissDialog() }),
        el('button', { class: 'primary', type: 'submit', text: 'Save' }),
      ]),
    ]);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const result = await commit(api.updatePage({
        id: page.id,
        name: name.value,
        url: url.value,
        groupId: select.value,
      }));
      if (result) dismissDialog();
    });
    return form;
  });
}

function openSettings() {
  openDialog(() => {
    const form = el('div', { class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dialog-title' }, [
      el('h3', { id: 'dialog-title', text: 'Settings' }),
      el('p', { class: 'dialog-copy', text: 'Groups, pages, and sign-in cookies stay on this Mac. Nothing is uploaded.' }),
      el('p', { class: 'dialog-copy', text: state.dataDirectory || '' }),
      el('div', { class: 'dialog-actions' }, [
        el('button', { class: 'ghost', type: 'button', text: 'Close', onclick: () => dismissDialog() }),
        el('button', {
          class: 'ghost',
          type: 'button',
          text: 'Import backup',
          'data-testid': 'import-backup',
          onclick: async () => {
            const result = await api.importBackup();
            if (result?.error) toast(result.error);
            else if (result?.state) {
              applyState(result.state);
              dismissDialog();
              hidePreviewShell();
              toast('Library replaced from the backup.');
            }
          },
        }),
        el('button', {
          class: 'primary',
          type: 'button',
          text: 'Export backup',
          'data-testid': 'export-backup',
          onclick: async () => {
            const result = await api.exportBackup();
            if (result?.error) toast(result.error);
            else if (result && !result.canceled) toast('Backup saved.');
          },
        }),
      ]),
    ]);
    return form;
  });
}

function openDialog(build) {
  dismissDialog();
  closeMenu();
  closePopover();
  const backdrop = el('div', { class: 'backdrop', 'data-testid': 'dialog' });
  const node = build();
  backdrop.append(node);
  backdrop.addEventListener('mousedown', (event) => {
    if (event.target === backdrop) dismissDialog();
  });
  node.addEventListener('keydown', (event) => trapTab(event, node));
  document.getElementById('dialog-root').append(backdrop);
  closeDialog = () => {
    backdrop.remove();
    coverPreview(false);
  };
  coverPreview(true);
  const field = node.querySelector('input, button, select');
  field?.focus();
  if (field && field.select && field.value) field.select();
}

function dismissDialog() {
  closeDialog?.();
  closeDialog = null;
}

function trapTab(event, node) {
  if (event.key !== 'Tab') return;
  const focusable = [...node.querySelectorAll('button, input, select, textarea')].filter((item) => !item.disabled);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function placeNear(node, anchor, align) {
  const rect = anchor.getBoundingClientRect();
  const width = node.offsetWidth;
  const height = node.offsetHeight;
  let left = align === 'end' ? rect.right - width : rect.left;
  let top = rect.bottom + 6;
  left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
  if (top + height > window.innerHeight - 8) top = Math.max(8, rect.top - height - 6);
  node.style.left = `${Math.round(left)}px`;
  node.style.top = `${Math.round(top)}px`;
}

function closePopover() {
  const hadPopover = Boolean(popover);
  popover?.remove();
  popover = null;
  if (hadPopover) coverPreview(false);
}

function openSavePopover(anchor) {
  closePopover();
  const items = [el('p', { class: 'popover-label', text: 'Save this page' })];
  for (const group of state.groups) {
    items.push(el('button', {
      class: 'popover-item',
      type: 'button',
      text: `${group.icon}  ${group.name}`,
      'data-testid': 'save-group',
      'data-group-name': group.name,
      onclick: () => saveTo(group.id, group.name),
    }));
  }
  items.push(el('button', {
    class: 'popover-item popover-new',
    type: 'button',
    text: 'New group',
    'data-testid': 'save-new-group',
    onclick: () => saveToNew(),
  }));
  const node = el('div', { class: 'popover', id: 'save-popover', role: 'menu' }, items);
  document.body.append(node);
  placeNear(node, anchor, 'end');
  popover = node;
  coverPreview(true);
}

async function saveTo(groupId, groupName) {
  closePopover();
  const result = await commit(api.saveToGroup(groupId));
  if (!result) return;
  toast(result.already ? `${result.page.name} is already in ${groupName}.` : `Saved to ${groupName}.`);
}

async function saveToNew() {
  closePopover();
  const result = await commit(api.saveToNewGroup());
  if (!result) return;
  toast(`Saved to new group “${result.groupName}”.`);
}

function renderPreview() {
  document.getElementById('preview-title').textContent = preview.title || 'Preview';
  document.getElementById('preview-url').textContent = preview.url || '';
  const shell = document.getElementById('preview');
  shell.dataset.previewState = preview.phase;
  document.getElementById('preview-progress').classList.toggle('is-loading', preview.phase === 'loading');
  const failed = document.getElementById('preview-failed');
  failed.hidden = preview.phase !== 'failed';
  failed.textContent = preview.phase === 'failed' ? (preview.message || 'This page didn’t load. Try Reload.') : '';
}

function hidePreviewShell() {
  preview = blankPreview();
  const shell = document.getElementById('preview');
  shell.hidden = true;
  shell.dataset.previewState = 'closed';
  document.getElementById('app').classList.remove('is-previewing');
  closePopover();
}

async function requestClosePreview() {
  if (!preview.open && document.getElementById('preview').hidden) return;
  hidePreviewShell();
  await api.closePreview();
}

async function openPreview(pageId) {
  const page = state.pages.find((item) => item.id === pageId);
  if (!page) return;
  preview = { open: true, pageId, url: page.url, title: page.name, phase: 'loading', message: '' };
  const shell = document.getElementById('preview');
  shell.hidden = false;
  document.getElementById('app').classList.add('is-previewing');
  renderPreview();
  await nextFrame();
  await nextFrame();
  reportBounds();
  const rect = document.getElementById('preview-surface').getBoundingClientRect();
  const result = await api.openPreview({
    pageId,
    bounds: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
  });
  if (result?.error) {
    hidePreviewShell();
    toast(result.error);
  }
}

function reportBounds() {
  if (document.getElementById('preview').hidden) return;
  const rect = document.getElementById('preview-surface').getBoundingClientRect();
  if (rect.width < 20 || rect.height < 20) return;
  api.setPreviewBounds({ x: rect.x, y: rect.y, width: rect.width, height: rect.height });
}

function onPreviewEvent(event) {
  if (event.type === 'closed') {
    hidePreviewShell();
    return;
  }
  if (event.type === 'crashed') {
    hidePreviewShell();
    toast('The page closed unexpectedly.');
    return;
  }
  if (event.type === 'thumbnail') {
    api.getState().then((next) => {
      if (next && !next.error && next.groups) applyState(next);
    });
    return;
  }
  if (!preview.open) return;
  preview.phase = event.type === 'failed' ? 'failed' : event.type === 'ready' ? 'ready' : event.type;
  if (event.url) preview.url = event.url;
  if (event.title) preview.title = event.title;
  if (event.message) preview.message = event.message;
  renderPreview();
}

function paintChrome() {
  document.getElementById('new-group').replaceChildren(iconEl('plus'), 'New group');
  document.getElementById('settings').replaceChildren(iconEl('settings'), 'Settings');
  document.querySelector('.search-icon').replaceChildren(iconEl('search'));
  document.getElementById('preview-reload').replaceChildren(iconEl('reload'));
  document.getElementById('preview-external').replaceChildren(iconEl('external'));
  document.getElementById('preview-close').replaceChildren(iconEl('close'));
  for (const button of [document.getElementById('preview-reload'), document.getElementById('preview-external'), document.getElementById('preview-close')]) {
    button.classList.add('icon-button');
  }
}

function bind() {
  document.getElementById('new-group').addEventListener('click', () => openGroupDialog());
  document.getElementById('settings').addEventListener('click', () => openSettings());
  document.getElementById('add-page').addEventListener('click', () => openAddDialog());
  document.getElementById('search').addEventListener('input', () => renderStage());
  document.getElementById('preview-close').addEventListener('click', () => requestClosePreview());
  document.getElementById('preview-reload').addEventListener('click', () => api.reloadPreview());
  document.getElementById('preview-external').addEventListener('click', async () => {
    const result = await api.openExternal();
    if (result?.error) toast(result.error);
  });
  document.getElementById('save-to-group').addEventListener('click', (event) => {
    event.stopPropagation();
    if (popover) closePopover();
    else openSavePopover(event.currentTarget);
  });
  document.addEventListener('mousedown', (event) => {
    if (popover && !popover.contains(event.target) && event.target.closest('#save-to-group') == null) closePopover();
    if (menu && !menu.contains(event.target) && event.target.closest('.tile-more, .group-more') == null) closeMenu();
  });
  window.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'f') {
      event.preventDefault();
      document.getElementById('search').focus();
      return;
    }
    if (event.key !== 'Escape') return;
    if (closeDialog) {
      dismissDialog();
      event.preventDefault();
      return;
    }
    if (popover) {
      closePopover();
      event.preventDefault();
      return;
    }
    if (menu) {
      closeMenu();
      event.preventDefault();
      return;
    }
    const search = document.getElementById('search');
    if (document.activeElement === search && search.value) {
      search.value = '';
      renderStage();
      return;
    }
    if (preview.open) {
      event.preventDefault();
      requestClosePreview();
    }
  });
  const observer = new ResizeObserver(() => reportBounds());
  observer.observe(document.getElementById('preview-surface'));
  window.addEventListener('resize', () => reportBounds());
  api.onPreviewEvent(onPreviewEvent);
}

async function boot() {
  if (!api) throw new Error('The app bridge is missing.');
  paintChrome();
  bind();
  const initial = await api.getState();
  if (!initial || initial.error || !initial.groups) {
    throw new Error(initial?.error || 'The library could not be read.');
  }
  applyState(initial);
}

boot().catch((error) => {
  console.error(error);
  toast(error.message || 'Groups Browser could not start.');
});
