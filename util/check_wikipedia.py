"""
check_wikipedia.py — verify Wikipedia page existence via the REST API

Uses the Wikipedia REST summary endpoint (no scraping, no auth needed):
  https://en.wikipedia.org/api/rest_v1/page/summary/{title}

Returns 200 + first sentence if the page exists, 404 if not,
and follows redirects to the canonical title automatically.

Usage:
  python util/check_wikipedia.py
"""

import time
import urllib.parse
import urllib.request
import json

CANDIDATES = [
    # Confirmed in previous session — verifying anyway
    ("Audrey Tang",          "Audrey_Tang"),
    ("Jaclyn Tsai",          "Jaclyn_Tsai"),
    ("David Van Reybrouck",  "David_Van_Reybrouck"),
    ("Alexei Navalny",       "Alexei_Navalny"),
    ("Yulia Navalnaya",      "Yulia_Navalnaya"),
    ("George Soros",         "George_Soros"),
    ("Oleg Orlov",           "Oleg_Orlov"),
    ("Natalia Estemirova",   "Natalia_Estemirova"),
    # Uncertain — need checking
    ("Brett Hennig",         "Brett_Hennig"),
    ("Claudia Chwalisz",     "Claudia_Chwalisz"),
    ("Tom Steinberg",        "Tom_Steinberg"),
    ("Richard D. Bartlett",  "Richard_D._Bartlett"),
    ("Ben Knight",           "Ben_Knight_(Loomio)"),
    ("Luca Belgiorno-Nettis","Luca_Belgiorno-Nettis"),
    ("Nicholas Gruen",       "Nicholas_Gruen"),
    # Australian democracy practitioners
    ("Kimbra White",         "Kimbra_White"),
    ("Nicole Hunter",        "Nicole_Hunter_(facilitator)"),
    ("Keith Greaves",        "Keith_Greaves"),
    ("Emily Jenke",          "Emily_Jenke"),
    ("Emma Fletcher",        "Emma_Fletcher_(DemocracyCo)"),
    ("Neha Madhok",          "Neha_Madhok"),
    ("Noura Mansour",        "Noura_Mansour"),
    ("Sonia Randhawa",       "Sonia_Randhawa"),
    ("Willow Berzin",        "Willow_Berzin"),
]

API_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary/"
HEADERS = {"User-Agent": "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"}


def check(title):
    url = API_BASE + urllib.parse.quote(title, safe="")
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            canonical = data.get("title", title)
            extract = data.get("extract", "")
            first = extract.split(". ")[0].strip() if extract else ""
            return "EXISTS", canonical, first[:120]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "MISSING", "", ""
        return f"HTTP {e.code}", "", ""
    except Exception as e:
        return f"ERROR: {e}", "", ""


def main():
    print(f"{'Name':<25} {'Result':<8} {'Canonical title / note'}")
    print("-" * 90)
    for name, title in CANDIDATES:
        status, canonical, first = check(title)
        if status == "EXISTS":
            note = canonical if canonical != title.replace("_", " ") else ""
            print(f"{name:<25} {'✓':<8} {note or '—'}")
            if first:
                print(f"  {first}...")
        else:
            print(f"{name:<25} {status:<8}")
        time.sleep(0.3)  # be polite to the API


if __name__ == "__main__":
    main()
