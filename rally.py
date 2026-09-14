"""Rally: explicit, authorized external control of the game in this file.

Three distinct backends: Python model, actual RTL simulation, and UART hardware.
No process-memory access, input injection, DMA, or third-party game integration.
"""
from __future__ import annotations
import argparse
import json
import queue
import random
import shutil
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUEST = struct.Struct('<BBHHHB')
RESPONSE = struct.Struct('<BBHbB')


class ProtocolError(ValueError):
    """A frame failed integrity, identity, or bounds validation."""


def crc8(data: bytes) -> int:
    """CRC-8, polynomial 0x07, init 0, no reflection or final xor."""
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ (0x07 if crc & 0x80 else 0)) & 255
    return crc


def checked(data: bytes, length: int, magic: int) -> bytes:
    if len(data) != length or data[:2] != bytes([magic, 1]):
        raise ProtocolError('wrong length, magic, or version')
    if crc8(data[:-1]) != data[-1]:
        raise ProtocolError('CRC mismatch')
    return data[:-1]


def request(seq: int, ball: int, paddle: int, flags: int = 1) -> bytes:
    if not all(isinstance(v, int) and 0 <= v <= 65535 for v in (seq, ball, paddle)):
        raise ValueError('sequence and coordinates must be unsigned 16-bit integers')
    if not isinstance(flags, int) or not 0 <= flags <= 255:
        raise ValueError('flags must be an unsigned byte')
    data = REQUEST.pack(0xA5, 1, seq, ball, paddle, flags)
    return data + bytes([crc8(data)])


@dataclass(frozen=True)
class Reply:
    seq: int
    move: int
    status: int


def decision(ball: int, paddle: int, flags: int) -> tuple[int, int]:
    status = (1 if not flags & 1 else 0) | (2 if max(ball, paddle) > 1023 else 0)
    status |= 4 if flags & 0xFE else 0
    error = ball - paddle
    move = 0 if status or abs(error) <= 2 else max(-8, min(8, error))
    return move, status


def response(seq: int, move: int, status: int) -> bytes:
    body = RESPONSE.pack(0x5A, 1, seq, move, status)
    return body + bytes([crc8(body)])


def decode_reply(data: bytes, expected_seq: int) -> Reply:
    _, _, seq, move, status = RESPONSE.unpack(checked(data, 7, 0x5A))
    if seq != expected_seq:
        raise ProtocolError('stale or out-of-order reply')
    if abs(move) > 8 or status & ~7 or (status and move):
        raise ProtocolError('unsafe movement or invalid status')
    return Reply(seq, move, status)


class ModelBackend:
    label = 'PYTHON MODEL — NOT FPGA HARDWARE'

    def exchange(self, data: bytes) -> bytes:
        _, _, seq, ball, paddle, flags = REQUEST.unpack(checked(data, 10, 0xA5))
        move, status = decision(ball, paddle, flags)
        return response(seq, move, status)

    def close(self) -> None:
        pass


class RTLBackend:
    label = 'SYSTEMVERILOG SIMULATION — NOT FPGA HARDWARE'

    def __init__(self) -> None:
        for tool in ('iverilog', 'vvp'):
            if shutil.which(tool) is None:
                raise RuntimeError(f'{tool} is required for --backend rtl; no model fallback')
        out = ROOT / 'out'
        out.mkdir(exist_ok=True)
        binary = out / 'rally.vvp'
        subprocess.run(['iverilog', '-g2012', '-s', 'rally_bridge', '-o', str(binary),
                        str(ROOT / 'rtl/rally.sv'), str(ROOT / 'sim/rally_bridge.sv')],
                       check=True, timeout=30)
        self.process = subprocess.Popen(['vvp', str(binary)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, text=True, bufsize=1)
        self.lines: queue.Queue[str] = queue.Queue()
        def reader() -> None:
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.lines.put(line.strip())
            self.lines.put('EOF')
        self.thread = threading.Thread(target=reader, daemon=True)
        self.thread.start()

    def exchange(self, data: bytes) -> bytes:
        if not 1 <= len(data) <= 40:
            raise ValueError('RTL bridge supports 1–40 input bytes')
        if (self.process.stdin is None or self.process.stdin.closed
                or self.process.poll() is not None):
            raise OSError('RTL bridge is closed; restart the backend to reconnect')
        self.process.stdin.write(f'{len(data)} {data.hex()}\n')
        self.process.stdin.flush()
        try:
            line = self.lines.get(timeout=3)
        except queue.Empty as exc:
            self.close()
            raise TimeoutError('RTL bridge stopped responding') from exc
        if not line.startswith('R '):
            raise ProtocolError(f'RTL produced no complete reply: {line}')
        return bytes.fromhex(line[2:])

    def close(self) -> None:
        if self.process.poll() is None:
            if self.process.stdin is not None:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.process.stdout is not None:
            self.process.stdout.close()


class SerialBackend:
    label = 'UART DEVICE — VERIFY BITSTREAM AND BOARD ID SEPARATELY'

    def __init__(self, port: str) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError('Install pyserial==3.5 for UART operation') from exc
        self.port = serial.Serial(port, baudrate=115200, timeout=0.01, write_timeout=0.1)
        self.port.reset_input_buffer()

    def exchange(self, data: bytes) -> bytes:
        if len(data) != 10 or data[:2] != b'\xa5\x01':
            raise ProtocolError('serial request has invalid framing')
        # Preserve an intentionally damaged CRC for hardware fault-injection tests.
        seq = int.from_bytes(data[2:4], 'little')
        self.port.reset_input_buffer()
        self.port.write(data)
        deadline = time.monotonic() + 0.1
        window = bytearray()
        while time.monotonic() < deadline:
            window.extend(self.port.read(1))
            if len(window) > 7:
                del window[:-7]
            if len(window) == 7:
                try:
                    decode_reply(bytes(window), seq)
                    return bytes(window)
                except ProtocolError:
                    pass
        raise TimeoutError('UART reply deadline exceeded; movement suppressed')

    def close(self) -> None:
        self.port.close()


class Game:
    """Single-paddle practice game with deterministic fixed-step physics."""
    def __init__(self, seed: int = 7):
        self.random = random.Random(seed)
        self.x, self.y, self.paddle = 512, 512, 512
        self.vx, self.vy = -7, 4
        self.hits = self.misses = self.frame = 0
        self.enabled = True

    def step(self, backend, fault_every: int = 0) -> dict:
        seq = self.frame & 65535
        packet = request(seq, self.y, self.paddle, int(self.enabled))
        if fault_every and (self.frame + 1) % fault_every == 0:
            packet = packet[:-1] + bytes([packet[-1] ^ 1])
        started = time.perf_counter_ns()
        error, move, status = '', 0, 0
        try:
            reply = decode_reply(backend.exchange(packet), seq)
            move, status = reply.move, reply.status
        except (ProtocolError, TimeoutError, OSError) as exc:
            error = str(exc)
        elapsed = time.perf_counter_ns() - started
        if not self.enabled or error:
            move = 0
        self.paddle = max(96, min(927, self.paddle + move))
        self.x += self.vx
        self.y += self.vy
        if self.y < 0 or self.y > 1023:
            self.y = -self.y if self.y < 0 else 2046 - self.y
            self.vy = -self.vy
        if self.x > 1000:
            self.x, self.vx = 2000 - self.x, -abs(self.vx)
        if self.x < 32:
            if abs(self.y - self.paddle) <= 96:
                self.x, self.vx = 64 - self.x, abs(self.vx)
                self.hits += 1
            else:
                self.misses += 1
                self.x, self.y = 512, self.random.randrange(100, 924)
                self.vx = -7
        row = dict(frame=self.frame, x=self.x, y=self.y, paddle=self.paddle,
                   move=move, status=status, error=error, host_rtt_ns=elapsed,
                   hits=self.hits, misses=self.misses, enabled=self.enabled,
                   backend=backend.label)
        self.frame += 1
        return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['model', 'rtl', 'serial'], default='model')
    parser.add_argument('--port', help='USB-UART device; required for serial backend')
    parser.add_argument('--headless', type=int, default=0, metavar='FRAMES')
    parser.add_argument('--trace', type=Path, default=ROOT / 'out/rally.jsonl')
    parser.add_argument('--fault-every', type=int, default=0)
    args = parser.parse_args()
    if args.headless < 0 or args.fault_every < 0:
        parser.error('frame counts cannot be negative')
    if args.backend == 'serial' and not args.port:
        parser.error('--port is required for --backend serial')
    backend = {'model': ModelBackend, 'rtl': RTLBackend,
               'serial': lambda: SerialBackend(args.port)}[args.backend]()
    game = Game()
    args.trace.parent.mkdir(parents=True, exist_ok=True)
    print(backend.label, flush=True)
    try:
        with args.trace.open('w', encoding='utf-8') as trace:
            def tick() -> dict:
                row = game.step(backend, args.fault_every)
                trace.write(json.dumps(row) + '\n')
                trace.flush()
                return row
            if args.headless:
                for _ in range(args.headless):
                    row = tick()
                print(json.dumps(row, indent=2))
                return
            import tkinter as tk
            window = tk.Tk()
            window.title('Rally | explicit external-controller experiment')
            label = tk.Label(window, text=backend.label + '\nSpace: enable/disable | Esc: close')
            label.pack()
            canvas = tk.Canvas(window, width=720, height=480, background='black')
            canvas.pack()
            status_label = tk.Label(window, text='')
            status_label.pack()
            def toggle(_event):
                game.enabled = not game.enabled
            window.bind('<space>', toggle)
            window.bind('<Escape>', lambda _event: window.destroy())
            def animate():
                row = tick()
                canvas.delete('all')
                x, y, p = row['x'] * 720 / 1024, row['y'] * 480 / 1024, row['paddle'] * 480 / 1024
                canvas.create_rectangle(12, p - 45, 22, p + 45, fill='white')
                canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill='white')
                status_label.config(text=f"Hits {row['hits']} | Misses {row['misses']} | Move {row['move']} | "
                                   f"Enabled {game.enabled} | {row['error']}")
                window.after(16, animate)
            animate()
            window.mainloop()
    finally:
        backend.close()


if __name__ == '__main__':
    main()
