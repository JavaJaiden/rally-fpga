"""Integrity and backend attribution for shareable replays."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import rally
import replay

class ReplayTests(unittest.TestCase):
    def test_replay_retains_trace_digest_and_escapes_label(self):
        row=rally.Game().step(rally.ModelBackend())
        row['backend']='MODEL <script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'trace.jsonl'; target=Path(directory)/'out.html'
            source.write_text(json.dumps(row)+'\n')
            replay.export(source,target)
            page=target.read_text()
            self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest(),page)
            self.assertNotIn(row['backend'],page)
            self.assertIn('MODEL &lt;script&gt;',page)

    def test_mixed_backends_rejected(self):
        row=rally.Game().step(rally.ModelBackend())
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'trace.jsonl'
            source.write_text(json.dumps(row)+'\n'+json.dumps(dict(row,backend='UART'))+'\n')
            with self.assertRaises(ValueError): replay.export(source,Path(directory)/'out.html')

if __name__=='__main__': unittest.main()
