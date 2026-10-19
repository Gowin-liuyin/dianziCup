"""Recheck exact observed WSL PID births after the Windows WSL hosts have exited."""

import json
from pathlib import Path

run = Path(__file__).parent
proc = Path(r"\\wsl.localhost\Ubuntu-22.04\proc")
rows = []
for receipt_path in sorted(run.glob("cbm*.linux_receipt.json")):
    receipt = json.loads(receipt_path.read_text())
    identities = {(row["pid"], row["birth_clock_ticks"]) for row in receipt["process_rows"]}
    for pid, birth in sorted(identities):
        entry = {"receipt": receipt_path.name, "pid": pid, "birth_clock_ticks": birth}
        try:
            raw = (proc / str(pid) / "stat").read_text()
        except FileNotFoundError:
            entry["status"] = "exited"
        except OSError as error:
            entry.update(status="identity_unavailable", errno=error.errno)
        else:
            current_birth = int(raw.rsplit(")", 1)[1].split()[19])
            entry["status"] = "still_owned" if current_birth == birth else "pid_reused_original_exited"
        rows.append(entry)
record = {"identities": rows, "remaining_owned": sum(row["status"] == "still_owned" for row in rows),
          "unknown": sum(row["status"] == "identity_unavailable" for row in rows)}
(run / "cbm_identity_exit.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"identities": len(rows), "remaining_owned": record["remaining_owned"], "unknown": record["unknown"]}))
raise SystemExit(int(bool(record["remaining_owned"] or record["unknown"])))
