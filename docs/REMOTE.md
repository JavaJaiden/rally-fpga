# Connect to a friend's controller

## Before you start

The player needs Python 3.10 or later, Tk for the game window, an OpenSSH client and a
copy of this repository. The player does not need an FPGA, UART driver or simulator.
The friend needs the repository, an SSH service they control and either a verified
FPGA connected over UART or an explicitly selected model/RTL backend.

The friend provides an SSH account and a reachable hostname or IP address. Rally does
not configure routers, enable remote login, create SSH accounts or change firewalls.
Use the normal SSH sign-in flow. Do not disable host-key checking.

## Friend's machine

For the physical FPGA, finish [board bring-up](../board/README.md), install pyserial in
your Python environment, then start the relay:

```sh
python3 -m pip install pyserial==3.5
python3 relay.py --backend serial --port YOUR_UART_DEVICE
```

`YOUR_UART_DEVICE` is the device path on the friend's machine. The player does not use
that path. The relay prints its local TCP port and selected backend when it is ready.
It accepts one client at a time and keeps the FPGA transactions in order.

You can test the same layout without a board:

```sh
python3 relay.py --backend model
```

For real HDL simulation, install Icarus Verilog and use `--backend rtl`. The relay never
falls back from serial or RTL to a Python model.

## Player's machine

Open the tunnel in one terminal:

```sh
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -L 127.0.0.1:4768:127.0.0.1:4768 FRIEND_USER@FRIEND_HOST
```

Replace `FRIEND_USER@FRIEND_HOST` with the friend's SSH account and address. Both `127.0.0.1`
addresses are intentional: the first is your local listener; the second is the relay as
seen from the friend's computer. Keep the tunnel terminal open.

Start Rally in another terminal:

```sh
python3 rally.py --backend remote --expect-backend serial
```

Use `--expect-backend model` or `--expect-backend rtl` when the friend selected those
backends. A mismatch stops startup. The label describes the relay's declared backend;
only the friend can establish the identity of the connected board and bitstream.

Space disables or re-enables assistance. Escape closes the game. Close the game first,
then press Ctrl-C in the tunnel terminal. The friend can press Ctrl-C to stop the relay.

## Ports and timeouts

The default port is 4768 on both computers. If it is already in use on your computer,
change the first port in the tunnel and the client's `--remote-port` together:

```sh
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:4769:127.0.0.1:4768 FRIEND_USER@FRIEND_HOST
python3 rally.py --backend remote --remote-port 4769 --expect-backend serial
```

The friend can change the relay port with `--tcp-port`. The tunnel's final port must
match it. The raw Rally client and relay both use IPv4 loopback only. SSH provides
[encrypted, authenticated port forwarding](https://man.openbsd.org/ssh#L) between machines.
Do not publish the raw relay with a reverse proxy or a public port forward.

The default client transaction deadline is 0.25 seconds. `--remote-timeout` accepts a
positive value up to five seconds. A higher deadline tolerates a slower link, but can
pause a game update for that long. The relay releases a client that sends no complete
request for two seconds. One request is outstanding at a time; there is no prediction
or latency compensation.

A timeout, disconnect or invalid reply closes the client's socket. Later updates apply
zero movement until you restart the client. Ordinary controller rejection, such as a
corrupt request, applies zero movement for that update and keeps the connection open.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Connection refused | Start the friend relay, then the SSH tunnel, then the game |
| SSH cannot connect | Ask the friend to check the account, host address and SSH access |
| Address already in use | Choose another local port as shown above |
| Expected backend mismatch | Match `--expect-backend` to the friend's chosen backend |
| Startup times out | Another player may own the relay, or the tunnel may not reach it |
| Movement stays at zero with a connection error | Restore the connection and restart the player client |
| Frequent transaction rejection | Check the friend's UART, bitstream, framing and selected backend |
| Slow game updates | Check round-trip delay; every update waits for a controller reply |

`ExitOnForwardFailure` detects failure to establish a forwarding listener. It does not
prove the destination relay is running; the Rally handshake checks that connection.
See the [OpenSSH option reference](https://man.openbsd.org/ssh_config#ExitOnForwardFailure).

## What crosses the connection

The player sends only the game's fixed ten-byte state request. The friend returns an
eight-byte transport result containing either a checked controller reply or a rejection
marker. Neither side accepts scripts, file paths, commands or program downloads over
this channel. The player installs and starts their own copy of Rally.

For exact framing, see [the wire protocol](PROTOCOL.md). For the tests and their limits,
see [verification](VERIFICATION.md).
