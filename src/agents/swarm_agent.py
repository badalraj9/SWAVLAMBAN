from src.agents.bully_agent import BullyAgent
from src.agents.cbaa_agent import CbaaAgent
from src.utils.message import Message

# Task Registry: reqs + value + pos so bids are distance/value-based.
TASK_REGISTRY = {
    i: {"reqs": [], "value": 10.0, "pos": ((i * 13) % 100, (i * 29) % 100)}
    for i in range(100)
}
# Task 5 requires "heavy_lift"
TASK_REGISTRY[5]["reqs"] = ["heavy_lift"]


class SwarmAgent(CbaaAgent, BullyAgent):
    def __init__(
        self,
        agent_id,
        incoming_queue=None,
        outgoing_queue=None,
        num_tasks=10,
        capabilities=None,
        num_agents=0,
        seed=42,
        transport=None,
    ):
        CbaaAgent.__init__(self, agent_id, incoming_queue, outgoing_queue, num_tasks,
                           transport=transport)
        BullyAgent.__init__(
            self,
            agent_id,
            incoming_queue,
            outgoing_queue,
            num_agents=num_agents,
            seed=seed,
            transport=transport,
        )
        self.capabilities = capabilities if capabilities else []

    def update_state(self):
        BullyAgent.update_state(self)
        CbaaAgent.update_state(self)

    def handle_message(self, msg: Message):
        BullyAgent.handle_message(self, msg)
        CbaaAgent.handle_message(self, msg)

    def calculate_bid(self, task_id):
        # S7: Capability Check
        reqs = TASK_REGISTRY.get(task_id, {}).get("reqs", [])
        for req in reqs:
            if req not in self.capabilities:
                return 0.0

        return super().calculate_bid(task_id)
