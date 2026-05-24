---
title: DigiPol
type: platform
status: inactive
country: AU
website: https://web.archive.org/web/*/https://digipol.app/
summary: "An open-source Australian app that lets citizens browse, read, and vote on bills before the Federal Parliament."
contributors:
  - BrianKhuu
---

DigiPol is an application developed by the Flux team to enable citizen participation in the legislative processes of the Australian Federal Parliament. It is open source, built by volunteer developers across Australia.

## Functionality

- **Browse bills** — navigate all bills currently before Parliament, pulled from the Australian Parliament website
- **Read explanatory memoranda** — each bill includes the official document explaining its purpose and contents
- **Read bill text** — access the specific wording of each bill
- **Vote on bills** — express support or opposition via yes/no vote, changeable at any time
- **Vote on issues** — topics of public interest not yet tied to legislation before Parliament

Planned future features include sharing vote results by electorate and state, and contacting elected representatives via linked contact points.

## Technical

DigiPol is built with the [Flutter](https://flutter.dev/) framework (Dart language), targeting Android and iOS. Votes are recorded on the [Ethereum](https://ethereum.org/) blockchain via a Python/Solidity API layer running on AWS Lambda. The SHA-256 algorithm is used to hash vote data before transmission.

Source code: [github.com/voteflux](https://github.com/voteflux)

## Links

- Website: [digipol.app](https://web.archive.org/web/*/https://digipol.app/) *(archived)*
