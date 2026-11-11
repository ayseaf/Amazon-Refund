function deleteGroupDetail(name, pageCount) {
  const count = Number(pageCount) || 0;
  if (count === 0) {
    return `Delete “${name}”? This group is empty. This cannot be undone.`;
  }
  const pages = count === 1 ? '1 page' : `${count} pages`;
  return `Delete “${name}” and its ${pages}? This cannot be undone.`;
}

function siteLabel(url, title) {
  const clean = String(title ?? '').replace(/\s+/g, ' ').trim();
  if (clean && clean.length <= 40) return clean;
  return new URL(url).hostname.replace(/^www\./, '');
}

module.exports = { deleteGroupDetail, siteLabel };
