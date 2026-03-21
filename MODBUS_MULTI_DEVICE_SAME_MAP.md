# Modbus Addressing: Repeated Map Per Device

This document describes the new addressing model for multiple OVEN devices on
one RS-485 port.

## Goal

When several devices are connected to one serial port, each device exposes the
same Modbus register map:

- `HR1..HR6` for device service status and telemetry
- `HR16..HR47` for `TRM138` channel data

The register numbers do not change between devices.

Only `Modbus Slave ID` changes.

## Practical Meaning

Recommended scheme for two devices on one port:

- first device on line 1 -> `Slave ID 10`
- second device on line 1 -> `Slave ID 11`

Then:

- `Slave ID 10`, `HR16..HR17` -> channel 1 value of device 1
- `Slave ID 11`, `HR16..HR17` -> channel 1 value of device 2
- `Slave ID 1`, `HR1..HR6` -> gateway service telemetry

This is the usual Modbus-TCP pattern and is more convenient for SCADA/HMI
systems than one global register map for all devices.

## Config Field

Each point can now define:

- `modbus_slave_id`

If it is omitted, the gateway resolves it from:

- line base for the bus
- device number on that bus

Default bus ranges:

- line 1 -> `10..41`
- line 2 -> `50..81`
- line 3 -> `90..121`
- line 4 -> `130..161`

## Rules

- all points belonging to one physical device must use the same `modbus_slave_id`
- `Slave ID 1` is reserved for service tags
- one `modbus_slave_id` cannot be reused by different devices in the same gateway
- register overlap is checked inside each `Slave ID`
- the same register addresses are allowed on different `Slave ID`

## Device Service Registers

These registers are published in reserved `Slave ID 1`:

| Register | Meaning |
|---|---|
| `HR1` | aggregated gateway status |
| `HR2` | aggregated last error code |
| `HR3` | aggregated success counter |
| `HR4` | aggregated timeout counter |
| `HR5` | aggregated protocol error counter |
| `HR6` | aggregated poll cycle counter |
| `HR10..HR13` | line status for bus 1..4 |

## TRM138 Channel Map

These registers are also repeated for every `Slave ID`:

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

## Example

See:

- `owen_config.multi_device.same_map.example.json`

Example meaning:

- device 1 on the line is published as `Slave ID 10`
- device 2 on the line is published as `Slave ID 11`
- both devices use the same `HR16..HR47` layout
- service telemetry is available in `Slave ID 1`
