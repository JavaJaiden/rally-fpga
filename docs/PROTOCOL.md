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
| 4 | 2 | Ball Y, valid 0–1023 |
| 6 | 2 | Paddle Y, valid 0–1023 |
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
