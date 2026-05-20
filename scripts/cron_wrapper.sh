#!/usr/bin/env bash
# Fallback wrapper for non-systemd installations. systemd is the preferred path
# because it integrates with the journal — this wrapper exists for local dev.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

cd "$REPO_DIR"

# Load env (only used outside systemd; systemd uses EnvironmentFile)
if [[ -f /etc/insurance-intel.env ]]; then
    set -a
    # shellcheck disable=SC1091
    source /etc/insurance-intel.env
    set +a
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

exec insurance-intel run
