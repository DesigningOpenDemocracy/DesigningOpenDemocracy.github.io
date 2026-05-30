#!/usr/bin/env python3
"""
pre_commit_check.py — Run all wiki quality checks in one pass

Runs the three checker scripts in sequence, prints combined output, and
exits non-zero if any hard check fails. Suitable as a git pre-commit hook
or a manual pre-PR sanity pass.

Hard failures (exit 1):
  check_links   — broken internal .md links
  check_concepts — invalid concept slugs on org pages

Informational only (always shown, never blocks):
  lint_orgs     — structural issues; 4 known Wayback exceptions always appear

Usage:
    python util/pre_commit_check.py
    python util/pre_commit_check.py --fix-hints

Install as git hook:
    echo 'python util/pre_commit_check.py' > .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import os
import subprocess
import sys

UTIL_DIR = os.path.dirname(os.path.abspath(__file__))


def run(script, *extra_args):
    cmd = [sys.executable, os.path.join(UTIL_DIR, script)] + list(extra_args)
    result = subprocess.run(cmd)
    return result.returncode


def section(title):
    print(f"\n── {title} " + "─" * max(0, 50 - len(title)))


def main():
    parser = argparse.ArgumentParser(description="Run all wiki quality checks")
    parser.add_argument("--fix-hints", action="store_true",
                        help="Pass --fix-hints through to lint_orgs")
    args = parser.parse_args()

    W = 56
    print(f"\n{'═' * W}")
    print(f"  Pre-commit check  —  {__import__('datetime').date.today()}")
    print(f"{'═' * W}")

    failures = []

    section("1/3  lint_orgs  (informational)")
    print("     4 known Wayback exceptions will always appear here.\n")
    lint_args = ["--fix-hints"] if args.fix_hints else []
    run("lint_orgs.py", *lint_args)

    section("2/3  check_concepts --all  (hard)")
    rc = run("check_concepts.py", "--all")
    if rc != 0:
        failures.append("check_concepts: invalid concept slugs found")

    section("3/3  check_links --all  (hard)")
    rc = run("check_links.py", "--all")
    if rc != 0:
        failures.append("check_links: broken internal links found")

    print(f"\n{'═' * W}")
    if failures:
        print("  FAILED:")
        for f in failures:
            print(f"    ✗  {f}")
    else:
        print("  All hard checks passed.")
    print(f"{'═' * W}\n")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
