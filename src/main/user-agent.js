/**
 * A current desktop Chrome token. Electron's default UA advertises "Electron",
 * which a number of large sites refuse before the page even renders.
 */
const CHROME_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36';

module.exports = { CHROME_UA };
