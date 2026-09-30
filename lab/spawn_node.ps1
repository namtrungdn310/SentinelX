# ==============================================================================
# SentinelX Lab — Dynamic Node Spawner (PowerShell for Windows)
# Spawns a new Backend Workload + SentinelX Agent dynamically into the lab.
# ==============================================================================

param(
    [string]$NodeName = "node-$((Get-Date -UFormat %s).Substring(6, 4))",
    [string]$ProjectToken = "sentinelx-lab-default-token",
    [string]$ControllerUrl = "http://sentinelx_controller:8000",
    [string]$NetworkName = "sentinelx_internal"
)

$ErrorActionPreference = "Stop"

Write-Host "[*] Spawning dynamic SentinelX Node: $NodeName" -ForegroundColor Cyan

# 1. Run Backend Workload Container
docker run -d `
  --name "sentinelx_backend_$NodeName" `
  --network "$NetworkName" `
  -e "NODE_NAME=$NodeName" `
  -e "PORT=8080" `
  --label "sentinelx.lab.dynamic=true" `
  --label "sentinelx.node=$NodeName" `
  sentinelx-backend:latest

# 2. Run SentinelX Agent Container
docker run -d `
  --name "sentinelx_agent_$NodeName" `
  --network "$NetworkName" `
  --cap-add=NET_ADMIN `
  --cap-add=NET_RAW `
  -e "SENTINELX_NODE_ID=$NodeName" `
  -e "SENTINELX_CONTROLLER_URL=$ControllerUrl" `
  -e "SENTINELX_ENROLLMENT_TOKEN=$ProjectToken" `
  -e "SENTINELX_HEARTBEAT_INTERVAL=3" `
  --label "sentinelx.lab.dynamic=true" `
  --label "sentinelx.node=$NodeName" `
  sentinelx-agent:latest

Write-Host "[+] Node '$NodeName' successfully launched!" -ForegroundColor Green
Write-Host "    Backend container: sentinelx_backend_$NodeName"
Write-Host "    Agent container:   sentinelx_agent_$NodeName"
Write-Host "    Check Controller logs or Dashboard to observe auto-enrollment."
