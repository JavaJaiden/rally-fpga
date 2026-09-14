"""Deterministic tests for Rally FPGA."""
import random
import struct
import unittest
import io
import queue
from unittest.mock import patch
import rally as r

class RallyTests(unittest.TestCase):
    def test_crc_known_vector(self):
        self.assertEqual(r.crc8(b'123456789'), 0xF4)

    def test_control_boundaries(self):
        for error, expected in [(-1023,-8),(-9,-8),(-8,-8),(-3,-3),(-2,0),(0,0),(2,0),(3,3),(8,8),(9,8),(1023,8)]:
            ball, paddle = (error,0) if error>=0 else (0,-error)
            self.assertEqual(r.decision(ball,paddle,1),(expected,0))
        for ball,paddle,flags in [(65535,0,1),(0,65535,1),(5,6,0),(5,6,3)]:
            move,status=r.decision(ball,paddle,flags)
            self.assertEqual(move,0); self.assertNotEqual(status,0)

    def test_request_roundtrip_random(self):
        rng=random.Random(20260914); backend=r.ModelBackend()
        for _ in range(2000):
            seq=rng.randrange(65536); ball=rng.randrange(1100); paddle=rng.randrange(1100); flags=rng.randrange(4)
            reply=r.decode_reply(backend.exchange(r.request(seq,ball,paddle,flags)),seq)
            self.assertEqual((reply.move,reply.status),r.decision(ball,paddle,flags))

    def test_all_single_bit_corruptions(self):
        data=r.request(0xAA55,512,300)
        for bit in range(80):
            corrupt=bytearray(data); corrupt[bit//8]^=1<<(bit%8)
            with self.assertRaises(r.ProtocolError): r.ModelBackend().exchange(bytes(corrupt))
        data=r.response(7,-8,0)
        for bit in range(56):
            corrupt=bytearray(data); corrupt[bit//8]^=1<<(bit%8)
            with self.assertRaises(r.ProtocolError): r.decode_reply(bytes(corrupt),7)

    def test_reject_stale_unsafe_and_bad_status(self):
        for seq,move,status in [(8,0,0),(7,9,0),(7,1,1),(7,0,128)]:
            with self.assertRaises(r.ProtocolError): r.decode_reply(r.response(seq,move,status),7)
        with self.assertRaises(ValueError): r.request(-1,0,0)
        with self.assertRaises(ValueError): r.request(0,0,0,256)

    def test_game_failure_is_zero_movement(self):
        class Broken:
            label='TEST TIMEOUT'
            def exchange(self,data): raise TimeoutError('injected')
        game=r.Game(); before=game.paddle
        row=game.step(Broken())
        self.assertEqual(row['move'],0); self.assertEqual(game.paddle,before)
        self.assertIn('injected',row['error'])

    def test_rtl_timeout_stays_fail_closed_on_later_frames(self):
        class Process:
            stdin = io.StringIO()
            stdout = io.StringIO()
            exited = False
            def poll(self): return 0 if self.exited else None
            def wait(self, timeout=None): self.exited = True
        backend = r.RTLBackend.__new__(r.RTLBackend)
        backend.process = Process()
        backend.lines = queue.Queue()
        game = r.Game()
        with patch.object(backend.lines, 'get', side_effect=queue.Empty):
            first = game.step(backend)
        self.assertEqual(first['move'], 0)
        self.assertIn('stopped responding', first['error'])
        # Real close after timeout must make later exchanges predictable too.
        backend.process.stdin.close()
        second = game.step(backend)
        self.assertEqual(second['move'], 0)
        self.assertTrue(second['error'])

    def test_disabled_and_deterministic_game(self):
        a,b=r.Game(19),r.Game(19)
        backend=r.ModelBackend()
        for _ in range(600):
            ar=a.step(backend); br=b.step(backend)
            ar.pop('host_rtt_ns'); br.pop('host_rtt_ns')
            self.assertEqual(ar,br)
        a.enabled=False
        self.assertEqual(a.step(backend)['move'],0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
