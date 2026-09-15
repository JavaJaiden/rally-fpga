# Rally wire contract

UART is 115200 baud, 8 data bits, no parity, one stop bit; the candidate 100 MHz
wrapper uses divisor 868. Multi-byte fields are little-endian. Each frame has CRC-8
(polynomial 0x07, initial 0, no reflection/final XOR) over all preceding bytes.
The check vector `123456789` produces 0xF4.

## Request: 10 bytes

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 1 | Magic 0xA5 |
| 1 | 1 | Version 1 |
| 2 | 2 | Sequence |
| 4 | 2 | Ball Y, valid 0 through 1023 |
| 6 | 2 | Paddle Y, valid 0 through 1023 |
| 8 | 1 | Flags: bit 0 enables; other bits must be zero |
| 9 | 1 | CRC-8 |

## Reply: 7 bytes

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 1 | Magic 0x5A |
| 1 | 1 | Version 1 |
| 2 | 2 | Echoed sequence |
| 4 | 1 | Signed two's-complement movement, -8 through +8 |
| 5 | 1 | Status bitmap |
| 6 | 1 | CRC-8 |

Status bit 0 means disabled, bit 1 invalid coordinate, bit 2 unsupported flags.
Any nonzero status implies zero movement. An error within ±2 pixels produces zero;
otherwise the difference is clamped to ±8. Invalid framing or CRC produces no reply.

## Flow and failure behavior

Only one transaction may be outstanding. The framer discards RX bytes during a pending
reply, keeps each TX byte stable until ready, and searches a sliding ten-byte window
for the next valid request. A quiet gap clears partial framing state. The default board
gap is 1,000,000 clocks (10 ms at the intended 100 MHz); simulation bridge uses a shorter
parameter to test recovery. UART framing errors reset the board framer.

The host validates framing, CRC, sequence echo, status and movement bounds. A failed
transaction applies zero movement. After a simulator failure, later frames stay at zero
movement with a transport error; restart the backend to reconnect. There is no silent
fallback to the model. Serial exchange uses a 100 ms reply deadline.

CRC and a wrapping 16-bit sequence identify common corruption/stale replies, not a
security or anti-cheat mechanism. They provide no authentication or replay-proof channel.

## Remote transport

The relay listens only on IPv4 loopback. An SSH local forward carries the connection
between the player and friend machines. TCP byte-stream reads use a single deadline
for the whole frame, including fragmented arrivals; see the [Python socket reference](https://docs.python.org/3.10/library/socket.html).

The server sends a five-byte greeting immediately after accepting a connection:

| Bytes | Meaning |
| --- | --- |
| 0 through 3 | ASCII `RLY1`, transport version 1 |
| 4 | Backend: 0=model, 1=RTL, 2=serial |

The greeting reports the selected backend. It does not authenticate the friend or
prove hardware identity. SSH authenticates the host; the friend verifies the FPGA.
`--expect-backend` lets the player reject an unintended model or simulator.

After the greeting, each request is the existing ten-byte Rally frame. Each response
is eight bytes: status 0 followed by the seven-byte Rally reply, or status 1 followed
by seven zero bytes for a rejected/unavailable controller transaction. There are no
variable-length payloads, executable commands or software downloads.

The relay owns one controller and processes one connected client at a time. It closes
a connection after two seconds without a complete request. A partial request is discarded
when that connection closes. CRC rejection keeps the connection open so a later valid
request can proceed.

The client uses a total transaction deadline, checks the existing reply CRC and sequence,
and rejects movement outside the existing bounds. Timeout, EOF, an unknown transport
status or an invalid reply closes the socket. Later frames apply zero movement until
the player restarts the client. A status-1 controller rejection applies zero movement
for that transaction but leaves the socket open.
