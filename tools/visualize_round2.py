from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.calibration import set_group_for_set
from src.e7_enhance.visualize_report import RADAR_CATEGORY_MAP, try_export_png, write_visualizations


REPORT_DIR = Path("reports")
VISUAL_DIR = REPORT_DIR / "visual"
SUMMARY_PATH = REPORT_DIR / "baili-formal-round2-summary.json"
REPRESENTATIVE_REPORT = REPORT_DIR / "baili-formal-round2-normal-epic-1m-seed17.json"
REPRESENTATIVE_POLICY = "category_baili_marginal_mid"


def main() -> int:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    single = write_visualizations(REPRESENTATIVE_REPORT, VISUAL_DIR, REPRESENTATIVE_POLICY, top=5)
    set_html = VISUAL_DIR / "baili-formal-round2-set-contribution.html"
    set_png = VISUAL_DIR / "baili-formal-round2-set-contribution.png"
    type_html = VISUAL_DIR / "baili-formal-round2-equipment-type-compare.html"
    type_png = VISUAL_DIR / "baili-formal-round2-equipment-type-compare.png"
    best_html = VISUAL_DIR / "baili-formal-round2-best-single-policy.html"
    best_png = VISUAL_DIR / "baili-formal-round2-best-single-policy.png"
    set_html.write_text(render_set_contribution(summary), encoding="utf-8")
    type_html.write_text(render_equipment_type_compare(summary), encoding="utf-8")
    best_html.write_text(render_best_single_policy(summary), encoding="utf-8")
    set_png_result = try_export_png(set_html, set_png)
    type_png_result = try_export_png(type_html, type_png)
    best_png_result = try_export_png(best_html, best_png)
    update_round2_index([best_html, Path(single["single_html"]), Path(single["compare_html"]), set_html, type_html], [best_png_result, set_png_result, type_png_result])
    result = {
        "single": single,
        "set_contribution_html": str(set_html),
        "set_contribution_png": str(set_png) if set_png.exists() else None,
        "equipment_type_compare_html": str(type_html),
        "equipment_type_compare_png": str(type_png) if type_png.exists() else None,
        "aggregate_best_single_html": str(best_html),
        "aggregate_best_single_png": str(best_png) if best_png.exists() else None,
        "png_notes": [best_png_result, set_png_result, type_png_result],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def render_set_contribution(summary: dict[str, Any]) -> str:
    run = summary["runs"]["normal_epic_1m"]
    policy = run["policy_aggregate"][run["top5_by_mean_cost"][0]["policy_name"]]
    values = group_baili_by_set_group(policy.get("baili_score_by_set") or {})
    rows = sorted(values.items(), key=lambda item: item[1], reverse=True)
    total = sum(float(value) for _, value in rows) or 1.0
    bars = "\n".join(render_bar(label, value, total) for label, value in rows[:18])
    return page(
        "套装组贡献图",
        f"""
        <section class="hero">
          <div>
            <div class="eyebrow">normal_85 Epic 1M×5</div>
            <h1>套装贡献</h1>
            <p>策略：{esc(policy['policy_name'])}，按 md 用途套装组汇总 R2-R58 正式百里分。</p>
          </div>
          <div class="metric">
            <span>体力 / 百里</span>
            <strong>{fmt(policy['cost_per_baili_score']['mean'])}</strong>
          </div>
        </section>
        <section class="panel">
          {bars}
        </section>
        """,
    )


def render_best_single_policy(summary: dict[str, Any]) -> str:
    run = summary["runs"]["normal_epic_1m"]
    policy = run["policy_aggregate"][run["top5_by_mean_cost"][0]["policy_name"]]
    category_values = radar_values(policy.get("target_score_by_category") or {})
    total = sum(value for _, value in category_values) or 1.0
    bars = "\n".join(render_bar(label, value, total) for label, value in category_values)
    seeds = ", ".join(str(seed) for seed in run["rank_stability"]["best_policy_by_seed"])
    return page(
        "聚合最佳单策略图",
        f"""
        <section class="hero">
          <div>
            <div class="eyebrow">normal_85 Epic / 1M×5 / seeds {esc(seeds)}</div>
            <h1>最佳单策略</h1>
            <p>policy_name：{esc(policy['policy_name'])}</p>
          </div>
          <div class="metric">
            <span>体力 / 百里</span>
            <strong>{fmt(policy['cost_per_baili_score']['mean'])}</strong>
          </div>
        </section>
        <section class="type-grid">
          {metric_card("百里 / 1000体力", policy['baili_score_per_1000_stamina']['mean'])}
          {metric_card("成功率", pct(policy['success_rate']['mean']))}
          {metric_card("+12停止率", pct(policy['stop_plus12']['mean']))}
          {metric_card("+15完成率", pct(policy['finish_plus15']['mean']))}
        </section>
        <section class="panel">
          <h2>正式分类贡献</h2>
          {bars}
        </section>
        <section class="panel">
          <p>ranking_metric: {esc(summary['scope'].get('ranking_metric'))}</p>
          <p>main_score_scope: {esc(summary['scope'].get('main_score_scope'))}</p>
          <p>samples: 1,000,000 × 5</p>
          <p>gear_source / item_source / rank: rift_new_1_32 / normal_85 / Epic</p>
        </section>
        """,
    )


def render_equipment_type_compare(summary: dict[str, Any]) -> str:
    labels = [
        ("normal_epic_1m", "普通85红装"),
        ("normal_heroic_1m", "普通85紫装"),
        ("rift_epic_1m", "异界85红装"),
    ]
    rows = []
    for key, label in labels:
        run = summary["runs"].get(key)
        if not run:
            continue
        policy = run["top5_by_mean_cost"][0]
        rows.append((label, policy))
    max_baili = max([float(policy["baili_score_per_1000_stamina"]["mean"] or 0) for _, policy in rows] + [1.0])
    cards = "\n".join(render_type_card(label, policy, max_baili) for label, policy in rows)
    return page(
        "装备类型对比图",
        f"""
        <section class="hero">
          <div>
            <div class="eyebrow">1M×5 深度验证</div>
            <h1>装备类型对比</h1>
            <p>三类装备分别统计，不混算；排序指标为 cost_per_baili_score。</p>
          </div>
        </section>
        <section class="type-grid">{cards}</section>
        """,
    )


def render_bar(label: str, value: float, total: float) -> str:
    pct = max(2.0, float(value) * 100 / total)
    return f"""
    <div class="bar-row">
      <div class="bar-label">{esc(label)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:{pct:.2f}%"></div></div>
      <div class="bar-value">{fmt(value)}</div>
    </div>
    """


def render_type_card(label: str, policy: dict[str, Any], max_baili: float) -> str:
    baili = float(policy["baili_score_per_1000_stamina"]["mean"] or 0)
    width = max(3.0, baili * 100 / max_baili)
    return f"""
    <article class="type-card">
      <h2>{esc(label)}</h2>
      <p class="policy">{esc(policy['policy_name'])}</p>
      <div class="meter"><div style="width:{width:.2f}%"></div></div>
      <dl>
        <dt>百里 / 千体</dt><dd>{fmt(policy['baili_score_per_1000_stamina']['mean'])}</dd>
        <dt>体力 / 百里</dt><dd>{fmt(policy['cost_per_baili_score']['mean'])}</dd>
        <dt>成功率</dt><dd>{pct(policy['success_rate']['mean'])}</dd>
        <dt>95% CI</dt><dd>{fmt(policy['cost_per_baili_score']['ci95'])}</dd>
      </dl>
    </article>
    """


def metric_card(label: str, value: Any) -> str:
    return f'<article class="type-card"><h2>{esc(label)}</h2><p class="metric-inline">{esc(value)}</p></article>'


def group_baili_by_set_group(values: dict[str, float]) -> dict[str, float]:
    labels = {
        "speed": "速度相关套装组",
        "output": "输出套装组",
        "tank": "坦克套装组",
        "dual": "双效套装组",
        "bruiser": "半肉套装组",
        "generic": "泛用/低优先级",
    }
    result = {label: 0.0 for label in labels.values()}
    for set_code, value in values.items():
        group = labels.get(set_group_for_set(set_code), labels["generic"])
        result[group] = result.get(group, 0.0) + float(value or 0)
    return {key: value for key, value in result.items() if value > 0}


def radar_values(by_category: dict[str, float]) -> list[tuple[str, float]]:
    result = []
    for label, categories in RADAR_CATEGORY_MAP.items():
        result.append((label, sum(float(by_category.get(category, 0) or 0) for category in categories)))
    return result


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    body {{ margin:0; background:#f4f9fc; color:#142033; font-family:"Microsoft YaHei","Segoe UI",sans-serif; }}
    .page {{ width:min(1120px,100%); margin:0 auto; padding:32px 28px 44px; background:white; }}
    .hero {{ display:grid; grid-template-columns:1fr auto; gap:24px; align-items:end; border-bottom:1px solid #d7ebf7; padding-bottom:22px; }}
    .eyebrow {{ color:#51708f; font-weight:700; font-size:18px; }}
    h1 {{ margin:6px 0; color:#143b5d; font-size:48px; line-height:1.05; }}
    p {{ margin:0; color:#52677d; }}
    .metric {{ min-width:220px; background:#eef8ff; border:1px solid #d7edf9; border-radius:8px; padding:16px; }}
    .metric span {{ display:block; color:#57738d; }}
    .metric strong {{ display:block; color:#1478b8; font-size:44px; overflow-wrap:anywhere; }}
    .panel {{ margin-top:22px; }}
    .bar-row {{ display:grid; grid-template-columns:180px 1fr 100px; gap:12px; align-items:center; padding:8px 0; }}
    .bar-label {{ font-weight:700; overflow-wrap:anywhere; }}
    .bar-track {{ height:22px; background:#edf5fb; border-radius:6px; overflow:hidden; }}
    .bar-fill {{ height:100%; background:#1478b8; }}
    .bar-value {{ text-align:right; font-weight:700; }}
    .type-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-top:22px; }}
    .type-card {{ border:1px solid #d7edf9; background:#fbfdff; border-radius:8px; padding:18px; min-width:0; }}
    .type-card h2 {{ margin:0 0 8px; color:#143b5d; }}
    .policy {{ min-height:44px; overflow-wrap:anywhere; }}
    .meter {{ height:14px; background:#edf5fb; border-radius:5px; overflow:hidden; margin:18px 0; }}
    .meter div {{ height:100%; background:#1478b8; }}
    dl {{ display:grid; grid-template-columns:1fr auto; gap:8px 12px; margin:0; }}
    dt {{ color:#57738d; }}
    dd {{ margin:0; font-weight:800; text-align:right; }}
    @media (max-width:760px) {{
      .page {{ padding:22px 14px 32px; }}
      .hero, .type-grid {{ grid-template-columns:1fr; }}
      h1 {{ font-size:36px; }}
      .bar-row {{ grid-template-columns:1fr; gap:6px; }}
      .bar-value {{ text-align:left; }}
    }}
  </style>
</head>
<body><main class="page">{body}</main></body>
</html>"""


def update_round2_index(html_paths: list[Path], png_results: list[dict[str, Any]]) -> None:
    index = VISUAL_DIR / "round2-index.html"
    links = "\n".join(f'<li><a href="{esc(path.name)}">{esc(path.name)}</a></li>' for path in html_paths)
    notes = "\n".join(f"<p>{esc(item.get('reason'))}</p>" for item in png_results if not item.get("created") and item.get("reason"))
    index.write_text(page("Round2 可视化索引", f"<section class=\"panel\"><ul>{links}</ul>{notes}</section>"), encoding="utf-8")


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"


def esc(value: Any) -> str:
    text = fmt(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


if __name__ == "__main__":
    raise SystemExit(main())
