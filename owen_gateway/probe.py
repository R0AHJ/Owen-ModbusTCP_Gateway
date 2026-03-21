from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from owen_gateway.protocol import decode_payload, hash_parameter_name
from owen_gateway.serial_client import OwenSerialClient


VALID_PROTOCOL_FORMATS = {
    "float32",
    "int16",
    "uint16",
    "uint32",
    "raw",
}


@dataclass(slots=True)
class SerialProbeConfig:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    timeout_ms: int
    address_bits: int = 8


@dataclass(slots=True)
class ProbeRequestConfig:
    address: int
    parameter: str
    protocol_format: str


@dataclass(slots=True)
class ProbeConfig:
    serial: SerialProbeConfig
    request: ProbeRequestConfig
    retries: int
    inter_request_delay_ms: int
    poll_interval_ms: int
    cycles: int


def load_probe_config(path: str | Path) -> ProbeConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    config = ProbeConfig(
        serial=SerialProbeConfig(**payload["serial"]),
        request=ProbeRequestConfig(**payload["request"]),
        retries=payload.get("retries", 0),
        inter_request_delay_ms=payload.get("inter_request_delay_ms", 15),
        poll_interval_ms=payload.get("poll_interval_ms", 1000),
        cycles=payload.get("cycles", 5),
    )
    validate_probe_config(config)
    return config


def validate_probe_config(config: ProbeConfig) -> None:
    serial = config.serial
    if serial.bytesize not in {7, 8}:
        raise ValueError("serial.bytesize must be 7 or 8")
    if serial.parity not in {"N", "E", "O"}:
        raise ValueError("serial.parity must be N, E or O")
    if serial.stopbits not in {1, 2}:
        raise ValueError("serial.stopbits must be 1 or 2")
    if serial.timeout_ms <= 0:
        raise ValueError("serial.timeout_ms must be > 0")
    if serial.address_bits not in {8, 11}:
        raise ValueError("serial.address_bits must be 8 or 11")

    request = config.request
    if not 0 <= request.address <= 0x7FF:
        raise ValueError("request.address must be in range 0..2047")
    if request.protocol_format not in VALID_PROTOCOL_FORMATS:
        raise ValueError(
            f"unsupported request.protocol_format: {request.protocol_format}"
        )
    hash_parameter_name(request.parameter)

    if config.retries < 0:
        raise ValueError("retries must be >= 0")
    if config.inter_request_delay_ms < 0:
        raise ValueError("inter_request_delay_ms must be >= 0")
    if config.poll_interval_ms < 0:
        raise ValueError("poll_interval_ms must be >= 0")
    if config.cycles <= 0:
        raise ValueError("cycles must be > 0")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe a single OVEN device")
    parser.add_argument("--config", required=True, help="path to probe config json")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logging level",
    )
    return parser


def run_probe(config: ProbeConfig) -> int:
    logger = logging.getLogger("owen_probe")
    client = OwenSerialClient(config.serial)  # type: ignore[arg-type]
    success_count = 0
    timeout_count = 0
    protocol_error_count = 0

    client.connect()
    logger.info(
        "probe started: port=%s %s,%s%s%s address=%s parameter=%s retries=%s",
        config.serial.port,
        config.serial.baudrate,
        config.serial.bytesize,
        config.serial.parity,
        config.serial.stopbits,
        config.request.address,
        config.request.parameter,
        config.retries,
    )
    try:
        for cycle in range(1, config.cycles + 1):
            logger.info("cycle %s/%s", cycle, config.cycles)
            attempt_success = False
            for attempt in range(config.retries + 1):
                try:
                    request, response, frame = client.exchange(
                        config.request.address,
                        config.request.parameter,
                    )
                    value = decode_payload(
                        frame.payload,
                        config.request.protocol_format,
                    )
                    success_count += 1
                    attempt_success = True
                    logger.info(
                        "response ok: attempt=%s value=%r request=%s response=%s",
                        attempt + 1,
                        value,
                        request.hex(" "),
                        response.hex(" "),
                    )
                    break
                except TimeoutError:
                    timeout_count += 1
                    logger.warning(
                        "timeout: attempt=%s/%s address=%s parameter=%s",
                        attempt + 1,
                        config.retries + 1,
                        config.request.address,
                        config.request.parameter,
                    )
                except Exception:
                    protocol_error_count += 1
                    logger.exception(
                        "probe failed: attempt=%s/%s address=%s parameter=%s",
                        attempt + 1,
                        config.retries + 1,
                        config.request.address,
                        config.request.parameter,
                    )

                if attempt < config.retries and config.inter_request_delay_ms > 0:
                    time.sleep(config.inter_request_delay_ms / 1000)

            if not attempt_success:
                logger.info("cycle %s finished without valid response", cycle)

            if cycle < config.cycles and config.poll_interval_ms > 0:
                time.sleep(config.poll_interval_ms / 1000)
    finally:
        client.close()
        logger.info(
            "probe finished: success=%s timeout=%s protocol_error=%s",
            success_count,
            timeout_count,
            protocol_error_count,
        )

    return 0 if success_count > 0 else 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_probe_config(args.config)
    try:
        return run_probe(config)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
