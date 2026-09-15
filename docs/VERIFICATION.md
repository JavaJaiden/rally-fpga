# Verification

Run `python3 verify.py` from the repository root. The command writes a new
`out/verification/results.json` and returns a nonzero exit code if a check fails.
A RUNNING or FAIL manifest is not a pass. `source_sha256` identifies the files checked;
`base_commit` records the committed Git HEAD when the run started. The source hashes
identify the checked working-tree bytes, including any uncommitted edits.

## Checks

| Level | What it exercises |
| --- | --- |
| Python | Reference model, protocol boundaries, replay export and real-socket failure cases |
| RTL | Icarus-compiled controller, UART and actual board wrapper, with independent comparisons |
| Remote processes | Separate relay and game processes over loopback TCP, using model and RTL controllers |
| Generic synthesis | Yosys `synth` and `check -assert` for the framer and UART modules |

The socket tests cover fragmented and coalesced packets, partial connections, corrupt
requests, backend mismatch, device errors, timeouts, stale sequences and unsafe movement.
The remote-process checks compare each run against a direct run of the same controller.
Both sides must have 1,000 identical game states and reject 43 injected corrupt requests.

The relay's two-second idle timeout and the client's transaction deadline serve different
purposes. The first releases an inactive player's controller slot. The second prevents a
late movement from being applied to a later frame. The client closes its connection after
a timeout, disconnect or invalid reply and requires a restart to reconnect.

## Evidence files

`evidence/remote-verification/` retains the network revision's logs and source hashes.
`evidence/local-verification/` retains the earlier local-controller run. Neither directory
is updated automatically by a future run; new verification writes to `out/`.

The [GitHub workflow](../.github/workflows/verify.yml) invokes the same verifier. Account
billing blocked hosted jobs during this audit. The retained passing results came from
local commands, independently of GitHub Actions.

## Checks that still require the deployment

The loopback tests do not establish a working SSH route, second physical host, internet
latency or attached FPGA. Test those on the actual two computers. For a physical board,
record its identity, reviewed wiring and constraints, bitstream hash and UART captures.
Follow [board bring-up](../board/README.md) before connecting or programming hardware.

Generic synthesis does not include vendor placement, routing, device utilization,
electrical measurements or timing closure. Neither the replay speed nor host round-trip
time is an FPGA latency measurement.
