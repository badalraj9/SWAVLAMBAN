import time
import logging
from enum import Enum
from src.utils.message import Message
import statistics


class AgentState(Enum):
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"


class OperationalMode(Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"


class BaseAgent:
    def __init__(
        self,
        agent_id: int,
        incoming_queue=None,
        outgoing_queue=None,
        num_agents: int = 0,
        seed: int = 42,
        transport=None,
    ):
        self.agent_id = agent_id
        self.incoming_queue = incoming_queue
        self.outgoing_queue = outgoing_queue
        self.transport = transport
        self.num_agents = num_agents
        self.state = AgentState.FOLLOWER
        self.leader_id = None
        self.running = True
        self.logger = logging.getLogger(f"Agent-{self.agent_id}")
        logging.basicConfig(level=logging.INFO)

        self.cycle_times = []
        self.wcet_bound_ms = 100.0
        self.wcet_max_ms = 0.0
        self.wcet_violations = 0
        self.mode = OperationalMode.NORMAL
        self.last_mode_log = 0.0

    def run(self):
        while self.running:
            start_time = time.monotonic()
            self.process_incoming_messages()
            self.update_state()
            self.execute_tasks()
            elapsed = time.monotonic() - start_time
            elapsed_ms = elapsed * 1000
            self.cycle_times.append(elapsed)
            if elapsed_ms > self.wcet_max_ms:
                self.wcet_max_ms = elapsed_ms
            if elapsed_ms > self.wcet_bound_ms:
                self.wcet_violations += 1
                self.logger.warning(
                    f"WCET VIOLATION {elapsed_ms:.2f}ms > {self.wcet_bound_ms}ms (violations={self.wcet_violations})"
                )
                if self.mode != OperationalMode.DEGRADED:
                    self.mode = OperationalMode.DEGRADED
                    self.logger.info("STATE: WCET ENTERING DEGRADED (graceful)")
            if len(self.cycle_times) >= 100:
                p99 = statistics.quantiles(self.cycle_times, n=100)[98]
                self.logger.info(
                    f"PERF: P99={p99 * 1000:.2f}ms WCET_MAX={self.wcet_max_ms:.2f}ms violations={self.wcet_violations}"
                )
                self.cycle_times = []
            sleep_time = max(0, 0.1 - elapsed)
            time.sleep(sleep_time)

    def process_incoming_messages(self):
        if self.transport is not None:
            for msg_json in self.transport.recv_all():
                try:
                    msg = Message.from_json(msg_json)
                    self.handle_message(msg)
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
            return
        if self.incoming_queue is None:
            return
        while not self.incoming_queue.empty():
            try:
                msg_json = self.incoming_queue.get_nowait()
                msg = Message.from_json(msg_json)
                self.handle_message(msg)
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")

    def handle_message(self, msg: Message):
        """Override in subclasses."""
        pass

    def send_message(self, receiver_id: int, msg_type: str, content: dict):
        msg = Message(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            msg_type=msg_type,
            content=content,
        )
        data = msg.to_json()
        if self.transport is not None:
            self.transport.send(receiver_id, data)
            return
        self.outgoing_queue.put(data)

    def update_state(self):
        """State machine logic."""
        pass

    def execute_tasks(self):
        """Task execution logic."""
        pass

    def stop(self):
        self.running = False
