"""Explicit PG setup and JSON-only checkpoints with remote tracing disabled."""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from langchain_core.runnables.config import var_child_runnable_config
from langchain_core.tracers.context import tracing_v2_callback_var
from langgraph.checkpoint.postgres import PostgresSaver
from langsmith import tracing_context
from psycopg.rows import DictRow, dict_row


class PlainJsonSerializer:
    """No pickle, object hooks, dynamic imports, tagged classes, or msgpack extensions."""

    def dumps_typed(self, obj: object) -> tuple[str, bytes]:
        self._validate(obj)
        payload = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode()
        if len(payload) > 1048576:
            raise ValueError("checkpoint too large")
        return "json", payload

    def loads_typed(self, value: tuple[str, bytes]) -> object:
        kind, payload = value
        if kind != "json" or len(payload) > 1048576:
            raise ValueError("unsafe checkpoint format")

        def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, child in pairs:
                if key in result:
                    raise ValueError("duplicate checkpoint key")
                result[key] = child
            return result

        result: object = json.loads(payload, object_pairs_hook=unique_object)
        self._validate(result)
        return result

    @staticmethod
    def _validate(value: object) -> None:
        pending = [(value, 0)]
        seen: set[int] = set()
        count = 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 24 or count > 50000:
                raise ValueError("checkpoint structure limit")
            if type(item) is str and isinstance(item, str):
                item.encode("utf-8")
                continue
            if item is None or type(item) in {bool, int}:
                continue
            if type(item) is float and isinstance(item, float) and math.isfinite(item):
                continue
            if type(item) not in {dict, list, tuple}:
                raise ValueError("checkpoint requires plain JSON")
            if id(item) in seen:
                raise ValueError("checkpoint cyclic or shared container")
            seen.add(id(item))
            if isinstance(item, dict):
                if any(type(key) is not str for key in item):
                    raise ValueError("checkpoint key must be text")
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list | tuple):
                pending.extend((child, depth + 1) for child in item)


def validate_checkpoint_schema(schema: str) -> str:
    if schema != "dianzi_investigation_checkpoints" and not re.fullmatch(
        r"test_r14_workflow_[a-z0-9_]{1,80}", schema
    ):
        raise ValueError("checkpoint schema requires explicit deployment or isolated test scope")
    return schema


class DeadlinePostgresSaver(PostgresSaver):
    """Refresh saver SQL timeouts against one original monotonic deadline."""

    def __init__(self, connection: psycopg.Connection[DictRow], deadline_monotonic: float) -> None:
        super().__init__(connection, serde=PlainJsonSerializer())
        self._deadline_monotonic = deadline_monotonic

    @contextmanager
    def _cursor(self, *, pipeline: bool = False) -> Iterator[psycopg.Cursor[DictRow]]:
        with super()._cursor(pipeline=pipeline) as cursor:
            remaining = self._deadline_monotonic - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("checkpoint deadline exhausted")
            milliseconds = max(1, math.floor(remaining * 1000))
            cursor.execute(f"SET statement_timeout = '{milliseconds}ms'")
            cursor.execute(f"SET lock_timeout = '{milliseconds}ms'")
            yield cursor


@contextmanager
def open_postgres_checkpointer(
    connection_string: str, schema: str, remaining_seconds: float
) -> Iterator[PostgresSaver]:
    """Connection and all checkpoint statements have bounded IO; tables must already exist."""
    validate_checkpoint_schema(schema)
    if remaining_seconds <= 0 or not math.isfinite(remaining_seconds):
        raise TimeoutError("deadline exhausted")
    milliseconds = max(1, math.floor(remaining_seconds * 1000))
    deadline = time.monotonic() + remaining_seconds
    with psycopg.connect(
        connection_string,
        autocommit=True,
        row_factory=dict_row,
        prepare_threshold=0,
        connect_timeout=max(1, min(5, math.ceil(remaining_seconds))),
        options=(
            f"-c search_path={schema} -c statement_timeout={milliseconds} "
            f"-c lock_timeout={milliseconds}"
        ),
    ) as connection:
        yield DeadlinePostgresSaver(connection, deadline)


def setup_checkpoint_schema(
    connection_string: str, schema: str, *, controlled_deployment: bool
) -> None:
    """Only an explicit deployment/test command calls setup; no request creates tables."""
    if controlled_deployment is not True:
        raise PermissionError("checkpoint setup requires controlled deployment")
    with open_postgres_checkpointer(connection_string, schema, 30) as saver:
        saver.setup()


@contextmanager
def local_graph_execution() -> Iterator[None]:
    """Ignore ambient LangSmith settings and inherited Runnable callbacks for private data."""
    callback_token = tracing_v2_callback_var.set(None)
    config_token = var_child_runnable_config.set(None)
    try:
        with tracing_context(enabled=False, parent=False):
            yield
    finally:
        var_child_runnable_config.reset(config_token)
        tracing_v2_callback_var.reset(callback_token)
