"""Run separate relay/client processes through real loopback TCP and real RTL.

This proves process and protocol separation on one computer. It does not measure
an SSH tunnel, a second physical computer, an internet route or a physical board.
"""
from pathlib import Path
import json
import queue
import signal
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'remote'


def state(row):
    return {**{k: v for k, v in row.items() if k not in ('host_rtt_ns', 'backend', 'error')},
            'rejected': bool(row['error'])}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / 'results.json'
    report = {'status': 'RUNNING', 'transport': 'loopback TCP, separate processes',
              'physical_board_tested': False, 'ssh_tunnel_tested': False, 'runs': []}
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    try:
        for mode in ('model', 'rtl'):
            with (OUT / f'relay-{mode}.log').open('w') as errors:
                process = subprocess.Popen([sys.executable, 'relay.py', '--backend', mode, '--tcp-port', '0'],
                                           cwd=ROOT, stdout=subprocess.PIPE, stderr=errors, text=True)
                lines = queue.Queue()
                reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
                reader.start()
                try:
                    hello = json.loads(lines.get(timeout=30))
                    if hello.get('backend') != mode or hello.get('listen') != '127.0.0.1':
                        raise RuntimeError('unexpected relay startup metadata')
                    command = [sys.executable, 'rally.py', '--backend', 'remote', '--expect-backend', mode,
                               '--remote-port', str(hello['port']), '--remote-timeout', '1',
                               '--headless', '1000', '--fault-every', '23',
                               '--trace', f'out/remote/{mode}.jsonl']
                    with (OUT / f'client-{mode}.log').open('w') as log:
                        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       check=True, timeout=120)
                    # Run a direct reference from the same source revision.
                    with (OUT / f'direct-{mode}.log').open('w') as log:
                        subprocess.run([sys.executable, 'rally.py', '--backend', mode, '--headless', '1000',
                                        '--fault-every', '23', '--trace', f'out/remote/direct-{mode}.jsonl'],
                                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
                    remote = [json.loads(line) for line in (OUT / f'{mode}.jsonl').read_text().splitlines()]
                    direct = [json.loads(line) for line in (OUT / f'direct-{mode}.jsonl').read_text().splitlines()]
                    if len(remote) != 1000 or [state(r) for r in remote] != [state(r) for r in direct]:
                        raise RuntimeError(f'{mode}: remote game differs from direct game')
                    rejected = [r for r in remote if r['error']]
                    if len(rejected) != 43 or any(r['move'] for r in rejected):
                        raise RuntimeError(f'{mode}: incorrect corruption handling')
                    if any(not r['backend'].startswith('REMOTE / ') for r in remote):
                        raise RuntimeError('remote backend attribution missing')
                    report['runs'].append({'backend': mode, 'frames': 1000, 'rejected': 43,
                                           'matches_direct_game': True})
                    print(f'PASS remote {mode}: 1000 frames, 43 rejected, direct game matches')
                finally:
                    if process.poll() is None:
                        process.send_signal(signal.SIGINT)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                    reader.join(timeout=1)
                    process.stdout.close()
        report['status'] = 'PASS'
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc)
        raise
    finally:
        manifest.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
