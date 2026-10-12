import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

ROUND_TITLES = {
    "propose": "Round 1 — Opening Positions",
    "debate": "Round 2 — Debate & Rebuttal",
    "vote": "Round 3 — Final Vote",
}


@dataclass
class AgentConfig:
    slot: int
    base_url: str
    api_key: str
    model: str


class NullEvents:
    def on_round_start(self, round_name: str, title: str) -> None:
        pass

    def on_agent_start(self, agent_id: str) -> None:
        pass

    def on_agent_response(self, agent_id: str, result: dict) -> None:
        pass

    def on_agent_error(self, agent_id: str, error: str) -> None:
        pass

    def on_round_complete(self, round_name: str) -> None:
        pass


def load_configs() -> list:
    load_dotenv()
    configs = []
    missing = []
    for i in (1, 2, 3, 4):
        base_url = os.environ.get(f"AGENT_{i}_BASE_URL", "").strip()
        api_key = os.environ.get(f"AGENT_{i}_API_KEY", "").strip()
        model = os.environ.get(f"AGENT_{i}_MODEL", "").strip()
        if not base_url or not api_key or not model:
            missing.append(f"AGENT_{i}_BASE_URL/API_KEY/MODEL")
        configs.append(AgentConfig(slot=i, base_url=base_url, api_key=api_key, model=model))
    if missing:
        print("Missing config in .env (copied from .env.example):", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(2)
    return configs


def call_agent(base_url: str, api_key: str, model: str, prompt: str) -> str:
    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Respond with JSON only: {\"position\": str, \"confidence\": number 0-1, \"reasoning\": str}."},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content or ""


def parse_response(text: str) -> dict:
    try:
        obj = json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        obj = json.loads(text[start : end + 1]) if start != -1 and end != -1 else {}
    try:
        confidence = float(obj.get("confidence", 0))
    except Exception:
        confidence = 0.0
    return {
        "position": str(obj.get("position", "")),
        "confidence": max(0.0, min(1.0, confidence)),
        "reasoning": str(obj.get("reasoning", "")),
        "raw": text,
    }


def _call_one(cfg: AgentConfig, prompt: str, events: NullEvents) -> tuple:
    agent_id = f"agent_{cfg.slot}"
    events.on_agent_start(agent_id)
    try:
        text = call_agent(cfg.base_url, cfg.api_key, cfg.model, prompt)
        result = parse_response(text)
        events.on_agent_response(agent_id, result)
        return agent_id, result
    except Exception as e:
        events.on_agent_error(agent_id, str(e))
        return agent_id, {"position": "", "confidence": 0.0, "reasoning": "", "raw": "", "error": str(e)}


def run_round(configs: list, prompt_for: callable, events: NullEvents = None) -> dict:
    events = events or NullEvents()
    prompts = {f"agent_{c.slot}": prompt_for(c) for c in configs}
    results = {}
    with ThreadPoolExecutor(max_workers=len(configs)) as pool:
        futures = {
            pool.submit(_call_one, cfg, prompts[f"agent_{cfg.slot}"], events): cfg
            for cfg in configs
        }
        for fut in futures:
            agent_id, result = fut.result()
            results[agent_id] = result
    return results


def run_debate(topic: str, configs: list, events: NullEvents = None) -> dict:
    events = events or NullEvents()
    rounds = {}

    events.on_round_start("propose", ROUND_TITLES["propose"])
    rounds["propose"] = run_round(
        configs, lambda c: f"Topic: {topic}\nState your position.", events
    )
    events.on_round_complete("propose")

    summary = json.dumps(rounds["propose"])
    events.on_round_start("debate", ROUND_TITLES["debate"])
    rounds["debate"] = run_round(
        configs,
        lambda c: f"Topic: {topic}\nOther positions: {summary}\nRevise or rebut your position.",
        events,
    )
    events.on_round_complete("debate")

    summary2 = json.dumps(rounds["debate"])
    events.on_round_start("vote", ROUND_TITLES["vote"])
    rounds["vote"] = run_round(
        configs,
        lambda c: f"Topic: {topic}\nDebate so far: {summary2}\nCast your final position.",
        events,
    )
    events.on_round_complete("vote")

    tally: dict = {}
    for vote in rounds["vote"].values():
        if vote.get("position"):
            tally[vote["position"]] = tally.get(vote["position"], 0.0) + vote["confidence"]
    winner = max(tally, key=tally.get) if tally else ""
    return {"topic": topic, "rounds": rounds, "tally": tally, "winner": winner}


def save_transcript(transcript: dict) -> str:
    path = f"debate_transcript_{int(time.time())}.json"
    with open(path, "w") as f:
        json.dump(transcript, f, indent=2)
    return path
