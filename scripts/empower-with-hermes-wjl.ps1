#!/usr/bin/env pwsh
# Point an EXISTING Hermes Desktop install (WINDOWS) at the hermes-wjl fork and
# set up a kid builder profile — without rebuilding the Electron app. Native
# PowerShell twin of empower-with-hermes-wjl.sh, so Windows users don't need
# Git Bash. Works in Windows PowerShell 5.1 and PowerShell 7+.
#
# One-liner (paste into PowerShell — no script file, no execution-policy change):
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/empower-with-hermes-wjl.ps1))) -Key <FREE_NVIDIA_KEY>
#
# Params:
#   -Key <k>          Free NVIDIA NIM key for the kid (free at build.nvidia.com)
#   -Llm <mode>       free | local | inherit   (default: free)
#   -Model <m>        Model id (default: google/gemma-4-31b-it)
#   -ProfileName <p>  Kid profile name (default: kid)
[CmdletBinding()]
param(
  [string]$Key = "",
  [ValidateSet("free", "local", "inherit")][string]$Llm = "free",
  [string]$Model = "google/gemma-4-31b-it",
  [string]$ProfileName = "kid"   # NOT $Profile — that shadows PowerShell's automatic $PROFILE.
)

$ErrorActionPreference = "Stop"

$Fork   = "https://github.com/wjlgatech/hermes-wjl.git"
$Agent  = Join-Path $env:USERPROFILE ".hermes\hermes-agent"
$Py     = Join-Path $Agent "venv\Scripts\python.exe"
$Hermes = Join-Path $Agent "venv\Scripts\hermes.exe"

function Assert-Exit($what) {
  # Native commands don't honor $ErrorActionPreference on Windows PowerShell 5.1,
  # so gate the critical steps on their exit code explicitly.
  if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)." }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "Missing 'git'. Install Git for Windows first: https://git-scm.com/download/win"
}
if (-not (Test-Path (Join-Path $Agent ".git"))) {
  Write-Host "X No Hermes install found at $Agent." -ForegroundColor Red
  Write-Host "  Install the Hermes desktop app first, then re-run."
  exit 1
}
if (-not (Test-Path $Py)) {
  throw "Python venv not found at $Py — is the desktop app fully installed?"
}

Write-Host "-> Pointing $Agent at the fork ($Fork)..."
git -C $Agent remote set-url origin $Fork;        Assert-Exit "git remote set-url"
git -C $Agent fetch origin --quiet;               Assert-Exit "git fetch"
git -C $Agent checkout main --quiet 2>$null
if ($LASTEXITCODE -ne 0) { git -C $Agent checkout -b main origin/main --quiet; Assert-Exit "git checkout main" }
git -C $Agent reset --hard origin/main --quiet;   Assert-Exit "git reset"
Write-Host ("  now at " + (git -C $Agent rev-parse --short HEAD))

Write-Host "-> Reinstalling the Python backend (no Electron rebuild)..."
& $Py -m pip install -e $Agent --quiet;           Assert-Exit "pip install"

Write-Host "-> Setting up the '$ProfileName' profile (kid mode, LLM: $Llm)..."
# kid-setup makes the profile active for BOTH the CLI and the desktop GUI
# (write_desktop_active_profile picks the right per-OS userData dir on Windows).
$KidArgs = @("-m", "hermes_cli.main", "kid-setup", "--profile", $ProfileName, "--llm", $Llm, "--model", $Model)
if ($Llm -eq "free" -and $Key) { $KidArgs += @("--provider", "nvidia", "--key", $Key) }
& $Py @KidArgs;                                   Assert-Exit "kid-setup"

Write-Host "-> Launching the existing desktop app on the fork (no rebuild)..."
Start-Process -FilePath $Hermes -ArgumentList "desktop", "--skip-build" -WindowStyle Hidden

Write-Host ""
Write-Host "Done. Your Hermes desktop app is now powered by hermes-wjl, in '$ProfileName' mode." -ForegroundColor Green
Write-Host "  Switch back anytime in the desktop profile switcher (or re-run with -ProfileName default)."
