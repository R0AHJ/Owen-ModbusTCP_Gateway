# Modbus Map: Single TRM138

Validated single-device layout:

- line: `COM6`, `9600 8N1`
- device base OVEN address: `96`
- device `SlaveID`: `96`
- endpoint: `0.0.0.0:15020`

## Service Registers

- `SlaveID 1`, `HR1..HR6`

## Device Registers

| Channel | OVEN Address | Value | Time Mark | Status |
|---|---:|---|---:|---:|
| `CH1` | `96` | `HR16..HR17` | `HR32` | `HR40` |
| `CH2` | `97` | `HR18..HR19` | `HR33` | `HR41` |
| `CH3` | `98` | `HR20..HR21` | `HR34` | `HR42` |
| `CH4` | `99` | `HR22..HR23` | `HR35` | `HR43` |
| `CH5` | `100` | `HR24..HR25` | `HR36` | `HR44` |
| `CH6` | `101` | `HR26..HR27` | `HR37` | `HR45` |
| `CH7` | `102` | `HR28..HR29` | `HR38` | `HR46` |
| `CH8` | `103` | `HR30..HR31` | `HR39` | `HR47` |

Additional register:

- `HR48` -> LU state mask, `bit0..bit7 -> LU1..LU8`

## Channel Status Codes

- `0` disabled / no data / empty payload
- `1` ok
- `2` temporary communication error
- `3` protocol error
- `4` failed, reduced polling

## Notes

- `time mark` is published as received from the device
- `time mark` does not change channel status
- `TRM138` parameters `C.SP`, `HYSt`, `AL.t` are read by OVEN address
- `C.SP` is decoded from OVEN `stored_dot`
