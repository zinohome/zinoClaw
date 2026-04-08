#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$SkillDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Manifest = Join-Path $SkillDir "manifest.json"
$RuntimeDir = Join-Path $SkillDir "runtime"
$VersionFile = Join-Path $RuntimeDir "version.txt"

function Log($msg) { Write-Host "[agent-browser-bootstrap] $msg" }
function Die($msg) { Write-Error "[agent-browser-bootstrap] ERROR: $msg"; exit 1 }

# 1. Read manifest
if (-not (Test-Path $Manifest)) { Die "manifest.json not found at $Manifest" }
$m = Get-Content $Manifest -Raw | ConvertFrom-Json
$RequiredVersion = $m.version

# 2. Check if already installed
if (Test-Path $VersionFile) {
    $installed = (Get-Content $VersionFile -Raw).Trim()
    if ($installed -eq $RequiredVersion) {
        Log "Runtime v$RequiredVersion already installed."
        exit 0
    }
    Log "Installed v$installed, need v$RequiredVersion. Upgrading..."
    Remove-Item -Recurse -Force $RuntimeDir
}

# 3. Detect platform
$arch = if ([Environment]::Is64BitOperatingSystem) {
    if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
} else { Die "32-bit Windows is not supported" }

$platform = "win32-$arch"
Log "Detected platform: $platform"

# 4. Read CDN URL
$pInfo = $m.platforms.$platform
if (-not $pInfo) { Die "Platform $platform not found in manifest.json" }
$url = "$($m.cdnBase)/$($pInfo.archive)"
$expectedSha = $pInfo.sha256

# 5. Download
$tmpDir = Join-Path $env:TEMP "agent-browser-bootstrap-$(Get-Random)"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
$archivePath = Join-Path $tmpDir $pInfo.archive

Log "Downloading runtime from $url ..."
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $archivePath -UseBasicParsing
} catch {
    Die "Download failed: $_"
}

# 6. Verify SHA256
if ($expectedSha) {
    Log "Verifying SHA256 checksum..."
    $actualSha = (Get-FileHash -Path $archivePath -Algorithm SHA256).Hash.ToLower()
    if ($actualSha -ne $expectedSha.ToLower()) {
        Die "SHA256 mismatch! Expected: $expectedSha, Got: $actualSha"
    }
    Log "Checksum OK."
}

# 7. Extract
Log "Extracting to $RuntimeDir ..."
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Expand-Archive -Path $archivePath -DestinationPath $RuntimeDir -Force

# Strip top-level directory (equivalent to tar --strip-components=1)
$innerDirs = Get-ChildItem -Path $RuntimeDir -Directory
if ($innerDirs.Count -eq 1) {
    $nested = $innerDirs[0].FullName
    Get-ChildItem -Path $nested | Move-Item -Destination $RuntimeDir -Force
    Remove-Item -Path $nested -Recurse -Force
}

# 8. Generate wrapper
$wrapperPath = Join-Path $SkillDir "agent-browser.cmd"
$chromiumPath = Get-ChildItem -Path (Join-Path $RuntimeDir "chromium") `
    -Filter "chrome.exe" -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -notlike "*headless*" } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $chromiumPath) {
    Die "Cannot find chrome.exe under $RuntimeDir\chromium\"
}

@"
@echo off
set "SKILL_DIR=%~dp0"
set "PATH=%SKILL_DIR%runtime\bin;%PATH%"
set "AGENT_BROWSER_HOME=%SKILL_DIR%runtime\daemon"
set "AGENT_BROWSER_EXECUTABLE_PATH=$chromiumPath"
"%SKILL_DIR%runtime\bin\agent-browser.exe" %*
"@ | Set-Content -Path $wrapperPath -Encoding ASCII

# Cleanup
Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue

Log "Runtime v$RequiredVersion installed successfully."
Log "Wrapper created at: $wrapperPath"
