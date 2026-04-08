# minimax-pdf dependency check & auto-install (Windows PowerShell)
#Requires -Version 5.1
$ErrorActionPreference = "Continue"

function Ok   { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green }
function Warn { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Fail { param($msg) Write-Host "[FAIL]  $msg" -ForegroundColor Red }
function Info { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan }

$Status = "READY"
$Installed = @()
$HasWinget = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)

# ── Python 3 ──────────────────────────────────────────────────────────────────
$pyCmd = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command python -ErrorAction SilentlyContinue }
if (-not $pyCmd) {
    $dcPy = Join-Path $env:USERPROFILE ".deskclaw\python\python.exe"
    if (Test-Path $dcPy) { $pyCmd = Get-Item $dcPy; Info "Using DeskClaw Python: $dcPy" }
}

if ($pyCmd) {
    $pyVer = & $pyCmd.Source --version 2>&1
    Ok "python $pyVer"
    $PY = $pyCmd.Source
} else {
    Fail "python not found"
    if ($HasWinget) {
        Info "Installing Python via winget..."
        winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements 2>$null
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $pyCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pyCmd) { Ok "python installed"; $PY = $pyCmd.Source; $Installed += "python" }
        else { Fail "python install failed"; $Status = "NOT READY" }
    } else {
        Fail "Install Python from https://www.python.org/downloads/"
        $Status = "NOT READY"
    }
}

if ($PY) {
    # ── reportlab ─────────────────────────────────────────────────────────────
    & $PY -c "import reportlab" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "reportlab"
    } else {
        Info "Installing reportlab..."
        & $PY -m pip install -q reportlab 2>$null
        & $PY -c "import reportlab" 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "reportlab installed"; $Installed += "reportlab" }
        else { Fail "reportlab install failed"; $Status = "NOT READY" }
    }

    # ── pypdf ─────────────────────────────────────────────────────────────────
    & $PY -c "import pypdf" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "pypdf"
    } else {
        Info "Installing pypdf..."
        & $PY -m pip install -q pypdf 2>$null
        & $PY -c "import pypdf" 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "pypdf installed"; $Installed += "pypdf" }
        else { Fail "pypdf install failed"; $Status = "NOT READY" }
    }

    # ── matplotlib (optional) ─────────────────────────────────────────────────
    & $PY -c "import matplotlib" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "matplotlib (chart/math/flowchart blocks enabled)"
    } else {
        Info "Installing matplotlib..."
        & $PY -m pip install -q matplotlib 2>$null
        & $PY -c "import matplotlib" 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "matplotlib installed"; $Installed += "matplotlib" }
        else { Warn "matplotlib not available — chart/math blocks degrade to text" }
    }
}

# ── Node.js ───────────────────────────────────────────────────────────────────
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    Ok "node $(node --version)"
} else {
    Fail "Node.js not found (required for cover rendering)"
    if ($HasWinget) {
        Info "Installing Node.js via winget..."
        winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements 2>$null
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        if (Get-Command node -ErrorAction SilentlyContinue) {
            Ok "Node.js installed"; $Installed += "node"
        } else {
            Fail "Node.js install failed — download from https://nodejs.org/"
            $Status = "NOT READY"
        }
    } else {
        Fail "Install Node.js from https://nodejs.org/"
        $Status = "NOT READY"
    }
}

# ── Playwright + Chromium ─────────────────────────────────────────────────────
if (Get-Command node -ErrorAction SilentlyContinue) {
    $npmGlobal = (npm root -g 2>$null).Trim()
    $env:NODE_PATH = $npmGlobal
    node -e "require('playwright')" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "playwright"
    } else {
        Info "Installing playwright..."
        npm install -g playwright --silent 2>$null
        if ($LASTEXITCODE -eq 0) {
            Info "Installing Chromium browser..."
            npx playwright install chromium 2>$null
            if ($LASTEXITCODE -eq 0) {
                Ok "playwright + chromium installed"
                $Installed += "playwright"
            } else {
                Warn "Chromium install failed — try: npx playwright install chromium"
            }
        } else {
            Fail "playwright install failed"
            $Status = "NOT READY"
        }
    }
}

# ── Result ────────────────────────────────────────────────────────────────────
Write-Host ""
if ($Status -eq "READY") {
    if ($Installed.Count -gt 0) {
        Ok "READY (installed: $($Installed -join ', '))"
    } else {
        Ok "READY — all dependencies satisfied"
    }
} else {
    Fail "NOT READY — see errors above"
    exit 1
}
