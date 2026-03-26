# Current Modbus Map: 2 Lines

Current verified setup:

- endpoint: `0.0.0.0:15020`
- line 1: `COM6`, `9600 8N1`, base address `96`, device `SlaveID 96`
- line 2: `COM8`, `9600 8N1`, base address `48`, device `SlaveID 48`

## Service Slave

`SlaveID 1`

- `HR1` gateway status
- `HR2` last error code
- `HR3` success counter
- `HR4` timeout counter
- `HR5` protocol error counter
- `HR6` poll cycle counter
- `HR10` line 1 status
- `HR11` line 2 status

## Device Slave Map

The same register layout is used on both device `SlaveID`.

| Channel | Value | Time Mark | Status |
|---|---|---:|---:|
| `CH1` | `HR16..HR17` | `HR32` | `HR40` |
| `CH2` | `HR18..HR19` | `HR33` | `HR41` |
| `CH3` | `HR20..HR21` | `HR34` | `HR42` |
| `CH4` | `HR22..HR23` | `HR35` | `HR43` |
| `CH5` | `HR24..HR25` | `HR36` | `HR44` |
| `CH6` | `HR26..HR27` | `HR37` | `HR45` |
| `CH7` | `HR28..HR29` | `HR38` | `HR46` |
| `CH8` | `HR30..HR31` | `HR39` | `HR47` |

Additional register:

- `HR48` -> LU state mask, `bit0..bit7 -> LU1..LU8`

## Channel Status Codes

- `0` disabled / no data / empty payload
- `1` ok
- `2` temporary communication error
- `3` protocol error
- `4` failed, reduced polling
