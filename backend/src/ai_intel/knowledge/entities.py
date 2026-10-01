"""实体规范化: 生态区分的规范键/别名/受限模糊候选; 硬标识冲突优先阻止合并。"""

from __future__ import annotations

from dataclasses import dataclass, field

ENTITIES_VERSION = "entities-1.0.0"


class EntityMergeConflictError(RuntimeError):
    """硬标识冲突(不同生态/不同硬 ID): 优先阻止合并, 不做模糊归一。"""


@dataclass(frozen=True)
class EntityKey:
    """规范键: ecosystem + canonical_name; 同名不同生态是两个实体。"""

    entity_type: str
    ecosystem: str
    canonical_name: str

    def key_text(self) -> str:
        return f"{self.entity_type}:{self.ecosystem}:{self.canonical_name}"


@dataclass(frozen=True)
class EntityRecord:
    """实体记录: 别名表可追溯来源; 硬标识用于合并前冲突检查。"""

    entity_key: EntityKey
    aliases: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    hard_identifiers: tuple[str, ...] = field(default_factory=tuple)


def canonicalize_entity(entity_type: str, ecosystem: str, raw_name: str) -> EntityKey:
    """规范化: 含生态维度, 防止同名跨生态误合并。"""
    return EntityKey(entity_type, ecosystem, raw_name.strip().lower())


def can_merge_entities(left: EntityRecord, right: EntityRecord) -> bool:
    """合并判定: 硬标识或生态不一致直接拒绝; 别名须有来源才可归一。"""
    if left.entity_key.ecosystem != right.entity_key.ecosystem:
        raise EntityMergeConflictError("same name across ecosystems must not merge")
    if set(left.hard_identifiers) and set(right.hard_identifiers):
        if not set(left.hard_identifiers) & set(right.hard_identifiers):
            raise EntityMergeConflictError("hard identifiers disagree; merge blocked")
    return True


def resolve_alias(entity: EntityRecord, candidate: str) -> str | None:
    """别名解析: 明示 alias 有来源才归一, 受限模糊候选不自动归一。"""
    for alias, source_record_id in entity.aliases:
        if alias == candidate and source_record_id:
            return entity.entity_key.key_text()
    return None
