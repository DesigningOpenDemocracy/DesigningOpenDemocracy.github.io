## 2026-09-05 - [Aria Label on Filter Reset Button]
**Learning:** Filter reset buttons using symbol characters like "✕ Reset" or standalone icons need explicit `aria-label` attributes even when a `title` attribute is present, because screen readers may pronounce the unicode symbol or rely on `aria-label` for primary accessible name computation.
**Action:** When adding filter controls or reset buttons, explicitly add `aria-label` describing the specific action (e.g. `aria-label="Reset country filter"`) alongside visual cues.

## 2026-09-08 - [Keyboard Accessible Sortable Table Headers]
**Learning:** Custom interactive table headers (`th.sortable`) in static site overrides require `tabindex="0"`, `scope="col"`, `aria-sort`, `aria-label`, and `Enter`/`Space` keydown event handlers. Without these, keyboard users cannot focus or activate table sorting, and screen readers cannot announce sort state.
**Action:** When adding sortable tables, ensure `th.sortable` elements have `tabindex="0"`, `aria-sort` updated dynamically (`none`, `ascending`, `descending`), keydown listeners for `Enter`/`Space`, and CSS `:focus-visible` outlines.

## 2026-09-17 - [Dynamic Table Empty State and Screen Reader Live Region]
**Learning:** In client-side filtered tables, when 0 rows match, displaying an explicit empty state row (`<tr class="org-empty-row">`) with a direct "Clear filters" action improves usability. Crucially, query selectors for data rows must exclude the empty state (`tr:not(.org-empty-row)`), and the result count element needs `aria-live="polite"` so screen reader users receive immediate verbal feedback as filters change.
**Action:** Always add `aria-live="polite"` to live search counters, exclude placeholder/empty rows from data row selectors, and provide a clear reset button in table empty states.
