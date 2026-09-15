# Documentation and unslop review

The Humanizer skill guided a manual edit of the README, remote setup guide, protocol,
verification guide, showcase, board instructions, provenance note and replay copy.
This was an editorial review, not an AI-authorship detector.

- Replaced promotional language with concrete behavior and commands.
- Separated the player and friend roles in the README, guide and architecture diagram.
- Explained the installed player client, fixed controller messages and SSH tunnel.
- Removed repeated caveats while keeping the actual limits beside the related claims.
- Preserved source attribution and the distinction between simulation and hardware.
- Checked Markdown fences, local file links and whitespace; inspected the diagram and
  replay in the browser, including a rejected frame showing zero movement.

An independent read-only reviewer checked the setup instructions against the code.
Two wording fixes followed: the verifier now describes the baseline commit separately
from the checked working-tree hashes, and the replay footer states the supported
interface and playback-speed limit without repeating earlier paragraphs.

The retained verification manifest records 20 passing Python tests, controller/UART/
board-wrapper RTL checks, separate-process remote demos and generic synthesis.
A second physical machine, SSH route, routed timing and physical FPGA were not tested.
