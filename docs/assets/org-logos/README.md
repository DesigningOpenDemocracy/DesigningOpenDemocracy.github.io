# Organisation logos

Each logo file is the property of its respective organisation. Used here for identification
and informational purposes under fair dealing / fair use provisions, except where a file is
sourced from Wikimedia Commons under an open license (marked below).

This is a proof-of-concept set covering a handful of well-known organisations — see the
`logo:` field convention in `CLAUDE.md` under "Organisation pages". Bulk backfill across the
rest of `docs/organisations/` is a deliberate followup, not part of the initial rollout.

| Organisation | Logo | License | Source |
|---|---|---|---|
| vTaiwan | ![](vtaiwan.png) | Fair use | [vtaiwan.tw](https://vtaiwan.tw/apple-touch-icon.png) (site icon) |
| g0v (gov zero) | ![](g0v.svg) | Fair use | [g0v.tw](https://g0v.tw/assets/img/g0v-only.svg) (site asset) |
| Decidim | ![](decidim.svg) | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Decidim-logo.svg) |
| Loomio | ![](loomio.png) | Fair use | [loomio.com](https://www.loomio.com/images/brand/icon-yellow-on-white-1024.png) (brand asset) |
| Consul Democracy | ![](consul-democracy.png) | Fair use | [consuldemocracy.org](https://consuldemocracy.org/wp-content/uploads/consul_logo.png) (site asset) |

## Adding a logo

1. Download the highest-quality version available (prefer SVG, then PNG) from the org's own
   site, or from Wikimedia Commons if a suitably licensed version exists there.
2. Place it at `docs/assets/org-logos/<org-slug>.<ext>`, where `<org-slug>` matches the org's
   filename under `docs/organisations/` (without `.md`).
3. Add `logo: /assets/org-logos/<org-slug>.<ext>` to the org's frontmatter.
   - A remote URL (e.g. a Wikimedia Commons or the org's own hosted file) is also valid when a
     local copy isn't warranted — see the international-comparator pattern in
     `docs/assets/party-logos/README.md`.
4. For non-free/fair use logos, prefer the org's own official site asset (favicon, brand kit,
   masthead) over a third-party mirror.
5. Update the table above.
