"""Health-reporting agent. Run one per monitored host.

  python3 agent.py --id h1 --server 10.0.0.100
  python3 agent.py --id h2 --server 10.0.0.100 --force-cpu 95   # controlled alert test
"""
import argparse, json, socket, time
import psutil
from protocol import REPORT_PORT, ALERT_PORT, encode


def collect(force_cpu=None):
    net = psutil.net_io_counters()
    return {
        "cpu_percent": force_cpu if force_cpu is not None else psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "process_count": len(psutil.pids()),
        "network_rx_bytes": net.bytes_recv,
        "network_tx_bytes": net.bytes_sent,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="host id, e.g. h1")
    ap.add_argument("--server", required=True, help="collector IP")
    ap.add_argument("--thresholds", default="thresholds.json")
    ap.add_argument("--interval", type=float, default=None, help="override report interval (s)")
    ap.add_argument("--force-cpu", type=float, default=None, help="fake CPU %% to trigger alerts in tests")
    ap.add_argument("--count", type=int, default=0, help="stop after N reports (0 = forever)")
    a = ap.parse_args()

    with open(a.thresholds) as f:
        th = json.load(f)
    interval = a.interval or th["report_interval_seconds"]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    psutil.cpu_percent(interval=None)  # prime: first call always returns 0.0
    seq = alert_seq = 0
    print(f"[{a.id}] sending to {a.server}:{REPORT_PORT} every {interval}s", flush=True)
    try:
        while a.count == 0 or seq < a.count:
            time.sleep(interval)
            stats = collect(a.force_cpu)
            msg = {"host_id": a.id, "seq": seq, "timestamp": time.time(), **stats}
            try:
                sock.sendto(encode(msg), (a.server, REPORT_PORT))
                if stats["cpu_percent"] >= th["cpu_percent"] or stats["memory_percent"] >= th["memory_percent"]:
                    alert = {**msg, "seq": alert_seq, "timestamp": time.time(), "reason": "threshold_exceeded"}
                    sock.sendto(encode(alert), (a.server, ALERT_PORT))
                    alert_seq += 1
                    print(f"[{a.id}] CRITICAL alert sent (cpu={stats['cpu_percent']}%)", flush=True)
            except OSError as e:
                print(f"[{a.id}] send failed: {e}", flush=True)
            seq += 1
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
