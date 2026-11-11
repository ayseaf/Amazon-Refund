# Groups Browser

A small macOS app that replaces a tab bar with a library. Groups sit in a fixed sidebar. Each group is a grid of page tiles. Opening a tile shows that page in a preview pane, and closing the pane destroys the page. Only one page is alive at a time.

## Why this is a desktop app

A Chrome extension cannot remove Chrome’s tab bar, and it cannot show YouTube, Instagram, or most Google pages inside an iframe. Those sites send `X-Frame-Options` or `Content-Security-Policy: frame-ancestors`, which a normal extension page has to obey.

[Tauri](https://tauri.app/) can embed a system webview, and on macOS that webview is WebKit. WebKit will load many of these sites, but keeping exactly one view, placing it in a pane beside the grid, capturing a thumbnail from that visible view, and destroying it on close is awkward. Tauri’s current webview APIs are built around one webview per window.

This app uses **Electron** and one `WebContentsView`. That view is a real Chromium page composited into the window, not an iframe, so frame-blocking headers do not apply. The same approach is what lets the preview load YouTube and Instagram. The view is created when a tile opens and destroyed when the preview closes. Tiles are stored JPEG files, not live pages.

## Install and run on macOS (Apple Silicon)

You need Node.js 22 or newer. On an Apple Silicon Mac, `npm install` downloads Electron’s arm64 build for that machine.

```bash
npm install
npm start
```

Run those from the repository root. On Apple Silicon, the Electron install fetches the arm64 binary.

The first window opens with three example groups: Video Editing, AI Tools, and Marketing. YouTube and Instagram are in that library. Delete them whenever you want; they are ordinary rows, and they do not come back.

Everything you add is stored on this Mac:

```text
~/Library/Application Support/GroupsBrowser/
```

That folder holds `library.json`, favicons, thumbnails, and the signed-in cookie jar. There is no account and no cloud. The app never asks for, reads, or stores passwords. A site you sign in to stays signed in because the preview uses one persistent session (`persist:groups-browser`).

## Using it

- **New group** is at the bottom of the sidebar. Give it a name and an icon.
- **Add page** on a group asks for an address, then fills in the title and icon. You can edit the name before it is saved.
- Click a tile to open it in the preview on the right. The grid stays beside it. **Reload**, **Open in default browser**, and **Close** are in the preview header. Escape closes it too.
- **Save to group…** bookmarks whatever URL is currently in the preview, including a page you navigated to. Pick a group, or **New group**, which creates a group named after the page and saves it there.
- Drag groups to reorder them. Drag a tile onto another tile to reorder it, or onto a sidebar group to move it. The **…** menu renames, moves, and deletes. Deleting a group tells you how many pages it contains.
- The search field filters every group by name or URL.
- **Settings** exports or imports the whole library as one JSON file. Import replaces what is on this Mac.

## Tests

```bash
npm test          # data layer: groups, pages, order, import/export
npm run test:e2e  # create a group, add a page, open the preview, close it
npm run test:sites # loads YouTube and Instagram; needs a network
```

`npm run test:e2e` needs a display. It checks that the preview is a pane rather than a fullscreen window, that a second tile replaces the first, that Escape and the close button destroy the page view, that a cookie set in the preview is still there after a restart, and that drag order survives a restart.

## Architecture

```text
src/data/store.js          local library (JSON + image files)
src/shared/                 URL rules, ordering, thumbnail policy
src/main/main.js            window, persistent session, thumbnail protocol
src/main/preview.js         the one WebContentsView
src/main/metadata.js        title and favicon lookup (no hidden browser)
src/preload/preload.js      the only bridge the UI is allowed to call
src/renderer/               sidebar, grid, dialogs
```

Thumbnails are 320×200 JPEGs taken from the visible preview, about a second after it finishes loading, and only when the address is still on the bookmarked site. A snapshot newer than a day is kept. The app does not open background pages to make images. A tile with no snapshot yet shows the site’s icon, or a letter if the icon cannot be fetched.

With the preview closed, process working sets summed to about 530 MB in a Linux check, but that number counts shared libraries in every process. The proportional footprint (PSS) was about **275 MB**. Opening a preview adds one renderer; closing it removes that renderer.

## Limitations

- Some sites still refuse to run inside any embedded browser, or they show a “this browser is not supported” wall. Sign-in on a few Google properties is stricter than merely loading the page. YouTube’s logged-out home and Instagram’s login page both loaded in testing.
- Protected video (Widevine DRM) may not play.
- A brand-new tile has no screenshot until you open it once. A nearly blank first paint is discarded and tried again on the next open.
- There is no tab strip, no history sync, and no ad blocker.
- A companion Chrome extension (“Add current page to group…”) is not included. The app is usable without it: paste an address, or save from the preview.
- The app is run from source with `npm start`. It is not packaged as a signed `.dmg`.
