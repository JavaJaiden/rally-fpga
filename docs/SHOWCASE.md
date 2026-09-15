# Demonstrate the remote setup

## Run it live without a board

Open two terminals in the repository. In the first, start the controller host:

```sh
python3 relay.py --backend rtl
```

In the second, start the player:

```sh
python3 rally.py --backend remote --expect-backend rtl --fault-every 23
```

The first process runs compiled SystemVerilog. The second runs the game and sends state
through a TCP connection. Both processes run locally for this demonstration. Moving the
relay to a friend's machine uses the [SSH setup](REMOTE.md); choosing `serial` there
connects it to the friend's verified FPGA.

Press Space to disable assistance. The ball keeps moving while controller movement
stays at zero. Press Space again to resume, then Escape to close the game.

## Show the recording

Download `docs/demo.html` and open it in a browser. It replays a retained remote-RTL run.
Pause at frame 22, the 23rd transaction: the corrupted request is rejected and movement
is zero. Frame 23 shows the next valid update. The backend label identifies the controller
used to produce the trace.

The SHA-256 digest on the page matches `docs/demo-trace.jsonl`. The HTML contains all of
its replay data and needs neither a running relay nor a board.

## Explain the design

- The player installs and runs a client. There is no hardware attached to that computer.
- The friend owns the controller host. UART connects that machine to the FPGA.
- An SSH tunnel carries state and controller replies between them.
- The player checks every reply before changing the paddle. A late response cannot be
  reused after the connection times out.

The game has an explicit state/control interface. Another game would need an adapter
for its supported interface. The remote layout does not by itself provide compatibility
with arbitrary games or establish that assistance is undetectable.

## Rebuild the recording

```sh
python3 verify.py
python3 replay.py --trace out/remote/rtl.jsonl --output out/rally-replay.html
```

The [verification record](../evidence/remote-verification/results.json) contains source
hashes and separate results for Python, RTL, remote transport and generic synthesis.
Physical-board operation and an actual SSH link between two computers remain untested.
