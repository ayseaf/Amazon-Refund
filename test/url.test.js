const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const { normalizeHttpUrl } = require('../src/shared/url');

describe('normalizeHttpUrl', () => {
  test('adds https when the scheme is omitted', () => {
    assert.equal(normalizeHttpUrl('youtube.com'), 'https://youtube.com/');
    assert.equal(normalizeHttpUrl('  www.instagram.com/reel  '), 'https://www.instagram.com/reel');
  });

  test('keeps an explicit http or https URL', () => {
    assert.equal(normalizeHttpUrl('http://localhost:4321/fixture'), 'http://localhost:4321/fixture');
    assert.equal(
      normalizeHttpUrl('https://www.youtube.com/watch?v=abc'),
      'https://www.youtube.com/watch?v=abc'
    );
  });

  test('strips embedded usernames and passwords', () => {
    assert.equal(
      normalizeHttpUrl('https://user:secret@example.com/path'),
      'https://example.com/path'
    );
  });

  test('rejects anything that is not http or https', () => {
    assert.equal(normalizeHttpUrl('javascript:alert(1)'), null);
    assert.equal(normalizeHttpUrl('file:///etc/passwd'), null);
    assert.equal(normalizeHttpUrl('data:text/html,hi'), null);
    assert.equal(normalizeHttpUrl(''), null);
    assert.equal(normalizeHttpUrl('   '), null);
    assert.equal(normalizeHttpUrl('https://'), null);
  });
});
