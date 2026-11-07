#!/usr/bin/env python3
"""Sidecar Helper para os nós réplicas.

Implementado utilizando EXCLUSIVAMENTE a biblioteca padrão do Python (http.server e urllib).
Assim, pode rodar diretamente dentro do contêiner padrão do Postgres ou em qualquer ambiente
sem exigir a instalação de dependências externas (como FastAPI ou httpx).

Endpoints:
- GET  /ping
- GET  /lamport/clock
- POST /lamport/tick
- POST /lamport/update {"received_clock": int}
- GET  /mutex/status
- POST /mutex/request {"requester_id": str, "clock": int, "node_id": str}
- POST /mutex/reply   {"from_node": str}
- POST /mutex/acquire {"timeout": float}
- POST /mutex/release
- POST /tx/prepare    {"tx_id": str, "payload": dict}
- POST /tx/commit     {"tx_id": str}
- POST /tx/abort      {"tx_id": str}
- GET  /tx/status?tx_id=...
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

NODE_ID = os.getenv("NODE_ID", "default-node")
PEERS_ENV = os.getenv("PEERS", "")
PEERS = [p.strip() for p in PEERS_ENV.split(",") if p.strip() and p.strip() != NODE_ID]
HELPER_PORT = int(os.getenv("HELPER_PORT", "9000"))


class LamportClockSync:
    def __init__(self, node_id: str):
        self.node_id = str(node_id)
        self.clock = 0
        self._lock = threading.Lock()

    def tick(self) -> tuple[int, str]:
        with self._lock:
            self.clock += 1
            return self.clock, self.node_id

    def update(self, received: int) -> tuple[int, str]:
        with self._lock:
            self.clock = max(self.clock, received) + 1
            return self.clock, self.node_id

    def get(self) -> tuple[int, str]:
        with self._lock:
            return self.clock, self.node_id


class RicartAgrawalaSync:
    def __init__(self, node_id: str, peers: list[str], clock: LamportClockSync):
        self.node_id = node_id
        self.peers = peers
        self.clock = clock

        self.state = "RELEASED"  # RELEASED, WANTED, HELD
        self.request_clock: int | None = None
        self.deferred_replies: set[str] = set()
        self.received_replies: set[str] = set()

        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def request_access(self, timeout_seconds: float = 5.0) -> bool:
        with self._lock:
            self.state = "WANTED"
            req_clock, _ = self.clock.tick()
            self.request_clock = req_clock
            self.received_replies.clear()

        needed_replies = len(self.peers)
        if needed_replies == 0:
            with self._lock:
                self.state = "HELD"
            return True

        # Dispara REQUEST para todos os peers em threads separadas
        for peer in self.peers:
            threading.Thread(
                target=self._send_request_thread,
                args=(peer, req_clock, self.node_id),
                daemon=True,
            ).start()

        start_time = time.time()
        with self._cond:
            while len(self.received_replies) < needed_replies:
                remaining = timeout_seconds - (time.time() - start_time)
                if remaining <= 0:
                    self.state = "RELEASED"
                    self.request_clock = None
                    return False
                self._cond.wait(timeout=remaining)

            self.state = "HELD"
            return True

    def _send_request_thread(self, peer: str, clock_val: int, node_id_val: str):
        url = f"http://{peer}:{HELPER_PORT}/mutex/request"
        payload = {"requester_id": self.node_id, "clock": clock_val, "node_id": node_id_val}
        status, data = _post_json(url, payload, timeout=3.0)
        if status == 200 and data.get("granted"):
            self.receive_reply(peer)

    def receive_request(self, requester_id: str, req_clock: int, req_node_id: str) -> bool:
        with self._lock:
            self.clock.update(req_clock)
            my_priority = False
            if self.state in ("WANTED", "HELD") and self.request_clock is not None:
                # Compara timestamp de Lamport (clock, node_id)
                my_priority = (self.request_clock, self.node_id) < (req_clock, req_node_id)

            should_defer = (self.state == "HELD") or (self.state == "WANTED" and my_priority)
            if should_defer:
                self.deferred_replies.add(requester_id)
                return False
            else:
                return True

    def receive_reply(self, from_node: str):
        with self._cond:
            if self.state == "WANTED":
                self.received_replies.add(from_node)
                self._cond.notify_all()

    def release_access(self) -> list[str]:
        with self._lock:
            self.state = "RELEASED"
            self.request_clock = None
            to_reply = list(self.deferred_replies)
            self.deferred_replies.clear()

        for peer in to_reply:
            threading.Thread(
                target=self._send_reply_thread,
                args=(peer,),
                daemon=True,
            ).start()
        return to_reply

    def _send_reply_thread(self, peer: str):
        url = f"http://{peer}:{HELPER_PORT}/mutex/reply"
        _post_json(url, {"from_node": self.node_id}, timeout=3.0)


class TwoPhaseParticipantSync:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.transactions: dict[str, dict] = {}
        self._lock = threading.Lock()

    def prepare(self, tx_id: str, payload: dict) -> bool:
        with self._lock:
            quantity = payload.get("quantity", 1)
            # Validação local do participante: quantity entre 1 e 50
            if not (0 < quantity <= 50):
                self.transactions[tx_id] = {"state": "ABORTED", "payload": payload}
                return False
            self.transactions[tx_id] = {"state": "PREPARED", "payload": payload}
            return True

    def commit(self, tx_id: str) -> bool:
        with self._lock:
            rec = self.transactions.get(tx_id)
            if not rec or rec["state"] != "PREPARED":
                return False
            rec["state"] = "COMMITTED"
            return True

    def abort(self, tx_id: str) -> bool:
        with self._lock:
            rec = self.transactions.get(tx_id)
            if rec:
                rec["state"] = "ABORTED"
            else:
                self.transactions[tx_id] = {"state": "ABORTED", "payload": {}}
            return True


def _post_json(url: str, data: dict, timeout: float = 3.0) -> tuple[int, dict]:
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception:
        return 0, {}


# Instâncias globais no processo do helper
CLOCK = LamportClockSync(node_id=NODE_ID)
MUTEX = RicartAgrawalaSync(node_id=NODE_ID, peers=PEERS, clock=CLOCK)
PARTICIPANT_2PC = TwoPhaseParticipantSync(node_id=NODE_ID)


class HelperHTTPHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length).decode("utf-8")
            return json.loads(raw)
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/ping":
            self._send_json(200, {"status": "ok", "node_id": NODE_ID})
        elif path == "/lamport/clock":
            c, n = CLOCK.get()
            self._send_json(200, {"clock": c, "node_id": n})
        elif path == "/mutex/status":
            with MUTEX._lock:
                self._send_json(200, {
                    "node_id": MUTEX.node_id,
                    "state": MUTEX.state,
                    "request_clock": MUTEX.request_clock,
                    "deferred_replies": list(MUTEX.deferred_replies),
                    "received_replies": list(MUTEX.received_replies),
                    "peers": MUTEX.peers,
                })
        elif path == "/tx/status":
            qs = parse_qs(parsed.query)
            tx_id = qs.get("tx_id", [""])[0]
            with PARTICIPANT_2PC._lock:
                rec = PARTICIPANT_2PC.transactions.get(tx_id)
                if not rec:
                    self._send_json(404, {"error": "Transaction not found"})
                else:
                    self._send_json(200, {"tx_id": tx_id, "state": rec["state"], "node_id": NODE_ID})
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read_json()

        if path == "/lamport/tick":
            c, n = CLOCK.tick()
            self._send_json(200, {"clock": c, "node_id": n})
        elif path == "/lamport/update":
            c, n = CLOCK.update(int(data.get("received_clock", 0)))
            self._send_json(200, {"clock": c, "node_id": n})
        elif path == "/mutex/request":
            req_id = data.get("requester_id")
            c = int(data.get("clock", 0))
            nid = data.get("node_id")
            granted = MUTEX.receive_request(req_id, c, nid)
            self._send_json(200, {"granted": granted, "node_id": NODE_ID})
        elif path == "/mutex/reply":
            from_node = data.get("from_node")
            MUTEX.receive_reply(from_node)
            self._send_json(200, {"status": "ack"})
        elif path == "/mutex/acquire":
            timeout = float(data.get("timeout", 5.0))
            ok = MUTEX.request_access(timeout_seconds=timeout)
            status = 200 if ok else 504
            self._send_json(status, {"acquired": ok, "node_id": NODE_ID})
        elif path == "/mutex/release":
            replied = MUTEX.release_access()
            self._send_json(200, {"status": "released", "replied_nodes": replied})
        elif path == "/tx/prepare":
            tx_id = data.get("tx_id")
            payload = data.get("payload", {})
            prepared = PARTICIPANT_2PC.prepare(tx_id, payload)
            self._send_json(200, {"tx_id": tx_id, "vote": "YES" if prepared else "NO", "node_id": NODE_ID})
        elif path == "/tx/commit":
            tx_id = data.get("tx_id")
            committed = PARTICIPANT_2PC.commit(tx_id)
            self._send_json(200, {"tx_id": tx_id, "committed": committed, "node_id": NODE_ID})
        elif path == "/tx/abort":
            tx_id = data.get("tx_id")
            aborted = PARTICIPANT_2PC.abort(tx_id)
            self._send_json(200, {"tx_id": tx_id, "aborted": aborted, "node_id": NODE_ID})
        else:
            self._send_json(404, {"error": "Not Found"})

    def log_message(self, format, *args):
        # Suprime logs normais de cada requisição para não poluir
        pass


def run_server():
    server = HTTPServer(("0.0.0.0", HELPER_PORT), HelperHTTPHandler)
    print(f"[{NODE_ID}] Distributed Helper running on port {HELPER_PORT}...")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
