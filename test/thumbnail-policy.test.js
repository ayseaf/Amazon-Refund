const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const { shouldRefreshThumbnail, HOUR } = require('../src/shared/thumbnail-policy');

const saved = 'https://www.youtube.com/';

describe('shouldRefreshThumbnail', () => {
  test('captures when the page has never been snapshotted and is still the same site', () => {
    assert.equal(
      shouldRefreshThumbnail({
        capturedAt: null,
        now: Date.parse('2026-11-11T00:00:00.000Z'),
        savedUrl: saved,
        currentUrl: 'https://youtube.com/feed',
      }),
      true
    );
  });

  test('skips a refresh inside the same day', () => {
    const now = Date.parse('2026-11-11T12:00:00.000Z');
    assert.equal(
      shouldRefreshThumbnail({
        capturedAt: new Date(now - 23 * HOUR).toISOString(),
        now,
        savedUrl: saved,
        currentUrl: saved,
      }),
      false
    );
  });

  test('refreshes once the snapshot is a day old', () => {
    const now = Date.parse('2026-11-11T12:00:00.000Z');
    assert.equal(
      shouldRefreshThumbnail({
        capturedAt: new Date(now - 25 * HOUR).toISOString(),
        now,
        savedUrl: saved,
        currentUrl: 'https://www.youtube.com/watch?v=1',
      }),
      true
    );
  });

  test('never snapshots a different site over a bookmark', () => {
    assert.equal(
      shouldRefreshThumbnail({
        capturedAt: null,
        now: Date.now(),
        savedUrl: saved,
        currentUrl: 'https://accounts.google.com/signin',
      }),
      false
    );
  });
});
