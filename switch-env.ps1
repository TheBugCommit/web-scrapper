#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Switch the active scraper environment by copying the target .env.* file to .env

.DESCRIPTION
    Usage:
        .\switch-env.ps1 test        # activates .env.test
        .\switch-env.ps1 production  # activates .env.production
        .\switch-env.ps1             # shows current active env

.EXAMPLE
    .\switch-env.ps1 test
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("test", "production", "")]
    [string]$Environment = ""
)

$Root     = $PSScriptRoot
$EnvFile  = Join-Path $Root ".env"
$Marker   = Join-Path $Root ".env.active"

function Get-ActiveEnv {
    if (Test-Path $Marker) { return Get-Content $Marker }
    return "(none -- .env not managed by this script)"
}

# -- Show current env if no argument -------------------------------------------
if (-not $Environment) {
    Write-Host ""
    Write-Host "  Current environment: $(Get-ActiveEnv)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Usage: .\switch-env.ps1 [test|production]" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

# -- Switch --------------------------------------------------------------------
$Source = Join-Path $Root ".env.$Environment"

if (-not (Test-Path $Source)) {
    Write-Error "Environment file not found: $Source"
    exit 1
}

Copy-Item -Path $Source -Destination $EnvFile -Force
Set-Content -Path $Marker -Value $Environment

Write-Host ""
Write-Host "  Switched to: $Environment" -ForegroundColor Green
Write-Host "  Active file: .env.$Environment -> .env" -ForegroundColor Gray
Write-Host ""

# Show a summary of key settings
Write-Host "  Key settings:" -ForegroundColor Yellow
$Lines = Get-Content $EnvFile | Where-Object { $_ -match "^SCRAPER_" -and $_ -notmatch "PASSWORD|SECRET" }
foreach ($Line in $Lines) {
    Write-Host "    $Line" -ForegroundColor Gray
}
Write-Host ""
