# Pre-Auth Tracker - ON-DEMAND run on Benny-PC (no schedule)
# Started from the "Update Pre-Auth Dashboard" desktop shortcut.
# Pauses Rob -> exports report from Edge -> counts -> deletes PDF -> resumes Rob -> publishes counts-only page
param([string]$RobTask = "Rob", [switch]$NoPublish)

$ErrorActionPreference = "Stop"
$root = "C:\PreauthTracker"
$pdf  = "$env:LOCALAPPDATA\PreauthExport\preauth.pdf"
$date = Get-Date -Format "yyyy-MM-dd"
$json = "$root\data\$date.json"          # re-running the same day replaces that day's counts
New-Item -ItemType Directory -Force "$root\logs", "$root\data", (Split-Path $pdf) | Out-Null
Start-Transcript "$root\logs\$date.log" -Append | Out-Null

function Finish([string]$msg, [string]$color) {
    Write-Host ""; Write-Host $msg -ForegroundColor $color
    Stop-Transcript | Out-Null
    Read-Host "Press Enter to close"
    exit
}

Write-Host "Pre-Auth update starting. Hands off the mouse and keyboard for about 5 minutes." -ForegroundColor Yellow
for ($i = 10; $i -gt 0; $i--) { Write-Host "  starting in $i..."; Start-Sleep 1 }

$ok = $false
try {
    # 1. Pause Rob: stop new 5-min runs, then wait for a run in progress to finish (max 5 min)
    Write-Host "Pausing Rob..."
    Disable-ScheduledTask -TaskName $RobTask | Out-Null
    $waited = 0
    while ((Get-ScheduledTask -TaskName $RobTask).State -eq "Running" -and $waited -lt 300) { Start-Sleep 5; $waited += 5 }
    if ((Get-ScheduledTask -TaskName $RobTask).State -eq "Running") { throw "Rob is still mid-run after 5 min" }

    # 2. Export Patient List - Custom to PDF (Edge automation)
    Write-Host "Exporting report from Ortho2 Edge..."
    python "$root\export_edge.py" $pdf
    if ($LASTEXITCODE -ne 0) { throw "Edge export failed (exit $LASTEXITCODE)" }

    # 3. Count on this PC -> data\YYYY-MM-DD.json (counts only; only written if counting succeeds)
    Write-Host "Counting..."
    python "$root\parse_counts.py" $pdf $json
    if ($LASTEXITCODE -ne 0) { throw "Counting failed (exit $LASTEXITCODE)" }
    $ok = $true
}
catch { Write-Host "ERROR: $_" -ForegroundColor Red }
finally {
    # 4. Always delete the PHI PDF and turn Rob back on, even if a step failed
    if (Test-Path $pdf) { Remove-Item $pdf -Force; Write-Host "PDF deleted." }
    Get-ChildItem "$(Split-Path $pdf)\tmp" -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Enable-ScheduledTask -TaskName $RobTask | Out-Null
    Write-Host "Rob resumed."
}
if (-not $ok) { Finish "Update FAILED. Rob is back on. Nothing was published. Details: $root\logs\$date.log" "Red" }

if ($NoPublish) { Finish "Test run OK: counts saved to $json (not published)." "Green" }

# 5. Rebuild, encrypt, push (Rob is already back on)
try { & "$root\publish.ps1" } catch { Finish "Counts saved, but publishing failed: $_" "Red" }
Finish "Done. Dashboard updates in 1-2 minutes." "Green"
