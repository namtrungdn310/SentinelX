"""Traffic generator and attack simulation script for SentinelX Lab.

Usage inside container or locally:
    python attack_scenarios.py normal --target http://sentinelx_lb:8080 --rate 5
    python attack_scenarios.py flood --target http://sentinelx_lb:8080 --concurrency 50
    python attack_scenarios.py cpu-stress --target http://172.28.2.31:8080 --duration 20
    python attack_scenarios.py memory-stress --target http://172.28.2.31:8080 --mb 256
    python attack_scenarios.py syn-flood --target 172.28.2.31 --port 8080 --duration 12
    python attack_scenarios.py port-scan --target 172.28.2.31 --start-port 8000 --end-port 8060
    python attack_scenarios.py udp-flood --target 172.28.2.31 --port 9999 --duration 10
"""

import argparse
import asyncio
import ipaddress
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request


def _validate_target_host(target: str) -> str:
    cleaned = target.strip()
    if "://" in cleaned:
        parsed = urllib.parse.urlsplit(cleaned)
        cleaned = parsed.hostname or ""
    if not cleaned:
        raise ValueError("Target host is required")
    try:
        ipaddress.ip_address(cleaned)
        return cleaned
    except ValueError:
        socket.getaddrinfo(cleaned, None)
        return cleaned


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
    """Send high-frequency HTTP request flood to trigger DDoS / traffic spike detection."""
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
        with urllib.request.urlopen(req, timeout=duration + 5) as resp:
            print(f"[+] Server response: {resp.read().decode()}")
    except Exception as err:
        print(f"[-] Failed to trigger CPU stress: {err}")


def trigger_backend_memory_stress(target_backend: str, mb: int = 256) -> None:
    """Trigger memory allocation on a backend node."""
    url = f"{target_backend.rstrip('/')}/stress/memory?mb={mb}"
    print(f"[!] Sending memory stress payload ({mb} MB) to {url}...")
    try:
        req = urllib.request.Request(url, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[+] Server response: {resp.read().decode()}")
    except Exception as err:
        print(f"[-] Failed to trigger memory stress: {err}")


def trigger_syn_flood(target: str, port: int, duration: int) -> None:
    """Send L4 TCP SYN flood via hping3 (falls back to socket burst if hping3 absent)."""
    host = _validate_target_host(target)
    print(f"[!] Launching TCP SYN flood against {host}:{port} for {duration}s...")
    try:
        proc = subprocess.Popen(
            ["hping3", "-S", "-p", str(port), "--flood", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(duration)
        proc.terminate()
        proc.wait(timeout=3)
        print("[+] hping3 SYN flood completed")
        return
    except FileNotFoundError:
        pass

    deadline = time.time() + duration
    sent = 0
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)
        try:
            s.connect_ex((host, port))
            sent += 1
        except OSError:
            pass
        finally:
            s.close()
    print(f"[+] Socket SYN burst finished. Attempts: {sent}")


def trigger_port_scan(target: str, start_port: int, end_port: int) -> None:
    """Scan distinct TCP ports sequentially to trigger Port Scan detector."""
    host = _validate_target_host(target)
    print(f"[!] Scanning TCP ports {start_port}-{end_port} on {host}...")
    scanned = 0
    for port in range(start_port, end_port + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.05)
        try:
            s.connect_ex((host, port))
            scanned += 1
        except OSError:
            pass
        finally:
            s.close()
    print(f"[+] Port scan finished ({scanned} ports probed)")


def trigger_udp_flood(target: str, port: int, duration: int) -> None:
    """Send sustained UDP packet burst to trigger Traffic Spike / UDP flood detector."""
    host = _validate_target_host(target)
    print(f"[!] Launching UDP flood against {host}:{port} for {duration}s...")
    payload = b"S" * 1024
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    deadline = time.time() + duration
    sent = 0
    try:
        while time.time() < deadline:
            try:
                sock.sendto(payload, (host, port))
                sent += 1
            except OSError:
                time.sleep(0.01)
    finally:
        sock.close()
    print(f"[+] UDP flood finished. Datagrams sent: {sent}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelX Lab Attack & Traffic Generator")
    parser.add_argument(
        "mode",
        choices=[
            "normal",
            "flood",
            "cpu-stress",
            "memory-stress",
            "syn-flood",
            "port-scan",
            "udp-flood",
        ],
        help="Simulation mode",
    )
    parser.add_argument("--target", default="http://sentinelx_lb:8080", help="Target URL or IP")
    parser.add_argument("--port", type=int, default=8080, help="Destination port for L4 tests")
    parser.add_argument("--start-port", type=int, default=8000, help="Start port for port-scan")
    parser.add_argument("--end-port", type=int, default=8050, help="End port for port-scan")
    parser.add_argument("--rate", type=float, default=2.0, help="Request rate (req/s) for normal mode")
    parser.add_argument("--concurrency", type=int, default=30, help="Concurrency level for flood")
    parser.add_argument("--duration", type=int, default=15, help="Duration in seconds")
    parser.add_argument("--mb", type=int, default=256, help="Memory to allocate (MB)")

    args = parser.parse_args()

    if args.mode == "normal":
        asyncio.run(simulate_normal_traffic(args.target, rate=args.rate))
    elif args.mode == "flood":
        asyncio.run(simulate_http_flood(args.target, concurrency=args.concurrency, duration=args.duration))
    elif args.mode == "cpu-stress":
        trigger_backend_cpu_stress(args.target, duration=args.duration)
    elif args.mode == "memory-stress":
        trigger_backend_memory_stress(args.target, mb=args.mb)
    elif args.mode == "syn-flood":
        trigger_syn_flood(args.target, port=args.port, duration=args.duration)
    elif args.mode == "port-scan":
        trigger_port_scan(args.target, start_port=args.start_port, end_port=args.end_port)
    elif args.mode == "udp-flood":
        trigger_udp_flood(args.target, port=args.port, duration=args.duration)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
        sys.exit(0)
