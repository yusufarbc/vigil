# Sysmon Installer Helper
# This script downloads Sysmon and the SwiftOnSecurity configuration, then installs it.

$sysmonUrl = "https://download.sysinternals.com/files/Sysmon.zip"
$configUrl = "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/master/sysmonconfig-export.xml"
$installDir = "C:\Sysmon"

# Ensure running as Admin
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Please run this script as Administrator!"
    exit
}

# Create Directory
if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Write-Host "Created $installDir" -ForegroundColor Green
}

# Download Sysmon
Write-Host "Downloading Sysmon..."
Invoke-WebRequest -Uri $sysmonUrl -OutFile "$installDir\Sysmon.zip"
Expand-Archive -Path "$installDir\Sysmon.zip" -DestinationPath $installDir -Force

# Download Config
Write-Host "Downloading SwiftOnSecurity Configuration..."
Invoke-WebRequest -Uri $configUrl -OutFile "$installDir\sysmonconfig.xml"

# Install
Write-Host "Installing Sysmon Service..."
Set-Location $installDir
.\Sysmon64.exe -accepteula -i sysmonconfig.xml

Write-Host "✅ Sysmon Installed Successfully!" -ForegroundColor Green
Write-Host "Logs are now available in Event Viewer > Applications and Services Logs > Microsoft > Windows > Sysmon > Operational"
