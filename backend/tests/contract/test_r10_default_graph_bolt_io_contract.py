"""Actual locked driver against synthetic loopback Bolt peers; no PG or real graph service."""

import json
import socket
import struct
import threading
import time
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from neo4j._codec.packstream._common import PackableBuffer, UnpackableBuffer
from neo4j._codec.packstream.v1 import Packer, Unpacker
from pydantic import SecretStr

from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge import default_graph_runtime as runtime
from ai_intel.knowledge.graph_projection import (
    GraphProjectionBatch,
    ProjectionDigestConflict,
    encode_projection_batch,
)


def read_exact(connection, size):
    received = bytearray()
    while len(received) < size:
        part = connection.recv(size - len(received))
        if not part:
            raise EOFError("synthetic peer disconnected")
        received.extend(part)
    return bytes(received)


def read_message(connection):
    payload = bytearray()
    while True:
        count = struct.unpack(">H", read_exact(connection, 2))[0]
        if count:
            payload.extend(read_exact(connection, count))
        elif payload:
            return Unpacker(UnpackableBuffer(payload)).unpack()


def send_success(connection, metadata):
    buffer = PackableBuffer()
    Packer(buffer).pack_struct(b"\x70", (metadata,))
    payload = bytes(buffer.data)
    connection.sendall(struct.pack(">H", len(payload)) + payload + b"\x00\x00")


class SyntheticBoltPeer:
    def __init__(self, stage):
        self.stage = stage
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(10)
        self.port = self.listener.getsockname()[1]
        self.connection = None
        self.stop = threading.Event()
        self.stalled = threading.Event()
        self.tags = []
        self.failure = None
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def serve(self):
        stalled_tag = {"run": "10", "consume": "3f", "commit": "12", "rollback": "13"}[self.stage]
        try:
            connection, address = self.listener.accept()
            self.connection = connection
            assert address[0] == "127.0.0.1"
            connection.settimeout(10)
            assert read_exact(connection, 20)[:4] == b"\x60\x60\xb0\x17"
            connection.sendall(b"\x00\x00\x08\x05")
            while not self.stop.is_set():
                message = read_message(connection)
                tag = message.tag.hex()
                self.tags.append(tag)
                if tag == stalled_tag:
                    self.stalled.set()
                    self.stop.wait(20)
                    return
                if tag == "01":
                    send_success(
                        connection,
                        {
                            "server": "Neo4j/5.26.32",
                            "connection_id": "synthetic-io",
                            "hints": {"connection.recv_timeout_seconds": 120},
                        },
                    )
                elif tag in {"6a", "11", "3f", "12", "13"}:
                    send_success(connection, {})
                elif tag == "10":
                    send_success(connection, {"fields": []})
                else:
                    raise AssertionError("unexpected synthetic Bolt message")
        except BaseException as error:
            self.failure = type(error).__name__
        finally:
            if self.connection is not None:
                with suppress(OSError):
                    self.connection.close()

    def close(self):
        self.stop.set()
        if self.connection is not None:
            with suppress(OSError):
                self.connection.shutdown(socket.SHUT_RDWR)
            with suppress(OSError):
                self.connection.close()
        with suppress(OSError):
            self.listener.close()


@pytest.mark.parametrize("stage", ["run", "consume", "commit", "rollback"])
def test_real_default_driver_cancels_stalled_post_begin_io_without_success(monkeypatch, stage):
    peer = SyntheticBoltPeer(stage)
    stores = []
    outcome = []
    parent_store = runtime._SchemaInitializedProjectionStore

    class RecordedStore(parent_store):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            stores.append(self)

        def initialize_schema(self):
            if stage != "rollback":
                return super().initialize_schema()
            with self._transaction() as transaction:
                transaction.run("RETURN $value", {"value": 1}).consume()
                raise ProjectionDigestConflict("synthetic_business_rejection")

    @contextmanager
    def hybrid(engine, settings):
        yield {"knowledge_change": MagicMock()}

    monkeypatch.setattr(runtime, "_SchemaInitializedProjectionStore", RecordedStore)
    monkeypatch.setattr(runtime, "build_projection_job_handlers", hybrid)
    settings = ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        neo4j_uri=f"bolt://127.0.0.1:{peer.port}",
        neo4j_username="synthetic-io",
        neo4j_password=SecretStr("synthetic-io-only"),
        dependency_timeout_seconds=3,
        opensearch_url=None,
        semantic_model_cache_directory=None,
    )
    batch = GraphProjectionBatch(
        batch_id=uuid4(),
        namespace=runtime.DEFAULT_GRAPH_NAMESPACE,
        partition_key="public",
        generation_id=uuid4(),
        event_id=uuid4(),
        sequence=1,
        kind="tombstone",
        scope_epochs=(("public", 1),),
        input_sha256="a" * 64,
        full_graph_sha256="b" * 64,
        nodes=(),
        edges=(),
        captured_at=datetime.now(UTC),
    )
    digest = encode_projection_batch(batch)[1]

    def apply():
        try:
            with runtime.build_default_graph_job_handlers(MagicMock(), settings):
                stores[0].apply_batch(batch, digest)
            outcome.append("returned_success")
        except BaseException as error:
            outcome.append(type(error).__name__)

    worker = threading.Thread(target=apply, daemon=True)
    peer.thread.start()
    worker.start()
    try:
        assert peer.stalled.wait(5), {"tags": peer.tags, "error": peer.failure}
        started = time.monotonic()
        worker.join(timeout=5)
        assert not worker.is_alive(), {"stage": stage, "tags": peer.tags}
        observation = {
            "stage": stage,
            "waited_after_stall": time.monotonic() - started,
            "tags_only": peer.tags,
            "outcome": outcome,
            "driver_closed": stores[0].driver._closed,
        }
        print("BOLT_IO_FIX_OBSERVATION=" + json.dumps(observation))
        assert outcome == ["JobExecutionError"]
        assert not stores[0].schema_initialized
        assert stores[0].driver._closed
        assert peer.failure is None
    finally:
        peer.close()
        worker.join(timeout=3)
        peer.thread.join(timeout=3)
    assert not worker.is_alive() and not peer.thread.is_alive()
