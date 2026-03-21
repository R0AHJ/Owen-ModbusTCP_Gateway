# Session Notes

## Current State

Project is reduced to the `OWEN RS-485 -> Modbus-TCP` scenario.

The gateway now works in the simplified multi-line / single-port mode:

- one common `Modbus TCP` port
- `SlaveID 1` reserved for service tags
- device `Slave ID` values assigned by line ranges

Confirmed working setup:

- line 1:
  - device: `OVEN TRM138`
  - serial: `COM6`, `9600 8N1`
  - base address: `96`
  - `SlaveID 10`
- line 2:
  - device: `OVEN TRM138`
  - serial: `COM8`, `9600 8N1`
  - base address: `48`
  - `SlaveID 50`
- OVEN network addressing mode: `8-bit`
- common Modbus-TCP port: `15020`
- Modbus client validation: `CoreBus`
- confirmed Modbus byte order for channel values: `ABCD`

## Key Fixes Already Made

- Removed obsolete OPC gateway code.
- Repaired local Python environment and PyCharm interpreter setup.
- Fixed `pymodbus 3.8.6` compatibility in the Modbus server layer.
- Added support for multiple RS-485 lines with independent serial settings.
- Simplified `Slave ID` strategy:
  - `SlaveID 1` is reserved for service tags
  - line 1 uses device ids from `10`
  - line 2 uses device ids from `50`
  - line 3 uses device ids from `90`
  - line 4 uses device ids from `130`
  - up to `32` devices per line
- Fixed OVEN address encoding:
  - config addresses like `96..103` are `8-bit` OVEN addresses
  - protocol frame now expands them to full network address form
- Added support for `rEAd` payloads returned by `TRM138`:
  - `float32` value
  - optional 2-byte time mark suffix
- Added single-device diagnostic probe:
  - module: `owen_gateway.probe`
  - config: `owen_probe.com6.json`

## Confirmed Device Behaviour

- Channels `96, 97, 98, 99, 100, 101, 103` respond correctly to `rEAd`.
- Channel `102` returns empty payload.
- Empty payload is treated as valid `disabled/no-data`, not as a communication failure.
- On line 2 device with base `48`:
  - channel `48` responds with valid value
  - channels `49..55` currently return empty payload and are treated as valid `disabled/no-data`

## Confirmed Runtime Validation

Validated on real hardware on `2026-03-21`:

- gateway started successfully with:
  - `line1 -> COM6`
  - `line2 -> COM8`
- Modbus-TCP server started successfully on port `15020`
- `CoreBus` was able to read holding registers from the gateway
- `SlaveID 1` returned valid service telemetry
- `SlaveID 10` returned valid data for the device on `COM6`
- `SlaveID 50` returned valid data for the device on `COM8`
- `HR1 = 1` confirms `gateway status = ok`
- `HR2 = 0` confirms `last error code = none`
- `HR16..HR17` decoded correctly as `float32`
- observed byte order in Modbus client: `ABCD`
- values on both active devices were live and changing

Conclusion:

- the real path `TRM138 -> RS-485 lines -> gateway -> Modbus-TCP client` is working

## Main Files To Use

- single device gateway config:
  - `owen_config.single_trm138.com6.json`
- current working two-line config:
  - `owen_config.com6.two_trm138.addr48_96.json`
- multi-device same-map example:
  - `owen_config.multi_device.same_map.example.json`
- multi-line example:
  - `owen_config.multiline.example.json`
- simplified example config:
  - `owen_config.example.json`
- diagnostic probe config:
  - `owen_probe.com6.json`

## Channel Quality Logic

Implemented in gateway:

- up to `3` consecutive unchanged time marks are acceptable
- after that, channel status becomes `stale`
- after `10` consecutive failed polls, channel status becomes `failed`
- failed channel is then polled less frequently

Channel status codes:

- `0` - disabled / no data / empty payload
- `1` - ok
- `2` - stale
- `3` - temporary communication error
- `4` - protocol error
- `5` - failed, reduced polling

## Modbus Map For Single TRM138

Service telemetry:

- `HR1` - gateway status
- `HR2` - last error code
- `HR3` - success counter
- `HR4` - timeout counter
- `HR5` - protocol error counter
- `HR6` - poll cycle counter

Channels:

- channel 1:
  - `HR16..HR17` value
  - `HR18` time mark
  - `HR19` channel status
- channel 2:
  - `HR20..HR21` value
  - `HR22` time mark
  - `HR23` channel status
- channel 3:
  - `HR24..HR25` value
  - `HR26` time mark
  - `HR27` channel status
- channel 4:
  - `HR28..HR29` value
  - `HR30` time mark
  - `HR31` channel status
- channel 5:
  - `HR32..HR33` value
  - `HR34` time mark
  - `HR35` channel status
- channel 6:
  - `HR36..HR37` value
  - `HR38` time mark
  - `HR39` channel status
- channel 7:
  - `HR40..HR41` value
  - `HR42` time mark
  - `HR43` channel status
- channel 8:
  - `HR44..HR45` value
  - `HR46` time mark
  - `HR47` channel status

Reference file with full meanings:

- `MODBUS_MAP_SINGLE_TRM138.md`
- `MODBUS_MULTI_DEVICE_SAME_MAP.md`
- `MULTI_LINE_GATEWAY.md`
- `MODBUS_MAP_CURRENT_2LINE.md`

## Commands

Probe one device:

```powershell
.\.venv\Scripts\python.exe -m owen_gateway.probe --config owen_probe.com6.json --log-level INFO
```

Run single-device gateway:

```powershell
.\.venv\Scripts\python.exe -m owen_gateway --config owen_config.single_trm138.com6.json --log-level INFO
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## What To Remember On Another Computer

- do not copy `.venv`
- create a fresh virtual environment
- install from `requirements.txt`
- adjust only the serial port name if needed
- start with the probe first
