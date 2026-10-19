"""Prepare the official pinned output vocabulary outside the repository."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import tiktoken_ext.openai_public

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CACHE = Path("D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016")
URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
EXPECTED = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"


def timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> None:
    started = timestamp()
    official_source = inspect.getsource(tiktoken_ext.openai_public.o200k_base)
    if URL not in official_source or EXPECTED not in official_source:
        raise RuntimeError("installed official vocabulary source differs from the pin")
    (RUN / "official_installed_o200k_source.txt").write_text(
        official_source, encoding="utf-8", newline="\n"
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / hashlib.sha1(URL.encode("utf-8")).hexdigest()
    downloaded = False
    if target.exists():
        vocabulary = target.read_bytes()
    else:
        request = urllib.request.Request(URL, headers={"User-Agent": "dianzi-r18-encoding/1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            vocabulary = response.read(8 * 1024 * 1024 + 1)
            if len(vocabulary) > 8 * 1024 * 1024:
                raise RuntimeError("vocabulary exceeds the authorized 8 MiB download bound")
            if response.status != 200:
                raise RuntimeError("vocabulary download did not return HTTP 200")
        if hashlib.sha256(vocabulary).hexdigest() != EXPECTED:
            raise RuntimeError("official vocabulary digest mismatch")
        with target.open("xb") as output:
            output.write(vocabulary)
        downloaded = True
    if hashlib.sha256(vocabulary).hexdigest() != EXPECTED:
        raise RuntimeError("existing vocabulary cache digest mismatch")
    child_environment = dict(os.environ, TIKTOKEN_CACHE_DIR=str(CACHE))
    child_code = (
        "import json,tiktoken; from unittest.mock import patch; "
        "guard=patch('tiktoken.load.read_file',side_effect=RuntimeError('network disabled')); "
        "network_mock=guard.start(); encoding=tiktoken.get_encoding('o200k_base'); "
        "samples=['安全情报证据与未知状态','citation: revision_id / source_uri','中文🌐']; "
        "counts=[len(encoding.encode(text,disallowed_special=())) for text in samples]; "
        "assert all(encoding.decode(encoding.encode(text,disallowed_special=()))==text "
        "for text in samples); "
        "print(json.dumps({'encoding':encoding.name,'counts':counts,'round_trips':3," 
        "'network_calls':network_mock.call_count})); assert network_mock.call_count==0"
    )
    result = subprocess.run(
        [str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", child_code],
        cwd=ROOT,
        env=child_environment,
        capture_output=True,
        timeout=30,
    )
    (RUN / "offline_encoding_smoke.log").write_bytes(result.stdout + result.stderr)
    receipt = {
        "started_at": started,
        "ended_at": timestamp(),
        "code_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "encoding": "o200k_base",
        "tiktoken_version": "0.14.0",
        "official_source_url": URL,
        "cache_directory": str(CACHE),
        "cache_filename": target.name,
        "vocabulary_sha256": EXPECTED,
        "vocabulary_bytes": len(vocabulary),
        "download_performed": downloaded,
        "download_maximum_bytes": 8 * 1024 * 1024,
        "offline_smoke_exit_code": result.returncode,
        "paid_model_calls": 0,
        "fees": "unknown",
        "boundary": "specified protocol output vocabulary; not provider billing tokens",
    }
    (RUN / "encoding_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, ensure_ascii=False))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
