# Release Notes: v0.1.0-pre1

## Scope

Preliminary release of the OVEN RS-485 -> Modbus TCP gateway for `TRM138`.

## Included

- device `SlaveID` equals base OVEN address
- TRM138 register map reordered to:
  - values `HR16..HR31`
  - time marks `HR32..HR39`
  - statuses `HR40..HR47`
- LU state mask in `HR48`
- `C.SP` decoding for OVEN `stored_dot`
- support for both `2`-byte and `3`-byte `stored_dot`
- `C.SP`, `HYSt`, `AL.t` read by channel address
- no internal Modbus RTU path to the device
- channel status no longer depends on unchanged `time mark`
- updated Windows and Linux example configs
- refreshed documentation

## Validation

- unit tests: `46 OK`
- real hardware validation on `COM4`, address `48`
- confirmed example:
  - `rEAd ~= 88.92`
  - `C.SP = 100.0`
  - `HYSt = 1`
  - `AL.t = 1`
  - `HR48 = 1`

## Compatibility Note

Legacy config field `health.stale_after_cycles` is accepted but ignored.
