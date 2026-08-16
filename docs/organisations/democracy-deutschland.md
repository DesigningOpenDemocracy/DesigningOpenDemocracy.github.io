---
title: DEMOCRACY Deutschland
type: civil-society
status: active
country: DE
website: https://democracy-app.de
logo: /assets/org-logos/democracy-deutschland.png
contact:
  checked: 2026-08-01
  email: contact@democracy-deutschland.de
  phone: +49 176 470 40 213
  source: https://democracy-deutschland.de/#!impressum
summary: A German volunteer-run nonprofit that brings the Bundestag to citizens' smartphones
  — users can vote on live parliamentary procedures and compare their choices with
  how their actual representatives voted.
concepts:
- democracy-tools
- e-government
- representative-democracy
location:
  latitude: 52.52
  longitude: 13.405
  name: Germany
  precision: city
events:
- date: '2017-08-15'
  title: Verein founded in Göttingen by Marius Krüger
  url: https://www.pressenza.com/de/2017/12/demokratie-echtzeit-neue-app-democracy-erfolgreich-crowdfinanziert/
  quote: Im August dieses Jahres entschied sich Marius Krüger dann dazu, den Worten
    Taten folgen zu lassen und gründete den gemeinnützigen Verein DEMOCRACY Deutschland
    e.V.
  proof_level: high
  url_checked: '2026-08-14'
- date: '2017-11-26'
  title: Crowdfunding campaign completed, securing €35,000 from 580+ supporters
  url: https://www.pressenza.com/de/2017/12/demokratie-echtzeit-neue-app-democracy-erfolgreich-crowdfinanziert/
  quote: der erfolgreiche Abschluss ihres initialen Crowdfundings sicherte ihnen gut
    35.000 € zweckgebundenes Startkapital für die Programmierung einer ersten Version
    der App
  proof_level: high
  url_checked: '2026-08-14'
- date: '2018-10-01'
  title: App launch — first app giving citizens real-time insight into Bundestag legislation,
    with shadow voting
  url: https://www.ghst.de/presse/pressemeldung-im-detail/app-democracy-fuer-transparentere-demokratie-geht-an-den-start
  quote: Mit der App DEMOCRACY startet am 1. Oktober die bundesweit erste App, mit
    der sich Bürgerinnen und Bürger einen Echtzeit-Einblick in die Gesetzesfindung
    des Deutschen Bundestages verschaffen können.
  proof_level: high
  url_checked: '2026-08-14'
  notable: true
activity:
  dod:
    checked: 2026-06-08
    date: 2026-03-15
    note: 'Latest commit: update GitHub Actions to Node.js 24-compatible versions'
    url: https://github.com/demokratie-live/democracy-client/commits/main
  rss:
    checked: 2026-08-09
    note: No feed found
last_checked: '2026-06-29'
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