# Party logos

Each logo file is the property of its respective party or rightsholder. Used here for identification and informational purposes under fair dealing / fair use provisions.

## Australian parties

| Party | Logo | License | Source |
|---|---|---|---|
| Australian Labor Party | `au/labor.svg` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Logo_of_Australian_Labor_Party.svg) |
| Liberal Party / Coalition | `au/liberal.png` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Liberal_Party_of_Australia_Logo_2015.png) |
| Australian Greens | `au/greens.svg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:AustralianGreensLogo_official.svg) |
| Victorian Socialists | `au/victorian-socialists.webp` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Victorian_Socialists_logo,_2025.webp) |
| One Nation | `au/one-nation.png` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:One_Nation_logo.png) |
| Jacqui Lambie Network | `au/jacqui-lambie-network.png` | Fair use | [Wikipedia](https://en.wikipedia.org/wiki/File:Jacqui_Lambie_Network_federal_logo.png) · [Party page](https://en.wikipedia.org/wiki/Jacqui_Lambie_Network) |
| Katter's Australian Party | `au/katter.png` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:KAP2016logo.png) |
| Libertarian Party | `au/libertarian.svg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Logo_of_the_Libertarian_Party_(Australia).svg) |
| Pirate Party Australia | `au/pirate-party.svg` | CC BY-SA 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Pirate_Party_Australia_logo.svg) |
| Fusion Party | `au/fusion.png` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Fusion-logo-full-colour.png) |
| Australian Democrats | `au/australian-democrats.png` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Australian_Democrats_2020_Logo.png) |
| Flux Party | `au/flux.svg` | Site asset | Hosted on [DOD](https://www.designingopendemocracy.com/organisations/flux-party/) |
| MiVote | `au/mivote.png` | MiVote branding | Extracted from MiVote's "Values & Vision" PDF via [Wayback Machine](https://www.designingopendemocracy.com/organisations/mivote/) |
| Democratic Labor Party (1955–1978) | `au/dlp.jpg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:DLP_Historic_Logo.jpg) |
| United Australia Party (1931–1945) | `au/uap-historical.svg` | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Logo_of_the_United_Australia_Party.svg) |
| Australia Party (1969–1986) | `au/australia-party.jpg` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Australia_Party_logo_1972.jpg) · [Party page](https://en.wikipedia.org/wiki/Australia_Party) |

## International comparators

These logos are fetched remotely at build time (their `path` in the JSON points to Commons URLs rather than local files).

| Party | Logo | License | Source |
|---|---|---|---|
| Your Party (UK) | `your-party` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Your_Party_logo.svg) · [Party page](https://en.wikipedia.org/wiki/Your_Party_(UK)) |
| Podemos (Spain) | `podemos` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Podemos_logo_c%C3%ADrculos.svg) · [Party page](https://en.wikipedia.org/wiki/Podemos) |
| Five Star Movement (Italy) | `five-star-movement` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:M5S_logo_2050.svg) · [Party page](https://en.wikipedia.org/wiki/Five_Star_Movement) |
| Pirate Party Germany | `pirate-party-germany` | CC BY 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Piratenpartei_deutschland_logo.svg) · [Party page](https://en.wikipedia.org/wiki/Pirate_Party_Germany) |
| Party for Freedom (Netherlands) | `pvv` | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:PVV-logo.svg) · [Party page](https://en.wikipedia.org/wiki/Party_for_Freedom) |

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
