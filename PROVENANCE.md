# Provenance

This repository separates Rally FPGA from the earlier combined learning lab at
`JavaJaiden/narby`, commit `f82a0f0127c6d2c4a394f4f00706604d8d47ef1d`.
Its application and RTL source files are unchanged by the split. The Python tests,
HDL harness, workflow and documentation have been separated for standalone use.
The original MIT notice is retained. The implementation was developed with AI assistance.

The source archive was checked against all 24 source/workflow Git blob hashes before
splitting. Split-baseline verification was recorded in `evidence/standalone-verification.json`;
previous combined-lab counts are not presented as new standalone results.

Board references:

- Essenceia, Alibaba AS02MC04 investigation: https://essenceia.github.io/projects/alibaba_cloud_fpga/
- FPGA Ninja TAXI, pinned board reference: https://github.com/fpganinja/taxi/tree/8567f91ef6bab46a261e98f5ab660731162605f5/src/cndm/board/AS02MC04

The board files are candidates, not a verified bitstream. This is a controller for
the included game; it does not access other programs or bypass their protections.

## Local hardening and showcase release

Subsequent commits add integrated tests, reproducible generic synthesis and shareable
demos. Current audit evidence is in `evidence/local-verification/results.json`.
The original split logs remain historical; physical board operation is still unverified.

## Remote controller transport

The remote client and relay are new Python components around the existing request/reply
protocol. SSH carries their connection between machines. The FPGA RTL remains unchanged.
Network revision evidence is retained under `evidence/remote-verification/`.
