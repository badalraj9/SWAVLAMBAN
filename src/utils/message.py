from dataclasses import dataclass, asdict
from typing import Any, Dict
import time
import json


@dataclass
class Message:
    sender_id: int
    receiver_id: int
    msg_type: str
    content: Dict[str, Any]
    timestamp: float = 0.0

    def to_json(self) -> str:
        self.timestamp = time.time()
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(json_str: str) -> "Message":
        data = json.loads(json_str)
        return Message(**data)
