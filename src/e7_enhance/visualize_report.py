from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


FORMAL_RADAR_LABELS = ["输出", "一速", "速度", "抗坦", "纯肉", "命坦", "双效", "半肉"]

RADAR_CATEGORY_MAP = {
    "输出": ("输出", "输出(必爆)"),
    "一速": ("一速",),
    "速度": ("速度套纯速度", "非速度套速度装"),
    "抗坦": ("抗坦",),
    "纯肉": ("纯肉",),
    "命坦": ("命坦",),
    "双效": ("双效",),
    "半肉": ("半肉(血防)", "半肉(通用)", "半肉(白字)"),
}

METRIC_CARDS = [
    ("baili_score_per_1000_stamina", "百里分 / 1000体力"),
    ("cost_per_baili_score", "体力 / 1百里分"),
    ("target_score_per_1000_stamina", "目标分 / 1000体力"),
    ("cost_per_target_score", "体力 / 1目标分"),
    ("success_rate", "成功率"),
    ("native_success_rate", "原生成功率"),
    ("rescued_success_rate", "补救成功率"),
    ("conversion_needed_rate", "转换需求率"),
    ("avg_success_baili_score", "平均成功百里分"),
    ("total_baili_score", "总百里分"),
]


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_visual_model(report: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    by_category = policy.get("target_score_by_category") or {}
    radar = []
    used_categories = set()
    for label in FORMAL_RADAR_LABELS:
        source_categories = RADAR_CATEGORY_MAP[label]
        used_categories.update(source_categories)
        radar.append(
            {
                "label": label,
                "value": round(sum(float(by_category.get(category, 0) or 0) for category in source_categories), 1),
                "sources": list(source_categories),
            }
        )
    auxiliary = {
        key: value
        for key, value in sorted(by_category.items())
        if key not in used_categories and ("未来可期" in key or key == "R61")
    }
    return {
        "report": report,
        "policy": policy,
        "radar": radar,
        "auxiliary_categories": auxiliary,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def render_single_policy_html(report: dict[str, Any], policy: dict[str, Any]) -> str:
    model = build_visual_model(report, policy)
    metric_cards = "\n".join(render_metric_card(policy, key, label) for key, label in METRIC_CARDS)
    stop_cards = "\n".join(
        render_small_card(f"+{checkpoint}", format_rate((policy.get("stop_rate_by_checkpoint") or {}).get(str(checkpoint))))
        for checkpoint in (0, 3, 6, 9, 12, 15)
    )
    auxiliary_note = ""
    if model["auxiliary_categories"]:
        auxiliary_note = "<p>未来可期仅作辅助展示，不进入正式百里主雷达。</p>"
    return page_shell(
        "百里策略审核图",
        f"""
        <section class="hero">
          <div>
            <div class="eyebrow">百里分 / 1000体力</div>
            <div class="big-number">{esc(policy.get("baili_score_per_1000_stamina"))}</div>
          </div>
          <div>
            <div class="eyebrow">体力 / 1百里分</div>
            <div class="big-number secondary">{esc(policy.get("cost_per_baili_score"))}</div>
          </div>
        </section>
        <section class="meta">
          {meta_item("policy_name", policy.get("policy_name"))}
          {meta_item("gear_source", report.get("gear_source"))}
          {meta_item("item_source", report.get("item_source"))}
          {meta_item("rank", report.get("rank"))}
          {meta_item("samples", report.get("calibration_runs"))}
          {meta_item("seed", report.get("seed"))}
          {meta_item("updated_at", model["generated_at"])}
        </section>
        <section class="panel radar-panel">
          <h2>正式分类贡献</h2>
          {render_radar_svg(model["radar"])}
        </section>
        <section class="cards">{metric_cards}</section>
        <section class="panel">
          <h2>停止率</h2>
          <div class="small-cards">{stop_cards}</div>
        </section>
        <section class="notes">
          <p>ranking_metric: {esc(report.get("ranking_metric"))}</p>
          <p>success_definition.source: {esc((report.get("success_definition") or {}).get("source"))}</p>
          <p>success_definition.main_score_scope: {esc((report.get("success_definition") or {}).get("main_score_scope"))}</p>
          <p>conversion_cost_counted: {esc((report.get("success_definition") or {}).get("conversion_cost_counted"))}</p>
          {auxiliary_note}
        </section>
        """,
    )


def render_top_compare_html(report: dict[str, Any], top: int = 5) -> str:
    policies = rank_policies(report)[:top]
    warning = ""
    if report.get("ranking_metric") != "cost_per_baili_score":
        warning = '<div class="warning">当前报告不是百里分优先排序。</div>'
    rows = "\n".join(render_compare_row(report, policy) for policy in policies)
    return page_shell(
        "top5 策略对比",
        f"""
        <section class="hero single">
          <div>
            <div class="eyebrow">top{len(policies)} 策略对比</div>
            <div class="title">百里分效率排序</div>
          </div>
        </section>
        {warning}
        <section class="panel">
          <table>
            <thead>
              <tr>
                <th>策略</th><th>百里/千体</th><th>体力/百里</th><th>目标/千体</th>
                <th>成功率</th><th>原生</th><th>补救</th><th>+12停</th><th>+15完成</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </section>
        <section class="notes">
          <p>best_policy: {esc(report.get("best_policy"))}</p>
          <p>ranking_metric: {esc(report.get("ranking_metric"))}</p>
        </section>
        """,
    )


def write_visualizations(input_path: Path | str, output_dir: Path | str | None = None, policy_name: str | None = None, top: int = 5) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = Path(output_dir) if output_dir else Path("reports") / "visual"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = load_report(input_path)
    policy = select_policy(report, policy_name)
    stem = sanitize_filename(input_path.stem)
    policy_stem = sanitize_filename(policy.get("policy_name") or "policy")
    single_html = output_dir / f"{stem}-{policy_stem}.html"
    single_png = output_dir / f"{stem}-{policy_stem}.png"
    compare_html = output_dir / f"{stem}-top{top}-compare.html"
    compare_png = output_dir / f"{stem}-top{top}-compare.png"
    single_html.write_text(render_single_policy_html(report, policy), encoding="utf-8")
    compare_html.write_text(render_top_compare_html(report, top=top), encoding="utf-8")
    single_png_result = try_export_png(single_html, single_png)
    compare_png_result = try_export_png(compare_html, compare_png)
    index_path = output_dir / "index.html"
    append_index(index_path, [single_html, compare_html], [single_png_result, compare_png_result])
    return {
        "policy_name": policy.get("policy_name"),
        "single_html": str(single_html),
        "single_png": str(single_png) if single_png.exists() else None,
        "compare_html": str(compare_html),
        "compare_png": str(compare_png) if compare_png.exists() else None,
        "index_html": str(index_path),
        "png_notes": [single_png_result, compare_png_result],
    }


def select_policy(report: dict[str, Any], policy_name: str | None = None) -> dict[str, Any]:
    policies = report.get("policies") or []
    if not policies:
        raise ValueError("report has no policies")
    if policy_name:
        for policy in policies:
            if policy.get("policy_name") == policy_name:
                return policy
        raise ValueError(f"policy not found: {policy_name}")
    best = report.get("best_policy")
    for policy in policies:
        if policy.get("policy_name") == best:
            return policy
    return rank_policies(report)[0]


def rank_policies(report: dict[str, Any]) -> list[dict[str, Any]]:
    metric = report.get("ranking_metric") or "cost_per_baili_score"
    policies = list(report.get("policies") or [])
    lower_is_better = metric.startswith("cost_per_")

    def key(policy: dict[str, Any]) -> tuple[float, str]:
        value = policy.get(metric)
        if value is None:
            ranked = float("inf") if lower_is_better else float("-inf")
        else:
            ranked = float(value)
        return (ranked if lower_is_better else -ranked, str(policy.get("policy_name") or ""))

    return sorted(policies, key=key)


def render_radar_svg(items: list[dict[str, Any]]) -> str:
    width = 760
    height = 520
    center_x = width / 2
    center_y = height / 2 + 20
    radius = 190
    max_value = max([float(item["value"]) for item in items] + [1.0])
    rings = []
    for step in range(1, 5):
        points = polygon_points(len(items), center_x, center_y, radius * step / 4)
        rings.append(f'<polygon points="{points}" class="ring" />')
    axes = []
    labels = []
    value_points = []
    for index, item in enumerate(items):
        x, y = radar_point(index, len(items), center_x, center_y, radius)
        axes.append(f'<line x1="{center_x:.1f}" y1="{center_y:.1f}" x2="{x:.1f}" y2="{y:.1f}" class="axis" />')
        label_x, label_y = radar_point(index, len(items), center_x, center_y, radius + 45)
        labels.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" class="radar-label">{esc(item["label"])}</text>')
        value_radius = radius * (float(item["value"]) / max_value)
        vx, vy = radar_point(index, len(items), center_x, center_y, value_radius)
        value_points.append(f"{vx:.1f},{vy:.1f}")
    values = " ".join(value_points)
    return f"""
    <svg class="radar" viewBox="0 0 {width} {height}" role="img" aria-label="正式分类贡献雷达图">
      {''.join(rings)}
      {''.join(axes)}
      <polygon points="{values}" class="radar-area" />
      {''.join(labels)}
    </svg>
    """


def polygon_points(count: int, center_x: float, center_y: float, radius: float) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in (radar_point(index, count, center_x, center_y, radius) for index in range(count)))


def radar_point(index: int, count: int, center_x: float, center_y: float, radius: float) -> tuple[float, float]:
    import math

    angle = -math.pi / 2 + 2 * math.pi * index / count
    return center_x + math.cos(angle) * radius, center_y + math.sin(angle) * radius


def render_metric_card(policy: dict[str, Any], key: str, label: str) -> str:
    value = format_rate(policy.get(key)) if key.endswith("_rate") else fmt(policy.get(key))
    return f'<div class="card"><div class="card-label">{esc(label)}</div><div class="card-value">{esc(value)}</div></div>'


def render_small_card(label: str, value: str) -> str:
    return f'<div class="small-card"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>'


def render_compare_row(report: dict[str, Any], policy: dict[str, Any]) -> str:
    best_class = "best" if policy.get("policy_name") == report.get("best_policy") else ""
    stop = policy.get("stop_rate_by_checkpoint") or {}
    return f"""
    <tr class="{best_class}">
      <td>{esc(policy.get("policy_name"))}{' <span>best_policy</span>' if best_class else ''}</td>
      <td>{esc(fmt(policy.get("baili_score_per_1000_stamina")))}</td>
      <td>{esc(fmt(policy.get("cost_per_baili_score")))}</td>
      <td>{esc(fmt(policy.get("target_score_per_1000_stamina")))}</td>
      <td>{esc(format_rate(policy.get("success_rate")))}</td>
      <td>{esc(format_rate(policy.get("native_success_rate")))}</td>
      <td>{esc(format_rate(policy.get("rescued_success_rate")))}</td>
      <td>{esc(format_rate(stop.get("12")))}</td>
      <td>{esc(format_rate(stop.get("15")))}</td>
    </tr>
    """


def page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f6fbff; color: #142033; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }}
    .page {{ width: min(100%, 1020px); margin: 0 auto; padding: 34px 28px 44px; background: #fff; }}
    .hero {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; border-bottom: 1px solid #d9ebf8; padding-bottom: 22px; }}
    .hero.single {{ grid-template-columns: 1fr; }}
    .eyebrow {{ color: #51708f; font-size: 22px; font-weight: 700; }}
    .big-number {{ color: #1478b8; font-size: 76px; line-height: 1.05; font-weight: 800; overflow-wrap: anywhere; }}
    .big-number.secondary {{ color: #253b56; }}
    .title {{ color: #1478b8; font-size: 52px; line-height: 1.1; font-weight: 800; overflow-wrap: anywhere; }}
    .meta {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 20px; padding: 20px 0; color: #42566d; }}
    .meta b {{ color: #17253a; overflow-wrap: anywhere; }}
    .panel {{ margin-top: 18px; padding: 18px; border: 1px solid #dbeefb; background: #fbfdff; border-radius: 8px; }}
    h2 {{ margin: 0 0 14px; font-size: 24px; color: #173a5d; }}
    .radar-panel {{ text-align: center; }}
    .radar {{ width: 100%; max-width: 790px; height: auto; }}
    .ring {{ fill: none; stroke: #d8e9f6; stroke-width: 1.2; }}
    .axis {{ stroke: #e3f0f9; stroke-width: 1; }}
    .radar-area {{ fill: rgba(20, 120, 184, 0.22); stroke: #1478b8; stroke-width: 3; }}
    .radar-label {{ fill: #173a5d; font-size: 20px; font-weight: 700; text-anchor: middle; dominant-baseline: middle; }}
    .cards {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }}
    .card, .small-card {{ background: #eef8ff; border: 1px solid #d7edf9; border-radius: 8px; padding: 14px; min-width: 0; }}
    .card-label {{ color: #57738d; font-size: 15px; }}
    .card-value {{ color: #17253a; font-size: 28px; font-weight: 800; overflow-wrap: anywhere; }}
    .small-cards {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }}
    .small-card span {{ display: block; color: #57738d; font-size: 14px; }}
    .small-card strong {{ display: block; color: #17253a; font-size: 20px; overflow-wrap: anywhere; }}
    .notes {{ margin-top: 18px; color: #52677d; font-size: 15px; line-height: 1.5; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
    th, td {{ border-bottom: 1px solid #dbeefb; padding: 10px 8px; text-align: right; vertical-align: top; overflow-wrap: anywhere; }}
    th:first-child, td:first-child {{ text-align: left; }}
    tr.best td {{ background: #eef8ff; font-weight: 700; }}
    td span {{ display: inline-block; margin-left: 6px; color: #1478b8; }}
    .warning {{ margin: 16px 0; padding: 12px; border: 1px solid #f0c36a; background: #fff8e5; border-radius: 8px; color: #6d520e; }}
    @media (max-width: 760px) {{
      .page {{ padding: 22px 14px 32px; }}
      .hero, .meta, .cards {{ grid-template-columns: 1fr; }}
      .big-number {{ font-size: 52px; }}
      .title {{ font-size: 36px; }}
      .small-cards {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      table {{ font-size: 13px; }}
      th, td {{ padding: 8px 5px; }}
    }}
  </style>
</head>
<body><main class="page">{body}</main></body>
</html>"""


def meta_item(label: str, value: Any) -> str:
    return f"<div>{esc(label)}: <b>{esc(fmt(value))}</b></div>"


def fmt(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def format_rate(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return f"{float(value) * 100:.2f}%"


def esc(value: Any) -> str:
    return html.escape(fmt(value), quote=True)


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^\w\-.一-龥]+", "-", value, flags=re.UNICODE).strip("-")
    return value or "report"


def try_export_png(html_path: Path, png_path: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return {"html": str(html_path), "png": None, "created": False, "reason": f"Playwright unavailable: {exc}"}
    try:  # pragma: no cover
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1040, "height": 1500}, device_scale_factor=1)
            page.goto(html_path.resolve().as_uri())
            page.locator(".page").screenshot(path=str(png_path))
            browser.close()
        return {"html": str(html_path), "png": str(png_path), "created": True, "reason": None}
    except Exception as exc:
        return {"html": str(html_path), "png": None, "created": False, "reason": f"PNG export failed: {exc}"}


def append_index(index_path: Path, html_paths: list[Path], png_results: list[dict[str, Any]]) -> None:
    existing_links = ""
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8")
        match = re.search(r"<ul>(.*?)</ul>", text, flags=re.S)
        existing_links = match.group(1) if match else ""
    new_links = "\n".join(f'<li><a href="{esc(path.name)}">{esc(path.name)}</a></li>' for path in html_paths)
    png_notes = "\n".join(f"<p>{esc(item.get('reason'))}</p>" for item in png_results if not item.get("created") and item.get("reason"))
    index_path.write_text(
        page_shell("可视化报告索引", f'<section class="panel"><h2>reports/visual</h2><ul>{existing_links}{new_links}</ul>{png_notes}</section>'),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Epic Seven calibration visual report")
    parser.add_argument("--input", required=True)
    parser.add_argument("--policy")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--output-dir", default=str(Path("reports") / "visual"))
    args = parser.parse_args(argv)
    result = write_visualizations(args.input, args.output_dir, args.policy, args.top)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
