"""Run the documented official CBM CLI against isolated source indexes."""

import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
BASE = [
    "wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--", "env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-gc-integrated-8a-validation-20261016",
    "CBM_ALLOWED_ROOT=/mnt/d/wt/gc-8a-validation/backend/src",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli",
]
PROJECT = "gc-integrated-8a-validation-src"
COMMANDS = [
    ("cbm_schema_actual", ["get_graph_schema", "--project", PROJECT]),
    ("cbm_architecture", ["get_architecture", "--project", PROJECT]),
    ("cbm_runtime_trace", ["trace_path", "--project", PROJECT, "--function-name", f"{PROJECT}.ai_intel.workers.runtime.consume_job", "--direction", "both", "--depth", "3"]),
    ("cbm_source_handler_trace", ["trace_path", "--project", PROJECT, "--function-name", f"{PROJECT}.ai_intel.ingestion.source_jobs.build_source_page_handler", "--direction", "both", "--depth", "3"]),
    ("cbm_receipt_trace", ["trace_path", "--project", PROJECT, "--function-name", f"{PROJECT}.ai_intel.ingestion.source_failure_receipts.SourceResponseRecorder.record_response", "--direction", "both", "--depth", "3"]),
    ("cbm_generation_trace", ["trace_path", "--project", PROJECT, "--function-name", f"{PROJECT}.ai_intel.infrastructure.models.generation.GenerationClient.generate", "--direction", "both", "--depth", "3"]),
    ("cbm_model_fields_trace", ["trace_path", "--project", PROJECT, "--function-name", f"{PROJECT}.ai_intel.enrichment.model_fields.generate_model_field_attempts", "--direction", "both", "--depth", "3"]),
    ("cbm_signals_trace", ["trace_path", "--project", PROJECT, "--function-name", f"{PROJECT}.ai_intel.enrichment.signals.enrich_structured_fields", "--direction", "both", "--depth", "3"]),
    ("cbm_assessment_index", ["index_repository", "--repo-path", "/mnt/d/wt/gc-8a-validation/backend/src/ai_intel/assessment", "--mode", "fast", "--persistence", "false", "--name", "gc-integrated-8a-validation-assessment"]),
    ("cbm_assets_index", ["index_repository", "--repo-path", "/mnt/d/wt/gc-8a-validation/backend/src/ai_intel/assets", "--mode", "fast", "--persistence", "false", "--name", "gc-integrated-8a-validation-assets"]),
]
for label, args in COMMANDS:
    result = subprocess.run([sys.executable, str(RUN / "run_command.py"), label, "--", *BASE, *args], check=False)
    if result.returncode:
        print(f"{label} failed with {result.returncode}")
