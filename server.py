"""Central monitoring server (collector). Run on srv.

  python3 server.py
Listens on UDP 9999 (reports) and UDP 9998 (critical alerts), tracks every host,
flags missing hosts after a timeout, and logs everything to results/server_log.csv
"""
import argparse, csv, json, os, socket, threading, time
from protocol import REPORT_PORT, ALERT_PORT, decode

lock = threading.Lock()
hosts = {}          # host_id -> state dict
malformed = 0


def listener(port, kind, th, writer, fh):
    global malformed
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    print(f"listening on UDP {port} ({kind})", flush=True)
    while True:
        data, addr = sock.recvfrom(2048)
        recv_t = time.time()
        try:
            m = decode(data)
        except ValueError as e:
            with lock:
                malformed += 1
            print(f"[malformed] from {addr[0]}: {e}", flush=True)
            continue
        latency_ms = (recv_t - m["timestamp"]) * 1000
        hid = m["host_id"]
        with lock:
            st = hosts.setdefault(hid, {"received": 0, "lost": 0, "last_seq": -1,
                                        "last_seen": recv_t, "down": False, "alerts": 0})
            if st["down"]:
                print(f"*** NODE RECOVERED: {hid}", flush=True)
                st["down"] = False
            st["last_seen"] = recv_t
            if kind == "report":
                if m["seq"] > st["last_seq"] + 1 and st["last_seq"] >= 0:
                    st["lost"] += m["seq"] - st["last_seq"] - 1   # gap in sequence = lost datagrams
                st["last_seq"] = m["seq"]
                st["received"] += 1
                flags = []
                if m["cpu_percent"] >= th["cpu_percent"]:
                    flags.append("CPU HIGH")
                if m["memory_percent"] >= th["memory_percent"]:
                    flags.append("MEM HIGH")
                print(f"[{hid}] seq={m['seq']} cpu={m['cpu_percent']:.1f}% mem={m['memory_percent']:.1f}% "
                      f"procs={m['process_count']} rx={m['network_rx_bytes']} lat={latency_ms:.2f}ms "
                      f"{'| ' + ', '.join(flags) if flags else '| NORMAL'}", flush=True)
            else:
                st["alerts"] += 1
                print(f"!!! CRITICAL ALERT from {hid}: cpu={m['cpu_percent']:.1f}% "
                      f"mem={m['memory_percent']:.1f}% alert_latency={latency_ms:.2f}ms", flush=True)
            writer.writerow([f"{recv_t:.6f}", kind, hid, m["seq"], m["cpu_percent"], m["memory_percent"],
                             m["process_count"], m["network_rx_bytes"], m["network_tx_bytes"], f"{latency_ms:.3f}"])
            fh.flush()


def monitor(timeout, writer, fh):
    while True:
        time.sleep(1)
        now = time.time()
        with lock:
            for hid, st in hosts.items():
                if not st["down"] and now - st["last_seen"] > timeout:
                    st["down"] = True
                    print(f"*** NODE DOWN: {hid} (no update for {now - st['last_seen']:.1f}s)", flush=True)
                    writer.writerow([f"{now:.6f}", "down", hid, "", "", "", "", "", "", ""])
                    fh.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thresholds", default="thresholds.json")
    ap.add_argument("--csv", default="results/server_log.csv")
    a = ap.parse_args()
    with open(a.thresholds) as f:
        th = json.load(f)
    os.makedirs(os.path.dirname(a.csv) or ".", exist_ok=True)
    fh = open(a.csv, "w", newline="")
    writer = csv.writer(fh)
    writer.writerow(["recv_time", "kind", "host_id", "seq", "cpu", "mem", "procs", "rx_bytes", "tx_bytes", "latency_ms"])
    for port, kind in ((REPORT_PORT, "report"), (ALERT_PORT, "alert")):
        threading.Thread(target=listener, args=(port, kind, th, writer, fh), daemon=True).start()
    threading.Thread(target=monitor, args=(th["timeout_seconds"], writer, fh), daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        with lock:
            print("\n--- summary ---")
            for hid, st in hosts.items():
                print(f"{hid}: received={st['received']} lost={st['lost']} alerts={st['alerts']} down={st['down']}")
            print(f"malformed datagrams: {malformed}")


if __name__ == "__main__":
    main()
