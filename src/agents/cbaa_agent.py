from src.agents.base_agent import BaseAgent, OperationalMode
from src.utils.message import Message
import time
import math


class CbaaAgent(BaseAgent):
    def __init__(self, agent_id, incoming_queue=None, outgoing_queue=None, num_tasks=10,
                 transport=None):
        super().__init__(agent_id, incoming_queue, outgoing_queue, transport=transport)
        self.num_tasks = num_tasks

        # State for CBAA
        self.y = [0.0] * num_tasks
        self.z = [-1] * num_tasks

        self.last_change_time = time.time()

        # Neighbor Liveness
        self.neighbor_heartbeats = {}  # id -> time
        self.neighbor_timeout = 2.0  # Seconds
        self.last_heartbeat_broadcast = 0.0

    def _agent_pos(self):
        return (float((self.agent_id * 17) % 100), float((self.agent_id * 31) % 100))

    def _task_info(self, task_id):
        value = 10.0
        pos = (float((task_id * 13) % 100), float((task_id * 29) % 100))
        try:
            from src.agents.swarm_agent import TASK_REGISTRY
            info = TASK_REGISTRY.get(task_id, {})
            value = float(info.get("value", value))
            if "pos" in info:
                pos = tuple(info["pos"])
        except Exception:
            pass
        return value, tuple(pos)

    def calculate_bid(self, task_id):
        value, task_pos = self._task_info(task_id)
        dist = math.dist(self._agent_pos(), task_pos)
        return value / (1.0 + dist)

    def update_state(self):
        current_time = time.time()

        # 0. Liveness Check
        dead_neighbors = []
        for nid, t in self.neighbor_heartbeats.items():
            if current_time - t > self.neighbor_timeout:
                dead_neighbors.append(nid)

        for nid in dead_neighbors:
            self.logger.info(f"Detected dead neighbor {nid}. Releasing tasks.")
            del self.neighbor_heartbeats[nid]
            # Release tasks owned by dead neighbor
            for j in range(self.num_tasks):
                if self.z[j] == nid:
                    self.y[j] = 0.0
                    self.z[j] = -1
                    # self.last_change_time = current_time # Trigger update

        # 1. Auction Step (Greedy)
        # MISSION CONTINUITY: If DEGRADED, freeze task reassignment.
        # We assume "keep last stable ownership" means we don't try to win NEW tasks.
        # But we must allow completing/releasing our own? (Not modeled here).
        # We skip the bidding loop.

        changed = False

        if self.mode == OperationalMode.NORMAL:
            for j in range(self.num_tasks):
                # If task is free or I can beat the bid
                # Note: If I already own it (z[j] == me), I don't need to re-bid unless someone beat me (handled in merge)
                # If I don't own it:
                if self.z[j] != self.agent_id:
                    my_bid = self.calculate_bid(j)
                    if my_bid > self.y[j]:
                        self.y[j] = my_bid
                        self.z[j] = self.agent_id
                        changed = True
        else:
            # DEGRADED MODE: Freeze. Do nothing.
            pass

        if changed:
            self.last_change_time = current_time
            self.send_cbaa_update()

        # 2. Heartbeat
        if current_time - self.last_heartbeat_broadcast > 1.0:
            self.send_message(-1, "HEARTBEAT", {})
            self.last_heartbeat_broadcast = current_time

    def send_cbaa_update(self):
        content = {"y": self.y, "z": self.z}
        self.send_message(-1, "CBAA_UPDATE", content)

    def handle_message(self, msg: Message):
        sender_id = msg.sender_id
        self.neighbor_heartbeats[sender_id] = time.time()

        if msg.msg_type == "CBAA_UPDATE":
            neighbor_y = msg.content["y"]
            neighbor_z = msg.content["z"]

            changed = False
            for j in range(self.num_tasks):
                # Advisory Check: If we are assigned a task by someone else
                if neighbor_z[j] == self.agent_id and self.z[j] != self.agent_id:
                    # Check Capabilities (Stub: assumed passed if calculate_bid works, but we can verify)
                    # Check Mode: If DEGRADED, do we accept new work?
                    # "Mission continuity... keep last stable ownership".
                    # If we are assigned a NEW task in DEGRADED mode, we might refuse (by not updating local state).
                    if self.mode == OperationalMode.DEGRADED:
                        # Refuse assignment locally (implicitly)
                        continue

                # Max-Consensus Rule
                if neighbor_y[j] > self.y[j]:
                    self.y[j] = neighbor_y[j]
                    self.z[j] = neighbor_z[j]
                    changed = True
                elif neighbor_y[j] == self.y[j]:
                    # Tie-breaking
                    if neighbor_z[j] > self.z[j]:
                        self.z[j] = neighbor_z[j]
                        changed = True

            if changed:
                self.last_change_time = time.time()
                self.send_cbaa_update()

        elif msg.msg_type == "HEARTBEAT":
            # Already updated timestamp above
            pass
