# Remote System Health Monitoring (UDP + Mininet + SDN) - Group 8, Project 11

UDP agents on Mininet hosts send CPU / memory / process / network stats to a central server.
A Ryu SDN controller gives critical alert traffic (UDP 9998) higher flow priority and DSCP 46 marking
than normal reports (UDP 9999).

## Layout
| File | Purpose |
|---|---|
| protocol.py | message format + validation (ports 9999 reports, 9998 critical alerts) |
| agent.py | runs on each monitored host, sends reports, fires critical alerts |
| server.py | collector: tracks hosts, thresholds, node-down timeout, CSV log |
| thresholds.json | CPU/mem thresholds, report interval, timeout |
| topology.py | Mininet: h1,h2,h3 - s2 - s1 - srv, remote controller 127.0.0.1:6653 |
| sdn_controller/controller.py | Ryu learning switch + priority flows |
| tests/ | unit tests + manual test cases below |
| results/ | CSV logs, screenshots, graphs |

## Setup (Ubuntu 20.04/22.04)
    sudo apt update
    sudo apt install -y mininet openvswitch-switch python3-pip python3-psutil git wireshark
    sudo mn          # then: pingall, exit      (clean up with: sudo mn -c)
    pip3 install ryu # if this fails on your Python version, use a python3.9 venv or POX

## Run (3 terminals, from the repo folder)
    # T1
    ryu-manager sdn_controller/controller.py
    # T2
    sudo python3 topology.py
    # in the mininet> prompt
    pingall
    srv python3 server.py > results/server.out 2>&1 &
    h1 python3 agent.py --id h1 --server 10.0.0.100 &
    h2 python3 agent.py --id h2 --server 10.0.0.100 &
    h3 python3 agent.py --id h3 --server 10.0.0.100 &
    # T3 (while traffic is running; flows expire after 60 s idle)
    sudo ovs-ofctl -O OpenFlow13 dump-flows s1
    sudo ovs-ofctl -O OpenFlow13 dump-flows s2

## D1 test cases
| # | Test | How | Expected |
|---|---|---|---|
| T1 | Connectivity | `pingall` | 0% loss |
| T2 | One agent | server + `h1` agent | reports printed, latency shown |
| T3 | Multiple agents | h1,h2,h3 together | 3 host ids tracked separately |
| T4 | Threshold / critical alert | `h2 python3 agent.py --id h2 --server 10.0.0.100 --force-cpu 95 &` | CPU HIGH + CRITICAL ALERT on server |
| T5 | Malformed packet | `h1 python3 -c "import socket;socket.socket(2,2).sendto(b'junk',('10.0.0.100',9999))"` | server prints [malformed], keeps running |
| T6 | Node failure | stop one agent (Ctrl-C / kill its process) | `NODE DOWN` after timeout_seconds |
| T7 | SDN flows | `dump-flows s1` | priority=300 udp_dst=9998 (set_field dscp 46), priority=200 udp_dst=9999 |
| T8 | Wireshark | capture on `srv-eth0` / `s1-eth1` | UDP 9999 and 9998 packets, DSCP 46 on 9998 |

Unit tests: `python3 -m unittest tests.test_protocol`

## Notes for the report
- Latency = server receive time minus agent send timestamp (all Mininet hosts share one clock).
- CPU / memory come from the shared VM; network counters are per Mininet host (own namespace). Say so.
- UDP gives no delivery guarantee; lost reports are counted from sequence-number gaps.
- D1 prioritisation = flow priority + DSCP marking. Real bandwidth queues (OVS QoS) belong to D2.
