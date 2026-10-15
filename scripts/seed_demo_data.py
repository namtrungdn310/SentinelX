"""SentinelX - Seed Demo Data Script.

Populates PostgreSQL Controller database with realistic sample projects, nodes,
and telemetry batches via REST API.

Usage:
    uv run python scripts/seed_demo_data.py [--api-url http://127.0.0.1:8000]
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
import httpx


async def seed_data(api_base_url: str) -> None:
    print(f"Connecting to SentinelX Controller at {api_base_url}...")
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        # Check health
        try:
            health = await client.get("/health")
            if health.status_code != 200:
                print(f"[WARN] Controller /health returned status {health.status_code}")
            else:
                print("[OK] Controller is healthy.")
        except httpx.ConnectError:
            print(f"[ERROR] Could not connect to {api_base_url}. Make sure Controller is running!")
            sys.exit(1)

        # 1. Create Projects
        projects_data = [
            {"name": "Production Web Cluster", "description": "Hạ tầng máy chủ web thương mại điện tử"},
            {"name": "Edge AI & Gateway", "description": "Reverse Proxy, Load Balancer và AI worker"},
            {"name": "Database & Storage", "description": "PostgreSQL Primary và Redis caching"},
        ]

        created_projects = []
        for p in projects_data:
            res = await client.post("/api/v1/projects", json=p)
            if res.status_code in (200, 201):
                p_obj = res.json()
                created_projects.append(p_obj)
                print(f"[+] Created Project: {p_obj['name']} ({p_obj['project_id']})")
            else:
                print(f"[-] Failed to create project {p['name']}: {res.text}")

        if not created_projects:
            print("[ERROR] No projects created. Aborting.")
            return

        # 2. Register Nodes
        nodes_data = [
            {
                "project_id": created_projects[0]["project_id"],
                "hostname": "edge-ingress-sg01",
                "ip_address": "10.0.1.10",
                "os_info": "Linux Ubuntu 24.04 LTS (x86_64)",
            },
            {
                "project_id": created_projects[0]["project_id"],
                "hostname": "api-gateway-node",
                "ip_address": "10.0.1.15",
                "os_info": "Linux Debian 12 Bookworm (x86_64)",
            },
            {
                "project_id": created_projects[1]["project_id"],
                "hostname": "worker-celery-pool",
                "ip_address": "10.0.3.12",
                "os_info": "Linux AlmaLinux 9 (x86_64)",
            },
            {
                "project_id": created_projects[2]["project_id"],
                "hostname": "pg-primary-cluster",
                "ip_address": "10.0.2.20",
                "os_info": "Linux Debian 12 Bookworm (x86_64)",
            },
            {
                "project_id": created_projects[0]["project_id"],
                "hostname": "backup-dr-vault",
                "ip_address": "10.0.4.8",
                "os_info": "Linux Rocky 9 (x86_64)",
            },
        ]

        created_nodes = []
        for n in nodes_data:
            res = await client.post("/api/v1/nodes", json=n)
            if res.status_code in (200, 201):
                n_obj = res.json()
                created_nodes.append(n_obj)
                print(f"[+] Registered Node: {n_obj['hostname']} ({n_obj['node_id']})")
            else:
                print(f"[-] Failed to register node {n['hostname']}: {res.text}")

        # 3. Enroll Active Nodes and Ingest Telemetry
        active_nodes = created_nodes[:4]  # Leave the last one unenrolled
        now = datetime.now(UTC)

        for i, node in enumerate(active_nodes):
            node_id = node["node_id"]
            # Enroll
            enroll_res = await client.post(
                "/api/v1/enrollment/agents",
                json={
                    "node_id": node_id,
                    "agent_version": "1.0.0",
                    "hostname": node["hostname"],
                    "ip_address": node["ip_address"],
                    "os_info": "Linux 6.8.0-generic",
                },
            )
            if enroll_res.status_code not in (200, 201):
                print(f"[-] Could not enroll agent for {node['hostname']}: {enroll_res.text}")
                continue

            token = enroll_res.json()["agent_token"]
            print(f"[OK] Enrolled Agent for {node['hostname']} with token.")

            # Ingest 15 metric samples
            samples = []
            base_cpu = 25.0 + (i * 18.0)
            base_mem = 40.0 + (i * 15.0)

            for step in range(15, 0, -1):
                obs_time = (now - timedelta(seconds=step * 10)).isoformat()
                samples.append({
                    "observed_at": obs_time,
                    "cpu_percent": min(95.0, round(base_cpu + (step % 5) * 2.5, 1)),
                    "memory_percent": min(95.0, round(base_mem + (step % 3) * 1.5, 1)),
                    "disk_percent": round(30.0 + i * 12.0, 1),
                    "network_rx_bytes": 10000000 + i * 5000000,
                    "network_tx_bytes": 8000000 + i * 4000000,
                })

            metric_res = await client.post(
                "/api/v1/telemetry/metrics",
                headers={"Authorization": f"Bearer {token}"},
                json={"node_id": node_id, "samples": samples},
            )
            if metric_res.status_code == 202:
                print(f"[OK] Ingested 15 telemetry samples for {node['hostname']}")
            else:
                print(f"[-] Failed to ingest metrics for {node['hostname']}: {metric_res.text}")

    print("\n[SUCCESS] Seed process complete! Refresh http://localhost:5174 to view live data.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed SentinelX Demo Data")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="FastAPI Controller base URL")
    args = parser.parse_args()

    asyncio.run(seed_data(args.api_url))
