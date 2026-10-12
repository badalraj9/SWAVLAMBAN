from src.agents.base_agent import BaseAgent, AgentState, OperationalMode
from src.utils.message import Message
import time
import random


class BullyAgent(BaseAgent):
    def __init__(
        self,
        agent_id,
        incoming_queue=None,
        outgoing_queue=None,
        num_agents: int = 0,
        seed: int = 42,
        transport=None,
    ):
        super().__init__(
            agent_id, incoming_queue, outgoing_queue, num_agents=num_agents,
            seed=seed, transport=transport,
        )
        self.seed = seed
        self.rng = random.Random(seed)
        self.leader_id = None
        self.coordinator_timeout = 2.0
        self.election_timeout = 1.0
        self.last_leader_msg = time.time()
        self.election_start_time = 0.0
        self.waiting_for_answer = False

        self.boot_uuid = f"{self.rng.getrandbits(32):08x}"
        self.term = 0
        self.known_leaders = {}

        self.leader_changes = []
        self.instability_threshold = 2
        self.instability_window = 15.0
        self.stability_reset_time = 30.0

        self.bft_enabled = True
        self.pending_proposals = {}
        self.vote_pool = {}
        self.vote_expiry = 3.0

    def update_state(self):
        current_time = time.time()
        if self.bft_enabled and self.pending_proposals:
            expired = [
                k
                for k, t in self.pending_proposals.items()
                if current_time - t > self.vote_expiry
            ]
            for k in expired:
                self.pending_proposals.pop(k, None)
                self.vote_pool.pop(k, None)

        # Operational Mode Logic
        # 1. Prune old changes
        self.leader_changes = [
            t
            for t in self.leader_changes
            if current_time - t <= self.instability_window
        ]

        # 2. Check Instability
        is_unstable = len(self.leader_changes) >= self.instability_threshold

        if is_unstable:
            if self.mode != OperationalMode.DEGRADED:
                self.mode = OperationalMode.DEGRADED
                self.logger.info("STATE: ENTERING DEGRADED OPERATIONS MODE")
                # Adjust params for degraded mode
                self.coordinator_timeout = 4.0  # Suppress elections (doubled)
        else:
            # Check exit condition: Stable for >= 30s
            last_change = self.leader_changes[-1] if self.leader_changes else 0
            if self.mode == OperationalMode.DEGRADED:
                if current_time - last_change > self.stability_reset_time:
                    self.mode = OperationalMode.NORMAL
                    self.logger.info("STATE: RETURNING TO NORMAL OPERATIONS MODE")
                    self.coordinator_timeout = 2.0  # Restore

        # Check leader timeout
        if self.state == AgentState.FOLLOWER:
            if current_time - self.last_leader_msg > self.coordinator_timeout:
                self.logger.info("Leader timed out. Starting election.")
                self.start_election()

        elif self.state == AgentState.CANDIDATE:
            if self.waiting_for_answer:
                if current_time - self.election_start_time > self.election_timeout:
                    self.declare_victory()

        elif self.state == AgentState.LEADER:
            if (
                getattr(self, "last_broadcast", 0) == 0
                or current_time - self.last_broadcast > 0.5
            ):
                # Include Identity & Term
                content = {
                    "id": self.agent_id,
                    "uuid": self.boot_uuid,
                    "term": self.term,
                }
                self.send_message(-1, "COORDINATOR", content)
                self.last_broadcast = current_time

    def start_election(self):
        self.state = AgentState.CANDIDATE
        self.election_start_time = time.time()
        self.waiting_for_answer = True
        self.leader_id = None

        self.term += 1  # New election term
        content = {"id": self.agent_id, "uuid": self.boot_uuid, "term": self.term}
        self.send_message(-1, "ELECTION", content)

    def declare_victory(self):
        self.state = AgentState.LEADER
        self.leader_id = self.agent_id
        self.waiting_for_answer = False
        self.logger.info("Declaring victory. I am the leader.")
        content = {"id": self.agent_id, "uuid": self.boot_uuid, "term": self.term}
        self.send_message(-1, "COORDINATOR", content)
        # Self-elected leader change logic? No, only track changes when we accept *others*.
        # Or should we track our own change?
        # If I become leader, it IS a change.
        self.leader_changes.append(time.time())

    def _quorum_size(self):
        n = self.num_agents if self.num_agents else max(4, len(self.known_leaders) + 1)
        f = (n - 1) // 3
        return (n + f) // 2 + 1

    def _refresh_leader_seen(self):
        t = getattr(self, "transport", None)
        if t is not None and self.leader_id is not None:
            seen = t.last_seen(self.leader_id)
            if seen:
                self.last_leader_msg = seen
                return
        self.last_leader_msg = time.time()

    def _proposal_key(self, leader_id, term, uuid_val):
        return (leader_id, term, uuid_val)

    def cast_local_vote(self, key):
        voters = self.vote_pool.setdefault(key, set())
        voters.add(self.agent_id)
        return self._try_commit(key)

    def _try_commit(self, key):
        waiters = self.vote_pool.get(key, set())
        if len(waiters) >= self._quorum_size():
            leader_id, term, _ = key
            if self.leader_id != leader_id:
                self.leader_changes.append(time.time())
            self.state = AgentState.FOLLOWER
            self.leader_id = leader_id
            self._refresh_leader_seen()
            self.waiting_for_answer = False
            self.logger.info(
                f"BFT COMMIT leader={leader_id} term={term} votes={len(waiters)}/{self._quorum_size()}"
            )
            self.pending_proposals.pop(key, None)
            self.vote_pool.pop(key, None)
            return True
        return False

    def handle_message(self, msg: Message):
        if msg.msg_type == "BFT_VOTE":
            prop = msg.content
            key = self._proposal_key(
                prop["proposed_id"], prop["term"], prop.get("uuid")
            )
            voters = self.vote_pool.setdefault(key, set())
            voters.add(msg.sender_id)
            self.neighbor_heartbeats[msg.sender_id] = (
                time.time() if hasattr(self, "neighbor_heartbeats") else time.time()
            )
            self._try_commit(key)
            return

        if msg.msg_type in ["ELECTION", "ANSWER", "COORDINATOR"]:
            if "id" not in msg.content:
                sender_id = msg.sender_id
            else:
                sender_id = msg.content["id"]

            msg_uuid = msg.content.get("uuid")
            msg_term = msg.content.get("term", 0)

            if msg.msg_type == "COORDINATOR":
                current_time = time.time()
                if sender_id in self.known_leaders:
                    record = self.known_leaders[sender_id]
                    if msg_term > record["term"]:
                        pass
                    elif msg_term < record["term"]:
                        self.logger.warning(
                            f"SECURITY: Stale term {msg_term} < {record['term']} from {sender_id}. Ignoring."
                        )
                        return
                    else:
                        if record["uuid"] and msg_uuid and record["uuid"] != msg_uuid:
                            self.logger.warning(
                                f"SECURITY: UUID mismatch for Agent {sender_id}. Ignoring."
                            )
                            return
                        if current_time - record["last_claim"] < 0.2:
                            self.logger.warning(
                                f"SECURITY: Rate limit exceeded for Agent {sender_id}. Ignoring."
                            )
                            return
                self.known_leaders[sender_id] = {
                    "uuid": msg_uuid,
                    "last_claim": current_time,
                    "term": msg_term,
                }
                if self.bft_enabled:
                    key = self._proposal_key(sender_id, msg_term, msg_uuid)
                    self.pending_proposals[key] = current_time
                    voters = self.vote_pool.setdefault(key, set())
                    voters.add(sender_id)
                    self.send_message(
                        -1,
                        "BFT_VOTE",
                        {"proposed_id": sender_id, "term": msg_term, "uuid": msg_uuid},
                    )
                    self._try_commit(key)
                    return
                if self.leader_id != sender_id:
                    self.leader_changes.append(current_time)

            if msg.msg_type == "ELECTION":
                if self.agent_id > sender_id:
                    self.send_message(
                        sender_id,
                        "ANSWER",
                        {
                            "id": self.agent_id,
                            "uuid": self.boot_uuid,
                            "term": self.term,
                        },
                    )
                    if (
                        self.state != AgentState.LEADER
                        and self.state != AgentState.CANDIDATE
                    ):
                        self.start_election()

            elif msg.msg_type == "ANSWER":
                if self.state == AgentState.CANDIDATE and sender_id > self.agent_id:
                    self.waiting_for_answer = False
                    self.state = AgentState.FOLLOWER
                    self.leader_id = sender_id
                    self._refresh_leader_seen()

            elif msg.msg_type == "COORDINATOR":
                if (
                    sender_id > self.agent_id
                    or (self.leader_id is None)
                    or (sender_id == self.leader_id)
                ):
                    self.state = AgentState.FOLLOWER
                    self.leader_id = sender_id
                    self._refresh_leader_seen()
                    self.waiting_for_answer = False
                elif sender_id < self.agent_id:
                    if self.state == AgentState.LEADER:
                        self.send_message(
                            sender_id,
                            "COORDINATOR",
                            {
                                "id": self.agent_id,
                                "uuid": self.boot_uuid,
                                "term": self.term,
                            },
                        )
                    else:
                        self.start_election()
