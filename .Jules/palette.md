## 2026-09-06 - [Accessible Sortable Table Headers]
**Learning:** Sortable table column headers using unicode indicators (e.g. `↕`, `↑`, `↓`) require explicit `tabindex="0"`, `aria-sort` (`none` | `ascending` | `descending`), keyboard listeners (`Enter`/`Space`), and `aria-hidden="true"` on the visual symbol span to ensure screen readers communicate sorting state cleanly and keyboard users can trigger sorting.
**Action:** When making custom table columns sortable, attach `tabindex="0"`, update `aria-sort` dynamically in JavaScript, and wrap decorative sort indicators with `aria-hidden="true"`.

## 2026-09-05 - [Aria Label on Filter Reset Button]
**Learning:** Filter reset buttons using symbol characters like "✕ Reset" or standalone icons need explicit `aria-label` attributes even when a `title` attribute is present, because screen readers may pronounce the unicode symbol or rely on `aria-label` for primary accessible name computation.
**Action:** When adding filter controls or reset buttons, explicitly add `aria-label` describing the specific action (e.g. `aria-label="Reset country filter"`) alongside visual cues.
