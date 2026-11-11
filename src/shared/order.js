/**
 * Drop `sourceId` before or after `targetId`.
 * Dropping an item on itself keeps the current order.
 */
function reorderIdList(ids, sourceId, targetId, position) {
  if (sourceId === targetId) return ids.slice();
  const without = ids.filter((id) => id !== sourceId);
  let index = without.indexOf(targetId);
  if (index < 0) throw new Error('Unknown drop target');
  if (position === 'after') index += 1;
  without.splice(index, 0, sourceId);
  return without;
}

module.exports = { reorderIdList };
