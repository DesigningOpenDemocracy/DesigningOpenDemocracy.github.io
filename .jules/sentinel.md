## 2026-09-02 - Unescaped HTML/XSS in GeoJSON Export HTML Descriptions
**Vulnerability:** Unescaped frontmatter string fields (`summary`, `website`, `status`, `country`, `type`, `concepts`) interpolated into raw HTML strings within `props["description"]` in `hooks/data_export.py` for GeoJSON export.
**Learning:** Build-time static data export scripts that construct HTML markup strings for popups/map feature descriptions must explicitly escape user/frontmatter input using `html.escape` to prevent XSS attacks when GeoJSON descriptions are rendered in client-side web maps.
**Prevention:** Always wrap unformatted or user-supplied strings with `html.escape(s)` or `html.escape(s, quote=True)` when embedding values into raw HTML string templates.
