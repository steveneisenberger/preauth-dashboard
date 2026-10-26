# Pre-Auth Tracker run on Benny-PC (Mon-Fri, first try 12:00 PM, retries every 30 min until 5:00 PM)
# Pauses Rob -> exports report from Edge -> counts -> deletes PDF -> resumes Rob -> publishes counts-only page
# Exit 0 = done (or nothing to do). Exit 1 = skipped/failed; the next 30-min trigger tries again.
param([string]$RobTask = "Rob")

$ErrorActionPreference = "Stop"
$root   = "C:\PreauthTracker"
$pdf    = "$env:LOCALAPPDATA\PreauthExport\preauth.pdf"
$date   = Get-Date -Format "yyyy-MM-dd"
$json   = "$root\data\$date.json"
$done   = "$root\logs\done-$date.txt"
$cutoff = (Get-Date).Date.AddHours(17)      # last attempt 5:00 PM
New-Item -ItemType Directory -Force "$root\logs", "$root\data", (Split-Path $pdf) | Out-Null
Start-Transcript "$root\logs\$date.log" -Append | Out-Null

function Stop-Run([int]$code, [string]$why) { Write-Host "$(Get-Date -f HH:mm) $why"; Stop-Transcript | Out-Null; exit $code }

# --- Pre-checks ---
if (Test-Path $done)        { Stop-Run 0 "Already published today." }
if ((Get-Date) -gt $cutoff) { Stop-Run 0 "Past 5:00 PM cutoff; giving up for today." }

Add-Type @"
using System; using System.Runtime.InteropServices;
public static class Idle {
  [StructLayout(LayoutKind.Sequential)] struct LII { public uint cbSize; public uint dwTime; }
  [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p);
  public static uint Seconds() { var l = new LII(); l.cbSize = 8; GetLastInputInfo(ref l); return ((uint)Environment.TickCount - l.dwTime) / 1000; }
}
"@
if (Get-Process LogonUI -ErrorAction SilentlyContinue) { Stop-Run 1 "Screen is locked; will retry in 30 min." }
if ([Idle]::Seconds() -lt 120)                         { Stop-Run 1 "Someone is using the PC (active in last 2 min); will retry in 30 min." }

# --- Export + count (skipped if counts already saved earlier today but publish failed) ---
if (-not (Test-Path $json)) {
    $ok = $false
    try {
        # 1. Pause Rob: stop new 5-min runs, then wait for a run in progress to finish (max 5 min)
        Write-Host "Pausing Rob ($RobTask)..."
        Disable-ScheduledTask -TaskName $RobTask | Out-Null
        $waited = 0
        while ((Get-ScheduledTask -TaskName $RobTask).State -eq "Running" -and $waited -lt 300) { Start-Sleep 10; $waited += 10 }
        if ((Get-ScheduledTask -TaskName $RobTask).State -eq "Running") { throw "Rob still busy after 5 min" }

        # 2. Export Patient List - Custom to PDF (Edge screen automation)
        python "$root\export_edge.py" $pdf
        if ($LASTEXITCODE -ne 0) { throw "Edge export failed (exit $LASTEXITCODE)" }

        # 3. Count on this PC -> data\YYYY-MM-DD.json (office/insurer/status counts only)
        python "$root\parse_counts.py" $pdf $json
        if ($LASTEXITCODE -ne 0) { throw "Counting failed (exit $LASTEXITCODE)" }
        $ok = $true
    }
    catch { Write-Host "ERROR: $_" }
    finally {
        # 4. Always delete the PHI PDF and turn Rob back on, even if a step failed
        if (Test-Path $pdf) { Remove-Item $pdf -Force; Write-Host "PDF deleted." }
        Enable-ScheduledTask -TaskName $RobTask | Out-Null
        Write-Host "Rob resumed."
    }
    if (-not $ok) {
        if (Test-Path $json) { Remove-Item $json -Force }   # never keep a partial count
        Stop-Run 1 "Run failed; will retry in 30 min."
    }
}

# 5. Rebuild, encrypt, push (Rob is already back on)
try { & "$root\publish.ps1" } catch { Stop-Run 1 "Publish failed: $_ ; will retry in 30 min." }
Set-Content $done (Get-Date)
Stop-Run 0 "Done."
