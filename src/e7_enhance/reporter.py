from __future__ import annotations

import json


RECOMMENDATION_LABELS = {
    "stop": "停止",
    "continue": "继续",
    "cautious_continue": "谨慎继续",
    "keep": "保留",
    "convert": "转换/过渡",
    "uncertain": "不确定",
}


def render_result(result: dict, debug: bool = False) -> str:
    if debug:
        return json.dumps(result, ensure_ascii=False, indent=2)
    summary = result["summary"]
    lines = [
        f"建议：{RECOMMENDATION_LABELS.get(summary['recommendation'], summary['recommendation'])}",
        f"目标体系：{summary.get('target_profile') or '-'}",
    ]
    if summary.get("next_check_at") is not None:
        lines.append(f"下一检查点：+{summary['next_check_at']}")
    reasons = summary.get("reasons") or []
    if reasons:
        lines.append("关键理由：")
        lines.extend(f"- {reason}" for reason in reasons)
    return "\n".join(lines)


def render_batch_markdown(results: list[dict]) -> str:
    rows = ["# 装备强化建议报告", "", "| # | 建议 | 下一检查点 | 目标体系 | 关键理由 |", "|---:|---|---|---|---|"]
    for index, result in enumerate(results, start=1):
        summary = result["summary"]
        recommendation = RECOMMENDATION_LABELS.get(summary["recommendation"], summary["recommendation"])
        next_check = f"+{summary['next_check_at']}" if summary.get("next_check_at") is not None else "-"
        reasons = "<br>".join(summary.get("reasons") or [])
        rows.append(f"| {index} | {recommendation} | {next_check} | {summary.get('target_profile') or '-'} | {reasons} |")
    rows.append("")
    return "\n".join(rows)
