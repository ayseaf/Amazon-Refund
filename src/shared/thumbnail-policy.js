const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

function hostKey(url) {
  return new URL(url).hostname.replace(/^www\./, '').toLowerCase();
}

/**
 * A thumbnail is taken from the live preview only, and at most once a day.
 * A navigation that leaves the bookmarked site must not overwrite it.
 */
function shouldRefreshThumbnail({ capturedAt, now, savedUrl, currentUrl }) {
  try {
    if (hostKey(savedUrl) !== hostKey(currentUrl)) return false;
  } catch {
    return false;
  }
  if (!capturedAt) return true;
  const then = Date.parse(capturedAt);
  if (Number.isNaN(then)) return true;
  return now - then >= DAY;
}

module.exports = { shouldRefreshThumbnail, HOUR, DAY };
