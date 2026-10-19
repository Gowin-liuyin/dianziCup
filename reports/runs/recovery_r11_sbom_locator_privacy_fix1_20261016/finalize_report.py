"""把实际冻结命令结果写入报告；没有完整绿结果时拒绝宣称回归通过。"""

import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
REPORT = RUN.parents[1] / "tasks/R11-sbom-locator-privacy-fix1.md"
LABELS = [
    "final_locator117",
    "final_dcbc_regression616",
    "final_default25_admitted",
    "final_history18_admitted",
    "final_inventory105_admitted",
    "final_migration119_admitted",
]


def main():
    records = {name: json.loads((RUN / (name + ".json")).read_text()) for name in LABELS}
    assert all(record["exit_code"] == 0 for record in records.values())
    assert all(
        records[name]["owned_database_connections_after_child_exit"] == 0
        for name in LABELS
        if name.endswith("admitted")
    )
    text = REPORT.read_text(encoding="utf-8")
    text = text.replace(
        "新运行的资源适配文件只改变独占数据库绑定",
        "新运行的资源适配文件只改变独占数据库绑定，"
        "并由 root 批准对测试 fixture 自有 engine 指定 NullPool",
    )
    text = text.replace(
        "没有执行原 runner 或写原目录。",
        "没有执行原 runner 或写原目录，也未 patch 默认 App/build_engine。",
    )
    text = text.replace(
        "冻结 locator unit：新增 55 + 既有 33/26", "首冻结9b22 locator unit：新增 55 + 既有 33/26"
    )
    text = text.replace(
        "冻结相关 unique pure/contract/security", "首冻结9b22 相关 unique pure/contract/security"
    )
    pending = (
        "尚待重新分配单进程 slot 才复跑冻结历史18/库存105/迁移119；"
        "现未把这三项冻结完整回归视为通过。"
    )
    assert pending in text
    text = text.replace(
        pending,
        "随后获得 root 单 slot，严格按默认25→历史18→原库存105→空库119逐组执行。"
        "每组子进程退出后，自有数据库剩余连接计数为0；最终全部通过。"
        "资源红保留，不能据此前 too-many 自动推断默认 App shutdown 泄漏。",
    )
    text = text.replace(
        "材料仍待完成 seal 和独立复核。",
        "材料由本 run seal 后交独立复核；精确 manifest/原字节和原红均保留。",
    )
    text = text.replace(
        "root 给予单 PG slot 后完成尚欠冻结 serial 回归并更新本报告，"
        "封存 source/material/exact hash；",
        "封存 source/material/exact hash 后，",
    )
    rows = []
    counts = [117, 616, 25, 18, 105, 119]
    for name, count in zip(LABELS, counts, strict=True):
        record = records[name]
        rows.append(
            f"| {name} | {record['started_at']}–{record['ended_at']}，"
            f"exit 0，{count} passed，0 fail/error/skip |"
        )
    final = (
        "\n## 最终 dcbc 冻结复验\n\n"
        "静态自查发现保留合法 PURL 键时仍会接受 namespace dot 段；"
        "新增 pkg:generic/../../private、pkg:npm/%2e%2e/private 两条 unit 先得到2 failed，"
        "仅在 locator 字段的 PURL 特判拒绝 . / .. namespace 段，"
        "普通带 namespace 的 PURL 阳例仍保留。该补充没有改 snapshot/PURL reference 或 HTTP 判断。"
        "最终源码为dcbc3d92；9b22不是最终修复版本，早先红绿证据保留。\n\n"
        "| 最终范围 | 真实结果（+08:00） |\n|---|---|\n"
        + "\n".join(rows)
        + "\n\n最终117包含新增58和旧33/26，616范围包含旧59，彼此不能累加。"
        "PG25/18/105/119分组不重复累加为正式评分结果；默认入口与0019/0020→0021/0022、"
        "历史、事务、并发、故障回滚和原始raw/hash分别保留完整assert。"
        "没有执行downgrade。旧HEAD0019硬编码oracle的独审原红仍由root按合同演进追踪，"
        "本轮不修改、不skip、不把它算passed。\n"
    )
    REPORT.write_text(text + final, encoding="utf-8")


if __name__ == "__main__":
    main()
