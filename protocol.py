"""Shared UDP message format (agreed by all 3 members).

Two UDP ports are used so the SDN controller can tell the traffic apart:
  REPORT_PORT (9999) - normal periodic health reports
  ALERT_PORT  (9998) - critical alerts sent immediately by an agent (prioritised by SDN)
"""
import json

REPORT_PORT = 9999
ALERT_PORT = 9998
MAX_SIZE = 1024

NUM = (int, float)
REQUIRED = {
    "host_id": str,
    "seq": int,
    "timestamp": NUM,
    "cpu_percent": NUM,
    "memory_percent": NUM,
    "process_count": int,
    "network_rx_bytes": int,
    "network_tx_bytes": int,
}


def encode(msg: dict) -> bytes:
    return json.dumps(msg, separators=(",", ":")).encode("utf-8")


def decode(data: bytes) -> dict:
    """Parse and validate a datagram. Raises ValueError if it is malformed."""
    if len(data) > MAX_SIZE:
        raise ValueError("datagram too large")
    try:
        msg = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"not valid JSON: {e}")
    if not isinstance(msg, dict):
        raise ValueError("JSON root is not an object")
    for key, typ in REQUIRED.items():
        if key not in msg:
            raise ValueError(f"missing field '{key}'")
        if isinstance(msg[key], bool) or not isinstance(msg[key], typ):
            raise ValueError(f"wrong type for '{key}'")
    for key in ("cpu_percent", "memory_percent"):
        if not 0 <= msg[key] <= 100:
            raise ValueError(f"'{key}' out of range")
    return msg
