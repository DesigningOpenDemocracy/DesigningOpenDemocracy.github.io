#!/bin/bash
# Prepare a fresh cloud container: install the pre-commit hook and util/ deps.
# No-ops outside remote sessions so local checkouts are left alone.
set -euo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}"
ln -sf ../../.githooks/pre-commit .git/hooks/pre-commit
python -m pip install -q -r util/requirements.txt
