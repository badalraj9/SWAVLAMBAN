import queue
from src.agents.bully_agent import BullyAgent
from src.utils.message import Message


def make_agent(agent_id=0, num_agents=5):
    return BullyAgent(agent_id, queue.Queue(), queue.Queue(), num_agents=num_agents, seed=42)


def test_1_single_coordinator_one_vote():
    agent = make_agent(agent_id=0, num_agents=5)
    msg = Message(sender_id=4, receiver_id=-1, msg_type="COORDINATOR",
                  content={"id": 4, "uuid": "abc123", "term": 1})
    agent.handle_message(msg)
    key = agent._proposal_key(4, 1, "abc123")
    voters = agent.vote_pool.get(key, set())
    assert len(voters) == 1, f"expected 1 vote, got {len(voters)}: {voters}"
    assert 4 in voters


def test_2_term_increments_once_per_election():
    agent = make_agent()
    initial = agent.term
    N = 5
    for _ in range(N):
        agent.start_election()
        agent.election_start_time = 0
        agent.waiting_for_answer = True
        agent.declare_victory()
        agent.state = agent.state.__class__.FOLLOWER if hasattr(agent.state, '__class__') else agent.state
        from src.agents.base_agent import AgentState
        agent.state = AgentState.FOLLOWER
    assert agent.term == initial + N, f"expected {initial + N}, got {agent.term}"


def test_3_quorum_table():
    expected = {}
    for n in range(4, 14):
        f = (n - 1) // 3
        expected[n] = (n + f) // 2 + 1
    for n, q_exp in expected.items():
        agent = make_agent(num_agents=n)
        assert agent._quorum_size() == q_exp, f"n={n}: expected {q_exp}, got {agent._quorum_size()}"
