import multiprocessing
import time
import logging
import random
from src.utils.message import Message
from src.utils.tamper_log import TamperEvidentLog


def _agent_runner(
    AgentClass, agent_id, incoming, outgoing, caps, num_agents=0, seed=42,
    use_udp=False, drop_rate=0.0,
):
    transport = None
    if use_udp:
        from src.utils.transport import UDPTransport
        transport = UDPTransport(agent_id, num_agents=num_agents,
                                 drop_rate=drop_rate, seed=seed)
        incoming = outgoing = None
    try:
        agent = AgentClass(
            agent_id,
            incoming,
            outgoing,
            capabilities=caps,
            num_agents=num_agents,
            seed=seed + agent_id,
            transport=transport,
        )
    except TypeError:
        try:
            agent = AgentClass(
                agent_id,
                incoming,
                outgoing,
                num_agents=num_agents,
                seed=seed + agent_id,
            )
        except TypeError:
            try:
                agent = AgentClass(
                    agent_id,
                    incoming,
                    outgoing,
                    capabilities=caps,
                    num_agents=num_agents,
                )
            except TypeError:
                try:
                    agent = AgentClass(agent_id, incoming, outgoing, capabilities=caps)
                except TypeError:
                    agent = AgentClass(agent_id, incoming, outgoing)
    if transport is not None and getattr(agent, "transport", None) is None:
        agent.transport = transport
    try:
        agent.run()
    except KeyboardInterrupt:
        pass


class Simulator:
    def __init__(
        self,
        num_agents: int,
        drop_rate=0.0,
        min_latency=0.0,
        max_latency=0.0,
        seed: int = 42,
        use_udp: bool = False,
    ):
        self.num_agents = num_agents
        self.seed = seed
        self.rng = random.Random(seed)
        self.queues = {}
        self.processes = []
        self.running = False
        self.drop_rate = drop_rate
        self.min_latency = min_latency
        self.max_latency = max_latency
        self.delayed_messages = []
        self.use_udp = use_udp
        self.switchboard_queue = multiprocessing.Queue()
        self.audit_log = TamperEvidentLog()

    @property
    def logger(self):
        return logging.getLogger("Simulator")

    def setup_agents(self, AgentClass, agent_capabilities=None):
        for i in range(self.num_agents):
            incoming = None if self.use_udp else multiprocessing.Queue()
            if not self.use_udp:
                self.queues[i] = incoming
            caps = agent_capabilities.get(i, []) if agent_capabilities else []
            p = multiprocessing.Process(
                target=_agent_runner,
                args=(
                    AgentClass,
                    i,
                    incoming,
                    self.switchboard_queue,
                    caps,
                    self.num_agents,
                    self.seed,
                    self.use_udp,
                    self.drop_rate,
                ),
            )
            self.processes.append(p)

    def start_async(self):
        self.running = True
        for p in self.processes:
            p.start()

    def stop(self):
        self.running = False
        for p in self.processes:
            if p.is_alive():
                p.terminate()
        for p in self.processes:
            p.join()

    def step(self, duration: float):
        if self.use_udp:
            time.sleep(duration)
            return
        start_time = time.time()
        while time.time() - start_time < duration:
            now = time.time()
            while not self.switchboard_queue.empty():
                try:
                    msg_json = self.switchboard_queue.get_nowait()
                    msg = Message.from_json(msg_json)
                    if self.rng.random() < self.drop_rate:
                        continue
                    latency = self.rng.uniform(self.min_latency, self.max_latency)
                    delivery_time = now + latency
                    self.delayed_messages.append((delivery_time, msg))
                except Exception:
                    pass
            remaining_messages = []
            for deliver_t, msg in self.delayed_messages:
                if now >= deliver_t:
                    self._deliver_message(msg)
                else:
                    remaining_messages.append((deliver_t, msg))
            self.delayed_messages = remaining_messages
            time.sleep(0.01)

    def kill_agent(self, agent_id):
        if 0 <= agent_id < len(self.processes):
            p = self.processes[agent_id]
            if p.is_alive():
                p.terminate()
                p.join()
                self.logger.info(f"Killed Agent {agent_id}")

    def _deliver_message(self, msg: Message):
        self.audit_log.append(
            "MSG",
            {
                "sender": msg.sender_id,
                "receiver": msg.receiver_id,
                "type": msg.msg_type,
                "content": msg.content,
            },
        )
        if msg.receiver_id == -1:
            for aid, q in self.queues.items():
                if aid != msg.sender_id:
                    q.put(msg.to_json())
        elif msg.receiver_id in self.queues:
            self.queues[msg.receiver_id].put(msg.to_json())
