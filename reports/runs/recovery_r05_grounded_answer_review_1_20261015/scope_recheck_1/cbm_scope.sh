#!/usr/bin/env bash
set -u
export CBM_CACHE_DIR=/tmp/dianzi-r05-grounded-independent-cache-20261015
export TZ=Asia/Shanghai
cbm=/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp
out=/mnt/d/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/scope_recheck_1
src=/mnt/c/Users/yinha/.codex/worktrees/r05-grounded-answer-independent-review/dianzi/backend/src
project=r05-grounded-scope-recheck-b151-20261015
run() {
    label=$1
    shift
    started=$(date --iso-8601=seconds)
    "$@" > "$out/$label.log" 2>&1
    status=$?
    ended=$(date --iso-8601=seconds)
    printf '%s\n' "started_at=$started" "completed_at=$ended" "exit_code=$status" "cwd=$PWD" "cache=$CBM_CACHE_DIR" "command=$*" > "$out/$label.receipt.txt"
    cat "$out/$label.log"
    return "$status"
}
run cbm_scope_index "$cbm" cli index_repository --repo-path "$src" --name "$project" --mode full --persistence false || exit $?
run cbm_scope_schema "$cbm" cli get_graph_schema --project "$project" --format json --diagnostics full
run cbm_scope_trace "$cbm" cli trace_path --project "$project" --function-name generate_grounded_answer --direction both --depth 3 --mode calls --include-evidence true --format json --max-output-tokens 5000
run cbm_state_trace "$cbm" cli trace_path --project "$project" --function-name _same_proposition_except_state --direction both --depth 2 --mode calls --include-evidence true --format json --max-output-tokens 3000
