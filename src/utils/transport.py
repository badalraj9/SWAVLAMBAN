import json
import os
import queue
import random
import socket
import time


class Transport:
    def send(self, receiver_id: int, data: str) -> bool:
        raise NotImplementedError

    def recv_all(self) -> list:
        raise NotImplementedError

    def last_seen(self, peer_id: int) -> float:
        return 0.0

    def close(self):
        pass


class QueueTransport(Transport):
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox: queue.Queue = queue.Queue()
        self.peers: dict = {}
        self._last_seen: dict = {}

    @staticmethod
    def plug(*transports):
        for t in transports:
            t.peers = {o.agent_id: o for o in transports if o is not t}

    def send(self, receiver_id: int, data: str) -> bool:
        if receiver_id == -1:
            for peer in self.peers.values():
                peer.inbox.put(data)
        else:
            peer = self.peers.get(receiver_id)
            if peer is None:
                return False
            peer.inbox.put(data)
        return True

    def recv_all(self) -> list:
        out = []
        while True:
            try:
                data = self.inbox.get_nowait()
            except queue.Empty:
                break
            try:
                sender = json.loads(data).get("sender_id")
            except Exception:
                sender = None
            if sender is not None:
                self._last_seen[sender] = time.time()
            out.append(data)
        return out

    def last_seen(self, peer_id: int) -> float:
        return self._last_seen.get(peer_id, 0.0)


class UDPTransport(Transport):
    BASE_PORT = int(os.environ.get("SWARM_BASE_PORT", "50000"))
    BUF = 65535

    def __init__(self, agent_id: int, num_agents: int = 0, peer_ids=None,
                 drop_rate: float = 0.0, seed: int = 42, host="127.0.0.1"):
        self.agent_id = agent_id
        self.host = host
        self.port = self.BASE_PORT + agent_id
        self.drop_rate = drop_rate
        self.rng = random.Random(seed + agent_id)
        if peer_ids is None and num_agents:
            peer_ids = [i for i in range(num_agents) if i != agent_id]
        self.peer_ids = list(peer_ids or [])
        self._last_seen: dict = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.setblocking(False)

    def _addr(self, peer_id: int):
        return (self.host, self.BASE_PORT + peer_id)

    def send(self, receiver_id: int, data: str) -> bool:
        raw = data.encode() if isinstance(data, str) else data
        targets = self.peer_ids if receiver_id == -1 else [receiver_id]
        sent_any = False
        for peer in targets:
            if peer == self.agent_id:
                continue
            if self.rng.random() < self.drop_rate:
                continue
            try:
                self.sock.sendto(raw, self._addr(peer))
                sent_any = True
            except OSError:
                continue
        return sent_any

    def recv_all(self) -> list:
        out = []
        while True:
            try:
                raw, _ = self.sock.recvfrom(self.BUF)
            except BlockingIOError:
                break
            except OSError:
                break
            try:
                data = raw.decode()
                sender = json.loads(data).get("sender_id")
            except Exception:
                continue
            if sender is not None:
                self._last_seen[sender] = time.time()
            out.append(data)
        return out

    def last_seen(self, peer_id: int) -> float:
        return self._last_seen.get(peer_id, 0.0)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
