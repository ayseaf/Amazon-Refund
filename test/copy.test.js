const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const { deleteGroupDetail, siteLabel } = require('../src/shared/copy');

describe('delete confirmation copy', () => {
  test('states that an empty group has no pages', () => {
    assert.equal(
      deleteGroupDetail('Social Media', 0),
      'Delete “Social Media”? This group is empty. This cannot be undone.'
    );
  });

  test('states the page count for a group that has pages', () => {
    assert.equal(
      deleteGroupDetail('Marketing', 1),
      'Delete “Marketing” and its 1 page? This cannot be undone.'
    );
    assert.equal(
      deleteGroupDetail('Video Editing', 2),
      'Delete “Video Editing” and its 2 pages? This cannot be undone.'
    );
  });
});

describe('siteLabel', () => {
  test('uses a short page title', () => {
    assert.equal(siteLabel('https://www.youtube.com/', 'YouTube'), 'YouTube');
  });

  test('falls back to the hostname when the title is empty or very long', () => {
    assert.equal(siteLabel('https://www.instagram.com/p/abc', ''), 'instagram.com');
    assert.equal(siteLabel('https://www.youtube.com/watch?v=1', 'A'.repeat(80)), 'youtube.com');
  });
});
