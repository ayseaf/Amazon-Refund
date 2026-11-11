const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const { reorderIdList } = require('../src/shared/order');

describe('reorderIdList', () => {
  test('moves an id before or after the drop target', () => {
    assert.deepEqual(reorderIdList(['a', 'b', 'c', 'd'], 'a', 'c', 'before'), ['b', 'a', 'c', 'd']);
    assert.deepEqual(reorderIdList(['a', 'b', 'c', 'd'], 'd', 'a', 'after'), ['a', 'd', 'b', 'c']);
  });

  test('leaves the list alone when an item is dropped on itself', () => {
    assert.deepEqual(reorderIdList(['a', 'b', 'c'], 'b', 'b', 'before'), ['a', 'b', 'c']);
  });

  test('rejects a target that is not in the list', () => {
    assert.throws(() => reorderIdList(['a', 'b'], 'a', 'z', 'before'), /target/);
  });
});
