# Remote Rally review

Reviewed new `remote.py`, `relay.py`, `test_remote.py`, `sim/check_remote.py`, plus Rally CLI integration and `verify.py` remote-check integration. Read-only repository review. No P1/P2 defect identified.

## Independent checks

- Current `python3 -m unittest test_remote -v`: 10 tests PASS.
- A second client cannot complete its handshake while the first owns the single-client relay.
- After the first owner disconnects, a fresh client handshakes and receives a valid movement.
- A disconnected client that sent only a partial request does not contaminate the next connection's framing.
- Replies with stale sequence, bad CRC or unsafe movement close the client transport, apply zero movement, and remain at zero movement on the following game step.

These additional probes used actual loopback sockets. No SSH tunnel, separate physical machine or FPGA board was tested by this review.

## Correctness observations

Fixed-size receive loops tolerate TCP fragmentation and coalescing. Client send and receive share a total transaction deadline. Timeout/disconnect closes the connection so a late response cannot be applied on a later tick. Relay rejection envelopes remain aligned and allow subsequent requests, while malformed success envelopes close the client. The relay processes one client at a time and validates controller replies before forwarding them. Backend provenance is explicit but remains a claim by the relay host, as its label states.

The separate-process checker compares 1,000 remote states against 1,000 direct states, requires exactly 43 rejected requests with zero movement, and checks remote attribution. Manifest flags distinguish loopback TCP from untested SSH and physical hardware. Subprocess cleanup interrupts or kills the relay in a finally block; normal relay shutdown closes its controller backend.

## Operational boundary

The relay disconnects a client after a 2-second idle/partial-request deadline. The client intentionally requires restart after transport loss. Document this behavior so users do not mistake a paused/stalled player or lost tunnel for automatic reconnect support. Multi-machine latency and actual UART hardware remain separate acceptance work.
