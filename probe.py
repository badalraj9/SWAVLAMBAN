import json
import sys
import urllib.request

from debate_core import call_agent, load_configs

if len(sys.argv) > 1 and sys.argv[1] == "--list-groq":
    cfgs = {c.slot: c for c in load_configs()}
    c = cfgs[3]
    req = urllib.request.Request(
        f"{c.base_url}/models",
        headers={"Authorization": f"Bearer {c.api_key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        for m in json.load(resp).get("data", []):
            print(m.get("id"))
elif len(sys.argv) > 3 and sys.argv[1] == "--try":
    import threading

    slot, model = int(sys.argv[2]), sys.argv[3]
    budget = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
    c = {c.slot: c for c in load_configs()}[slot]
    out: dict = {}

    def run():
        try:
            out["r"] = call_agent(c.base_url, c.api_key, model, "Reply ok.")
        except Exception as e:
            out["e"] = str(e)[:400]

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(budget)
    if t.is_alive():
        print(f"TRY {model}: TIMEOUT after {budget:g}s")
    elif "e" in out:
        print(f"TRY {model}: FAIL -> {out['e']}")
    else:
        print(f"TRY {model}: OK -> {out['r'][:150]}")
elif len(sys.argv) > 2 and sys.argv[1] == "--check":
    import threading

    slot, budget = int(sys.argv[2]), float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    c = {c.slot: c for c in load_configs()}[slot]
    out: dict = {}

    def run():
        try:
            out["r"] = call_agent(c.base_url, c.api_key, c.model, "Reply ok.")
        except Exception as e:
            out["e"] = str(e)[:400]

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(budget)
    if t.is_alive():
        print(f"AGENT_{c.slot} {c.model}: TIMEOUT after {budget:g}s (no response, connection hanging)")
    elif "e" in out:
        print(f"AGENT_{c.slot} {c.model}: FAIL -> {out['e']}")
    else:
        print(f"AGENT_{c.slot} {c.model}: OK -> {out['r'][:150]}")
else:
    for c in load_configs():
        try:
            r = call_agent(c.base_url, c.api_key, c.model, "Reply ok.")
            print(f"AGENT_{c.slot} {c.model}: OK -> {r[:150]}")
        except Exception as e:
            print(f"AGENT_{c.slot} {c.model}: FAIL -> {str(e)[:400]}")
