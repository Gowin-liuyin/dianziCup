"""PoC 关联: 公告优先/社区候选后置; 状态机 lab_verified 仅由隔离验证记录支持。"""

from __future__ import annotations

from dataclasses import dataclass, field

POC_VERSION = "poc-1.0.0"
POC_STATES = ("candidate_found", "static_reviewed", "lab_verified", "verification_failed")
STATIC_ONLY_STATES = ("candidate_found", "static_reviewed")


class PocReviewError(RuntimeError):
    """状态跃迁违规: 静态审核不得自动升 lab_verified; 仓库脚本不得自动执行。"""


@dataclass(frozen=True)
class PocRecord:
    """PoC 记录: 仓库/commit/许可/依赖/适用目标保留; 来源区分公告引用与社区候选。"""

    poc_id: str
    source_kind: str
    repository_url: str = ""
    commit_sha: str = ""
    license_id: str = "unknown"
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    applicable_targets: tuple[str, ...] = field(default_factory=tuple)
    cited_by_advisory: bool = False
    state: str = "candidate_found"


def promote_poc_state(record: PocRecord, target_state: str, lab_record_id: str = "") -> PocRecord:
    """状态跃迁: lab_verified 仅接受实际隔离验证记录 ID 支持。"""
    if target_state not in POC_STATES:
        raise PocReviewError(f"unknown poc state: {target_state}")
    if target_state == "lab_verified":
        if record.state not in ("static_reviewed", "verification_failed"):
            raise PocReviewError("static review must complete before lab verification")
        if not lab_record_id:
            raise PocReviewError("lab_verified requires an isolated validation record id")
        return PocRecord(**{**record.__dict__, "state": "lab_verified"})
    return PocRecord(**{**record.__dict__, "state": target_state})


def handle_untrusted_repository(record: PocRecord, allow_execute: bool, mount_secrets: bool) -> str:
    """恶意仓库防护: 安装脚本不自动执行、不挂载秘密。"""
    if allow_execute or mount_secrets:
        raise PocReviewError("untrusted repository scripts must not execute or receive secrets")
    return "quarantined_for_static_review"
