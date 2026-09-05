## 2026-09-05 - [Aria Label on Filter Reset Button]
**Learning:** Filter reset buttons using symbol characters like "✕ Reset" or standalone icons need explicit `aria-label` attributes even when a `title` attribute is present, because screen readers may pronounce the unicode symbol or rely on `aria-label` for primary accessible name computation.
**Action:** When adding filter controls or reset buttons, explicitly add `aria-label` describing the specific action (e.g. `aria-label="Reset country filter"`) alongside visual cues.
