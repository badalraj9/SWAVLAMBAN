import math

class Evaluator:
    def __init__(self, w_value=0.5, w_distance=0.3, w_bytes=0.2,
                 distance_budget=1000.0, bytes_threshold=65536.0):
        self.w_value = w_value
        self.w_distance = w_distance
        self.w_bytes = w_bytes
        self.distance_budget = distance_budget
        self.bytes_threshold = bytes_threshold

    def _distance(self, a, b):
        try:
            return math.dist(a, b)
        except Exception:
            return 0.0

    def calculate_score(self, scenario_data):
        tasks = scenario_data.get("tasks", [])
        agents = scenario_data.get("agents", [])
        total_bytes = scenario_data.get("total_bytes", 0)

        total_value = sum(t.get("value", 0) for t in tasks)
        completed_value = sum(
            t.get("value", 0) for t in tasks if t.get("assigned_to") is not None
        )
        value_ratio = completed_value / total_value if total_value > 0 else 0.0

        agent_locs = {a.get("id"): a.get("location") for a in agents}
        total_distance = 0.0
        for t in tasks:
            aid = t.get("assigned_to")
            tloc = t.get("location") or t.get("pos")
            aloc = agent_locs.get(aid)
            if aid is not None and tloc is not None and aloc is not None:
                total_distance += self._distance(tuple(aloc), tuple(tloc))

        distance_score = 1.0 / (1.0 + total_distance / self.distance_budget)

        bytes_score = 1.0 / (1.0 + total_bytes / self.bytes_threshold)

        score = (
            self.w_value * value_ratio
            + self.w_distance * distance_score
            + self.w_bytes * bytes_score
        )
        return score
