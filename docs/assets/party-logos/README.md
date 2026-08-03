# Party logos

Each logo file is the property of its respective party or rightsholder. Used here for identification and informational purposes under fair dealing / fair use provisions.

The `license` field in `docs/data/party-governance.json` records the specific license for each logo. Confirmed licenses:

| Logo | License | Source |
|---|---|---|
| `au/australia-party.jpg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Australia_Party_logo_1972.jpg) |
| `au/australian-democrats.png` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Australian_Democrats_2020_Logo.png) |
| `au/dlp.jpg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:DLP_Historic_Logo.jpg) |
| `au/flux.svg` | Site asset | [DOD](https://www.designingopendemocracy.com/organisations/flux-party/) |
| `au/fusion.png` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Fusion-logo-full-colour.png) |
| `au/greens.svg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:AustralianGreensLogo_official.svg) |
| `au/jacqui-lambie-network.png` | Fair use | [Wikipedia](https://en.wikipedia.org/wiki/File:Jacqui_Lambie_Network_federal_logo.png) |
| `au/katter.png` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:KAP2016logo.png) |
| `au/labor.svg` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Logo_of_Australian_Labor_Party.svg) |
| `au/liberal.png` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Liberal_Party_of_Australia_Logo_2015.png) |
| `au/libertarian.svg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Logo_of_the_Libertarian_Party_(Australia).svg) |
| `au/mivote.png` | MiVote branding | [Wayback Machine PDF](https://www.designingopendemocracy.com/organisations/mivote/) |
| `au/one-nation.png` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:One_Nation_logo.png) |
| `au/pirate-party.svg` | CC BY-SA 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Pirate_Party_Australia_logo.svg) |
| `au/uap-historical.svg` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Logo_of_the_United_Australia_Party.svg) |
| `au/victorian-socialists.webp` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Victorian_Socialists_logo,_2025.webp) |

International comparators (all in JSON, none stored locally — fetched from Commons at build time via the `logo.path` field):

| Logo | License | Source |
|---|---|---|
| `your-party` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Your_Party_logo.svg) |
| `podemos` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Podemos_logo_circulos.svg) |  
| `five-star-movement` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:M5S_logo_2050.svg) |
| `pirate-party-germany` | CC BY 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Piratenpartei_deutschland_logo.svg) |
| `pvv` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:PVV-logo.svg) |

## Adding a logo

1. Download the highest-quality version available (prefer SVG, then PNG)
2. Place it in the appropriate subdirectory (`au/` for Australian parties, etc.)
3. Add `logo` to the party's entry in `docs/data/party-governance.json`:
   ```json
   "logo": {
     "path": "/assets/party-logos/au/party-slug.ext",
     "license": "CC BY-SA 4.0",
     "source": "https://commons.wikimedia.org/wiki/File:..."
   }
   ```
4. For non-free/fair use logos, prefer Wikipedia's version and link to the file description page
5. Update the table above
