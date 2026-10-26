# Rebuilds the dashboard from data\*.json, encrypts it with StatiCrypt, and pushes to GitHub Pages.
# Only the encrypted index.html leaves this PC.
$ErrorActionPreference = "Stop"
$root = "C:\PreauthTracker"
Set-Location $root
if (-not $env:PREAUTH_PW) { throw "PREAUTH_PW is not set" }

python "$root\build.py"

npx --yes staticrypt@3 "$root\build\index.html" -p $env:PREAUTH_PW -d "$root\repo" --short --remember 30 `
  --template-title "Pre-Auth Tracker" `
  --template-instructions "Counts only. Enter the team password." `
  --template-button "Open dashboard" `
  --template-color-primary "#14181f" --template-color-secondary "#f5f6f8"

Remove-Item "$root\build\index.html"   # unencrypted copy stays off disk

Set-Location "$root\repo"
git add index.html
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git commit -m ("Update " + (Get-Date -Format "yyyy-MM-dd HH:mm"))
  git push
  Write-Host "Pushed. Site updates in 1-2 minutes."
} else { Write-Host "No changes to publish." }
