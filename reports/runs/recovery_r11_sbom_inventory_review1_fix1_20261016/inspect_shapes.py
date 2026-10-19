"""只输出形状位置与hash，诊断不显示原URI或口令。"""

import hashlib
import json
import re

from review_runner_final import RUN


def main():
    patterns = [
        re.compile(r"postgresql(?:\+[A-Za-z0-9_]+)?://[^\s\"'<>\\]+"),
        re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>]*:[^\s\"'<>]*@"),
        re.compile(r"file:///C:/private/[^\s\"'<>]+"),
        re.compile(r"synthetic_password"),
    ]
    output = []
    for name in ("pg_new.log", "pg_new.xml"):
        text = (RUN / name).read_text(encoding="utf-8")
        for category, pattern in enumerate(patterns):
            for match in pattern.finditer(text):
                output.append({"path": name, "category": category, "line": text[:match.start()].count("\n") + 1, "length": len(match[0]), "sha256": hashlib.sha256(match[0].encode()).hexdigest()})
        for pattern in patterns:
            text = pattern.sub("[redacted shape]", text)
        lines = text.splitlines()
        selected = []
        for index, line in enumerate(lines):
            if "[redacted shape]" in line:
                selected.append({"line": index + 1, "text": line[:400]})
        output.append({"path": name, "safe_context": selected})
    (RUN / "shape_diagnosis_final.json").write_bytes(json.dumps(output, indent=2).encode())
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
