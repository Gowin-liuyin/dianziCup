"""Resume qualified traces after the observed native subprocess timeout, without reindexing."""

from review_runner import CLI, ROOT, connection, run

connection()
project = "r11-pg-assessments-review1-fix1-20261016-51f15a5c"
tasks = [("cbm_assessment_read_retry", project + ".ai_intel.assessment.assessment_service.AssessmentService.read", project)]
for method in ("create_candidate", "record_leaf_review", "validate", "publish", "retire"):
    tasks.append(("cbm_rule_" + method, project + ".ai_intel.assessment.rule_service.RuleService." + method, project))
tasks.append(("cbm_assets_writer", project + "-assets.inventory.InventoryService.import_manifest", project + "-assets"))
for label, function, graph in tasks:
    assert run(label, ["wsl", "-e", CLI, "cli", "--json", "trace_path", "--project", graph, "--function-name", function, "--direction", "outbound", "--depth", "2", "--limit", "60"], timeout=45) == 0
assert run("callers_rg", ["rg", "-n", "RuleService|AssessmentService|lock_rule_inputs|load_rule_inputs|cleanup_unreferenced_object|store_bytes|read_verified", "backend/src", "backend/tests"], ROOT) == 0
