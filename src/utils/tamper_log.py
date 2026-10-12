import hashlib
import json
import time


class TamperEvidentLog:
    def __init__(self):
        self.chain = []
        self._prev_hash = "0" * 64

    def _hash(self, entry: dict) -> str:
        payload = json.dumps(entry, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def append(self, entry_type: str, data: dict) -> dict:
        entry = {
            "idx": len(self.chain),
            "ts": time.time(),
            "type": entry_type,
            "data": data,
            "prev_hash": self._prev_hash,
        }
        entry["hash"] = self._hash(entry)
        self.chain.append(entry)
        self._prev_hash = entry["hash"]
        return entry

    def verify(self) -> tuple[bool, int]:
        prev = "0" * 64
        for i, e in enumerate(self.chain):
            actual_hash = self._hash(
                {
                    k: v
                    for k, v in e.items()
                    if k in ("idx", "ts", "type", "data", "prev_hash")
                },
            )
            if e["prev_hash"] != prev or e["hash"] != actual_hash:
                return False, i
            prev = e["hash"]
        return True, -1

    def tamper(self, idx: int, new_data: dict):
        if 0 <= idx < len(self.chain):
            self.chain[idx]["data"] = new_data

    def to_jsonl(self, path: str):
        with open(path, "w") as f:
            for e in self.chain:
                f.write(json.dumps(e) + "\n")

    @staticmethod
    def from_jsonl(path: str) -> "TamperEvidentLog":
        log = TamperEvidentLog()
        with open(path) as f:
            for line in f:
                e = json.loads(line)
                log.chain.append(e)
        if log.chain:
            log._prev_hash = log.chain[-1]["hash"]
        return log
