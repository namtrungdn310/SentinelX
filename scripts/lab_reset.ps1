# ==============================================================================
# SentinelX Lab — Environment Reset Script (PowerShell for Windows)
# ==============================================================================

Write-Host "[*] Cleaning up dynamic SentinelX lab containers..." -ForegroundColor Yellow
$dynamicContainers = docker ps -aq --filter "label=sentinelx.lab.dynamic=true"
if ($dynamicContainers) {
    docker rm -f $dynamicContainers
    Write-Host "[+] Dynamic containers removed." -ForegroundColor Green
}

Write-Host "[*] Tearing down Docker Compose lab services..." -ForegroundColor Yellow
docker compose down -v --remove-orphans

Write-Host "[+] SentinelX Lab has been completely reset to a clean state." -ForegroundColor Green
