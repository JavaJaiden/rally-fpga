# Rally FPGA

External control of an included Pong game through a CRC-framed UART protocol.
The Python reference, SystemVerilog simulator, and serial board are selected
explicitly. No backend silently substitutes for another.

This standalone repository contains the game, replay exporter, RTL, tests, CI,
and candidate Alibaba AS02MC04 board files. It has no dependency on FeedGuard
or the previous combined repository.

## Run

Python 3.10 or newer is required. The reference model has no third-party packages.

```sh
python3 -m unittest -v
python3 rally.py --backend model --headless 1000 --fault-every 23
python3 replay.py --trace out/rally.jsonl --output out/rally-replay.html
```

Open `out/rally-replay.html` to replay the recorded model run. For a game window,
install Tk support for your Python distribution and run:

```sh
python3 rally.py --backend model
```

Space enables/disables the controller. Escape closes the window.

## Controller and protocol

The controller computes a signed position error, applies a two-pixel deadband,
and clamps movement to eight pixels per transaction. Valid positions range
from 0 through 1023. Invalid coordinates, invalid flags, or disabled control
produce a status response and zero movement.

Requests contain a version, sequence, positions, flags and CRC-8. Replies echo
the sequence and contain a bounded move, status and CRC. The host rejects bad
framing, CRC, sequence and motion bounds. Transport failures produce zero
movement for the current update. CRC detects transmission errors, not forgery.

## Verification

```sh
# Requires Icarus Verilog and vvp; missing tools cause failure.
python3 sim/check_rtl.py

# Run the included game through the compiled RTL bridge.
python3 rally.py --backend rtl
```

The standalone HDL harness contains only Rally and UART checks. The workflow
runs Python tests, real RTL comparisons and generic Yosys structural checks.
A workflow file is not a passing result; current local results are under
`evidence/`. No board operation or routed timing is claimed.

## Physical UART

After the board has been identified, reviewed, built and independently tested:

```sh
python3 -m pip install pyserial==3.5
python3 rally.py --backend serial --port YOUR_SERIAL_DEVICE
```

Read [the board procedure](board/README.md) before connecting any pins or
programming hardware. The board wrapper and constraints are candidates,
not a board-qualified bitstream.

This controller operates only through the included game's explicit interface.
It has no third-party process access, input injection or protection bypass.
It is neither a universal controller for arbitrary games nor a claim of
undetectable behavior.

## Source and license

See [PROVENANCE.md](PROVENANCE.md) and [LICENSE](LICENSE).
