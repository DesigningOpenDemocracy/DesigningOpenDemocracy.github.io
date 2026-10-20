## 2026-09-05 - [Aria Label on Filter Reset Button]
**Learning:** Filter reset buttons using symbol characters like "✕ Reset" or standalone icons need explicit `aria-label` attributes even when a `title` attribute is present, because screen readers may pronounce the unicode symbol or rely on `aria-label` for primary accessible name computation.
**Action:** When adding filter controls or reset buttons, explicitly add `aria-label` describing the specific action (e.g. `aria-label="Reset country filter"`) alongside visual cues.

## 2026-09-08 - [Keyboard Accessible Sortable Table Headers]
**Learning:** Custom interactive table headers (`th.sortable`) in static site overrides require `tabindex="0"`, `scope="col"`, `aria-sort`, `aria-label`, and `Enter`/`Space` keydown event handlers. Without these, keyboard users cannot focus or activate table sorting, and screen readers cannot announce sort state.
**Action:** When adding sortable tables, ensure `th.sortable` elements have `tabindex="0"`, `aria-sort` updated dynamically (`none`, `ascending`, `descending`), keydown listeners for `Enter`/`Space`, and CSS `:focus-visible` outlines.

## 2026-09-17 - [Dynamic Table Empty State and Screen Reader Live Region]
**Learning:** In client-side filtered tables, when 0 rows match, displaying an explicit empty state row (`<tr class="org-empty-row">`) with a direct "Clear filters" action improves usability. Crucially, query selectors for data rows must exclude the empty state (`tr:not(.org-empty-row)`), and the result count element needs `aria-live="polite"` so screen reader users receive immediate verbal feedback as filters change.
**Action:** Always add `aria-live="polite"` to live search counters, exclude placeholder/empty rows from data row selectors, and provide a clear reset button in table empty states.

## 2026-09-21 - [Focus Visible and Explicit Button Types on Custom Controls]
**Learning:** Custom interactive `<button>` elements lacking a `type` attribute default to `type="submit"`, which can cause unexpected form submissions or browser quirks. Furthermore, buttons rendered without explicit CSS `:focus-visible` styles inherit browser-default focus indicators that can be faint or suppressed, leaving keyboard users without visual focus feedback.
**Action:** Always specify `type="button"` on non-submitting action buttons and provide `:focus-visible` outline styles (`outline: 2px solid ...; outline-offset: 2px;`) to ensure clear keyboard navigation.

## 2026-10-13 - [Empty State Placement in Filtered Content Lists]
**Learning:** In client-side filtered lists/feeds, placing the dynamic empty state container after content iteration loops can push the message off-screen or below the fold when zero items match. Positioning the empty state element directly below filter controls ensures immediate visibility within the viewport upon filter application.
**Action:** Place dynamic empty state elements directly adjacent to/below filter bars or control bars rather than after list iteration containers.

## 2026-10-24 - [Consistent Clear-Filter Action in Empty States Across Directory Views]
**Learning:** In multi-view directory applications (e.g. Directory, News, Archive), maintaining consistent empty-state patterns — including centered padding, distinct text color, and a direct `<button type="button" class="org-empty-clear-btn">Clear filters</button>` action — ensures users can instantly recover from empty filter/search results on any list page without hunting for the top reset button.
**Action:** When creating or updating client-side filtered lists, ensure empty state containers include an inline "Clear filters" action button hooked directly to the main filter reset function alongside consistent empty state CSS styling.
