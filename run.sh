#!/usr/bin/env bash
# Run the configurator from source against the dev or prod backend.
#   ./run.sh dev               GUI against https://smaldev.smalnets.com
#   ./run.sh prod              GUI against https://smalnets.com
#   ./run.sh dev provision     headless scripts/provision_router.py
#   ./run.sh dev diagnose      scripts/diagnose_hotspot.py
set -euo pipefail
cd "$(dirname "$0")"

env_name="${1:-}"
case "$env_name" in
    dev|prod) shift ;;
    *) echo "Usage: $0 dev|prod [gui|provision|diagnose]" >&2; exit 2 ;;
esac

case "${1:-gui}" in
    gui) target=config_program/main.py ;;
    provision) target=scripts/provision_router.py ;;
    diagnose) target=scripts/diagnose_hotspot.py ;;
    *) echo "Unknown mode '$1'. Use gui, provision or diagnose." >&2; exit 2 ;;
esac

[ -x .venv/bin/python ] || { echo "Missing .venv — see README 'Setup (virtual environment)'." >&2; exit 1; }
export SMALNETS_ENV="$env_name"
echo "Smalnets configurator -> $env_name"
exec .venv/bin/python "$target"
