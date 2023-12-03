---
title: ElectionDates.org
contributors:
  - BrianKhuu
  - Usmaan
---

# Election Dates

[ElectionDates.org](https://www.electiondates.org/)

Election Dates is a project that aim to make it easy to find and share the next election date for a country.

Currently a basic proof of concept website is now running and will be cleaned up further before being opensourced for public contributions and improvements.

If any dates is missing then you can submit suggestions.

This website electiondates.org has a singular purpose of making it
easier for the public to find out when the next election is on.

## Interface

The main interface should include information from all locations not
just a single country.

While it can direct or highlight a country that it think you are located
at, it should always be easy to access a global list. E.g. Maybe you
want to look for the next election across multiple countries.

### Key Components

- Main short sentence for "TLDR" messaging of selected entry (Default:
  User's country, next election or finished election status)
- Filter options (Default: User's country, All election type,
  Chronologically sorted)
- Public Crowdsourcing Tip Line
- Table of election dates data linked to filter options and pagenated if
  needed
- Sharable URL

### Other Thoughts

Also maybe we should include an info bubble to allow for showing links
and description about the date. E.g. where did the information come from
and is there a link to a government website on voting in it?

Should we rely on only one source for results? What if the results is
disputed? Also should we note down election integrity observer's results
(inconsistencies in voting count)?

How shall we show early election dates?

## Design Philosophy

We are using Unix philosophy, where we have a program/website/etc...
that serves a singular purpose. This does not mean we only do one thing.
We can serve the single purpose in multiple ways (e.g. JSON API).

## Overall Design Goal

This is from the perspective of an incoming web user

- Minimum graphic : Should be fast to load
- Ease of navigation : Should be easy to find and filter any election
  dates as possible. (e.g. filter by country, range of dates, type)
- Easy to share : Should be able to share a URL with the same view.
  (e.g. sharing a specific election date countdown on twitter)

## Future Idea

- Provide an interface for programmatic access to the database. This may
  be located in api.electiondates.org
- Provide a way for users to subscribe to election date reminders via
  email or other means.
- Twitter bot to post next election date every week or so of elections
  around the world?

## Wishlist

- Dark Mode
  <https://stackoverflow.com/questions/50840168/how-to-detect-if-the-os-is-in-dark-mode-in-browsers>
- Microformats compatible for ease of use in social media:
  <http://microformats.org/>
