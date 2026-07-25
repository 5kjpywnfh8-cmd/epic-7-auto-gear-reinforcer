"""Offline, redacted PCAP timing probe for the MuMu capture reader.

The probe only counts TCP payload bytes in a capture-relative time window. It
never prints packet contents or submits captured data to an external service.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def payload_window_bytes(pcap_path: Path, start_seconds: float, end_seconds: float) -> int:
    """Return TCP payload bytes in one capture-relative time window."""
    from scapy.all import IP, Raw, TCP, rdpcap

    packets = rdpcap(str(pcap_path))
    if not packets:
        return 0
    origin = float(packets[0].time)
    total = 0
    for packet in packets:
        offset = float(packet.time) - origin
        if start_seconds <= offset < end_seconds and IP in packet and TCP in packet and Raw in packet:
            total += len(bytes(packet[Raw].load))
    return total


def has_post_entry_sync_candidate(
    pcap_path: Path,
    start_seconds: float = 60.0,
    end_seconds: float = 120.0,
    minimum_bytes: int = 100_000,
) -> bool:
    """Return whether the window contains a large TCP sync candidate."""
    return payload_window_bytes(pcap_path, start_seconds, end_seconds) >= minimum_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline MuMu PCAP sync timing probe")
    parser.add_argument("pcap", type=Path)
    parser.add_argument("--start-seconds", type=float, default=60.0)
    parser.add_argument("--end-seconds", type=float, default=120.0)
    parser.add_argument("--minimum-bytes", type=int, default=100_000)
    args = parser.parse_args()
    observed = payload_window_bytes(args.pcap, args.start_seconds, args.end_seconds)
    candidate = observed >= args.minimum_bytes
    print({"post_entry_payload_bytes": observed, "sync_candidate": candidate})
    return 0 if candidate else 1


if __name__ == "__main__":
    raise SystemExit(main())
