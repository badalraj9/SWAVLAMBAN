from src.simulation.simulator import Simulator
from src.agents.swarm_agent import SwarmAgent

TASKS_S1 = [{"id": i, "value": 10, "pos": (0, 0)} for i in range(10)]


PLACEHOLDER_SCORE = 0.85

def run_scenario(scenario_id, num_agents=5):
    import warnings
    warnings.warn(
        "run_scenario returns PLACEHOLDER_SCORE, not a real measurement. "
        "Agent state is process-isolated; real scoring needs Evaluator + log side-channel.",
        UserWarning,
    )
    print(f"Running Scenario {scenario_id}...")
    sim = Simulator(num_agents=num_agents)
    sim.setup_agents(SwarmAgent)
    sim.start_async()

    sim.step(10.0)
    sim.stop()

    PLACEHOLDER_confidence = PLACEHOLDER_SCORE
    print(f"Scenario {scenario_id} Complete. PLACEHOLDER_SCORE: {PLACEHOLDER_confidence} (STUB)")
    return PLACEHOLDER_confidence


if __name__ == "__main__":
    run_scenario("S1")
