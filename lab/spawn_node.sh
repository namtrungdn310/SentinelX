#!/usr/bin/env bash
# ==============================================================================
# SentinelX Lab — Dynamic Node Spawner
# Spawns a new Backend Workload + SentinelX Agent dynamically into the lab.
# Demonstrates Multi-Node capability without changing compose.yaml!
# ==============================================================================

set -euo pipefail

NODE_NAME="${1:-node-$(date +%s | tail -c 4)}"
PROJECT_TOKEN="${2:-sentinelx-lab-default-token}"
CONTROLLER_URL="${CONTROLLER_URL:-http://sentinelx_controller:8000}"
NETWORK_NAME="sentinelx_internal"

echo "[*] Spawning dynamic SentinelX Node: ${NODE_NAME}"

# 1. Run Backend Workload Container
docker run -d \
  --name "sentinelx_backend_${NODE_NAME}" \
  --network "${NETWORK_NAME}" \
  -e NODE_NAME="${NODE_NAME}" \
  -e PORT="8080" \
  --label "sentinelx.lab.dynamic=true" \
  --label "sentinelx.node=${NODE_NAME}" \
  sentinelx-backend:latest

# 2. Run SentinelX Agent Container
docker run -d \
  --name "sentinelx_agent_${NODE_NAME}" \
  --network "${NETWORK_NAME}" \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  -e SENTINELX_NODE_ID="${NODE_NAME}" \
  -e SENTINELX_CONTROLLER_URL="${CONTROLLER_URL}" \
  -e SENTINELX_ENROLLMENT_TOKEN="${PROJECT_TOKEN}" \
  -e SENTINELX_HEARTBEAT_INTERVAL="3" \
  --label "sentinelx.lab.dynamic=true" \
  --label "sentinelx.node=${NODE_NAME}" \
  sentinelx-agent:latest

echo "[+] Node '${NODE_NAME}' successfully launched!"
echo "    Backend container: sentinelx_backend_${NODE_NAME}"
echo "    Agent container:   sentinelx_agent_${NODE_NAME}"
echo "    Check Controller logs or Dashboard to observe auto-enrollment."
