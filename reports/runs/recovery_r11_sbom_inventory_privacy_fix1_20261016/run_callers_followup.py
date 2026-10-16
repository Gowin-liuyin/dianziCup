"""冻结后源码rg核真实公开/内部投影调用，不把CBM缺图边当作无caller。"""

from run_checks import ROOT, run

if __name__ == "__main__":
    raise SystemExit(
        run(
            "callers_followup_rg",
            [
                "rg",
                "-n",
                "freeze_sbom_sidecar|safe_sbom_sidecar|safe_sbom_snapshot|get_snapshot_sbom|"
                "list_snapshots|_decoded_uri_text|reference\\(",
                "backend/src/ai_intel/assets",
            ],
            cwd=ROOT,
        )
    )
