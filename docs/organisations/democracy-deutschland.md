---
title: DEMOCRACY Deutschland
type: civil-society
status: active
country: DE
website: https://democracy-app.de
summary: "A German volunteer-run nonprofit that brings the Bundestag to citizens' smartphones — users can vote on live parliamentary procedures and compare their choices with how their actual representatives voted."
concepts:
  - e-government
  - representative-democracy
location:
  latitude: 52.5200
  longitude: 13.4050
  name: Germany
activity:
  dod:
    date: 2026-03-15
    note: "Latest commit: update GitHub Actions to Node.js 24-compatible versions"
    url: https://github.com/demokratie-live/democracy-client/commits/main
    checked: 2026-06-08
  rss:
    note: "No feed found"
    checked: 2026-06-08
last_checked: "2026-06-29"
---

DEMOCRACY Deutschland e.V. is a German nonprofit building open-source civic technology to close the gap between parliamentary decisions and the citizens affected by them. Their flagship product is the **DEMOCRACY app**, available on Android (including [F-Droid](https://f-droid.org/en/packages/de.democracydeutschland.app/)), iOS, and as a web interface.

The app tracks every procedure coming to a vote in the German Bundestag. Citizens can cast their own shadow vote on each item before the session, then see how their chosen parties and individual representatives actually voted. The comparison is the point: it makes the distance between a citizen's preferences and their representatives' choices concrete and visible.

Key features:

- **Live Bundestag tracking** — procedures listed by upcoming session week
- **Shadow voting** — cast a personal vote before the official result is known
- **Party and MP alignment** — compare your voting record against parties and named representatives
- **Community results** — see the aggregate shadow vote from all app users
- **Parliamentary notifications** — alerts when a tracked vote goes live

The codebase (TypeScript / React Native / Expo) is open source under Apache 2.0 at [github.com/demokratie-live](https://github.com/demokratie-live). The app has an F-Droid anti-feature flag for a hard-coded API endpoint (`api.democracy-app.de`), which is worth noting for self-hosting but does not affect typical use.

## Links

- Website: [democracy-app.de](https://democracy-app.de)
- F-Droid: [f-droid.org/packages/de.democracydeutschland.app](https://f-droid.org/en/packages/de.democracydeutschland.app/)
- GitHub: [github.com/demokratie-live](https://github.com/demokratie-live)

## See also

- [E-Government](../concepts/e-government.md)
- [Representative Democracy](../concepts/representative-democracy.md)
- [Democracy Apps & Tools](../concepts/democracy-tools.md)
