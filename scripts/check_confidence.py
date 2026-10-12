import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "confidence_score.json"
REPORT_PATH = ROOT / "HELL_TEST_REPORT_FINAL.md"

def load():
    data = json.loads(JSON_PATH.read_text())
    metrics = data["metrics"]
    weights = data["weights"]
    recomputed = sum(metrics[k] * weights[k] for k in weights)
    return data, recomputed

def report_score():
    text = REPORT_PATH.read_text()
    m = re.search(r"\*\*Confidence Score\*\*:\s*([0-9.]+)", text)
    return float(m.group(1)) if m else None, text

def main():
    fix = "--fix" in sys.argv
    data, recomputed = load()
    stored = data["confidence_score"]
    if abs(recomputed - stored) > 1e-6:
        print(f"FAIL: {JSON_PATH.name} stored {stored} != recomputed {recomputed:.4f}")
        sys.exit(1)
    rep, text = report_score()
    print(f"json recomputed={recomputed:.4f} stored={stored} report={rep}")
    if rep is None:
        print("FAIL: no Confidence Score in report")
        sys.exit(1)
    if abs(rep - recomputed) > 0.005:
        if fix:
            new_text = re.sub(
                r"(\*\*Confidence Score\*\*:)\s*[0-9.]+",
                f"\\1 {recomputed:.4f}",
                text,
            )
            REPORT_PATH.write_text(new_text)
            print(f"Regenerated report score -> {recomputed:.4f} from {JSON_PATH.name}")
        else:
            print(f"FAIL: drift json={recomputed:.4f} vs report={rep} (run with --fix to regenerate)")
            sys.exit(1)
    else:
        print("OK: scores in sync")

if __name__ == "__main__":
    main()
