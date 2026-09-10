#!/usr/bin/env bash
#
# Compile the Smalnets Router Config Tool into a standalone Linux binary.
#
# Usage:
#   ./build_linux.sh [OPTIONS]
#
# Options:
#   --env prod|dev      Backend variant (default: prod)
#                         prod -> https://smalnets.com
#                         dev  -> https://smalnets.ddns.net
#   --upload            Upload the built binary to the matching server's
#                       release folders (releases/<tag>/ and releases/latest/).
#                       Reads SSH credentials from './deploy_config'
#                       (see deploy_config.sample).
#   --version X.Y.Z     Override the version instead of auto-incrementing it.
#   --no-tag            Do not create/push a vX.Y.Z git tag.
#   -h, --help          Show this help.
#
# Version handling:
#   * With no --version flag the script reads the most recent vX.Y.Z git tag
#     and auto-increments the patch number (0.0.6 -> 0.0.7).
#   * The version is written to config_program/version.txt and embedded into
#     the binary file name (smalnets_<version>[-dev]_<arch>.bin).
#   * Unless --no-tag is given, the script creates a vX.Y.Z tag from the
#     current HEAD and pushes it (mirrors the GitHub Actions flow, which
#     builds + deploys on tag push).
#
# System prerequisites (Ubuntu/Debian):
#   sudo apt-get install -y build-essential libgl1-mesa-dev
#
# Deploy credentials:
#   cp deploy_config.sample deploy_config   # then edit usernames/IPs
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DEPLOY_CONFIG="${DEPLOY_CONFIG:-$ROOT/deploy_config}"

usage() {
    cat <<'EOF'
Usage: ./build_linux.sh [OPTIONS]

Options:
  --env prod|dev      Backend variant (default: prod)
                        prod -> https://smalnets.com
                        dev  -> https://smalnets.ddns.net
  --upload            Upload the built binary to the matching server's
                      release folders (releases/<tag>/ and releases/latest/).
                      Reads SSH credentials from './deploy_config'
                      (see deploy_config.sample).
  --version X.Y.Z     Override the version instead of auto-incrementing it.
  --no-tag            Do not create/push a vX.Y.Z git tag.
  -h, --help          Show this help.

Version handling:
  * With no --version flag the script reads the most recent vX.Y.Z git tag
    and auto-increments the patch number (0.0.6 -> 0.0.7).
  * The version is written to config_program/version.txt and embedded into
    the binary file name (smalnets_<version>[-dev]_<arch>.bin).
  * Unless --no-tag is given, the script creates a vX.Y.Z tag from the
    current HEAD and pushes it (mirrors the GitHub Actions flow, which
    builds + deploys on tag push).
EOF
    exit 0
}

VARIANT="prod"
UPLOAD=0
DO_TAG=1
VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)  VARIANT="${2:-}"; shift 2 ;;
        --upload) UPLOAD=1; shift ;;
        --version) VERSION="${2:-}"; shift 2 ;;
        --no-tag) DO_TAG=0; shift ;;
        -h|--help) usage ;;
        *) echo "ERROR: unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

case "$VARIANT" in
    prod) API_URL="https://smalnets.com";      LABEL="" ;;
    dev)  API_URL="https://smalnets.ddns.net"; LABEL="-dev" ;;
    *) echo "ERROR: VARIANT must be 'dev' or 'prod' (got '$VARIANT')" >&2; exit 1 ;;
esac

# ---------------------------------------------------------------- version
if [[ -z "$VERSION" ]]; then
    LAST_TAG="$(git tag --sort=-v:refname | head -n1 | sed 's/^v//' || true)"
    if [[ -z "$LAST_TAG" || ! "$LAST_TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        LAST_TAG="0.0.0"
    fi
    IFS='.' read -r MAJOR MINOR PATCH <<< "$LAST_TAG"
    VERSION="${MAJOR}.${MINOR}.$((PATCH + 1))"
fi
VERSION="${VERSION#v}"
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: invalid version '$VERSION' (expected X.Y.Z)" >&2
    exit 1
fi
TAG="v${VERSION}"

echo -n "$VERSION" > config_program/version.txt
cat > config_program/build_config.py <<EOF
BASE_URL = '$API_URL'
VARIANT = '$VARIANT'
EOF

echo "==> Building $VARIANT variant v$VERSION (API: $API_URL)"

# ------------------------------------------------------------------ build
if ! command -v gcc >/dev/null 2>&1; then
    echo "ERROR: no C compiler found. Install it with:"
    echo "  sudo apt-get install -y build-essential libgl1-mesa-dev"
    exit 1
fi

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
OUT="dist/smalnets_${VERSION}${LABEL}_${ARCH}.bin"
cp build/main.bin "$OUT"
echo "==> Done: $OUT"

# -------------------------------------------------------------------- tag
if [[ "$DO_TAG" == "1" ]]; then
    if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
        echo "==> Tag $TAG already exists (not re-tagging)"
    else
        git tag "$TAG"
        git push origin "$TAG"
        echo "==> Created and pushed tag $TAG"
    fi
fi

# ------------------------------------------------------------------ upload
if [[ "$UPLOAD" == "1" ]]; then
    if ! command -v ssh >/dev/null 2>&1 || ! command -v scp >/dev/null 2>&1; then
        echo "ERROR: ssh/scp not found; cannot use --upload" >&2
        exit 1
    fi
    if [[ ! -f "$DEPLOY_CONFIG" ]]; then
        echo "ERROR: $DEPLOY_CONFIG not found." >&2
        echo "Copy deploy_config.sample to deploy_config and set your SSH credentials." >&2
        exit 1
    fi
    source "$DEPLOY_CONFIG"
    case "$VARIANT" in
        prod) SSH_USER="${PROD_USER:-}"; SSH_HOST="${PROD_HOST:-}" ;;
        dev)  SSH_USER="${DEV_USER:-}";  SSH_HOST="${DEV_HOST:-}" ;;
    esac
    if [[ -z "$SSH_USER" || -z "$SSH_HOST" ]]; then
        echo "ERROR: missing ${VARIANT^^}_USER / ${VARIANT^^}_HOST in $DEPLOY_CONFIG" >&2
        exit 1
    fi
    BASE="${UPLOAD_BASE:-/var/www/smalnets/storage/app/public/releases}"
    echo "==> Uploading $OUT to ${SSH_USER}@${SSH_HOST}"
    ssh -o StrictHostKeyChecking=no "${SSH_USER}@${SSH_HOST}" \
        "mkdir -p $BASE/$TAG $BASE/latest"
    scp -o StrictHostKeyChecking=no "$OUT" "${SSH_USER}@${SSH_HOST}:$BASE/$TAG/"
    scp -o StrictHostKeyChecking=no "$OUT" "${SSH_USER}@${SSH_HOST}:$BASE/latest/"
    echo "==> Upload complete (releases/$TAG/ and releases/latest/)"
    echo "    URL: https://$SSH_HOST/releases/$TAG/${OUT#dist/}"
fi