#!/usr/bin/env bash
# ==============================================================================
# SentinelX Lab — Environment Reset Script
# Stops containers, cleans up dynamic nodes and resets lab volumes.
# ==============================================================================

set -euo pipefail

echo "[*] Cleaning up dynamic SentinelX lab containers..."
DYNAMIC_CONTAINERS=$(docker ps -aq --filter "label=sentinelx.lab.dynamic=true" || true)
if [ -n "$DYNAMIC_CONTAINERS" ]; then
  docker rm -f $DYNAMIC_CONTAINERS
  echo "[+] Dynamic containers removed."
fi

echo "[*] Tearing down Docker Compose lab services..."
docker compose down -v --remove-orphans

echo "[+] SentinelX Lab has been completely reset to a clean state."
