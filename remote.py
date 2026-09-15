"""Rally's fixed-frame transport over a loopback socket forwarded by SSH.

The relay sends controller replies, never executable code. One client owns the
controller at a time. SSH supplies authentication and encryption between machines.
"""
from __future__ import annotations

import math
import socket
import socketserver
import time

import rally

MODES = {'model': 0, 'rtl': 1, 'serial': 2}
LABELS = {
    'model': 'PYTHON MODEL (no FPGA)',
    'rtl': 'SYSTEMVERILOG SIMULATION (no FPGA)',
    'serial': 'UART DEVICE (board identity must be checked by host)',
}


class RemoteError(OSError):
    """A remote transaction cannot be used to move the paddle."""


def receive_exact(connection: socket.socket, count: int, deadline: float) -> bytes:
    """Read a fixed frame within one total deadline, including fragmented reads."""
    data = bytearray()
    while len(data) < count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('remote reply deadline exceeded')
        connection.settimeout(remaining)
        part = connection.recv(count - len(data))
        if not part:
            raise RemoteError('remote connection closed before a complete frame')
        data.extend(part)
    return bytes(data)


class RemoteBackend:
    """Player-side client. The local port may be forwarded to a friend's relay."""

    def __init__(self, host: str = '127.0.0.1', port: int = 4768,
                 timeout: float = .25, expected_backend: str | None = None):
        if host != '127.0.0.1':
            raise ValueError('connect to 127.0.0.1 through an SSH tunnel')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('remote port must be between 1 and 65535')
        if not math.isfinite(timeout) or not 0 < timeout <= 5:
            raise ValueError('remote timeout must be greater than 0 and at most 5 seconds')
        if expected_backend is not None and expected_backend not in MODES:
            raise ValueError('unknown expected backend')
        self.timeout = timeout
        self.connection: socket.socket | None = None
        try:
            self.connection = socket.create_connection((host, port), timeout=timeout)
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            hello = receive_exact(self.connection, 5, time.monotonic() + timeout)
            if hello[:4] != b'RLY1' or hello[4] not in MODES.values():
                raise RemoteError('unsupported relay handshake')
            self.remote_backend = next(name for name, code in MODES.items() if code == hello[4])
            if expected_backend and self.remote_backend != expected_backend:
                raise RemoteError(f'expected {expected_backend} relay; received {self.remote_backend}')
            self.label = 'REMOTE / ' + LABELS[self.remote_backend]
        except BaseException:
            self.close()
            raise

    def exchange(self, data: bytes) -> bytes:
        if len(data) != 10:
            raise ValueError('remote requests must be exactly 10 bytes')
        if self.connection is None:
            raise RemoteError('remote connection is closed; restart the client to reconnect')
        deadline = time.monotonic() + self.timeout
        try:
            self.connection.settimeout(self.timeout)
            self.connection.sendall(data)
            envelope = receive_exact(self.connection, 8, deadline)
        except OSError:
            # A late reply must never become the next frame's movement.
            self.close()
            raise
        if envelope == b'\x01' + bytes(7):
            raise RemoteError('remote controller rejected or could not complete the transaction')
        try:
            if envelope[0] != 0:
                raise rally.ProtocolError('invalid relay status')
            rally.decode_reply(envelope[1:], int.from_bytes(data[2:4], 'little'))
        except rally.ProtocolError as exc:
            self.close()
            raise RemoteError(str(exc)) from exc
        return envelope[1:]

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None


class RelayServer(socketserver.TCPServer):
    """Serializes clients so only one socket can operate the FPGA at a time."""
    allow_reuse_address = True
    request_queue_size = 1

    def __init__(self, address, backend, mode: str):
        if address[0] != '127.0.0.1':
            raise ValueError('relay must bind 127.0.0.1; use SSH forwarding between machines')
        if mode not in MODES:
            raise ValueError('unknown relay backend')
        self.backend = backend
        self.mode = mode
        super().__init__(address, RelayHandler)


class RelayHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        connection = self.request
        connection.settimeout(2)
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            connection.sendall(b'RLY1' + bytes([MODES[self.server.mode]]))
            while True:
                data = receive_exact(connection, 10, time.monotonic() + 2)
                try:
                    reply = self.server.backend.exchange(data)
                    rally.decode_reply(reply, int.from_bytes(data[2:4], 'little'))
                    result = b'\0' + reply
                except (rally.ProtocolError, OSError):
                    result = b'\x01' + bytes(7)
                connection.settimeout(2)
                connection.sendall(result)
        except OSError:
            # EOF, a partial request or an idle/disconnected client releases ownership.
            return
