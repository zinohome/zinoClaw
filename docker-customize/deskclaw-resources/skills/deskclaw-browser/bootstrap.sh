#!/bin/bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="$SKILL_DIR/manifest.json"
RUNTIME_DIR="$SKILL_DIR/runtime"
VERSION_FILE="$RUNTIME_DIR/version.txt"

log() { echo "[agent-browser-bootstrap] $*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# -------------------------------------------------------------------
# 1. Read manifest
# -------------------------------------------------------------------
[ -f "$MANIFEST" ] || die "manifest.json not found at $MANIFEST"

REQUIRED_VERSION=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$MANIFEST" 2>/dev/null) \
  || REQUIRED_VERSION=$(node -e "console.log(require('$MANIFEST').version)" 2>/dev/null) \
  || die "Cannot parse manifest.json (need python3 or node)"

CDN_BASE=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['cdnBase'])" "$MANIFEST" 2>/dev/null) \
  || CDN_BASE=$(node -e "console.log(require('$MANIFEST').cdnBase)" 2>/dev/null) \
  || die "Cannot read cdnBase from manifest.json"

# -------------------------------------------------------------------
# 2. Check if already installed and version matches
# -------------------------------------------------------------------
if [ -f "$VERSION_FILE" ]; then
  INSTALLED_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
  if [ "$INSTALLED_VERSION" = "$REQUIRED_VERSION" ]; then
    log "Runtime v$REQUIRED_VERSION already installed."
    exit 0
  fi
  log "Installed v$INSTALLED_VERSION, need v$REQUIRED_VERSION. Upgrading..."
  rm -rf "$RUNTIME_DIR"
fi

# -------------------------------------------------------------------
# 3. Detect platform
# -------------------------------------------------------------------
OS_RAW=$(uname -s)
ARCH_RAW=$(uname -m)

case "$OS_RAW" in
  Darwin) OS="darwin" ;;
  Linux)  OS="linux"  ;;
  *)      die "Unsupported OS: $OS_RAW (only macOS and Linux are supported)" ;;
esac

case "$ARCH_RAW" in
  arm64|aarch64) ARCH="arm64" ;;
  x86_64|amd64)  ARCH="x64"   ;;
  *)             die "Unsupported architecture: $ARCH_RAW" ;;
esac

PLATFORM="${OS}-${ARCH}"
log "Detected platform: $PLATFORM"

# -------------------------------------------------------------------
# 4. Read archive name and SHA256 from manifest
# -------------------------------------------------------------------
read_manifest_field() {
  python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
p = m['platforms'].get(sys.argv[2])
if not p: sys.exit(1)
print(p[sys.argv[3]])
" "$MANIFEST" "$PLATFORM" "$1" 2>/dev/null
}

ARCHIVE_NAME=$(read_manifest_field "archive") || die "Platform $PLATFORM not found in manifest.json"
EXPECTED_SHA256=$(read_manifest_field "sha256") || EXPECTED_SHA256=""
DOWNLOAD_URL="${CDN_BASE}/${ARCHIVE_NAME}"

# -------------------------------------------------------------------
# 5. Download
# -------------------------------------------------------------------
TMPDIR_BOOT=$(mktemp -d)
ARCHIVE_PATH="$TMPDIR_BOOT/$ARCHIVE_NAME"

cleanup() { rm -rf "$TMPDIR_BOOT"; }
trap cleanup EXIT

log "Downloading runtime from $DOWNLOAD_URL ..."

if command -v curl >/dev/null 2>&1; then
  curl -fSL --progress-bar -o "$ARCHIVE_PATH" "$DOWNLOAD_URL" || die "Download failed. Check network connection."
elif command -v wget >/dev/null 2>&1; then
  wget -q --show-progress -O "$ARCHIVE_PATH" "$DOWNLOAD_URL" || die "Download failed. Check network connection."
else
  die "Neither curl nor wget found. Cannot download runtime."
fi

# -------------------------------------------------------------------
# 6. Verify SHA256
# -------------------------------------------------------------------
if [ -n "$EXPECTED_SHA256" ]; then
  log "Verifying SHA256 checksum..."
  if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL_SHA256=$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    ACTUAL_SHA256=$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}')
  else
    log "WARNING: No sha256sum or shasum found, skipping verification."
    ACTUAL_SHA256="$EXPECTED_SHA256"
  fi

  if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
    die "SHA256 mismatch! Expected: $EXPECTED_SHA256, Got: $ACTUAL_SHA256. File may be corrupted."
  fi
  log "Checksum OK."
fi

# -------------------------------------------------------------------
# 7. Extract
# -------------------------------------------------------------------
log "Extracting to $RUNTIME_DIR ..."
mkdir -p "$RUNTIME_DIR"

if [[ "$ARCHIVE_NAME" == *.tar.gz ]] || [[ "$ARCHIVE_NAME" == *.tgz ]]; then
  tar -xzf "$ARCHIVE_PATH" -C "$RUNTIME_DIR" --strip-components=1
elif [[ "$ARCHIVE_NAME" == *.zip ]]; then
  unzip -qo "$ARCHIVE_PATH" -d "$RUNTIME_DIR"
  # Strip top-level directory if exactly one exists (match tar --strip-components=1)
  _inner=$(find "$RUNTIME_DIR" -mindepth 1 -maxdepth 1 -type d)
  if [ "$(echo "$_inner" | wc -l)" -eq 1 ]; then
    mv "$_inner"/* "$_inner"/.[!.]* "$RUNTIME_DIR"/ 2>/dev/null || true
    rmdir "$_inner" 2>/dev/null || true
  fi
else
  die "Unknown archive format: $ARCHIVE_NAME"
fi

# -------------------------------------------------------------------
# 8. Set permissions
# -------------------------------------------------------------------
chmod +x "$RUNTIME_DIR/bin/agent-browser" 2>/dev/null || true
chmod +x "$RUNTIME_DIR/bin/node" 2>/dev/null || true

if [ "$OS" = "darwin" ]; then
  log "Removing macOS quarantine attributes..."
  xattr -dr com.apple.quarantine "$RUNTIME_DIR" 2>/dev/null || true
fi

# -------------------------------------------------------------------
# 9. Generate wrapper script
# -------------------------------------------------------------------
WRAPPER_PATH="$SKILL_DIR/agent-browser"

CHROMIUM_PATH=""
if [ "$OS" = "darwin" ]; then
  # Prefer full Chrome over headless shell: look in chromium-* dirs, skip chromium_headless_shell-*
  CHROMIUM_PATH=$(find "$RUNTIME_DIR/chromium" -path "*/chromium-*/Contents/MacOS/*" -type f ! -name ".*" 2>/dev/null | head -1)
  # Fallback: any .app in chromium/
  [ -z "$CHROMIUM_PATH" ] && CHROMIUM_PATH=$(find "$RUNTIME_DIR/chromium" -path "*/Contents/MacOS/*" -type f ! -name ".*" 2>/dev/null | head -1)
fi
if [ -z "$CHROMIUM_PATH" ]; then
  # Linux: look for chrome binary, skip headless_shell
  CHROMIUM_PATH=$(find "$RUNTIME_DIR/chromium" -name "chrome" -type f 2>/dev/null | head -1)
  [ -z "$CHROMIUM_PATH" ] && CHROMIUM_PATH=$(find "$RUNTIME_DIR/chromium" \( -name "chromium" -o -name "headless_shell" \) -type f 2>/dev/null | head -1)
fi
if [ -z "$CHROMIUM_PATH" ]; then
  die "Cannot find Chromium binary in $RUNTIME_DIR/chromium/"
fi
CHROMIUM_REL_PATH="${CHROMIUM_PATH#$RUNTIME_DIR/}"
log "Found Chromium: runtime/$CHROMIUM_REL_PATH"

cat > "$WRAPPER_PATH" << WRAPPER_EOF
#!/bin/bash
SKILL_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
export PATH="\$SKILL_DIR/runtime/bin:\$PATH"
export AGENT_BROWSER_HOME="\$SKILL_DIR/runtime/daemon"
export AGENT_BROWSER_EXECUTABLE_PATH="\$SKILL_DIR/runtime/$CHROMIUM_REL_PATH"
exec "\$SKILL_DIR/runtime/bin/agent-browser" "\$@"
WRAPPER_EOF

chmod +x "$WRAPPER_PATH"

log "Runtime v$REQUIRED_VERSION installed successfully."
log "Wrapper created at: $WRAPPER_PATH"
