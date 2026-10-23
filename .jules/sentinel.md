## 2026-09-02 - Unescaped HTML/XSS in GeoJSON Export HTML Descriptions
**Vulnerability:** Unescaped frontmatter string fields (`summary`, `website`, `status`, `country`, `type`, `concepts`) interpolated into raw HTML strings within `props["description"]` in `hooks/data_export.py` for GeoJSON export.
**Learning:** Build-time static data export scripts that construct HTML markup strings for popups/map feature descriptions must explicitly escape user/frontmatter input using `html.escape` to prevent XSS attacks when GeoJSON descriptions are rendered in client-side web maps.
**Prevention:** Always wrap unformatted or user-supplied strings with `html.escape(s)` or `html.escape(s, quote=True)` when embedding values into raw HTML string templates.

## 2026-09-18 - Unescaped String Interpolation in JSON-LD Script Blocks
**Vulnerability:** Raw Jinja string interpolation inside double quotes (`"url": "{{ e.url }}"`, `"startDate": "{{ e.date }}"`, `"addressCountry": "{{ e.country or '' }}"`) inside `<script type="application/ld+json">` in `docs/overrides/calendar.html` allowed double quotes to break JSON string syntax and allowed `</script>` tags in `url` or `country` fields to break out of the script tag context into HTML execution context (XSS).
**Learning:** Jinja template strings embedded inside `<script>` blocks (including JSON-LD) must never be manually quoted with `"{ { var } }"`. Unescaped quotes break JSON syntax, and unescaped `</script>` tags terminate the script element in HTML parsers regardless of quotes.
**Prevention:** Always use Jinja's `| tojson` filter (`"url": {{ e.url | tojson }}`) when injecting variables into `<script>` blocks or JSON-LD data. `tojson` emits JSON string quotes and safely encodes HTML special characters (`<`, `>`, `&`).

## 2026-10-22 - Unsanitized URI Schemes in Build-Time Card Hooks
**Vulnerability:** Frontmatter string fields (`url`, `website`, `image`) interpolated into raw HTML link/img elements (`<a href="...">`, `<img src="...">`) in build-time card hooks (`hooks/org_cards.py`, `hooks/event_card.py`, `hooks/shared_link_card.py`) were escaped with `html.escape()`, which escapes HTML syntax (`<`, `>`, `&`, `"`) but leaves dangerous URI schemes (e.g. `javascript:alert(1)`) intact.
**Learning:** `html.escape()` protects against HTML element/attribute context breakout, but does not sanitize protocol schemes in URI attributes like `href` or `src`.
**Prevention:** Always validate URI schemes with an explicit allowlist check (`is_safe_url`: `http://`, `https://`, `mailto:`, relative `/`, `#`, `./`) before embedding frontmatter or external URLs into raw HTML attributes.
