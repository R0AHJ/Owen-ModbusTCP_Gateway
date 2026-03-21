from __future__ import annotations

import argparse
import asyncio
import logging

from owen_gateway.config import load_config
from owen_gateway.service import OwenGatewayService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OVEN RS-485 to Modbus-TCP gateway")
    parser.add_argument("--config", default="owen_config.json", help="path to config json")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logging level",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    service = OwenGatewayService(config)
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        return 0
    return 0
