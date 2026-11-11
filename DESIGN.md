---
name: Amazon Price Tracker & Refund Assistant
description: A local claim-ticket ledger with a burgundy rail, tissue ground, and a stamp on every price difference.
colors:
  rail: "#8c1d33"
  rail-deep: "#731628"
  stamp: "#8c1d33"
  rail-ink: "#fff6f6"
  ground: "#e4f0ea"
  ink: "#1a2420"
  muted: "#31423b"
  slip: "#fffcfb"
  line: "#c5d4cc"
typography:
  headline:
    fontFamily: "Barlow, \"Avenir Next\", \"Segoe UI\", sans-serif"
    fontSize: "1.85rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Barlow, \"Avenir Next\", \"Segoe UI\", sans-serif"
    fontSize: "1.05rem"
    fontWeight: 600
    letterSpacing: "-0.02em"
    lineHeight: 1.45
  body:
    fontFamily: "Barlow, \"Avenir Next\", \"Segoe UI\", sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  label:
    fontFamily: "Barlow, \"Avenir Next\", \"Segoe UI\", sans-serif"
    fontSize: "0.82rem"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.01em"
  meta:
    fontFamily: "Barlow, \"Avenir Next\", \"Segoe UI\", sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  figure:
    fontFamily: "\"Barlow Condensed\", Barlow, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    letterSpacing: "-0.02em"
  stamp:
    fontFamily: "\"Barlow Condensed\", Barlow, sans-serif"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "0.08em"
rounded:
  ticket: "2px"
  stamp: "999px"
spacing:
  control: "0.45rem"
  row: "0.7rem"
  cell: "0.75rem"
  stack: "1rem"
  column: "2rem"
  page-end: "4rem"
components:
  button-primary:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.rail-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.ticket}"
    padding: "0.5rem 0.85rem"
  button-primary-hover:
    backgroundColor: "{colors.rail-deep}"
    textColor: "{colors.rail-ink}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.ticket}"
    padding: "0.5rem 0.85rem"
  button-secondary-hover:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.ink}"
  text-field:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.ticket}"
    padding: "0.45rem 0.55rem"
  nav-link:
    textColor: "{colors.rail-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.ticket}"
    padding: "0.45rem 0.7rem"
  nav-link-hover:
    backgroundColor: "rgba(255, 246, 246, 0.14)"
    textColor: "{colors.rail-ink}"
  nav-link-current:
    backgroundColor: "{colors.rail-ink}"
    textColor: "{colors.rail}"
    typography: "{typography.body}"
    rounded: "{rounded.ticket}"
    padding: "0.45rem 0.7rem"
  nav-link-current-hover:
    backgroundColor: "{colors.rail-ink}"
    textColor: "{colors.rail-deep}"
  stamp-dashed:
    backgroundColor: "transparent"
    textColor: "{colors.stamp}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "0.05rem 0.7rem 0.1rem"
  stamp-solid:
    backgroundColor: "transparent"
    textColor: "{colors.stamp}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "0.05rem 0.7rem 0.1rem"
  stamp-double:
    backgroundColor: "transparent"
    textColor: "{colors.stamp}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "0.08rem 0.7rem"
  ledger:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "0.7rem 0.75rem"
---

# Design System: Amazon Price Tracker & Refund Assistant

## Overview

**Creative North Star: "The dry-cleaning claim ticket"**

The window is a local ledger printed on shirt-tissue paper. Burgundy stays on the rail and on the stamp, so the table can be read before the ticket-counter color registers. Barlow carries the sentences. Barlow Condensed carries the money and the stamp.

Density is a claim ticket. Each section opens with a heading and one measured sentence, then a hairline table or a hairline list. On the dashboard, paid, latest, and difference share one row. A right-hand margin holds the guarantee, the last synchronization, and Check prices. Totals stay in that sentence. The page has no hero metric cards, and it does not dress itself as Amazon.

The signature is the claim stamp on each difference. The border is dashed when the price has not been checked, solid when it has, and double when the drop meets the savings threshold. A stamp whose check is less than eight seconds old inks in. That motion is removed when the reader prefers reduced motion.

**Key Characteristics:**

- Burgundy rail on a tissue ground, with slip reserved for the table sheet and the fields
- Barlow for interface text; Barlow Condensed for figures, the stamp, the rail's second line, and code
- State is the stamp's line: dashed, solid, or double
- The table owns the page; totals are one sentence
- Flat sheets: 1px hairlines, no shadows, 2px corners on controls

## Colors

One ticket-counter burgundy on green-gray paper. Everything else is ink, moss, slip, or a hairline.

### Primary

- **Burgundy Rail** (`#8c1d33`): The side navigation, primary buttons, the text caret, text selection, and the scrollbar thumb.
- **Pressed Burgundy** (`#731628`): Primary-button hover, the current rail link's hover text, and problem text.
- **Claim Stamp** (`#8c1d33`): The stamp's border and letters. The stylesheet names it separately from the rail; the value is the same burgundy.

### Neutral

- **Slip Text** (`#fff6f6`): Type, the brand mark, and the current-section chip on the rail. Also the selection foreground.
- **Shirt Tissue** (`#e4f0ea`): The page ground and the scrollbar track.
- **Ledger Ink** (`#1a2420`): Body text, the secondary button's stroke and label, and the focus ring. On the rail, the focus ring switches to slip text.
- **Moss** (`#31423b`): Secondary lines, column labels, captions, form labels, placeholders, field borders, and quiet status text.
- **Claim Slip** (`#fffcfb`): The table sheet, field fill, and secondary-button hover.
- **Tissue Hairline** (`#c5d4cc`): Row rules, list rules, the table's top and bottom edges, and fieldset tops.

**The Rail and Stamp Rule.** Burgundy is the rail, the primary button, the caret, the selection, and the stamp. It does not fill the page, and there is no second accent.

**The Tissue and Slip Rule.** Shirt tissue is the only page ground. Claim slip is the sheet under a table and the fill inside a field.

## Typography

**Display Font:** none. Page titles use the headline size below. There is no larger display role.

**Body Font:** Barlow (with Avenir Next, Segoe UI, sans-serif)

**Label/Mono Font:** Barlow for labels. Barlow Condensed (with Barlow, sans-serif) for figures, the stamp, the rail's second line, and `code`. No monospace is loaded.

**Character:** One grotesque in two widths. Barlow is the reading voice. Barlow Condensed is the ticket's numerals and the stamp. The faces are bundled from `@fontsource` (`@fontsource/barlow` at 400 and 600, `@fontsource/barlow-condensed` at 600 and 700), not requested from a Google stylesheet. `font-synthesis` is off, so a weight that was not imported does not faux-bold.

### Hierarchy

- **Headline** (600, 1.85rem, line-height 1.15, tracking -0.03em): The page title. At 800px and below it is 1.5rem.
- **Title** (600, 1.05rem, line-height 1.45, tracking -0.02em): Section headings. Top margin is 1.6rem, except the first heading in the margin, which sits flush. The shipped heading leaves the weight to the user agent; with synthesis off, that bold resolves to the bundled 600. The wordmark in the rail sets 600 explicitly, at 0.98rem, tracking -0.02em.
- **Body** (400, 16px, line-height 1.45): Interface sentences. The reading measure is 68ch. Margin notes wrap at 36ch.
- **Label** (600, 0.82rem, tracking 0.01em, moss): Column headers. A stacked narrow row reprints the column name at 0.75rem in the same weight and color. Form labels are 0.92rem moss, regular weight, stacked 0.3rem above the control.
- **Meta** (400, 0.88rem, moss): The secondary line under a product, a figure, or a list row. Captions are 0.9rem in the same color.
- **Figure** (Barlow Condensed 600, 1.25rem, tracking -0.02em): Paid, latest, difference, and estimate amounts. Numerals are tabular.
- **Stamp** (Barlow Condensed 700, tracking 0.08em, line-height 1.35, uppercase): The word inside the claim stamp, at body size.

**The Condensed Money Rule.** Barlow Condensed is for figures, the stamp, the rail's second line, and code. Sentences stay in Barlow.

**The Sentence Totals Rule.** A page total is one sentence under the heading. It is not a display numeral and not a row of metric cards.

## Layout

The shell is a two-column grid: a 15.5rem rail and a fluid main column, at least the viewport tall. The rail's own padding is 1.25rem 0.75rem 2rem, with a 0.15rem gap between links. The main column's padding is 1.75rem 2rem 4rem. Under 800px that padding becomes 1.1rem 0.9rem 3rem, and the page title drops to 1.5rem.

The dashboard sheet places the heading and the margin side by side (`minmax(0, 1fr)` and `minmax(16rem, 22rem)`), then lets the ledger span both. The gap is 1rem by 2rem. The lower band, and the monitoring page, use the same margin width with a 1.25rem by 2rem gap, and that band becomes one column at 1100px.

At 800px the sheet stacks in this order: heading, ledger, margin. The rail becomes one sticky scrolling row, pinned to the top at z-index 2. Its second line hides, and each section link stays on one line.

The repeated rhythm is 0.45rem inside controls, 0.7rem by 0.75rem inside table cells, 1rem between a heading's sentence and the next block, 2rem between columns, and 4rem under the page.

**The Ledger Owns the Page Rule.** The table is the body of the dashboard. The margin is for the guarantee, the last synchronization, and Check prices, and under 800px that margin stacks beneath the table.

## Elevation & Depth

The sheet is flat. No shadow is defined. Depth comes from three planes: the burgundy rail, the tissue ground, and the slip table. A 1px tissue hairline separates rows, closes the table, and tops a fieldset. The sticky rail is the only layered element, and only after the window is narrower than 800px.

The stamp's ink-in is the only motion: 420ms, `cubic-bezier(0.16, 1, 0.3, 1)`, from opacity 0.15 and 3px down to full ink. It runs when the check is under eight seconds old, and it is disabled under `prefers-reduced-motion`. Buttons change color immediately, with no lift.

**The Flat Sheet Rule.** Surfaces do not cast shadows. A hover changes a fill or a label color. It does not raise the control.

## Shapes

Corners are nearly square. Rail links, fields, and buttons use a 2px radius, the same corner drawn on the 1.75rem ticket mark (a 32-unit outline with a 2-unit corner and a 1.5 stroke). The claim stamp is the exception: a full pill (999px), at least 6.5rem wide, with uppercase condensed type.

The stamp's border is 1px burgundy, dashed or solid. The double form uses a 4px double border so both lines are visible, with slightly tighter vertical padding (0.08rem 0.7rem). Tables and lists are unrounded. Their edges are the hairline.

**The Stamp Line Rule.** State is the stamp's line. Dashed means not checked. Solid means checked. Double means the drop meets the savings threshold. The word (Not checked, Other offer, Lower, Higher, Unchanged) can change without a new color or a fill.

**The Ticket Corner Rule.** Controls and rail links use the 2px ticket corner. The stamp is the only pill.

## Components

### Buttons

Ticket-counter controls: 2px corners, a 1px stroke, padding 0.5rem 0.85rem, the body face, and a pointer. Disabled buttons drop to opacity 0.45 and lose the pointer.

- **Shape:** 2px ticket corner (`rounded.ticket`).
- **Primary:** Burgundy fill, slip text, 1px burgundy stroke. Used for Check prices, Save settings, and Delete local purchase data.
- **Hover / Focus:** Hover fills with pressed burgundy. Focus is the global 2px ledger-ink ring, offset 2px.
- **Secondary:** Transparent fill, ledger-ink label, 1px ink stroke. Hover fills with claim slip. Used for storing or removing a key, and for loading or removing sample orders.

### Cards / Containers

There is no card. The container is the slip ledger: a full-width sheet with a hairline on the top and bottom edges, no radius, and no shadow. Cells pad 0.7rem 0.75rem, align to the baseline, and draw a hairline under each row. Column labels are the label face in moss. Amounts in a numeric column sit flush right. The sheet's table holds a 52rem minimum until 800px, then each row stacks, the header hides, and the cell's `data-label` prints above the value. Inside a difference cell the stamp and the figure share a baseline, with 0.45rem between them.

### Inputs / Fields

Text fields and selects share one chrome: claim-slip fill, 1px moss stroke, 2px corner, padding 0.45rem 0.55rem, a 12rem minimum width, and a burgundy caret. Placeholder text is moss. Focus is the same 2px ink ring, offset 2px. A problem is a pressed-burgundy sentence at weight 600 under the control, not a recolored stroke. Quiet status text is moss.

Checkbox rows are a horizontal ink label with the control beside the words. Fieldsets have no box: a hairline across the top, a 600-weight legend, and 0.8rem of air under that line.

### Navigation

The rail is burgundy type on burgundy, in the body face, with links padded 0.45rem 0.7rem and the 2px corner. The current section is a slip chip with burgundy type. A resting link hovers to slip text at 14% (`rgba(255, 246, 246, 0.14)`). The current chip keeps its slip fill on hover and turns the type to pressed burgundy. Focus rings on the rail and the brand are slip text.

The brand is a 1.75rem ticket outline, then "Amazon Price Tracker" at 0.98rem / 600, then "Refund Assistant" in Barlow Condensed 600, 0.85rem, tracking 0.04em, uppercase. Under 800px that second line is hidden and the rail scrolls sideways.

### Lists

A plain list has no markers. Each item is padded 0.55rem 0 and closed with a 1px hairline, the same rule as a table row. The product name is weight 600. The line under it is meta.

### Claim stamp

A pill of transparent slip, burgundy letters, and a burgundy border, min-width 6.5rem. The line form is the whole state signal:

- **Dashed** (1px): the price has not been checked. The word is "Not checked".
- **Solid** (1px): a check exists and the double condition is not met. Words include "Other offer", "Higher", "Unchanged", and a drop below the savings threshold.
- **Double** (4px): the offer is comparable and the savings meet the threshold. The word is "Lower".

The figure for a known difference sits on the same baseline, 0.45rem to the right of the stamp. While the check is fresh, the stamp plays the ink-in motion described in Elevation & Depth.

## Do's and Don'ts

### Do:

- **Do** keep burgundy on the rail, the primary button, the caret, the selection, and the stamp.
- **Do** print the page on shirt tissue, and put tables and fields on claim slip.
- **Do** set sentences in Barlow, and set figures in Barlow Condensed 600 with tabular numerals.
- **Do** load Barlow 400 and 600 and Barlow Condensed 600 and 700 from the bundled `@fontsource` files.
- **Do** show each difference as a claim stamp: dashed, solid, or double at 4px.
- **Do** keep a page total in one sentence under the heading, with paid, latest, and difference in one row.
- **Do** separate rows with a 1px tissue hairline and leave the sheet flat.
- **Do** use a 2px ledger-ink focus ring, offset 2px, and switch that ring to slip text on the rail.
- **Do** stack the lower work band at 1100px, and stack the sheet, the table, and the rail at 800px.
- **Do** drop the stamp's ink animation when the reader prefers reduced motion.

### Don't:

- **Don't** add a hero row of metric cards, or a display-size total.
- **Don't** dress the interface as Amazon. No marketplace orange, smile, or store chrome.
- **Don't** use a box-shadow, and don't lift a button, row, or rail on hover.
- **Don't** fill the stamp, or recolor it, to show state. The line form is the state.
- **Don't** request a Barlow weight that is not bundled. Synthesis is off, and Condensed 700 belongs to the stamp.
- **Don't** load the faces from a Google Fonts stylesheet.
