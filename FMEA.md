# SWARM-01 FMEA — Failure Modes & Effects Analysis

| # | Failure Mode | Detection Method | System Response | Residual Risk |
|---|--------------|------------------|-----------------|---------------|
| F1 | Node crash | Heartbeat timeout `cbaa_agent.py:32` + `coordinator_timeout` `bully_agent.py:62` | Release tasks `cbaa_agent.py:40`; re-elect leader `bully_agent.py:64` | Quorum loss if >f nodes crash; audit log loss |
| F2 | Leader crash | `last_leader_msg` >2s `bully_agent.py:62` | `start_election` → `declare_victory`; BFT quorum `bully_agent.py:125` | 2-4s blackout; election storm if rapid kills |
| F3 | Network partition | No `COORDINATOR` in partition; `HellSimulator` partition groups | Per-partition leader elected; heal merges on `clear_partition` | Split-brain until heal; no auto-merge conflict resolution |
| F4 | Jamming / 50% loss | `drop_rate` `simulator.py:74`; `DEGRADED` flag `bully_agent.py:45` | Freeze CBAA `cbaa_agent.py:54`; 4s timeout `bully_agent.py:50` | Convergence stalls; WCET violated |
| F5 | Message latency 500ms | `delayed_messages` `simulator.py:76` | Async loop `base_agent.py:38` non-blocking 10Hz | Stale bids; need seeded replay for debug |
| F6 | Spoofed COORDINATOR | UUID+term check `bully_agent.py:168` | Reject + `SECURITY` warning; rate-limit `bully_agent.py:171` | Single-source trust pre-BFT |
| F7 | Replay stale term | `msg_term < record` `bully_agent.py:164` | Ignore | Term overflow not bounded |
| F8 | Coordinator spam | Rate 1/0.2s `bully_agent.py:171` | Ignore | Queue growth `VULN-002` |
| F9 | Election storm | `leader_changes` window `bully_agent.py:40` | `DEGRADED` suppress elections 4s | TUNABLE: thresholds `instability_threshold=2/15s`, `coordinator_timeout 2s->4s`, `stability_reset 30s` (`bully_agent.py:33-35,70`). Known trigger-happy: 2 legit re-elections in 15s trips DEGRADED. Measure via `python scripts/measure_degraded.py hell_test.log`. Livelock if storm persists >30s |
| F10 | Byzantine leader (f≤3) | BFT quorum `(n+f)//2+1` `bully_agent.py:129` + `BFT_VOTE` | Require quorum before `COMMIT`; fake leader never reaches quorum (e.g. 7/10) | BFT-lite only covers leader, not CBAA bids |
| F11 | Byzantine CBAA bid | None yet | Max-consensus blindly accepts `y` `cbaa_agent.py:106` | Malicious high bid hijacks all tasks |
| F12 | Clock skew / NTP jump | None (`time.time` `base_agent.py:37`) | Timeout false trigger | Use `monotonic` + `TAMPER_LOG` verify |
| F13 | Audit log tamper | `TamperEvidentLog.verify` `utils/tamper_log.py:18` | Detection `(False, idx)`; chain break | No auto-recovery; manual forensics |

**Mitigated:** F1-F10 (BFT-lite closes F10 partially)
**Open:** F11-F13 → next upgrades: signed CBAA bids (HMAC), monotonic clock, checkpoint replication.
