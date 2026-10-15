"""复用原337用例实际argv且仅把输出目录切到本修复run，不修改分母。"""

import json
import sys

from run_checks import PYTHON, ROOT, RUN, run


def main():
    receipts = ROOT / "reports/runs/recovery_r11_sbom_inventory_20261016/commands.jsonl"
    command = next(
        json.loads(line)
        for line in receipts.read_text().splitlines()
        if json.loads(line)["name"] == "pure_final"
    )
    arguments = [value for value in command["argv"][1:] if not value.startswith("--junitxml=")]
    label = sys.argv[1] if len(sys.argv) > 1 else "original_pure337_final"
    return run(
        label,
        [str(PYTHON), *arguments, f"--junitxml={RUN / (label + '.xml')}"],
    )


if __name__ == "__main__":
    raise SystemExit(main())
