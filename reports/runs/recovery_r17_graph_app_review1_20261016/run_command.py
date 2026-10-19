"""Run review commands with byte-preserving output and China-time receipts."""

import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys

RUN = Path(__file__).resolve().parent


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("cwd")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    zone = datetime.timezone(datetime.timedelta(hours=8))
    start = datetime.datetime.now(zone).isoformat(timespec="milliseconds")
    result = subprocess.run(args.argv, cwd=args.cwd, capture_output=True, check=False)
    end = datetime.datetime.now(zone).isoformat(timespec="milliseconds")
    (RUN / f"{args.label}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{args.label}.stderr.log").write_bytes(result.stderr)
    receipt = {"label": args.label, "cwd": args.cwd, "argv": args.argv,
               "start": start, "end": end, "exit_code": result.returncode}
    (RUN / f"{args.label}.command.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (RUN / "commands.jsonl").open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))
    print(result.stdout.decode("utf-8", errors="replace")[-2500:])
    print(result.stderr.decode("utf-8", errors="replace")[-1000:])
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
