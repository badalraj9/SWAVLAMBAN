from tests.hell_common import HellSimulator, MaliciousSwarmAgent
from src.agents.swarm_agent import SwarmAgent

print('=== BFT malicious ===')
sim = HellSimulator(num_agents=10)
sim.setup_agents(MaliciousSwarmAgent)
sim.start_async()
sim.step(8)
coords = [m.content['id'] for m in sim.msg_log if m.msg_type=='COORDINATOR']
votes = [m for m in sim.msg_log if m.msg_type=='BFT_VOTE']
print(f'COORDINATOR {set(coords)} n={len(coords)}')
print(f'BFT_VOTE n={len(votes)}')
sim.stop()

print('--- honest ---')
sim2 = HellSimulator(num_agents=10)
sim2.setup_agents(SwarmAgent)
sim2.start_async()
sim2.step(6)
coords2 = [m.content['id'] for m in sim2.msg_log if m.msg_type=='COORDINATOR']
votes2 = [m for m in sim2.msg_log if m.msg_type=='BFT_VOTE']
print(f'COORDINATOR {set(coords2)} n={len(coords2)} votes {len(votes2)}')
sim2.stop()
print('DONE')
