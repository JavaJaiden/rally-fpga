# Two-minute Rally demonstration

1. Open `docs/demo.html`. Explain: “This is an external cheat for the Pong game included
   in the project. The game exports state and accepts checked movement; it is not a
   universal adapter for commercial games.”
2. Point to the backend label: the retained replay came from compiled SystemVerilog.
   Pause and scrub to frame 22 (the 23rd transaction). Validation reports rejection and
   movement is zero. Continue to frame 23 to show recovery.
3. Explain the split: the game owns physics; the controller sees ball and paddle Y and
   proposes movement. The host checks CRC, sequence, status and bounds before applying it.
4. Show `python3 verify.py` and `evidence/local-verification/results.json`. Separate
   model, RTL, and synthesis results from the still-unperformed board bring-up.

## Talking points

- A repeated simulator timeout originally crashed the next frame. A regression now proves
  two successive game updates stay at zero movement after transport failure.
- Tests exercise the actual board wrapper through serial pins in simulation, using an
  independent reply sampler at the configured 868-clock divisor.
- The two-pixel deadband avoids tiny corrections; the eight-pixel clamp bounds actuation.
- A physical demo requires the verified board and vendor toolchain. The replay is portable,
  but it cannot establish electrical behavior or hardware latency.

## Rebuild the retained demo

```sh
python3 verify.py
python3 replay.py --trace out/rally-rtl.jsonl --output out/rally-replay.html
```

The trace digest on the page identifies `docs/demo-trace.jsonl`, retained with this demo.
