---
title: DigiPol
contributors:
  - BrianKhuu
---

**NPV Required: This article should be written from a
neutral/third-person point of view. Currently it mentions the word "we"
6 times**

**This is currently a stub page based on DigiPol Team current project
description documents which is currently a work in progress**

**What's missing at the moment is a section on how to contact the
digipol team and the historical background of the project**

# Introduction

Main website located at <https://digipol.app/>

## What is DigiPol?

DigiPol is an application to enable participation with the legislative
processes of Australian Federal Parliament.

The current version of DigiPol is a technical preview designed to
orientate users to some of the basic functionality which we will build
upon.

## What functionality does DigiPol provide?

Users are able to:

- Explore, search and view all the bills in Federal Parliament
- Review Explanatory Memoranda to learn about the bills
- Review the actual text of bills
- Vote on bills

### Explore, search and view all the bills in Parliament

With DigiPol, you can easily navigate all the bills which are currently
before Parliament. The app pulls all the bills from the Australian
Parliament website and displays them in an easy-to-navigate format.

### Review the Explanatory Memoranda

Each bill comes with an Explanatory Memoranda document which provides an
overview of the bill’s purpose and info on what the bill contains. This
is the information which is presented to Parliament as part of the
process of passing legislation.

### Review the text of bills

You can review the specific wording of each bill in order to understand
the nuanced detail contained with the bill.

### Vote on bills

You can express your support or opposition for bills by voting YES or
NO. You can also change your vote at a later time should you wish.

### Vote on issues

You can express your support or opposition on issues by voting YES or
NO. Issues are defined as topics of public interest with no relevant
legislation currently before Parliament. Issues are currently curated by
Flux but will be sourced from the community in future releases.

### Share results (planned for future release)

Users can share the results of votes on bills and issues via social
media., with future releases having breakdowns by electorate and state.

### Contact representatives (planned for future release)

Users can contact their elected representatives, via linked contact
points (email, Soc.media, phone).

# Frequently Asked Questions

## General

### Who is behind DigiPol?

DigiPol is released by Flux - a political movement working to improve
our democracy by increasing accountability and participation in our
political processes.

The application has been coded by a team of developers from across
Australia who have contributed their skills, time and energy to build an
[<span class="underline">open-source
codebase](https://github.com/voteflux).

### Is this the finished product?

DigiPol is the first application developed and released by Flux and is
intended as a technical preview to orientate users to some of the basic
functionality.

We will continue to develop and release additional features and
functionality but we work within the constraints of being a
volunteer-driven project. If you would like to see specific features
developed sooner, you can contribute to our
[<span class="underline">open-source
codebase](https://github.com/voteflux).

### Can I use DigiPol on my desktop?

At this time, DigiPol is only available on Android and iOS devices.

## Technical

### What technologies does DigiPol use?

[<span class="underline">The DigiPol
app](https://github.com/voteflux/voting_app) is built using the
[<span class="underline">Flutter](https://flutter.dev/) framework.
Flutter is an open-source UI development kit created by Google which is
used to develop applications for Android, iOS, Windows, Mac, Linux and
the web.

Flutter utilises the [<span class="underline">Dart programming
language](https://dart.dev/). Dart is optimised for making apps which
work and look good on all devices, and facilitating iterative
development (making it easier for developing small incremental changes).

DigiPol sends your votes directly to the blockchain via HTTP requests.

[<span class="underline">The API (Application Programming Interface)
functionality](https://github.com/voteflux/voting-app-api), which
enables the application to interact with an underlying blockchain is
coded in Python and
[<span class="underline">Solidity](https://solidity.readthedocs.io/en/v0.6.12/).

Code running on [<span class="underline">AWS
Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) is
used to manage the tracking of bills on
[<span class="underline">aph.gov.au](https://www.aph.gov.au/), counting
votes on the blockchain and ensuring the information displayed in
DigiPol is up-to-date.

Transactions (bills & votes) are verified on the
[<span class="underline">Ethereum](https://ethereum.org/en/) blockchain.
Ethereum is an [<span class="underline">open-source
platform](https://ethereum.org/en/learn/) for running decentralised
applications.

## Security Features

We utilise functionality including:

- Authenticating users (not yet implemented)
- Private key management (basic version implemented)
- Hashing transactions (currently implemented)

### Authenticating users

To prevent manipulation of votes, we will ensure our users are real and
unique people. We will verify users using a combination of electoral
roll data and validation with a 3rd party identification verification
service.

For the technical preview, we are not yet authenticating our users. We
will implement this functionality prior to the main release. The
objective at this time is to make users familiar with the basic
functionality of navigating, exploring and voting on bills.

### Private key management

During installation, DigiPol generates a Private Key on your device.
This Private Key is used to verify that your transactions come from only
your device.

The app generates a cryptographically secure random number which is used
to create a seed unique to your device. This seed is used to create your
device’s Private Key.

The key generation happens in the background without any requirement for
the user to do anything. In the initial release, it is not possible to
backup Private Keys, nor transfer Private Keys between devices.

Future releases will implement key management standards
[<span class="underline">BIP32](https://en.bitcoin.it/wiki/BIP_0032) and
[<span class="underline">BIP39](https://en.bitcoin.it/wiki/BIP_0039) so
users can transfer their personal profiles between devices and restore
from backups.

### Hashing transactions

DigiPol uses the
[<span class="underline">SHA-256](https://en.wikipedia.org/wiki/SHA-2)
algorithm to
[<span class="underline">hash](https://en.wikipedia.org/wiki/Cryptographic_hash_function)
data prior to sending it from your device to the blockchain. This
ensures that your voting information is kept private.

Hashing involves using your private key to convert your vote on a bill
into a standardised format which can not be read by a 3rd party.

SHA-256 is widely regarded as an international standard for
authenticating transactions on the internet. It is used for securing
Bitcoin transactions, the DKIM messaging standard (email authentication)
and ensuring the integrity of software packages downloaded from the
internet.
