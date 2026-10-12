from src.agents.base_agent import BaseAgent, AgentState
from src.utils.message import Message
import time


class TrivialAgent(BaseAgent):
    def __init__(self, agent_id, incoming_queue, outgoing_queue):
        super().__init__(agent_id, incoming_queue, outgoing_queue)
        self.last_broadcast = 0.0
        self.last_leader_heartbeat = time.time()
        self.leader_timeout = 2.0  # Seconds before declaring leader dead

    def update_state(self):
        # Initialize leader_id if None
        if self.leader_id is None:
            self.leader_id = self.agent_id
            self.state = AgentState.LEADER

        current_time = time.time()

        # If I am not the leader, check for timeout
        if self.state == AgentState.FOLLOWER:
            if current_time - self.last_leader_heartbeat > self.leader_timeout:
                self.logger.info(
                    f"Agent {self.agent_id}: Leader {self.leader_id} timed out. Declaring self leader."
                )
                self.leader_id = self.agent_id
                self.state = AgentState.LEADER

        # Periodically broadcast existence / heartbeat
        if current_time - self.last_broadcast > 1.0:
            self.send_message(-1, "HEARTBEAT", {"id": self.agent_id})
            self.last_broadcast = current_time

    def handle_message(self, msg: Message):
        if msg.msg_type == "HEARTBEAT":
            sender_id = msg.content["id"]

            # Trivial Logic: Higher ID always wins
            if sender_id > self.leader_id:
                self.leader_id = sender_id
                self.state = AgentState.FOLLOWER
                self.last_leader_heartbeat = time.time()
            elif sender_id == self.leader_id:
                # Leader is alive
                self.last_leader_heartbeat = time.time()
                if self.state == AgentState.LEADER and sender_id != self.agent_id:
                    # I thought I was leader, but someone else claims to be leader with same ID?
                    # (Shouldn't happen with unique IDs)
                    pass
            elif sender_id < self.leader_id:
                # Lower ID, ignore unless I am leader, then I might send a heartbeat back so they know I exist
                # But my periodic heartbeat handles that.
                pass

            # If I am the leader and I see someone with higher ID, I step down (handled above)
            # If I see someone with lower ID claiming to be leader (not explicit in heartbeat here,
            # but heartbeat implies "I am here").
            # In this Trivial implementation, Heartbeat just means "I exist".
            # The logic "Highest ID wins" means if I see a higher ID, I follow it.
            # If I don't see a higher ID for a while, I become leader.

            # Wait, if sender_id > self.agent_id, they are a better candidate than me.
            # If sender_id > self.leader_id, they are a better leader than current.

            if sender_id > self.agent_id:
                # There is someone better than me out there.
                pass
