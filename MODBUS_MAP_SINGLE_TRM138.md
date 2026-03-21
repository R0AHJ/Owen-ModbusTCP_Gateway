# Modbus Map: Single OVEN TRM138

This file describes the active Modbus-TCP map for the current single-device
gateway scenario:

- device: `OVEN TRM138`
- serial line: `COM6`, `9600 8N1`
- OVEN base address range: `96..103`
- OVEN addressing mode in config: `8-bit`
- Modbus transport: `Modbus TCP`
- gateway listen address: `0.0.0.0:15020`
- recommended test client unit id: `1`

## Addressing Note

The configured register addresses are used literally in the gateway map:

- service status starts at `HR1`
- channel 1 starts at `HR16`

For clients with zero-based addressing this usually means:

- `HR1` -> address `1`
- `HR2` -> address `2`
- `HR16` -> address `16`

Always verify how the specific Modbus client interprets register numbering.

## Service Registers

| Register | Name | Type | Meaning |
|---|---|---|---|
| `HR1` | `gateway_status` | `uint16` | Aggregated gateway/bus status |
| `HR2` | `last_error_code` | `uint16` | Last detected error code |
| `HR3` | `success_counter` | `uint16` | Successful point polls counter |
| `HR4` | `timeout_counter` | `uint16` | Poll timeout counter |
| `HR5` | `protocol_error_counter` | `uint16` | Protocol/decoding error counter |
| `HR6` | `poll_cycle_counter` | `uint16` | Poll cycle counter |

## Gateway Status Values

| Value | Meaning |
|---:|---|
| `1` | `ok` |
| `2` | `degraded` |
| `3` | `offline` |
| `4` | `protocol error` |

Meaning details:

- `gateway status = ok` means all configured points on the bus were read normally
- `gateway status = degraded` means only part of the configured points were read
- `gateway status = offline` means all configured points failed by communication
- `gateway status = protocol error` means all configured points failed by protocol/format validation

## Last Error Code Values

| Value | Meaning |
|---:|---|
| `0` | `none` |
| `1` | `timeout` |
| `2` | `bad flag` |
| `3` | `hash mismatch` |
| `4` | `decode error` |
| `5` | `io error` |

Meaning details:

- `last error code = none` means no active/last recorded error for the latest cycle
- `timeout` means no valid response was received from the device in time
- `bad flag` means the response looked like a request frame instead of a response
- `hash mismatch` means the returned OVEN parameter hash did not match the requested parameter
- `decode error` means the payload could not be parsed as configured
- `io error` means a non-timeout serial/runtime failure occurred

## Channel Registers

Each channel occupies four holding registers:

- `2` registers for `float32` value
- `1` register for `time mark`
- `1` register for `channel status`

Byte order observed in validation client:

- `float32` values were decoded correctly with byte order `ABCD`

| Channel | OVEN Address | Value Registers | Time Mark | Status | Value Type |
|---|---:|---|---|---|---|
| `CH1` | `96` | `HR16..HR17` | `HR18` | `HR19` | `float32` |
| `CH2` | `97` | `HR20..HR21` | `HR22` | `HR23` | `float32` |
| `CH3` | `98` | `HR24..HR25` | `HR26` | `HR27` | `float32` |
| `CH4` | `99` | `HR28..HR29` | `HR30` | `HR31` | `float32` |
| `CH5` | `100` | `HR32..HR33` | `HR34` | `HR35` | `float32` |
| `CH6` | `101` | `HR36..HR37` | `HR38` | `HR39` | `float32` |
| `CH7` | `102` | `HR40..HR41` | `HR42` | `HR43` | `float32` |
| `CH8` | `103` | `HR44..HR45` | `HR46` | `HR47` | `float32` |

## Channel Status Values

| Value | Meaning |
|---:|---|
| `0` | `disabled / no data / empty payload` |
| `1` | `ok` |
| `2` | `stale` |
| `3` | `temporary communication error` |
| `4` | `protocol error` |
| `5` | `failed, reduced polling` |

Meaning details:

- `channel status = 0` is valid for channels that return empty payload instead of a measurement
- `channel status = 1` means value is accepted as normal
- `channel status = 2` means the value still decodes but the time mark has not changed for too many cycles
- `channel status = 3` means a temporary communication problem occurred
- `channel status = 4` means a protocol/format validation problem occurred
- `channel status = 5` means repeated failures pushed the channel into reduced polling mode

## Time Mark Logic

- if payload length is `6`, the last two bytes are interpreted as the channel time mark
- up to `3` consecutive unchanged time marks are acceptable
- after that the channel status becomes `stale`
- after `10` consecutive failed polls the channel status becomes `failed`
- failed channels are polled less frequently

## Observed Runtime Validation

Validated on real hardware on `2026-03-21`:

- `CoreBus` successfully connected to the gateway
- `HR1 = 1` -> `gateway status = ok`
- `HR2 = 0` -> `last error code = none`
- `HR16..HR17` decoded as a live `float32` value around `493.xxx`
- channels `96, 97, 98, 99, 100, 101, 103` returned valid data
- channel `102` returned empty payload and is treated as valid no-data
