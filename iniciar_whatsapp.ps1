# ==============================================================================
# Script de arranque rápido para Academic Bot en WhatsApp (vía Código QR)
# ==============================================================================
$ErrorActionPreference = "Stop"
$BotRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$WaDir = Join-Path $BotRoot "whatsapp_qr"

Write-Host "=== Academic Bot — Conector de WhatsApp por Código QR ===" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $WaDir "node_modules"))) {
    Write-Host "Instalando dependencias de WhatsApp (Baileys + QR)..." -ForegroundColor Yellow
    Push-Location $WaDir
    npm install
    Pop-Location
}

Write-Host "Iniciando conector WhatsApp QR y panel en http://localhost:3005 ..." -ForegroundColor Green
Push-Location $WaDir
node index.js
Pop-Location
