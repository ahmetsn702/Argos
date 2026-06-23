# start_agents.ps1 — Argos agent startup script
# Ensures OpenCode (port 4096) and Kiro are running silently.
# Registers itself to run at Windows login.

# ---------------------------------------------------------------------------
# 1. OpenCode — check port 4096
# ---------------------------------------------------------------------------
$opencodeRunning = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("localhost", 4096)
    $opencodeRunning = $tcp.Connected
    $tcp.Close()
} catch {}

if ($opencodeRunning) {
    Write-Host "[OK]   OpenCode already listening on port 4096 - skipping."
} else {
    Write-Host "[START] OpenCode not detected on port 4096 - starting..."
    Start-Process -FilePath "opencode" `
                  -ArgumentList "serve", "--port", "4096" `
                  -WindowStyle Hidden
    Write-Host "[DONE]  OpenCode process launched."
}

# ---------------------------------------------------------------------------
# 2. Kiro — check process
# ---------------------------------------------------------------------------
$kiroProc = Get-Process -Name "kiro" -ErrorAction SilentlyContinue

if ($kiroProc) {
    Write-Host "[OK]   Kiro is already running (PID $($kiroProc.Id)) - skipping."
} else {
    Write-Host "[START] Kiro not detected - starting..."
    Start-Process -FilePath "C:\Users\ahmed\AppData\Local\Kiro-Cli\kiro.exe" `
                  -WindowStyle Hidden
    Write-Host "[DONE]  Kiro process launched."
}

# ---------------------------------------------------------------------------
# 3. Register this script in Windows startup (HKCU Run key)
# ---------------------------------------------------------------------------
$regPath  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$regKey   = "ArgosAgents"
$regValue = 'powershell.exe -WindowStyle Hidden -File "C:\Footprint\argos\start_agents.ps1"'

$existing = Get-ItemProperty -Path $regPath -Name $regKey -ErrorAction SilentlyContinue

if ($existing -and $existing.$regKey -eq $regValue) {
    Write-Host "[OK]   Startup registry entry already present - skipping."
} else {
    Set-ItemProperty -Path $regPath -Name $regKey -Value $regValue
    Write-Host "[DONE]  Startup registry entry created: $regKey"
}

Write-Host ""
Write-Host "=== start_agents.ps1 complete ==="
