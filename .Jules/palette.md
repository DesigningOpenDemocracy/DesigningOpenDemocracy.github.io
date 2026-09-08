## 2026-09-05 - [Aria Label on Filter Reset Button]
**Learning:** Filter reset buttons using symbol characters like "✕ Reset" or standalone icons need explicit `aria-label` attributes even when a `title` attribute is present, because screen readers may pronounce the unicode symbol or rely on `aria-label` for primary accessible name computation.
**Action:** When adding filter controls or reset buttons, explicitly add `aria-label` describing the specific action (e.g. `aria-label="Reset country filter"`) alongside visual cues.

## 2026-09-08 - [Keyboard Accessible Sortable Table Headers]
**Learning:** Custom interactive table headers (`th.sortable`) in static site overrides require `tabindex="0"`, `scope="col"`, `aria-sort`, `aria-label`, and `Enter`/`Space` keydown event handlers. Without these, keyboard users cannot focus or activate table sorting, and screen readers cannot announce sort state.
**Action:** When adding sortable tables, ensure `th.sortable` elements have `tabindex="0"`, `aria-sort` updated dynamically (`none`, `ascending`, `descending`), keydown listeners for `Enter`/`Space`, and CSS `:focus-visible` outlines.
