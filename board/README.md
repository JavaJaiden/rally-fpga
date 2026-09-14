# AS02MC04 bring-up contract

**Status: candidate integration, not compiled in Vivado or tested on a physical board.** The generic RTL and host program are separate from this board wrapper. Do not connect unverified pins or program an unknown card from a presumed matching model number.

## Hardware identity

The article identifies an Alibaba AS02MC04 with an XCKU3P-FFVB676. Its build example uses a `-2-e` speed grade; the pinned FPGA Ninja constraints identify `-1-e`. Read the actual device marking and confirm the Vivado target. The script therefore requires an explicit part rather than selecting one silently.

Pin facts were cross-checked against [FPGA Ninja's AS02MC04 constraints](https://github.com/fpganinja/taxi/blob/8567f91ef6bab46a261e98f5ab660731162605f5/src/cndm/board/AS02MC04/fpga/fpga.xdc). The board article's [updated voltage notes](https://essenceia.github.io/projects/alibaba_cloud_fpga/) matter: configuration/JTAG voltage and GPIO-bank voltage are not interchangeable.

| Lab signal | Candidate FPGA pin | Requirement |
|---|---|---|
| 100 MHz clock positive / negative | E18 / D18 | Existing differential oscillator; LVDS |
| UART receive | A14 | J5 GPIO; verify pad routing and 3.3 V VCCO |
| UART transmit | E12 | J5 GPIO; verify pad routing and 3.3 V VCCO |
| Heartbeat LED | B9 | Existing board LED; polarity affects display only |

The UART assignment is this project's wiring choice, not a factory USB-UART port. Required bench equipment is a suitable JTAG programmer with verified target voltage, a **3.3 V TTL** USB-UART adapter, appropriate board power and cooling, a multimeter, and preferably a logic analyzer. A 5 V TTL or bipolar RS-232 interface is not a substitute. The UART adapter must not power the accelerator card. Verify supply and connector requirements from the actual board before energizing it.

```text
Computer USB -> 3.3 V USB-UART TX -> verified A14 input
Computer USB <- 3.3 V USB-UART RX <- verified E12 output
USB-UART GND -------------------- verified board ground
Board power/cooling ------------ separate, verified supply
JTAG --------------------------- separate programming/debug path
```

Leave PCIe and SFP data interfaces unused for Rally. A power riser with a USB-shaped connector is not evidence of a USB protocol connection to the FPGA.

## Build and review

Run from the `rally-fpga` repository root. Replace `VERIFIED_PART` with the exact confirmed identifier; it is intentionally not a copy-and-run default.

```sh
vivado -mode batch -source board/build.tcl -tclargs VERIFIED_PART synth
vivado -mode batch -source board/build.tcl -tclargs VERIFIED_PART implement BOARD_PINOUT_AND_VOLTAGE_VERIFIED
vivado -mode batch -source board/build.tcl -tclargs VERIFIED_PART bitstream BOARD_PINOUT_AND_VOLTAGE_VERIFIED
```

The script does not program hardware or write nonvolatile flash. It retains Vivado DRC checks, checks worst setup/hold slack, and emits utilization, timing, CDC and unconstrained-path reports. Those checks are not a substitute for reviewing all reports. The asynchronous input exception targets only the first UART synchronizer stage and fails if the expected register cannot be uniquely identified. Do not broaden that exception just to obtain a green timing report.

The wrapper uses a configuration-initialized power-on counter, then a single 100 MHz clock domain. There is no assumption about reset-button polarity. Reconfiguration restarts that counter. A heartbeat proves only activity in the clocked wrapper, not protocol correctness.

## Acceptance sequence

First reproduce `python3 -m unittest -v` and `python3 sim/check_rtl.py`. Then record the board identity, clock and voltage measurements, build revision, tool version and report results. Review the wrapper and constraints before creating a bitstream. Load a temporary JTAG configuration only after that review; do not overwrite the factory flash during first bring-up.

Check UART idle-high level and approximately 8.68 microseconds per bit. At 100 MHz, the configured divisor 868 yields about 115,207 baud. Send one request at a time. Verify a centered target, both movement directions, disabled control, bad coordinates, corrupted CRC, partial request, reconnect and reset. A rejected or missing response must produce zero movement in the custom game.

Run the serial backend only after these checks:

```sh
python3 -m pip install pyserial==3.5
python3 rally.py --backend serial --port YOUR_SERIAL_DEVICE
```

Record the serial device, bitstream hash, board photograph, protocol trace and any logic-analyzer capture together. A serial response alone does not prove which board or bitstream produced it. No such physical acceptance record is included in this delivery.
