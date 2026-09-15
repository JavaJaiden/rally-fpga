"""Real-socket tests for the player client and the friend's relay."""
import contextlib
import socket
import threading
import time
import unittest

import rally as r
from remote import RemoteBackend, RemoteError, RelayServer, receive_exact


@contextlib.contextmanager
def serving(backend=None, mode='model'):
    server=RelayServer(('127.0.0.1',0),backend or r.ModelBackend(),mode)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
    thread.start()
    try:
        yield server.server_address
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        if thread.is_alive(): raise AssertionError('relay did not stop')


class RemoteTests(unittest.TestCase):
    def test_remote_game_matches_local_model_and_rejects_bad_crc(self):
        with serving() as address:
            remote=RemoteBackend(*address)
            try:
                self.assertIn('REMOTE',remote.label)
                self.assertIn('PYTHON MODEL',remote.label)
                a,b=r.Game(),r.Game()
                for _ in range(100):
                    ar=a.step(remote,fault_every=23);br=b.step(r.ModelBackend(),fault_every=23)
                    for key in ('host_rtt_ns','backend'):ar.pop(key);br.pop(key)
                    ar['error']=bool(ar['error']);br['error']=bool(br['error'])
                    self.assertEqual(ar,br)
            finally:remote.close()

    def test_bad_remote_ports_are_rejected_before_connecting(self):
        for port in (-1, 0, 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                RemoteBackend(port=port)

    def test_partial_request_does_not_contaminate_next_connection(self):
        with serving() as address:
            with socket.create_connection(address,timeout=1) as client:
                receive_exact(client,5,time.monotonic()+1)
                client.sendall(b'\xa5\x01')
            remote=RemoteBackend(*address)
            try:
                wire=r.request(12,900,100)
                self.assertEqual(remote.exchange(wire),r.ModelBackend().exchange(wire))
            finally:remote.close()

    def test_stale_or_unsafe_server_reply_closes_the_connection(self):
        for reply in (r.response(999,1,0),r.response(0,9,0),r.response(0,1,1)):
            with self.subTest(reply=reply):
                listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
                def peer():
                    with listener:
                        client,_=listener.accept()
                        with client:
                            client.sendall(b'RLY1\x00')
                            receive_exact(client,10,time.monotonic()+1)
                            client.sendall(b'\0'+reply)
                thread=threading.Thread(target=peer,daemon=True);thread.start()
                remote=RemoteBackend(*listener.getsockname())
                try:
                    game=r.Game();row=game.step(remote)
                    self.assertTrue(row['error']);self.assertEqual(row['move'],0)
                    self.assertIsNone(remote.connection)
                finally:remote.close();thread.join(timeout=2)

    def test_fragmented_request_and_two_coalesced_requests(self):
        with serving() as address:
            with socket.create_connection(address,timeout=1) as client:
                self.assertEqual(receive_exact(client,5,time.monotonic()+1),b'RLY1\x00')
                packet=r.request(7,900,100)
                for value in packet:client.sendall(bytes([value]))
                self.assertEqual(receive_exact(client,8,time.monotonic()+1),b'\0'+r.ModelBackend().exchange(packet))
                other=r.request(8,200,300)
                client.sendall(packet+other)
                expected=b'\0'+r.ModelBackend().exchange(packet)+b'\0'+r.ModelBackend().exchange(other)
                self.assertEqual(receive_exact(client,16,time.monotonic()+1),expected)

    def test_late_reply_is_discarded_and_later_game_steps_stay_zero(self):
        class Slow(r.ModelBackend):
            def exchange(self,data):time.sleep(.15);return super().exchange(data)
        with serving(Slow()) as address:
            remote=RemoteBackend(*address,timeout=.03)
            try:
                game=r.Game();game.y=900
                first=game.step(remote)
                self.assertEqual(first['move'],0)
                self.assertTrue(first['error'])
                time.sleep(.2)
                second=game.step(remote)
                self.assertEqual(second['move'],0)
                self.assertTrue(second['error'])
            finally:remote.close()

    def test_relay_refuses_nonloopback_binding(self):
        with self.assertRaises(ValueError):RelayServer(('0.0.0.0',0),r.ModelBackend(),'model')

    def test_expected_backend_mismatch_is_rejected(self):
        with serving() as address:
            with self.assertRaises(RemoteError):RemoteBackend(*address,expected_backend='serial')

    def test_backend_failure_does_not_apply_a_move(self):
        class Broken(r.ModelBackend):
            def exchange(self,data):raise OSError('device disconnected')
        with serving(Broken()) as address:
            remote=RemoteBackend(*address)
            try:
                row=r.Game().step(remote)
                self.assertEqual(row['move'],0);self.assertTrue(row['error'])
            finally:remote.close()

    def test_partial_reply_and_disconnect_cannot_apply_movement(self):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
        def peer():
            with listener:
                client,_=listener.accept()
                with client:
                    client.sendall(b'RLY1\x00')
                    receive_exact(client,10,time.monotonic()+1)
                    client.sendall(b'\0\x5a')
        thread=threading.Thread(target=peer,daemon=True);thread.start()
        remote=RemoteBackend(*listener.getsockname())
        try:
            game=r.Game();row=game.step(remote)
            self.assertTrue(row['error']);self.assertEqual(row['move'],0)
            self.assertTrue(game.step(remote)['error'])
        finally:remote.close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
