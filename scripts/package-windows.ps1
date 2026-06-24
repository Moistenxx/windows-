param(
  [string]$ApiBase = "http://127.0.0.1:8000",
  [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$release = Join-Path $root "release"
$package = Join-Path $release "ai-video-workbench-windows-$Version"
$zip = "$package.zip"

Remove-Item $package, $zip -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $package | Out-Null

Push-Location (Join-Path $root "client")
$env:VITE_API_BASE_URL = $ApiBase
$env:VITE_APP_VERSION = $Version
npm run build
Pop-Location

Copy-Item (Join-Path $root "client\dist") (Join-Path $package "dist") -Recurse
Set-Content -Encoding ASCII -Path (Join-Path $package "START-WINDOWS-CLIENT.cmd") -Value '@echo off
start "" "%~dp0dist\index.html"
'
Compress-Archive -Path (Join-Path $package "*") -DestinationPath $zip -Force
Write-Host "Created $zip"
