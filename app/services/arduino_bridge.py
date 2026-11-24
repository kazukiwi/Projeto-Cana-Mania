"""Transporte serial remoto entre o servidor e a ponte local do Arduino."""
from __future__ import annotations

import queue
import threading


class BridgeSerial:
    """Interface serial compatível com RFIDSerialService, atendida por um WS."""

    def __init__(self):
        self.commands: queue.Queue[str] = queue.Queue()
        self.responses: queue.Queue[bytes] = queue.Queue()
        self._lock = threading.Lock()
        self._connected = False

    @property
    def is_open(self):
        with self._lock:
            return self._connected

    def attach(self):
        with self._lock:
            if self._connected:
                return False
            for pending in (self.commands, self.responses):
                while True:
                    try:
                        pending.get_nowait()
                    except queue.Empty:
                        break
            self._connected = True
            return True

    def detach(self):
        with self._lock:
            self._connected = False
        self.responses.put(b"")

    def write(self, data: bytes):
        if not self.is_open:
            raise OSError("Ponte Arduino desconectada")
        self.commands.put(data.decode("ascii", errors="strict").strip())
        return len(data)

    def flush(self):
        pass

    def readline(self):
        if not self.is_open:
            raise OSError("Ponte Arduino desconectada")
        try:
            return self.responses.get(timeout=0.2)
        except queue.Empty:
            return b""

    def feed_response(self, line: str):
        if not line or len(line) > 128:
            raise ValueError("Mensagem serial invalida")
        self.responses.put((line.strip() + "\n").encode("ascii", errors="strict"))


bridge_serial = BridgeSerial()
