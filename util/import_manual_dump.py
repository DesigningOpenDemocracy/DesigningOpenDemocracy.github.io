#!/usr/bin/env python3
"""
import_manual_dump.py — turn a human-saved browser snapshot into a
manual_verified cache entry, for citation URLs no automated fetch can
reach (bot-blocked, rate-limited, robots.txt-disallowed) but a human's own
browser still can. See util/manual_dump.py's docstring for the full
workflow and why this exists as a local, gitignored escape hatch rather
than something CI or the weekly cron ever runs.

For each manual-dump/snapshots/* file (url-map.txt itself excluded):
  1. Recover the source URL, in order of preference: an explicit
     manual-dump/snapshots/url-map.txt line ('<filename> <url>' — the
     authoritative mapping, since browsers have become unreliable about
     stamping the old 'saved from url=' comment); the stamp itself when
      present; else the page's <link rel="canonical"> / og:url declaration.
      Downloaded binary documents (.pdf/.docx/.odt/... — citation URLs whose
      last path segment is literally a filename) carry none of those, so
      they require a url-map.txt line. A print-to-PDF of a JS-rendered page
      works here too: it sniffs as the %PDF- case and its rendered text is
      exactly what a human saw, which plain "Save Page As" often fails to
      capture on SPA sites.
  2. Extract plain text — html_to_text() for HTML saves (the exact same
      extraction a live fetch uses), zip-XML extraction for office
      documents, pdfminer extraction for PDFs — all shared with
      check_fragments.py's _fetch_page_text so a snapshot and a live fetch
      verify identically.
  3. Check every piece of evidence (event/footnote/shared-link quotes)
     that cites this URL against the extracted text, and record each
     result in the shared evidence cache as manual_verified[hash] = bool,
     plus one {filename: url, source, checked, good, mismatch} entry in
     manual-dump/import.json — the greppable index of what's in imported/
     backing which URL.
 4. Remove the URL from manual-dump/requests.txt and move the file into
    manual-dump/imported/ (a sibling of snapshots/, so the inbox only ever
    holds unprocessed saves), along with its companion <name>_files/
    asset folder if the page was saved as "complete"; a re-run won't
    reprocess it.

A snapshot whose URL can't be recovered at all is skipped with a
ready-to-paste url-map.txt line printed, so resolving it is one copy-paste,
not archaeology. A snapshot whose recovered URL doesn't match any known
citation is left in place (not moved) and reported, since that's more
likely a mistake (wrong page saved, or the citation was since removed) than
something to silently discard.

manual_verified is deliberately a separate field from the automated
verified map, not merged into it — stale automated data captured before a
site started blocking scripts must never be silently presented as if it
were reconfirmed just because a human happened to import an unrelated
snapshot later. Only entries this script itself writes go in
manual_verified.

A snapshot whose URL doesn't match any known citation is left in place
(not moved) and reported, since that's more likely a mistake (wrong page
saved, or the citation was since removed) than something to silently
discard.

Usage:
    python util/import_manual_dump.py             # import every pending snapshot
    python util/import_manual_dump.py --dry-run    # report what would happen, write nothing

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import glob
import json
import os
import shutil
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(__file__))
import manual_dump  # noqa: E402
import pagecache  # noqa: E402
from check_fragments import (  # noqa: E402
    EVIDENCE_PATH, _extract_pdf_text, _extract_zip_xml_text, collect_evidence,
    context_for_quote, load_evidence, save_evidence, sha256,
)
from text_fragment import html_to_text, normalize_ws, quote_matches  # noqa: E402


def import_snapshot(path, cache, evidence_by_url, url_map, imp_map, dry_run=False):
    """Import one saved page or downloaded document. Returns True if it was
    matched to at least one citation (and, unless dry_run, imported), False
    otherwise."""
    basename = os.path.basename(path)
    # Binary documents (a downloaded .docx/.odt/... or .pdf — the citation
    # URL's last path segment is often literally the filename) are sniffed by
    # bytes, not extension, mirroring _fetch_page_text. They carry no
    # browser stamp and no meta tags, so url-map.txt is their only URL
    # recovery path.
    with open(path, "rb") as f:
        raw_bytes = f.read()
    text = None
    if raw_bytes[:2] == b"PK":
        text = _extract_zip_xml_text(raw_bytes)
        if text is None:
            print("  SKIPPED  " + basename + "  (zip archive but no known "
                  "document format inside — not .docx/.odt?)")
            return False
        url = url_map.get(basename)
        source = "url-map" if url else None
        if not url:
            print("  SKIPPED  " + basename + "  (downloaded file — source URL unknown)")
            print("            add a line to " + manual_dump.URL_MAP_PATH + ":")
            print("              " + basename + " <paste-the-file's-url-here>")
            return False
    elif raw_bytes[:5] == b"%PDF-":
        text = _extract_pdf_text(raw_bytes)
        if text is None:
            print("  SKIPPED  " + basename + "  (PDF, but pdfminer.six isn't "
                  "installed or the file wouldn't parse)")
            return False
        url = url_map.get(basename)
        source = "url-map" if url else None
        if not url:
            print("  SKIPPED  " + basename + "  (downloaded file — source URL unknown)")
            print("            add a line to " + manual_dump.URL_MAP_PATH + ":")
            print("              " + basename + " <paste-the-file's-url-here>")
            return False
    else:
        raw_html = raw_bytes.decode("utf-8", errors="replace")
        text = html_to_text(raw_html)
        if not text:
            print("  EMPTY  " + basename + " — extracted no text, skipped")
            return False
        # Recovery order: explicit human mapping > browser stamp > page's own
        # canonical/og:url declaration. url-map.txt wins because it's deliberate
        # human intent and fixes both unstamped saves and sites whose meta tags
        # declare a variant URL.
        url = url_map.get(basename)
        source = "url-map" if url else None
        if not url:
            url = manual_dump.parse_saved_from_url(raw_html)
            source = "stamp" if url else None
        if not url:
            url = manual_dump.parse_meta_url(raw_html)
            source = "meta tag" if url else None
        if not url:
            print("  SKIPPED  " + basename + "  (source URL unknown)")
            print("            add a line to " + manual_dump.URL_MAP_PATH + ":")
            print("              " + basename + " <paste-the-page's-url-here>")
            return False

    # Meta-tag recovery often differs from the citation by exactly one
    # trailing slash (e.g. a site declaring ".../reports/" for a citation
    # stored as ".../reports") — the URL-level analogue of the whitespace
    # normalisation quotes already get, so accept that single equivalence
    # and say so, rather than reporting a false NO MATCH. Anything beyond
    # one slash stays unmatched: no fuzzy matching.
    items = evidence_by_url.get(url)
    if not items and url.endswith("/"):
        items = evidence_by_url.get(url[:-1])
        if items:
            source += ", trailing slash normalised"
            url = url[:-1]
    elif not items and url + "/" in evidence_by_url:
        items = evidence_by_url[url + "/"]
        source += ", trailing slash normalised"
        url = url + "/"
    if not items:
        print("  NO MATCH  " + basename + "  (recovered from " + source + ")")
        print("            url: " + url)
        print("            (no citation in the wiki currently points at this URL)")
        return False

    entry = cache.get(url, {})
    manual_verified = dict(entry.get("manual_verified", {}))
    contexts = dict(entry.get("contexts", {}))
    good = bad = 0
    for evidence, source_label, kind in items:
        ev_key = sha256(normalize_ws(evidence))
        result = quote_matches(text, evidence)
        manual_verified[ev_key] = result
        if result:
            good += 1
            ctx = context_for_quote(text, evidence)
            if ctx:
                contexts[ev_key] = ctx
        else:
            bad += 1
        print(("  MANUAL GOOD  " if result else "  MANUAL MISMATCH  ") + source_label)

    print("  IMPORTED  " + basename + "  (" + url + ", via " + source + ") — " +
          str(good) + " good, " + str(bad) + " mismatch")

    if dry_run:
        return True

    cache[url] = {**entry, "manual_verified": manual_verified,
                  "manual_checked": date.today().isoformat(), "contexts": contexts}
    manual_dump.dequeue_request(url)
    # The human-obtained copy is also the best text this URL has ever yielded
    # to us (bot-blocked and SPA sites give script fetches shells — confirmed
    # on governancehubafrica.org/about, 21 chars vs ~7,900 rendered), so seed
    # .pagecache/ with it: later --offline quote adjustments then work for
    # manually-resolved citations too. Verdicts still flow only through
    # manual_verified above; the stored copy never feeds back into automated
    # checks.
    pagecache.store(url, text)

    os.makedirs(manual_dump.IMPORTED_DIR, exist_ok=True)
    dest = os.path.join(manual_dump.IMPORTED_DIR, basename)
    if os.path.exists(dest):
        stem, ext = os.path.splitext(dest)
        dest = stem + "-" + date.today().isoformat() + ext
    shutil.move(path, dest)
    # A "Save Page As → complete" save comes as <name>.html plus a
    # companion <name>_files/ asset folder. Nothing here reads those
    # assets (extraction is text-only), but leaving them behind clutters
    # the inbox with orphaned folders — so they follow their page into
    # imported/, keeping the pair together and the inbox clean.
    stem, ext = os.path.splitext(path)
    files_dir = stem + "_files"
    if os.path.isdir(files_dir):
        shutil.move(files_dir, os.path.join(manual_dump.IMPORTED_DIR,
                                            os.path.basename(files_dir)))
    imp_map[os.path.basename(dest)] = {
        "url": url, "source": source, "checked": date.today().isoformat(),
        "good": good, "mismatch": bad}
    return True


def load_import_map():
    """Read manual-dump/import.json ({} when absent/corrupt — the map is a
    convenience index, so losing it must never fail an import)."""
    try:
        with open(manual_dump.IMPORT_MAP_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_import_map(imp_map):
    try:
        os.makedirs(os.path.dirname(manual_dump.IMPORT_MAP_PATH), exist_ok=True)
        with open(manual_dump.IMPORT_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(imp_map, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
    except OSError as e:
        print("Could not write " + manual_dump.IMPORT_MAP_PATH + " (" + str(e) + ")")


def rebuild_import_map(cache, url_map):
    """Reconstruct the import manifest from what's actually sitting in
    imported/ — for backfilling entries created before the manifest existed,
    or regenerating it after loss. Each file's URL is re-recovered the same
    way the import did it (url-map > stamp > meta tags; downloaded zips only
    have url-map), and verdict counts come from that URL's entry in the
    shared evidence cache. Files whose URL can't be recovered are still
    listed, honestly with url: null. The result mirrors imported/ exactly:
    entries for files no longer present are dropped."""
    entries = {}
    if not os.path.isdir(manual_dump.IMPORTED_DIR):
        return entries
    for name in sorted(os.listdir(manual_dump.IMPORTED_DIR)):
        path = os.path.join(manual_dump.IMPORTED_DIR, name)
        # Companion <name>_files/ asset folders belong to their page's
        # entry and get no line of their own.
        if not os.path.isfile(path) or name.endswith("_files"):
            continue
        with open(path, "rb") as f:
            raw = f.read()
        url = source = None
        if raw[:2] == b"PK":
            url = url_map.get(name)
            source = "url-map" if url else None
        else:
            html = raw.decode("utf-8", errors="replace")
            url = url_map.get(name)
            source = "url-map" if url else None
            if not url:
                url = manual_dump.parse_saved_from_url(html)
                source = "stamp" if url else None
            if not url:
                url = manual_dump.parse_meta_url(html)
                source = "meta tag" if url else None
        mv = cache.get(url, {}).get("manual_verified", {}) if url else {}
        entries[name] = {
            "url": url,
            "source": source or "unknown",
            "checked": cache.get(url, {}).get("manual_checked") if url else None,
            "good": sum(1 for v in mv.values() if v),
            "mismatch": sum(1 for v in mv.values() if not v),
        }
    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Import human-saved browser snapshots from manual-dump/snapshots/ "
                    "into the evidence cache as manual_verified entries.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be imported without writing the cache "
                            "or moving/removing any files.")
    parser.add_argument("--rebuild-map", action="store_true",
                        help="Don't import anything; reconstruct manual-dump/import.json "
                            "from the files already in imported/ (for backfilling entries "
                            "created before the manifest existed, or regenerating a lost one).")
    args = parser.parse_args()

    if args.rebuild_map:
        entries = rebuild_import_map(load_evidence(), manual_dump.load_url_map())
        save_import_map(entries)
        known = sum(1 for e in entries.values() if e["url"])
        print("Manifest rebuilt from imported/: " +
              str(len(entries)) + " files, " + str(known) + " with a recovered URL")
        print("Import map: " + manual_dump.IMPORT_MAP_PATH)
        return

    snapshots = sorted(
        f for f in glob.glob(os.path.join(manual_dump.SNAPSHOTS_DIR, "*"))
        if os.path.isfile(f) and os.path.basename(f) != "url-map.txt")
    if not snapshots:
        # First run on this machine: create the drop location so the human
        # doesn't have to guess/mkdir it, then explain what goes where.
        try:
            os.makedirs(manual_dump.SNAPSHOTS_DIR, exist_ok=True)
            print("Created " + manual_dump.SNAPSHOTS_DIR)
        except OSError as e:
            print("Could not create " + manual_dump.SNAPSHOTS_DIR + " (" + str(e) + ")")
        print()
        print("No saved pages waiting. Workflow:")
        print("  1. `just dump-requests` — see which citation URLs need a human browser")
        print("  2. open each URL, let it fully load, then File → Save Page As →")
        print('     "Web Page, HTML only" into ' + manual_dump.SNAPSHOTS_DIR)
        print("     (a \"complete\" save also works — its _files folder just tags along)")
        print("  3. re-run this script (--dry-run first to preview matches)")
        print("  4. if a snapshot reports 'source URL unknown', add its line to")
        print("     " + manual_dump.URL_MAP_PATH + " and re-run")
        return

    fake_args = SimpleNamespace(slug=None, events_only=False)
    evidence_by_url = {}
    for url, evidence, source_label, kind, _path in collect_evidence(fake_args):
        evidence_by_url.setdefault(url, []).append((evidence, source_label, kind))

    cache = load_evidence()
    url_map = manual_dump.load_url_map()
    imp_map = load_import_map()
    imported = 0
    for path in snapshots:
        if import_snapshot(path, cache, evidence_by_url, url_map, imp_map,
                           dry_run=args.dry_run):
            imported += 1

    if not args.dry_run:
        save_evidence(cache)
        save_import_map(imp_map)

    print()
    print(str(imported) + " of " + str(len(snapshots)) + " snapshot(s) imported" +
          (" (dry run — nothing written)" if args.dry_run else ""))
    print("Evidence file: " + EVIDENCE_PATH)
    if not args.dry_run:
        print("Import map: " + manual_dump.IMPORT_MAP_PATH)


if __name__ == "__main__":
    main()
