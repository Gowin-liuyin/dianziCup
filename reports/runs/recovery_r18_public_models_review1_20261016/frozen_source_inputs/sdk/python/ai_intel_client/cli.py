"""CLI input/output for actual backend calls; credentials come only from environment."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Never

from pydantic import ValidationError

from ai_intel_client.client import (
    ClientConfigurationError,
    ClientInputError,
    DianziApiError,
    DianziClient,
    DianziTransportError,
    ResponseContractError,
    validate_json_bytes,
)
from ai_intel_client.models import AskRequest, StackCheckRequest, StackCheckResult

MAX_INPUT_BYTES = 1048576


class ClientArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ClientInputError("command arguments are invalid")


def build_parser() -> argparse.ArgumentParser:
    parser = ClientArgumentParser(prog="dianzi-intel")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "ask"):
        operation = subcommands.add_parser(name)
        operation.add_argument(
            "--input", type=Path, help="Explicit JSON file; otherwise read stdin"
        )
        operation.add_argument("--idempotency-key", help="Operation key, never an API credential")
    return parser


def _read_input(path: Path | None) -> bytes:
    if path is None:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        with path.open("rb") as source:
            raw = source.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ClientInputError("input exceeds the synchronous client size boundary")
    validate_json_bytes(raw)
    return raw


def legacy_stack_exit_code(result: StackCheckResult) -> int:
    """The frozen legacy result has no risk confirmation; no inference can justify 0/1."""
    return 2


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        options = build_parser().parse_args(arguments)
        with DianziClient.from_environment() as client:
            raw = _read_input(options.input)
            if options.command == "check":
                checked = client.check_stack(
                    StackCheckRequest.model_validate_json(raw),
                    idempotency_key=options.idempotency_key,
                )
                sys.stdout.write(checked.wire_json(ensure_ascii=True) + "\n")
                sys.stderr.write("Risk classification is unavailable; retain uncertainty.\n")
                return legacy_stack_exit_code(checked)
            answer = client.ask(
                AskRequest.model_validate_json(raw), idempotency_key=options.idempotency_key
            )
            sys.stdout.write(answer.wire_json(ensure_ascii=True) + "\n")
            sys.stderr.write(
                "A returned answer or task handle does not establish risk certainty.\n"
            )
            return 2
    except (
        ClientConfigurationError,
        ClientInputError,
        ResponseContractError,
        DianziApiError,
        DianziTransportError,
        ValidationError,
        OSError,
        UnicodeError,
    ):
        sys.stderr.write("The operation could not be completed; check configuration and access.\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
