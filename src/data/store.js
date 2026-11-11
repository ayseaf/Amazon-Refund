const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { normalizeHttpUrl } = require('../shared/url');
const { createSeed } = require('./seed');

const ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;
const FORMAT = 'groups-browser';
const VERSION = 1;

function nowIso() {
  return new Date().toISOString();
}

function cleanName(name) {
  const value = String(name ?? '').replace(/\s+/g, ' ').trim();
  if (!value) throw new Error('Give it a name.');
  if ([...value].length > 80) throw new Error('Use a name of 80 characters or fewer.');
  return value;
}

function cleanIcon(icon) {
  const value = String(icon ?? '').trim();
  if (!value) throw new Error('Choose an icon.');
  if ([...value].length > 8) throw new Error('Choose a shorter icon.');
  return value;
}

function assertId(id) {
  if (typeof id !== 'string' || !ID_PATTERN.test(id)) {
    throw new Error('Invalid id');
  }
  return id;
}

function emptyState() {
  return { version: VERSION, selectedGroupId: null, groups: [], pages: [] };
}

function pageFile(dir, folder, id, suffix) {
  assertId(id);
  const root = path.resolve(dir, folder);
  const file = path.resolve(root, `${id}${suffix}`);
  if (file !== root && !file.startsWith(`${root}${path.sep}`)) {
    throw new Error('Invalid id');
  }
  return file;
}

class Library {
  constructor(directory, state) {
    this.directory = directory;
    this.version = VERSION;
    this.selectedGroupId = state.selectedGroupId ?? null;
    this.groups = state.groups.map((group) => ({ ...group }));
    this.pages = state.pages.map((page) => ({ ...page }));
  }

  static open(directory, { seed = true } = {}) {
    fs.mkdirSync(directory, { recursive: true });
    fs.mkdirSync(path.join(directory, 'favicons'), { recursive: true });
    fs.mkdirSync(path.join(directory, 'thumbs'), { recursive: true });
    const file = path.join(directory, 'library.json');
    if (!fs.existsSync(file)) {
      const lib = new Library(directory, seed ? createSeed() : emptyState());
      lib.save();
      return lib;
    }
    return Library.load(directory);
  }

  static load(directory) {
    const raw = fs.readFileSync(path.join(directory, 'library.json'), 'utf8');
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new Error('The library file on this Mac could not be read.');
    }
    return new Library(directory, {
      version: VERSION,
      selectedGroupId: parsed.selectedGroupId ?? null,
      groups: Array.isArray(parsed.groups) ? parsed.groups : [],
      pages: Array.isArray(parsed.pages) ? parsed.pages : [],
    });
  }

  filePath() {
    return path.join(this.directory, 'library.json');
  }

  save() {
    const payload = {
      version: VERSION,
      selectedGroupId: this.selectedGroupId,
      groups: this.groups.map(serializeGroup),
      pages: this.pages.map(serializePage),
    };
    const file = this.filePath();
    const temp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(temp, `${JSON.stringify(payload, null, 2)}\n`);
    fs.renameSync(temp, file);
  }

  getState() {
    const groups = [...this.groups].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
    const pages = [...this.pages].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
    return {
      selectedGroupId: this.selectedGroupId,
      groups: groups.map((group) => ({
        ...serializeGroup(group),
        pageCount: this.pageCount(group.id),
      })),
      pages: pages.map((page) => ({
        ...serializePage(page),
        hasFavicon: fs.existsSync(this.faviconPath(page.id)),
        hasThumbnail: fs.existsSync(this.thumbPath(page.id)),
      })),
    };
  }

  pageCount(groupId) {
    return this.pages.filter((page) => page.groupId === groupId).length;
  }

  createGroup({ name, icon, select = true }) {
    const stamp = nowIso();
    const group = {
      id: randomUUID(),
      name: cleanName(name),
      icon: cleanIcon(icon),
      order: this.groups.length,
      createdAt: stamp,
      updatedAt: stamp,
    };
    this.groups.push(group);
    if (select || this.selectedGroupId == null) this.selectedGroupId = group.id;
    this.save();
    return { ...group };
  }

  updateGroup(id, patch) {
    const group = this.requireGroup(id);
    if (patch.name != null) group.name = cleanName(patch.name);
    if (patch.icon != null) group.icon = cleanIcon(patch.icon);
    group.updatedAt = nowIso();
    this.save();
    return { ...group };
  }

  deleteGroup(id) {
    const index = this.groups.findIndex((group) => group.id === id);
    if (index < 0) throw new Error('Unknown group');
    const removedPages = this.pages.filter((page) => page.groupId === id);
    for (const page of removedPages) this.removePageFiles(page.id);
    this.pages = this.pages.filter((page) => page.groupId !== id);
    this.groups.splice(index, 1);
    reindex(this.groups);
    if (this.selectedGroupId === id) {
      const next = this.groups[index] || this.groups[index - 1] || null;
      this.selectedGroupId = next ? next.id : null;
    }
    this.save();
    return { pageCount: removedPages.length };
  }

  reorderGroups(orderedIds) {
    assertPermutation(this.groups.map((group) => group.id), orderedIds, 'group');
    const byId = new Map(this.groups.map((group) => [group.id, group]));
    this.groups = orderedIds.map((id, order) => {
      const group = byId.get(id);
      group.order = order;
      return group;
    });
    this.save();
  }

  selectGroup(id) {
    this.requireGroup(id);
    this.selectedGroupId = id;
    this.save();
  }

  addPage({ groupId, name, url }) {
    this.requireGroup(groupId);
    const normalized = normalizeHttpUrl(url);
    if (!normalized) throw new Error('Enter a full http or https address.');
    const siblings = this.pages.filter((page) => page.groupId === groupId);
    const stamp = nowIso();
    const page = {
      id: randomUUID(),
      groupId,
      name: cleanName(name),
      url: normalized,
      order: siblings.length ? Math.max(...siblings.map((item) => item.order)) + 1 : 0,
      createdAt: stamp,
      updatedAt: stamp,
      thumbnailCapturedAt: null,
      faviconMime: null,
    };
    this.pages.push(page);
    this.save();
    return { ...page };
  }

  updatePage(id, patch) {
    const page = this.requirePage(id);
    if (patch.name != null) page.name = cleanName(patch.name);
    if (patch.url != null) {
      const normalized = normalizeHttpUrl(patch.url);
      if (!normalized) throw new Error('Enter a full http or https address.');
      if (normalized !== page.url) {
        page.url = normalized;
        this.clearThumbnail(id, { save: false });
      }
    }
    if (patch.groupId != null) {
      this.requireGroup(patch.groupId);
      page.groupId = patch.groupId;
    }
    page.updatedAt = nowIso();
    this.save();
    return { ...page };
  }

  deletePage(id) {
    this.requirePage(id);
    this.pages = this.pages.filter((page) => page.id !== id);
    this.removePageFiles(id);
    this.save();
  }

  movePage(id, groupId) {
    const page = this.requirePage(id);
    this.requireGroup(groupId);
    if (page.groupId === groupId) return { ...page };
    const siblings = this.pages.filter((item) => item.groupId === groupId);
    page.groupId = groupId;
    page.order = siblings.length ? Math.max(...siblings.map((item) => item.order)) + 1 : 0;
    page.updatedAt = nowIso();
    this.save();
    return { ...page };
  }

  reorderPages(groupId, orderedIds) {
    this.requireGroup(groupId);
    const current = this.pages.filter((page) => page.groupId === groupId).map((page) => page.id);
    assertPermutation(current, orderedIds, 'page');
    const byId = new Map(this.pages.map((page) => [page.id, page]));
    orderedIds.forEach((id, order) => {
      byId.get(id).order = order;
    });
    this.save();
  }

  setFavicon(id, { bytes, mime }) {
    this.requirePage(id);
    const page = this.requirePage(id);
    fs.writeFileSync(this.faviconPath(id), Buffer.from(bytes));
    page.faviconMime = mime || 'application/octet-stream';
    page.updatedAt = nowIso();
    this.save();
  }

  setThumbnail(id, { bytes, capturedAt }) {
    const page = this.requirePage(id);
    fs.writeFileSync(this.thumbPath(id), Buffer.from(bytes));
    page.thumbnailCapturedAt = capturedAt || nowIso();
    page.updatedAt = nowIso();
    this.save();
  }

  clearThumbnail(id, { save = true } = {}) {
    const page = this.requirePage(id);
    page.thumbnailCapturedAt = null;
    removeIfExists(this.thumbPath(id));
    if (save) this.save();
  }

  clearFavicon(id) {
    const page = this.requirePage(id);
    page.faviconMime = null;
    page.updatedAt = nowIso();
    removeIfExists(this.faviconPath(id));
    this.save();
  }

  faviconPath(id) {
    return pageFile(this.directory, 'favicons', id, '');
  }

  thumbPath(id) {
    return pageFile(this.directory, 'thumbs', id, '.jpg');
  }

  removePageFiles(id) {
    if (!ID_PATTERN.test(id)) return;
    removeIfExists(this.faviconPath(id));
    removeIfExists(this.thumbPath(id));
  }

  exportSnapshot() {
    const state = this.getState();
    return {
      format: FORMAT,
      version: VERSION,
      selectedGroupId: this.selectedGroupId,
      groups: state.groups.map(({ pageCount, ...group }) => group),
      pages: state.pages.map((page) => ({
        id: page.id,
        groupId: page.groupId,
        name: page.name,
        url: page.url,
        order: page.order,
        createdAt: page.createdAt,
        updatedAt: page.updatedAt,
        thumbnailCapturedAt: page.thumbnailCapturedAt,
        faviconMime: page.faviconMime,
        faviconBase64: readBase64(this.faviconPath(page.id)),
        thumbnailBase64: readBase64(this.thumbPath(page.id)),
      })),
    };
  }

  importSnapshot(snapshot) {
    const next = validateSnapshot(snapshot);
    replaceTree(path.join(this.directory, 'favicons'));
    replaceTree(path.join(this.directory, 'thumbs'));
    for (const page of next.pages) {
      if (page.faviconBytes) fs.writeFileSync(this.faviconPath(page.id), page.faviconBytes);
      if (page.thumbnailBytes) fs.writeFileSync(this.thumbPath(page.id), page.thumbnailBytes);
    }
    this.selectedGroupId = next.selectedGroupId;
    this.groups = next.groups;
    this.pages = next.pages.map(({ faviconBytes, thumbnailBytes, ...page }) => page);
    this.save();
  }

  requireGroup(id) {
    const group = this.groups.find((item) => item.id === id);
    if (!group) throw new Error('Unknown group');
    return group;
  }

  requirePage(id) {
    const page = this.pages.find((item) => item.id === id);
    if (!page) throw new Error('Unknown page');
    return page;
  }
}

function serializeGroup(group) {
  return {
    id: group.id,
    name: group.name,
    icon: group.icon,
    order: group.order,
    createdAt: group.createdAt,
    updatedAt: group.updatedAt,
  };
}

function serializePage(page) {
  return {
    id: page.id,
    groupId: page.groupId,
    name: page.name,
    url: page.url,
    order: page.order,
    createdAt: page.createdAt,
    updatedAt: page.updatedAt,
    thumbnailCapturedAt: page.thumbnailCapturedAt ?? null,
    faviconMime: page.faviconMime ?? null,
  };
}

function reindex(groups) {
  groups.forEach((group, order) => {
    group.order = order;
  });
}

function assertPermutation(current, orderedIds, noun) {
  if (!Array.isArray(orderedIds) || orderedIds.length !== current.length) {
    throw new Error(`Reorder must include every ${noun}`);
  }
  const seen = new Set(orderedIds);
  if (seen.size !== current.length || current.some((id) => !seen.has(id))) {
    throw new Error(`Reorder must include every ${noun}`);
  }
}

function removeIfExists(file) {
  if (fs.existsSync(file)) fs.unlinkSync(file);
}

function readBase64(file) {
  if (!fs.existsSync(file)) return null;
  return fs.readFileSync(file).toString('base64');
}

function replaceTree(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
}

function validateSnapshot(snapshot) {
  if (!snapshot || snapshot.format !== FORMAT || snapshot.version !== VERSION) {
    throw new Error('This file is not a Groups Browser backup.');
  }
  if (!Array.isArray(snapshot.groups) || !Array.isArray(snapshot.pages)) {
    throw new Error('This file is not a Groups Browser backup.');
  }

  const groups = snapshot.groups.map((group) => {
    assertId(group.id);
    return {
      id: group.id,
      name: cleanName(group.name),
      icon: cleanIcon(group.icon),
      order: requireNumber(group.order),
      createdAt: requireString(group.createdAt),
      updatedAt: requireString(group.updatedAt),
    };
  });
  const groupIds = new Set(groups.map((group) => group.id));
  if (groupIds.size !== groups.length) throw new Error('Invalid id');

  const pages = snapshot.pages.map((page) => {
    assertId(page.id);
    if (!groupIds.has(page.groupId)) throw new Error('Unknown group');
    const url = normalizeHttpUrl(page.url);
    if (!url) throw new Error('Enter a full http or https address.');
    const faviconBytes = decodeImage(page.faviconBase64);
    const thumbnailBytes = decodeImage(page.thumbnailBase64);
    return {
      id: page.id,
      groupId: page.groupId,
      name: cleanName(page.name),
      url,
      order: requireNumber(page.order),
      createdAt: requireString(page.createdAt),
      updatedAt: requireString(page.updatedAt),
      thumbnailCapturedAt: page.thumbnailCapturedAt == null ? null : requireString(page.thumbnailCapturedAt),
      faviconMime: page.faviconMime == null ? null : requireString(page.faviconMime),
      faviconBytes,
      thumbnailBytes,
    };
  });
  const pageIds = new Set(pages.map((page) => page.id));
  if (pageIds.size !== pages.length) throw new Error('Invalid id');

  let selectedGroupId = snapshot.selectedGroupId ?? null;
  if (selectedGroupId != null) {
    assertId(selectedGroupId);
    if (!groupIds.has(selectedGroupId)) throw new Error('Unknown group');
  }

  return { selectedGroupId, groups, pages };
}

function requireNumber(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('This file is not a Groups Browser backup.');
  return value;
}

function requireString(value) {
  if (typeof value !== 'string' || !value) throw new Error('This file is not a Groups Browser backup.');
  return value;
}

function decodeImage(value) {
  if (value == null) return null;
  if (typeof value !== 'string') throw new Error('This file is not a Groups Browser backup.');
  return Buffer.from(value, 'base64');
}

function filterPages(pages, query) {
  const q = String(query ?? '').trim().toLowerCase();
  if (!q) return pages.slice();
  return pages.filter((page) => page.name.toLowerCase().includes(q) || page.url.toLowerCase().includes(q));
}

module.exports = { Library, filterPages, ID_PATTERN };
