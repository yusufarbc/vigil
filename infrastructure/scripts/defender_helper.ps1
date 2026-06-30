# Check if running as Administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  Warning: This script is NOT running as Administrator." -ForegroundColor Yellow
    Write-Host "Windows Defender commands (Get-MpComputerStatus, Start-MpScan) require Admin privileges."
} else {
    Write-Host "✅ Running as Administrator." -ForegroundColor Green
}

Write-Host "`nTesting Access to Windows Defender..."
try {
    $status = Get-MpComputerStatus
    Write-Host "✅ Successfully retrieved Defender Status." -ForegroundColor Green
    Write-Host "RealTimeProtection: " $status.RealTimeProtectionEnabled
} catch {
    Write-Host "❌ Failed to access Windows Defender. Error: $_" -ForegroundColor Red
}
