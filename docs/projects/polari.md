---
title: Polari — Open Source Research & Democracy Platform
template: project.html
status: active
contributors:
  - Dausume
website: https://github.com/dausume/Polari-Framework
summary: "A self-hosted, modular research framework with a built-in policy scoring system — allowing communities to directly rate and analyse policies, politicians, and special interest groups using a participatory democratic methodology."
---

Polari is a project by DOD member Dustin ("Dausume"), a Full Stack Engineer based in the US. It consists of two interconnected open-source platforms: a general-purpose research framework and a democracy/policy scoring application built on top of it.

## The two platforms

### Polari Research Framework

Polari is a backend infrastructure tool that solves a common problem in open-source research: integrating multiple Python libraries into a coherent, persistent system. You define your data objects in Python; Polari automatically generates:

- A **SQLite database** for persistence
- A **Falcon REST API** for all configured objects
- A modular node/tree architecture that lets multiple research systems interconnect

An Angular frontend (`polari-platform-angular`) provides a UI layer with table and graph configuration, mapping (GeoJSON/map tiles), light/dark mode, and a no-code interface for basic workflows. The whole stack deploys via Docker Compose with official images (`dausume/polari:python`, `dausume/polari:angular`).

The design is deliberately modular — domain-specific modules (geocoding, geospatial, materials science) plug into the same backbone. The democracy platform is one such module.

### Democracy Platform / Policy Scorecard

Built on the Polari backbone, the Democracy Platform is a direct scoring and analysis system for policies and the actors involved in them. The intent:

- Citizens can **directly rate policies** across configurable dimensions
- The same scoring applies to **politicians and special interest groups** based on their involvement in policy development
- The system is designed as an alternative route to **participatory policy design** — not just voting on existing proposals, but enabling communities to draft and evaluate policies themselves

The scoring methodology and database design are described in a pitch deck (available on request); the frontend prototype (`American-Scorecard-Frontend`) demonstrates the interface approach.

## Current status

Actively developed — Dustin commits regularly, with work through May 2026 on:

- Mapping and graphing capabilities
- No-code/flow-design UI (backend substantially complete)
- Docker deployment improvements (`polari-node`, `polari-suite`)
- Angular version updates and dependency maintenance

The platform is at an early version (0.0.1) and primarily seeking contributors and early adopters willing to help mature the no-code interface and policy scoring modules.

## Get involved

- **Backend:** [github.com/dausume/Polari-Framework](https://github.com/dausume/Polari-Framework) (Python, GPL-3.0)
- **Frontend:** [github.com/dausume/polari-platform-angular](https://github.com/dausume/polari-platform-angular) (TypeScript/Angular)
- **Deployment:** [github.com/dausume/polari-node](https://github.com/dausume/polari-node) (Docker Compose)
- Raise it in the [DOD community channels](../community/community.md)

See also the [original introduction post from September 2023](../blog/posts/2023-09-10.md).
