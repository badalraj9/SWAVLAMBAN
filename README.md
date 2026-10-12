# SWARM-01 · Distributed Swarm Coordination + Multi-LLM Debate

> Self-healing leader election, auction-based task allocation, and adversarial verification —
> plus a 4-model debate harness with a live terminal UI.

---

## ✨ What this is

| Subsystem | What it does |
|---|---|
| **🤖 Swarm (`src/`)** | Fully distributed drone-swarm coordination: Bully leader election, CBAA task auction, BFT-lite commit, UDP networking, chaos-tested to 50% packet loss |
| **💬 Debate (`debate_core.py` + `debate.py`)** | Fans one topic out to 4 LLMs in parallel (OpenRouter ×2, Groq, NVIDIA NIM), runs 3 debate rounds, tallies confidence-weighted votes with a live rich CLI |

---

## 🧠 Concepts implemented

### Leader election — Modified Bully Algorithm
`src/agents/bully_agent.py` · States `FOLLOWER → CANDIDATE → LEADER`.
Highest-ID wins. Followers detect leader silence via heartbeat timeout and start
elections; candidates that hear no `ANSWER` declare victory with `COORDINATOR`.

### BFT-lite commit — quorum before authority
A leader claim only commits after `(n+f)//2 + 1` votes (`f = (n−1)//3`),
collected through a propose/vote exchange (`BFT_VOTE`) with vote expiry.
One `COORDINATOR` message counts as exactly one vote — the receiver's own
corroboration is a separate, explicit step.

### Identity binding — spoof / replay / spam resistance
Every election message carries a random `boot_uuid` plus a monotonic `term`
(incremented once per election, at election start). Followers reject UUID
mismatches, stale terms, and rate-limit coordinator claims.

### Task allocation — Consensus-Based Auction (CBAA)
`src/agents/cbaa_agent.py` · Agents bid `value / (1 + distance)` on tasks,
converge through the max-consensus rule, break ties by higher ID, and only bid
on tasks matching their capabilities (e.g. `heavy_lift`).

### Failure detection over the socket
Heartbeats flow over real UDP; leader timeouts read `transport.last_seen()`,
so "leader is unresponsive" means *no packets arrived* — not an in-memory timer.

### Pluggable transport
`src/utils/transport.py` · One interface, two backends:

| | `QueueTransport` | `UDPTransport` |
|---|---|---|
| Use | deterministic tests | real networking |
| Wire | in-process queues | `SOCK_DGRAM` JSON-over-UDP |
| Addressing | `plug()` peers | `BASE_PORT + agent_id` (override via `SWARM_BASE_PORT`) |
| Loss | — | seeded `Random(seed + agent_id)` drop before `sendto()` |
| Broadcast | fan-out | unicast loop over `peer_ids` (documented: fine ≤10 nodes, needs multicast beyond) |

### Tamper-evident audit log
`src/utils/tamper_log.py` · Hash-chained, single-hash entry scheme with
`verify()` that pinpoints the first tampered index.

### Graceful degradation
Election storms (≥2 leader changes / 15 s) flip the swarm to `DEGRADED`:
task reassignment freezes, timeouts relax `2 s → 4 s`, recovery after 30 s calm.
The agent loop also self-monitors WCET/P99 cycle times. Thresholds are tunable —
see `FMEA.md` and `scripts/measure_degraded.py`.

### Chaos harness & scoring
Multiprocessing switchboard with drop/latency injection, network partitions,
malicious agents (spoof/spam/silent), gate verifiers, and a weighted
`Evaluator` (`0.5·value + 0.3·distance + 0.2·bytes`). Risk priorities use a
documented custom RPN: `impact × likelihood / detectability`.

---

## 🏗️ Architecture

```
                    ┌─────────────┐
                    │  Simulator  │  switchboard · drop/latency · partitions
                    │ (processes) │  audit log · kill_agent · step()
                    └──────┬──────┘
                           │ Transport (Queue | UDP/JSON)
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  ┌───────────┐      ┌───────────┐      ┌───────────┐
  │  Agent N  │      │  Agent N+1│  ... │  Agent N+k│
  │ Bully+BFT │      │ Bully+BFT │      │ Bully+BFT │
  │ CBAA bid  │      │ CBAA bid  │      │ CBAA bid  │
  └───────────┘      └───────────┘      └───────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
              ┌────────────────────────┐
              │ Tamper-evident audit   │──▶ frontend/ (read-only visualizer)
              │ Evaluator (0.5/0.3/0.2)│──▶ HELL_TEST_REPORT_FINAL.md
              └────────────────────────┘

  debate.py (rich Live CLI: spinners · panels · tally bars)
      │ events (on_agent_start/response, on_round_start/complete)
      ▼
  debate_core.py ──parallel fan-out──▶ OpenRouter ×2 · Groq · NVIDIA NIM
      │ 3 rounds: propose → debate → vote · confidence-weighted tally
      ▼  debate_transcript_<ts>.json
```

### Repo map

```
src/
  agents/       base_agent.py · bully_agent.py · cbaa_agent.py · swarm_agent.py · trivial_agent.py
  simulation/   simulator.py · evaluator.py · scenarios.py
  utils/        transport.py · message.py · tamper_log.py
tests/          hell_runner.py · hell_test_suite.py · gate{1..4}_verifier.py · test_bft_fixes.py · …
scripts/        check_confidence.py · measure_degraded.py
frontend/       serve.py · index.html          # read-only log visualizer
debate_core.py  headless orchestrator (no UI imports)
debate.py       rich CLI — consumes orchestrator events only
probe.py        endpoint probe: --check N · --try SLOT MODEL · --list-groq
.env.example    4 agent slots (keys/models blank — you fill them)
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+ · `pip install -r requirements.txt`

### 1 · Swarm chaos tests
```bash
export PYTHONPATH=$PYTHONPATH:.          # Windows: $env:PYTHONPATH="$pwd"
python -m pytest tests/test_bft_fixes.py tests/test_integration_mvs.py -v
python tests/hell_runner.py              # full adversarial suite → hell_test.log
```

### 2 · UDP mode
```bash
SWARM_BASE_PORT=50000 python <your_entry>   # one fixed port per agent: BASE_PORT + agent_id
```
Bump `SWARM_BASE_PORT` per session if two suites share a machine.

### 3 · Visualizer
```bash
python frontend/serve.py                 # → http://localhost:8000 (read-only, reads hell_test.log)
```

### 4 · LLM debate
```bash
cp .env.example .env        # fill keys + models
python probe.py             # one cheap call per endpoint — verify before a full run
python debate.py "Should AI coding assistants auto-apply edits or always ask first?"
python debate.py            # no arg → single interactive prompt (TTY only; CI prints usage)
```
Single-model probe: `python probe.py --try 3 qwen/qwen3.8-27b 90`
List live Groq models: `python probe.py --list-groq`

---

## 📊 Verification

| Gate | Result |
|---|---|
| Leader re-election | **< 4 s** (limit 10 s) |
| Task stability | **> 99%** (goal 95%) |
| Real-time loop | **10 Hz** (100 ms budget, P99 tracked) |
| Packet loss | **survives 50%** |
| Byzantine spoof / replay / spam | **blocked / rejected / rate-limited** |
| Confidence score | **0.9575** — `scripts/check_confidence.py` fails CI on drift vs the report |

Debate harness verified headless: 3 rounds × 4 agents = 12 calls, event counts
asserted without network (`NullEvents`).

---

## ⚙️ Configuration

| Var | Meaning |
|---|---|
| `AGENT_{1..4}_BASE_URL` | OpenAI-compatible endpoint |
| `AGENT_{1..4}_API_KEY` | key (never committed — `.env` is git-ignored) |
| `AGENT_{1..4}_MODEL` | model ID, pure config — no defaults, no hardcoding |
| `SWARM_BASE_PORT` | UDP base port (default `50000`) |

One client path handles all providers: `OpenAI(base_url=…, api_key=…)` —
no provider branching.

---

## ⚠️ Known limitations

- UDP broadcast is a unicast loop over `peer_ids` — add agents by updating peer lists; real multicast needed past ~10 nodes.
- BFT-lite covers leader claims only; CBAA bids are unsigned (see `FMEA.md` F11).
- Free-text vote positions split the tally on paraphrases; enumerated-option voting is the planned fix.
- Clocks use `time.time()` — NTP jumps can false-trigger timeouts (F12).

---

## 📂 Further reading

- **[DESIGN_NOTES.md](DESIGN_NOTES.md)** — architecture decisions, hardening, custom RPN rationale
- **[FMEA.md](FMEA.md)** — failure modes, tunable DEGRADED thresholds, residual risks
- **[HELL_TEST_REPORT_FINAL.md](HELL_TEST_REPORT_FINAL.md)** — adversarial results
- **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)** — 5-minute demo narrative

## 📜 License
Unclassified / Open Source for Swavlamban 2025.
