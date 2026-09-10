#!/usr/bin/env bash
#
# Compile the Smalnets Router Config Tool into a standalone Linux binary.
# Builds the prod and/or dev variant in a single run.
#
# Usage:
#   ./build_linux.sh [OPTIONS]
#
# Options:
#   --env prod|dev|both Backend variant(s) to build (default: prod)
#                         prod -> https://smalnets.com
#                         dev  -> https://smalnets.ddns.net
#                         both -> prod + dev binaries
#   --upload            Upload the built binary(ies) to the matching server's
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
  --env prod|dev|both Backend variant(s) to build (default: prod)
                        prod -> https://smalnets.com
                        dev  -> https://smalnets.ddns.net
                        both -> prod + dev binaries
  --upload            Upload the built binary(ies) to the matching server's
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
    prod|dev) TARGETS=("$VARIANT") ;;
    both)     TARGETS=(prod dev) ;;
    *) echo "ERROR: VARIANT must be 'dev', 'prod' or 'both' (got '$VARIANT')" >&2; exit 1 ;;
esac

variant_url() {
    if [[ "$1" == "prod" ]]; then
        echo "https://smalnets.com"
    else
        echo "https://smalnets.ddns.net"
    fi
}
variant_label() {
    if [[ "$1" == "dev" ]]; then
        echo "-dev"
    fi
}
variant_outdir() {
    if [[ "$1" == "dev" ]]; then
        echo "build/dev"
    else
        echo "build"
    fi
}

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
echo "==> Building v$VERSION for: ${TARGETS[*]}"

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

ARCH="$(uname -m)"
mkdir -p dist

for T in "${TARGETS[@]}"; do
    API_URL="$(variant_url "$T")"
    LABEL="$(variant_label "$T")"
    OUT_DIR="$(variant_outdir "$T")"
    cat > config_program/build_config.py <<EOF
BASE_URL = '$API_URL'
VARIANT = '$T'
EOF
    echo "==> Building $T variant v$VERSION (API: $API_URL)"
    rm -rf \
        "$OUT_DIR/main.bin" \
        "$OUT_DIR/main.build" \
        "$OUT_DIR/main.dist" \
        "$OUT_DIR/main.onefile-build"
    python -m nuitka --standalone \
        --onefile \
        --assume-yes-for-downloads \
        --plugin-enable=pyside6 \
        --output-dir="$OUT_DIR" \
        --include-data-files=assets/images/logo.png=assets/images/logo.png \
        --include-data-files=config_program/version.txt=version.txt \
        --include-module=build_config \
        --follow-import-to=api \
        --follow-import-to=controllers \
        --follow-import-to=routeros \
        --follow-import-to=views \
        config_program/main.py
    OUT="dist/smalnets_${VERSION}${LABEL}_${ARCH}.bin"
    cp "$OUT_DIR/main.bin" "$OUT"
    echo "==> Done: $OUT"
done

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
    BASE="${UPLOAD_BASE:-/var/www/smalnets/storage/app/public/releases}"
    for T in "${TARGETS[@]}"; do
        if [[ "$T" == "prod" ]]; then
            SSH_USER="${PROD_USER:-}"
            SSH_HOST="${PROD_HOST:-}"
        else
            SSH_USER="${DEV_USER:-}"
            SSH_HOST="${DEV_HOST:-}"
        fi
        if [[ -z "$SSH_USER" || -z "$SSH_HOST" ]]; then
            if [[ "${#TARGETS[@]}" -eq 1 ]]; then
                echo "ERROR: missing ${T^^}_USER / ${T^^}_HOST in $DEPLOY_CONFIG" >&2
                exit 1
            fi
            echo "==> Skipping $T upload (${T^^}_USER / ${T^^}_HOST not set in deploy_config)"
            continue
        fi
        LABEL="$(variant_label "$T")"
        OUT="dist/smalnets_${VERSION}${LABEL}_${ARCH}.bin"
        echo "==> Uploading $OUT to ${SSH_USER}@${SSH_HOST}"
        ssh -o StrictHostKeyChecking=no "${SSH_USER}@${SSH_HOST}" \
            "mkdir -p $BASE/$TAG $BASE/latest"
        scp -o StrictHostKeyChecking=no "$OUT" "${SSH_USER}@${SSH_HOST}:$BASE/$TAG/"
        scp -o StrictHostKeyChecking=no "$OUT" "${SSH_USER}@${SSH_HOST}:$BASE/latest/"
        echo "==> Uploaded $T (releases/$TAG/ and releases/latest/)"
        echo "    URL: https://$SSH_HOST/releases/$TAG/${OUT#dist/}"
    done
fi