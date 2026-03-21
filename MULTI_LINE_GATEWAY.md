# Multi-Line Gateway

The gateway can work with up to `4` independent RS-485 lines on one common
`Modbus TCP` endpoint.

Each line can have its own serial settings:

- `port`
- `baudrate`
- `bytesize`
- `parity`
- `stopbits`
- `timeout_ms`
- `address_bits`
- `poll_interval_ms`

## Slave ID Scheme

The gateway uses one common Modbus-TCP port for all lines.

To keep device addressing simple and deterministic:

- `Slave ID 1` is reserved for service tags
- devices on line 1 use `10..41`
- devices on line 2 use `50..81`
- devices on line 3 use `90..121`
- devices on line 4 use `130..161`

This gives:

- up to `32` devices per line
- up to `4` lines
- no `Slave ID` overlap
- enough free room inside Modbus limits

## Automatic Resolution

If `modbus_slave_id` is not set explicitly, the gateway resolves it as:

- `bus.modbus_slave_base + device - 1`

Examples:

- line 1 base `10`, device `1` -> `Slave ID 10`
- line 1 base `10`, device `2` -> `Slave ID 11`
- line 2 base `50`, device `1` -> `Slave ID 50`
- line 2 base `50`, device `2` -> `Slave ID 51`

## Service Slave

Reserved `Slave ID 1` contains service tags:

- `HR1` gateway status
- `HR2` last error code
- `HR3` success counter
- `HR4` timeout counter
- `HR5` protocol error counter
- `HR6` poll cycle counter
- `HR10..HR13` line status for buses `1..4`

## Config Model

Use one top-level `modbus` section and a `buses` array.

Example:

```json
{
  "modbus": {
    "host": "0.0.0.0",
    "port": 15020
  },
  "buses": [
    {
      "name": "line1",
      "modbus_slave_base": 10,
      "serial": {
        "port": "COM5",
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout_ms": 1000,
        "address_bits": 8
      },
      "poll_interval_ms": 1000
    },
    {
      "name": "line2",
      "modbus_slave_base": 50,
      "serial": {
        "port": "COM6",
        "baudrate": 2400,
        "bytesize": 8,
        "parity": "E",
        "stopbits": 1,
        "timeout_ms": 1200,
        "address_bits": 8
      },
      "poll_interval_ms": 1500
    }
  ]
}
```

## Limits

- up to `4` buses
- up to `32` devices per bus
- up to `128` devices total

## Example Files

- single line, two devices: `owen_config.com6.two_trm138.addr48_96.json`
- repeated map on one line: `owen_config.multi_device.same_map.example.json`
- multi-line example: `owen_config.multiline.example.json`
