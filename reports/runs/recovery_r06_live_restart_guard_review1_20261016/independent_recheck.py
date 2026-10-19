"""Repeat identical reviewer probes against a new frozen checkout without overwriting reds."""

import json
from pathlib import Path
import subprocess
import sys

import review_driver as review

RUN = Path(__file__).resolve().parent


def main():
    tag = sys.argv[1]
    if not tag.isalnum():
        raise ValueError("review recheck tag must be alphanumeric")
    target = RUN / ("recheck_" + tag)
    target.mkdir()
    review.RUN = target
    review.main()
    commands = []
    code = (
        "import sys\n"
        f"sys.path.insert(0,{str(RUN)!r})\n"
        "import actual_ack_probe as probe\n"
        f"probe.RUN=__import__('pathlib').Path({str(target)!r})\n"
        "probe.main()\n"
    )
    commands.append(review.execute("actual_ack_recheck", [sys.executable, "-B", "-c", code], RUN))
    commands.append(review.execute("already_exited_actor_recheck", [sys.executable, "-B", str(RUN / "already_exited_actor_probe.py"), str(target.relative_to(RUN) / "already_exited_actor_results.json")], RUN))
    (target / "additional_commands.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"target": str(target), "additional_commands": commands}))


if __name__ == "__main__":
    main()
