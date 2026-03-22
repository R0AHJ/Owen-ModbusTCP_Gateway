# Linux Deployment

This folder contains a minimal Linux deployment kit for the current gateway.

## Files

- `../owen_config.linux.json` - ready-to-edit Linux gateway config
- `../owen_config.linux.multiline.json` - Linux multi-line example, same scheme as Windows multi-line config
- `../owen_probe.linux.json` - probe config for one TRM138
- `run_gateway.sh` - start gateway from project root
- `run_probe.sh` - test one device from project root
- `owen-gateway.service` - example `systemd` unit

## Expected Layout

Recommended target path on Linux:

```text
/opt/owen-modbus-gateway
```

Project contents to copy:

- `owen_gateway/`
- `requirements.txt`
- `owen_config.linux.json`
- `owen_probe.linux.json`
- `linux_deploy/`

Do not copy:

- `.venv`
- `.idea`
- `__pycache__`

## Install

```bash
cd /opt/owen-modbus-gateway
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Probe One Device

Edit `owen_probe.linux.json` first, then run:

```bash
./linux_deploy/run_probe.sh
```

## Run Gateway

Edit `owen_config.linux.json` first, then run:

```bash
./linux_deploy/run_gateway.sh
```

For a multi-line Linux setup use:

- `owen_config.linux.multiline.json`

It provides a practical 2-line Linux setup:

- `bus1 -> /dev/ttyUSB0`
- `bus2 -> /dev/ttyUSB1`
- common `Modbus TCP` port `15020`
- service `SlaveID 1`
- line slave bases `10`, `50`
- two devices per line in the example:
  - base `48`
  - base `96`

## Serial Port Access

Usually the service user must be in the `dialout` group:

```bash
sudo usermod -aG dialout $USER
```

Re-login after changing groups.

## systemd

Copy the unit file and enable it:

```bash
sudo cp linux_deploy/owen-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now owen-gateway.service
```

Logs:

```bash
journalctl -u owen-gateway.service -f
```
