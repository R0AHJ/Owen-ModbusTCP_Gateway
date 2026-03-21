# Current Modbus Map: 2 Lines

Current verified runtime setup:

- common Modbus-TCP endpoint: `0.0.0.0:15020`
- line 1: `COM6`, `9600 8N1`, device base `96`, `SlaveID 10`
- line 2: `COM8`, `9600 8N1`, device base `48`, `SlaveID 50`
- byte order for `float32`: `ABCD`

## Slave IDs

| Slave ID | Meaning |
|---:|---|
| `1` | gateway service tags |
| `10` | line 1, `COM6`, device base `96` |
| `50` | line 2, `COM8`, device base `48` |

## Service Tags In `SlaveID 1`

| Register | Meaning |
|---|---|
| `HR1` | aggregated gateway status |
| `HR2` | aggregated last error code |
| `HR3` | aggregated success counter |
| `HR4` | aggregated timeout counter |
| `HR5` | aggregated protocol error counter |
| `HR6` | aggregated poll cycle counter |
| `HR10` | line 1 status |
| `HR11` | line 2 status |
| `HR12` | line 3 status |
| `HR13` | line 4 status |

Status codes:

- `1` ok
- `2` degraded
- `3` offline
- `4` protocol error

Last error codes:

- `0` none
- `1` timeout
- `2` bad flag
- `3` hash mismatch
- `4` decode error
- `5` io error

## Device Map In `SlaveID 10` And `SlaveID 50`

The same channel map is used for both devices:

| Channel | Value | Time Mark | Status |
|---|---|---|---|
| `CH1` | `HR16..HR17` | `HR18` | `HR19` |
| `CH2` | `HR20..HR21` | `HR22` | `HR23` |
| `CH3` | `HR24..HR25` | `HR26` | `HR27` |
| `CH4` | `HR28..HR29` | `HR30` | `HR31` |
| `CH5` | `HR32..HR33` | `HR34` | `HR35` |
| `CH6` | `HR36..HR37` | `HR38` | `HR39` |
| `CH7` | `HR40..HR41` | `HR42` | `HR43` |
| `CH8` | `HR44..HR45` | `HR46` | `HR47` |

Channel status codes:

- `0` disabled / no data / empty payload
- `1` ok
- `2` stale
- `3` temporary communication error
- `4` protocol error
- `5` failed, reduced polling

## Observed Behaviour

For `SlaveID 10`:

- device on `COM6`, base `96`, responds normally
- channel `102` maps to `CH7` and returns empty payload as valid `status 0`

For `SlaveID 50`:

- device on `COM8`, base `48`, responds normally on `CH1`
- channels based on addresses `49..55` currently return empty payload as valid `status 0`
