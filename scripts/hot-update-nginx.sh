#!/usr/bin/env bash
# Update only managed Nginx resource limits/logging; no installation or database import.
set -Eeuo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$EUID" -ne 0 ]]; then
    echo "Run with sudo: sudo bash scripts/hot-update-nginx.sh" >&2
    exit 1
fi
if [[ ! -f /etc/3xi/installed.json ]]; then
    echo "An existing 3xi installation is required; no installation was started." >&2
    exit 1
fi
cd "$project_dir"
exec python3 -m threexi tune --nginx-only --profile high --nginx-logs off "$@"
