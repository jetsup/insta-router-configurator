#!/usr/bin/env bash
#
# Compile the Smalnets Router Config Tool into a standalone Linux binary.
#
# Usage:
#   ./build_linux.sh [VERSION] [dev|prod]
#
#   VERSION    optional, defaults to config_program/version.txt
#   VARIANT    optional, prod (default) or dev. Picks the backend URL:
#                prod -> https://smalnets.com
#                dev  -> https://smalnets.ddns.net
#
# System prerequisites (Ubuntu/Debian):
#   sudo apt-get install -y build-essential libgl1-mesa-dev
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v gcc >/dev/null 2>&1; then
    echo "ERROR: no C compiler found. Install it with:"
    echo "  sudo apt-get install -y build-essential libgl1-mesa-dev"
    exit 1
fi

VERSION="${1:-$(cat config_program/version.txt 2>/dev/null || echo 0.0.0)}"
VARIANT="${2:-prod}"
LABEL=""

case "$VARIANT" in
    prod) API_URL="https://smalnets.com" ;;
    dev)  API_URL="https://smalnets.ddns.net"; LABEL="-dev" ;;
    *) echo "ERROR: VARIANT must be 'dev' or 'prod' (got '$VARIANT')" >&2; exit 1 ;;
esac

VERSION="${VERSION#v}"
echo -n "$VERSION" > config_program/version.txt
cat > config_program/build_config.py <<EOF
BASE_URL = '$API_URL'
VARIANT = '$VARIANT'
EOF

echo "==> Building $VARIANT variant (API: $API_URL)"

echo "==> Creating venv"
python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
pip install zstandard Nuitka PySide6 requests RouterOS-api

echo "==> Compiling Linux binary (v${VERSION})"
python -m nuitka --standalone \
    --onefile \
    --assume-yes-for-downloads \
    --plugin-enable=pyside6 \
    --output-dir=build \
    --include-data-files=assets/images/logo.png=assets/images/logo.png \
    --include-data-files=config_program/version.txt=version.txt \
    --include-module=build_config \
    --follow-import-to=api \
    --follow-import-to=controllers \
    --follow-import-to=routeros \
    --follow-import-to=views \
    config_program/main.py

mkdir -p dist
ARCH="$(uname -m)"
cp build/main.bin "dist/smalnets_${VERSION}${LABEL}_${ARCH}.bin"
echo "==> Done: dist/smalnets_${VERSION}${LABEL}_${ARCH}.bin"
