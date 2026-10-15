"""Classify credential-shaped fixture URL tokens without printing their contents."""

import hashlib
import ast
import json
import re
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PATTERN = re.compile(r"https?://[^/\s\"'<>]+:[^/@\s\"'<>]+@")
result = []
for path in RUN.glob("pure*.xml"):
    for case in ElementTree.parse(path).iter("testcase"):
        name = case.get("name", "")
        matches = PATTERN.findall(name)
        if matches:
            source = ROOT / "backend" / (case.get("classname", "").replace(".", "/") + ".py")
            assert source.is_file()
            literals = [node.value for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
                        if isinstance(node, ast.Constant) and isinstance(node.value, str)]
            source_tokens = {hashlib.sha256(token.encode()).hexdigest() for value in literals
                             for token in PATTERN.findall(value)}
            hashes = [hashlib.sha256(value.encode()).hexdigest() for value in matches]
            literal_prefix_matches = [any(token.split("://", 1)[1] in value for value in literals)
                                      for token in matches]
            if any(value not in source_tokens and not literal_prefix_matches[index]
                   for index, value in enumerate(hashes)):
                raise ValueError("URL fixture prefix unmatched in " + source.relative_to(ROOT).as_posix())
            result.append({"file": path.name, "test_module": case.get("classname"),
                           "case_base_name": name.split("[")[0], "match_count": len(matches),
                           "token_hashes": hashes, "source_path": source.relative_to(ROOT).as_posix(),
                           "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                           "classification": "exact literal or credential prefix in explicit URL rejection test"})
output = {"classified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
          "url_shapes_in_case_names": result}
(RUN / "lexical_url_classification.json").write_bytes((json.dumps(output, indent=2) + "\n").encode())
print(json.dumps(output, indent=2))
