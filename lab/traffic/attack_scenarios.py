"""Traffic generator and attack simulation script for SentinelX Lab.

Usage inside container or locally:
    python attack_scenarios.py normal --target http://sentinelx_lb:8080 --rate 5
    python attack_scenarios.py flood --target http://sentinelx_lb:8080 --concurrency 50
    python attack_scenarios.py cpu-stress --target http://backend01:8080 --duration 10
"""

import argparse
import asyncio
import sys
import time
import urllib.request
import urllib.parse


async def simulate_normal_traffic(target: str, rate: float = 2.0) -> None:
    """Send steady normal HTTP requests through the Load Balancer."""
    print(f"[*] Starting normal traffic simulation to {target} (interval: {1/rate:.2f}s)...")
    req_id = 0
    while True:
        req_id += 1
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "SentinelX-NormalUser/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                print(f"[{req_id}] Code: {resp.status} - Normal request succeeded")
        except Exception as err:
            print(f"[{req_id}] Request failed: {err}")
        await asyncio.sleep(1.0 / rate)


async def simulate_http_flood(target: str, concurrency: int = 30, duration: int = 15) -> None:
    """Send high-frequency HTTP request flood to trigger DDoS / rate-limit detection."""
    print(f"[!] Launching HTTP Flood against {target} with concurrency {concurrency} for {duration}s...")
    stop_time = time.time() + duration
    total_sent = 0

    async def _worker() -> None:
        nonlocal total_sent
        while time.time() < stop_time:
            try:
                req = urllib.request.Request(target, headers={"User-Agent": "Attacker-Botnet/2.1"})
                with urllib.request.urlopen(req, timeout=2) as _:
                    pass
                total_sent += 1
            except Exception:
                pass
            await asyncio.sleep(0.01)

    tasks = [asyncio.create_task(_worker()) for _ in range(concurrency)]
    await asyncio.gather(*tasks)
    print(f"[+] HTTP Flood finished. Total requests sent: {total_sent}")


def trigger_backend_cpu_stress(target_backend: str, duration: int = 10) -> None:
    """Trigger CPU overload on a backend node."""
    url = f"{target_backend.rstrip('/')}/stress/cpu?duration={duration}"
    print(f"[!] Sending CPU stress payload to {url}...")
    try:
        req = urllib.request.Request(url, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=duration + 3) as resp:
            print(f"[+] Server response: {resp.read().decode()}")
    except Exception as err:
        print(f"[-] Failed to trigger CPU stress: {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelX Lab Attack & Traffic Generator")
    parser.add_argument("mode", choices=["normal", "flood", "cpu-stress"], help="Simulation mode")
    parser.add_argument("--target", default="http://sentinelx_lb:8080", help="Target URL")
    parser.add_argument("--rate", type=float, default=2.0, help="Request rate (req/s) for normal mode")
    parser.add_argument("--concurrency", type=int, default=30, help="Concurrency level for flood")
    parser.add_argument("--duration", type=int, default=15, help="Duration in seconds")

    args = parser.parse_args()

    if args.mode == "normal":
        asyncio.run(simulate_normal_traffic(args.target, rate=args.rate))
    elif args.mode == "flood":
        asyncio.run(simulate_http_flood(args.target, concurrency=args.concurrency, duration=args.duration))
    elif args.mode == "cpu-stress":
        trigger_backend_cpu_stress(args.target, duration=args.duration)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
        sys.exit(0)
