"""Fixed private object reader; no request-defined program, URL, bucket or filename tool."""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from threading import Timer
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, TypeAdapter

from ai_intel.infrastructure.content_store import (
    MAX_CONTENT_REQUEST_BYTES,
    MAX_DEADLINE_CONTENT_BYTES,
)
from ai_intel.infrastructure.minio_store import MinioContentStore, ObjectStoreUnavailableError
from ai_intel.infrastructure.process_limits import bound_process_resources


class _ObjectRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    remaining_seconds: Annotated[float, Field(gt=0)]
    byte_limit: Annotated[int, Field(gt=0, le=MAX_DEADLINE_CONTENT_BYTES)]


class _LocalRead(_ObjectRead):
    storage: Literal["local"]
    root_directory: str


class _MinioRead(_ObjectRead):
    storage: Literal["minio"]
    endpoint: str
    bucket: str
    access_key: SecretStr = Field(repr=False)
    secret_key: SecretStr = Field(repr=False)
    secure: bool
    ca_file: str | None
    timeout_seconds: Annotated[float, Field(gt=0, le=30)]
    test_mode: bool


_REQUEST: TypeAdapter[_LocalRead | _MinioRead] = TypeAdapter(
    Annotated[_LocalRead | _MinioRead, Field(discriminator="storage")]
)


def main() -> None:
    """Return verified bytes or a fixed one-byte failure; never print config or exceptions."""
    logging.disable(logging.CRITICAL)
    watchdog: Timer | None = None
    try:
        request_bytes = sys.stdin.buffer.read(MAX_CONTENT_REQUEST_BYTES + 1)
        if len(request_bytes) > MAX_CONTENT_REQUEST_BYTES:
            raise ValueError("content worker input limit exceeded")
        request = _REQUEST.validate_json(request_bytes)
        deadline = time.monotonic() + request.remaining_seconds
        watchdog = Timer(request.remaining_seconds, os._exit, args=(124,))
        watchdog.daemon = True
        watchdog.start()
        resource_handle = bound_process_resources(memory_bytes=512 * 1024 * 1024, cpu_seconds=5)
        if isinstance(request, _LocalRead):
            root = Path(request.root_directory)
            if not root.is_absolute():
                raise ValueError("content worker root must be absolute")
            path = root / request.content_hash[:2] / request.content_hash
            chunks: list[bytes] = []
            total = 0
            with path.open("rb") as stream:
                while chunk := stream.read(min(1024 * 1024, request.byte_limit + 1 - total)):
                    total += len(chunk)
                    if total > request.byte_limit:
                        raise ValueError("content worker object limit exceeded")
                    chunks.append(chunk)
                    if time.monotonic() >= deadline:
                        raise TimeoutError("content worker deadline exhausted")
            payload = b"".join(chunks)
        else:
            store = MinioContentStore(
                request.endpoint,
                request.bucket,
                request.access_key,
                request.secret_key,
                secure=request.secure,
                ca_file=request.ca_file,
                timeout_seconds=request.timeout_seconds,
                max_object_bytes=request.byte_limit,
                test_mode=request.test_mode,
            )
            try:
                payload = store.read_verified(request.content_hash)
            finally:
                store._client._http.clear()
        if hashlib.sha256(payload).hexdigest() != request.content_hash:
            raise ValueError("content worker checksum mismatch")
        if time.monotonic() >= deadline:
            raise TimeoutError("content worker deadline exhausted")
        output = b"O" + payload
        del resource_handle
    except FileNotFoundError:
        output = b"M"
    except TimeoutError:
        output = b"T"
    except ValueError:
        output = b"V"
    except (OSError, ObjectStoreUnavailableError):
        output = b"U"
    finally:
        if watchdog is not None:
            watchdog.cancel()
            watchdog.join()
    sys.stdout.buffer.write(output)


if __name__ == "__main__":
    main()
