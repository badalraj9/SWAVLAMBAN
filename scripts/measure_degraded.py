import re
import sys
from pathlib import Path

def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("hell_test.log")
    if not path.exists():
        print(f"No log at {path}; run: python -m pytest tests/hell_runner.py (logs to hell_test.log)")
        sys.exit(0)
    text = path.read_text(errors="ignore")
    enters = len(re.findall(r"ENTERING DEGRADED", text))
    exits = len(re.findall(r"RETURNING TO NORMAL", text))
    elections = len(re.findall(r"Starting election|Declaring victory", text))
    print(f"log={path} degraded_enters={enters} returns={exits} elections={elections}")
    if elections:
        print(f"false-positive proxy: enters/election={enters / elections:.3f} (tunable thresholds 2/15s, 2s->4s, reset 30s)")

if __name__ == "__main__":
    main()
