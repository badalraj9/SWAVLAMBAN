# Swavlamban 2025 - Design Notes

## 1. Problem & Constraints

The challenge requires a fully distributed swarm coordination system operating under severe constraints:
-   **Fully Distributed**: No central server; all consensus must be peer-to-peer.
-   **Lossy Communication**: Simulated radio link with packet loss, latency jitter, and bandwidth limits (≤64 kbps).
-   **Real-Time Performance**: The system must maintain a ≥10 Hz update loop.
-   **Adversarial Environment**: The system must survive node failures, partitions, and malicious behavior.

Our solution prioritizes **simplicity as a reliability feature**. By avoiding complex cryptographic overhead or heavy consensus protocols (like Paxos/Raft), we ensure the system meets the strict real-time and bandwidth requirements while maintaining robustness.

## 2. Architecture Overview

### Leader Election: Modified Bully Algorithm
We utilize a Bully Algorithm optimized for lossy networks.
-   **State Machine**: Nodes transition between `FOLLOWER`, `CANDIDATE`, and `LEADER`.
-   **Timeout-Based**: Failure detection relies on heartbeat/coordinator message timeouts.
-   **Optimization**: Instead of broadcasting to all, we target higher-ID nodes first to reduce message complexity.

### Task Allocation: CBAA (Consensus-Based Auction Algorithm)
Tasks are allocated using a market-based approach.
-   **Bidding**: Agents bid on tasks based on capability matching and random tie-breaking.
-   **Convergence**: Agents exchange bid maps and converge on a conflict-free assignment using the "Max-Consensus" rule.
-   **Capability-Aware**: Agents only bid on tasks for which they possess the required capabilities (e.g., "heavy_lift").

### Event-Driven Communication
-   **Asynchronous Processing**: Messages are processed in a non-blocking loop to ensure the 10 Hz cycle is never stalled.
-   **Message Types**: `ELECTION`, `ANSWER`, `COORDINATOR` (Election); `CBAA_UPDATE` (Tasking); `HEARTBEAT` (Liveness).

## 3. Adversarial Testing & Discovery

During the "Hell-Test" phase, our adversarial agent identified three critical vulnerabilities:

1.  **Byzantine Spoofing**: A malicious node could impersonate the elected leader by sending `COORDINATOR` messages with the leader's ID.
2.  **Coordinator Spam**: A compromised node could flood the network with valid-looking leadership claims, consuming bandwidth.
3.  **Stale Leader Replay**: Old messages from a previous term could be replayed to confuse the swarm.

These findings drove the hardening strategy described below.

### Risk Scoring: Custom RPN
`attack_plan.json` uses `priority = impact*likelihood/detectability`, not standard `impact*likelihood*detectability`. In this threat model low detectability amplifies risk by division, while high detectability is protective and lowers priority. E.g. H1 `10*8/5=16` is intentional, not a typo for `400`.

### Clarification: Leader ID Artifact
In the provided simulator logs, the "Leader" is often identified by the highest ID active in the network. During adversarial testing, a malicious agent (e.g., Agent 9) may continue to broadcast leadership claims. While the simulator might log "Agent 9" as the leader due to its high ID, **honest agents reject these messages** if they fail the security checks (UUID mismatch or stale term). Thus, leadership authority is determined by *message acceptance*, not merely by the sender's ID.

## 4. Minimal Hardening Strategy

We implemented a "Lightweight Legitimacy" layer to address the discovered vulnerabilities without introducing heavy cryptography or violating the "No Persistence" constraint.

| Design Choice | Rationale |
| :--- | :--- |
| **No PBFT / Raft** | Full consensus protocols are too heavy for the ≤64 kbps / 10Hz constraint. The probability of Byzantine failure is lower than the cost of stalling the network. |
| **No TLS / Signatures** | Asymmetric crypto (RSA/ECC) exceeds the CPU budget for 10Hz loops on embedded hardware. |
| **UUID + Term Binding** | **Primary Defense**. Each leader generates a random `boot_uuid` and a monotonic `term`. Followers bind the Leader ID to this UUID. If the UUID changes (spoofing) or term regresses (replay), the message is rejected. |
| **Coordinator Rate-Limit** | Honest agents ignore excessive coordinator claims from the same ID, neutralizing spam attacks. |

## 5. Operational Doctrine Alignment

This section details how the system complies with Indian Navy operational philosophy, prioritizing mission continuity and disciplined behavior under stress.

### Mission Continuity Over Optimality
In scenarios of command instability (e.g., frequent leader elections or "storms"), the swarm enters a **Mission Continuity Mode**.
-   **Behavior**: It freezes task assignments to prevent thrashing and suppresses new election attempts unless the leader completely disappears.
-   **Rationale**: It is better to execute a sub-optimal plan reliably than to continuously re-optimize without action.

### Explicit Degraded Operations Handling
The system explicitly tracks its operational state (`NORMAL` vs `DEGRADED`).
-   **Trigger**: High instability or packet loss enters `DEGRADED` mode.
-   **Response**: Agents adopt a conservative posture, refraining from aggressive bidding and minimizing network chatter.
-   **Logging**: Transitions are explicitly logged (`STATE: ENTERING DEGRADED OPERATIONS MODE`) to ensure situational awareness.

### Restrained Leadership Authority
Leadership is treated as advisory rather than absolute during degraded states.
-   **Local Safety**: Agents verify capability matches and deadline feasibility before accepting tasks.
-   **Refusal**: Agents may silently refuse tasking if it violates safety constraints or occurs during a degraded state, preventing blind obedience to potentially compromised or unstable commands.

The swarm encodes naval doctrine by continuing operations under degraded command rather than aggressively re-optimizing.

## 6. Known Limitations

-   **Crash Recovery**: The system assumes stable execution epochs. If a leader crashes and restarts, it generates a new UUID. Followers will treat this as a new entity. While this ensures security against spoofing, it may require a new election cycle to fully re-establish authority.
-   **Persistent Identity**: Persistent identity across hard reboots is outside the scope of this submission. We prioritize the security of the *current* mission over state preservation across power cycles.
