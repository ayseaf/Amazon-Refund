const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Library, filterPages } = require('../src/data/store');

function tempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'groups-browser-'));
}

describe('Library seed', () => {
  test('creates the example groups the first time the folder is opened', () => {
    const lib = Library.open(tempDir());
    const names = lib.getState().groups.map((group) => group.name);
    assert.deepEqual(names, ['Video Editing', 'AI Tools', 'Marketing']);
    const pages = lib.getState().pages.map((page) => page.name);
    assert.ok(pages.includes('YouTube'));
    assert.ok(pages.includes('Instagram'));
    const youtube = lib.getState().pages.find((page) => page.name === 'YouTube');
    assert.equal(youtube.url, 'https://www.youtube.com/');
    const instagram = lib.getState().pages.find((page) => page.name === 'Instagram');
    assert.equal(instagram.url, 'https://www.instagram.com/');
  });

  test('does not recreate the examples after they are deleted', () => {
    const dir = tempDir();
    const first = Library.open(dir);
    for (const group of first.getState().groups) first.deleteGroup(group.id);
    assert.equal(Library.open(dir).getState().groups.length, 0);
  });
});

describe('groups and pages', () => {
  test('creates, renames, reorders, and deletes a group with its pages', () => {
    const lib = Library.open(tempDir(), { seed: false });
    const social = lib.createGroup({ name: 'Social Media', icon: '💬' });
    const video = lib.createGroup({ name: 'Video', icon: '🎬' });
    assert.equal(lib.getState().selectedGroupId, video.id);

    lib.updateGroup(social.id, { name: 'Social', icon: '🌐' });
    assert.deepEqual(
      lib.getState().groups.map((group) => [group.name, group.icon]),
      [
        ['Social', '🌐'],
        ['Video', '🎬'],
      ]
    );

    lib.reorderGroups([video.id, social.id]);
    assert.deepEqual(
      lib.getState().groups.map((group) => group.id),
      [video.id, social.id]
    );

    const page = lib.addPage({ groupId: video.id, name: 'YouTube', url: 'youtube.com' });
    assert.equal(page.url, 'https://youtube.com/');
    assert.equal(lib.deleteGroup(video.id).pageCount, 1);
    assert.equal(lib.getState().pages.length, 0);
    assert.equal(lib.getState().selectedGroupId, social.id);
    assert.equal(lib.getState().groups.length, 1);
  });

  test('can add a group without leaving the one that is open', () => {
    const lib = Library.open(tempDir(), { seed: false });
    const first = lib.createGroup({ name: 'Video Editing', icon: '🎬' });
    const second = lib.createGroup({ name: 'Social Media', icon: '💬', select: false });
    assert.equal(lib.getState().selectedGroupId, first.id);
    assert.equal(lib.getState().groups.at(-1).id, second.id);
  });

  test('asks the delete confirmation to include the page count via the returned count', () => {
    const lib = Library.open(tempDir(), { seed: false });
    const group = lib.createGroup({ name: 'Marketing', icon: '📣' });
    lib.addPage({ groupId: group.id, name: 'Instagram', url: 'https://instagram.com' });
    lib.addPage({ groupId: group.id, name: 'Mailchimp', url: 'https://mailchimp.com' });
    assert.equal(lib.pageCount(group.id), 2);
  });

  test('edits, reorders, and moves pages, then reloads the same order from disk', () => {
    const dir = tempDir();
    const lib = Library.open(dir, { seed: false });
    const a = lib.createGroup({ name: 'A', icon: 'A' });
    const b = lib.createGroup({ name: 'B', icon: 'B' });
    const first = lib.addPage({ groupId: a.id, name: 'One', url: 'https://one.example/a' });
    const second = lib.addPage({ groupId: a.id, name: 'Two', url: 'https://two.example/b' });
    const third = lib.addPage({ groupId: a.id, name: 'Three', url: 'https://three.example/c' });

    lib.updatePage(second.id, { name: 'Two renamed', url: 'https://two.example/renamed' });
    lib.reorderPages(a.id, [third.id, first.id, second.id]);
    lib.movePage(first.id, b.id);

    const reloaded = Library.open(dir);
    const groupA = reloaded.getState().pages.filter((page) => page.groupId === a.id);
    assert.deepEqual(
      groupA.map((page) => page.name),
      ['Three', 'Two renamed']
    );
    assert.equal(groupA.find((page) => page.name === 'Two renamed').url, 'https://two.example/renamed');
    const groupB = reloaded.getState().pages.filter((page) => page.groupId === b.id);
    assert.deepEqual(groupB.map((page) => page.id), [first.id]);
    assert.equal(reloaded.getState().groups.at(-1).id, b.id);
  });

  test('rejects a bad URL, an unknown group, and a reorder that drops an id', () => {
    const lib = Library.open(tempDir(), { seed: false });
    const group = lib.createGroup({ name: 'A', icon: 'A' });
    assert.throws(() => lib.addPage({ groupId: group.id, name: 'X', url: 'javascript:alert(1)' }), /http/);
    assert.throws(() => lib.addPage({ groupId: 'missing', name: 'X', url: 'https://example.com' }), /group/);
    const page = lib.addPage({ groupId: group.id, name: 'X', url: 'https://example.com' });
    assert.throws(() => lib.reorderPages(group.id, []), /every page/);
    assert.equal(lib.getState().pages[0].id, page.id);
  });
});

describe('thumbnails and favicons', () => {
  test('stores image bytes beside the library and clears them with the page', () => {
    const dir = tempDir();
    const lib = Library.open(dir, { seed: false });
    const group = lib.createGroup({ name: 'A', icon: 'A' });
    const page = lib.addPage({ groupId: group.id, name: 'Pic', url: 'https://example.com' });
    lib.setFavicon(page.id, { bytes: Buffer.from('png-bytes'), mime: 'image/png' });
    lib.setThumbnail(page.id, {
      bytes: Buffer.from('jpeg-bytes'),
      capturedAt: '2026-11-01T00:00:00.000Z',
    });

    let state = lib.getState().pages[0];
    assert.equal(state.hasFavicon, true);
    assert.equal(state.hasThumbnail, true);
    assert.equal(state.thumbnailCapturedAt, '2026-11-01T00:00:00.000Z');
    assert.ok(fs.existsSync(path.join(dir, 'favicons', `${page.id}`)));
    assert.ok(fs.existsSync(path.join(dir, 'thumbs', `${page.id}.jpg`)));

    lib.clearThumbnail(page.id);
    assert.equal(lib.getState().pages[0].hasThumbnail, false);
    assert.equal(fs.existsSync(path.join(dir, 'thumbs', `${page.id}.jpg`)), false);

    lib.deletePage(page.id);
    assert.equal(fs.existsSync(path.join(dir, 'favicons', `${page.id}`)), false);
  });
});

describe('import and export', () => {
  test('round-trips groups, pages, order, selection, and images exactly', () => {
    const source = Library.open(tempDir(), { seed: false });
    const video = source.createGroup({ name: 'Video Editing', icon: '🎬' });
    const marketing = source.createGroup({ name: 'Marketing', icon: '📣' });
    source.selectGroup(video.id);
    const youtube = source.addPage({
      groupId: video.id,
      name: 'YouTube',
      url: 'https://www.youtube.com/',
    });
    const instagram = source.addPage({
      groupId: marketing.id,
      name: 'Instagram',
      url: 'https://www.instagram.com/',
    });
    source.reorderPages(video.id, [youtube.id]);
    source.setFavicon(youtube.id, { bytes: Buffer.from([1, 2, 3, 4]), mime: 'image/png' });
    source.setThumbnail(instagram.id, {
      bytes: Buffer.from([9, 8, 7]),
      capturedAt: '2026-11-02T03:04:05.000Z',
    });

    const snapshot = source.exportSnapshot();
    const restored = Library.open(tempDir(), { seed: false });
    restored.createGroup({ name: 'This should disappear', icon: 'X' });
    restored.importSnapshot(snapshot);

    const again = restored.exportSnapshot();
    assert.equal(again.selectedGroupId, video.id);
    assert.deepEqual(again.groups, snapshot.groups);
    assert.deepEqual(again.pages, snapshot.pages);

    const saved = JSON.parse(fs.readFileSync(path.join(restored.directory, 'library.json'), 'utf8'));
    assert.equal(saved.groups.length, 2);
    assert.equal(saved.pages.find((page) => page.name === 'YouTube').faviconMime, 'image/png');
  });

  test('leaves the library untouched when the backup is invalid', () => {
    const lib = Library.open(tempDir(), { seed: false });
    const group = lib.createGroup({ name: 'Keep me', icon: 'K' });
    lib.addPage({ groupId: group.id, name: 'Stay', url: 'https://stay.example/' });
    const before = lib.exportSnapshot();

    assert.throws(() => lib.importSnapshot({ format: 'nope', version: 1, groups: [], pages: [] }), /backup/);
    assert.throws(
      () =>
        lib.importSnapshot({
          format: 'groups-browser',
          version: 1,
          selectedGroupId: null,
          groups: [{ id: '../evil', name: 'Bad', icon: 'B', order: 0, createdAt: 'x', updatedAt: 'x' }],
          pages: [],
        }),
      /id/
    );
    assert.throws(
      () =>
        lib.importSnapshot({
          format: 'groups-browser',
          version: 1,
          selectedGroupId: null,
          groups: [{ id: 'group-ok', name: 'Ok', icon: 'O', order: 0, createdAt: '2026-01-01T00:00:00.000Z', updatedAt: '2026-01-01T00:00:00.000Z' }],
          pages: [
            {
              id: 'page-ok',
              groupId: 'missing-group',
              name: 'Orphan',
              url: 'javascript:alert(1)',
              order: 0,
              createdAt: '2026-01-01T00:00:00.000Z',
              updatedAt: '2026-01-01T00:00:00.000Z',
              thumbnailCapturedAt: null,
              faviconMime: null,
              faviconBase64: null,
              thumbnailBase64: null,
            },
          ],
        }),
      /http|group/
    );

    assert.deepEqual(lib.exportSnapshot(), before);
  });
});

describe('filterPages', () => {
  test('matches a query against names and URLs across pages', () => {
    const pages = [
      { name: 'YouTube', url: 'https://www.youtube.com/' },
      { name: 'Instagram', url: 'https://www.instagram.com/' },
      { name: 'ChatGPT', url: 'https://chatgpt.com/' },
    ];
    assert.deepEqual(
      filterPages(pages, 'tube').map((page) => page.name),
      ['YouTube']
    );
    assert.deepEqual(
      filterPages(pages, 'INSTAGRAM.com').map((page) => page.name),
      ['Instagram']
    );
    assert.equal(filterPages(pages, '   ').length, 3);
  });
});
