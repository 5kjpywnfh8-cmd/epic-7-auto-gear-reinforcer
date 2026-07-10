from __future__ import annotations

from .models import Gear, validate_gear_source_rank, validate_gear_structure
from .rules import STAT_KEY_LABELS, speed_potential_set_eligible
from .score_engine import Evaluation, evaluate_gear, full_category_diagnostics, full_category_matches, speed_value
from .strategy_defaults import DEFAULT_GEAR_SOURCE, STRATEGY_VERSION, StrategyDefault, default_strategy_for

CHECKPOINTS = [0, 3, 6, 9, 12, 15]


def advise_gear(
    gear: Gear,
    item_source: str = "normal_85",
    gear_source: str = DEFAULT_GEAR_SOURCE,
    enable_dp_assist: bool | None = None,
) -> dict:
    validate_gear_structure(gear)
    validate_gear_source_rank(gear, item_source)
    evaluation = evaluate_gear(gear)
    roll_analysis = analyze_roll_hits(gear, evaluation)
    summary = summarize_recommendation(evaluation, roll_analysis)
    strategy = default_strategy_for(item_source=item_source, rank=gear.rank, gear_source=gear_source)
    dp_debug = apply_default_strategy(
        gear=gear,
        item_source=item_source,
        gear_source=gear_source,
        strategy=strategy,
        summary=summary,
        enable_dp_assist=enable_dp_assist,
    )
    summary = dp_debug.pop("summary")
    return {
        "summary": summary,
        "debug": {
            "strategy_version": STRATEGY_VERSION,
            "default_strategy": strategy_debug(strategy, enable_dp_assist),
            "dp_assist": dp_debug,
            "official_score": evaluation.official_score,
            "official_parts": evaluation.official_parts,
            "effective_score": evaluation.effective_score,
            "baili_score": evaluation.baili_score,
            "target_score": evaluation.target_score,
            "target_score_source_row": evaluation.target_score_source_row,
            "target_score_formula": evaluation.target_score_formula,
            "rating_level": evaluation.rating_label,
            "rating_semantics": "current_static",
            "fit_status": evaluation.fit_status,
            "valid_substats": evaluation.valid_substats,
            "invalid_substats": evaluation.invalid_substats,
            "roll_hit_analysis": roll_analysis,
            "ocr_raw_result": None,
        },
    }


def apply_default_strategy(
    gear: Gear,
    item_source: str,
    gear_source: str,
    strategy: StrategyDefault,
    summary: dict,
    enable_dp_assist: bool | None,
) -> dict:
    checkpoint = nearest_checkpoint(gear.enhance)
    enabled = strategy.enable_dp_assist if enable_dp_assist is None else bool(enable_dp_assist)
    debug = {
        "summary": summary,
        "enabled": enabled,
        "checkpoint": checkpoint,
        "baseline_recommendation": summary["recommendation"],
        "baseline_continue": summary_to_continue(summary),
        "baseline_policy": strategy.policy_name,
        "dp_decision": None,
        "dp_expected_utility": None,
        "dp_continue_utility": None,
        "dp_utility_gap": None,
        "dp_expected_formal_baili_score": None,
        "dp_expected_terminal_value": None,
        "dp_expected_final_speed": None,
        "dp_expected_speed_rolls": None,
        "dp_speed_potential_set_eligible": None,
        "dp_speed_potential_threshold_blocked_probability": None,
        "dp_expected_speed_potential_value": None,
        "dp_expected_incremental_stamina": None,
        "dp_best_target_category": None,
        "dp_best_source_row": None,
        "overrode_baseline": False,
        "reason": "disabled" if not enabled else "not_dp_checkpoint",
        "decision_mode": "disabled" if not enabled else "exact_dp",
        "lightweight_basis": None,
    }
    if not enabled or checkpoint >= 15 or strategy.policy_name not in policies_by_name(item_source, gear.rank):
        return debug

    if checkpoint in (0, 3):
        prediction = lightweight_prediction(gear, item_source, gear_source)
        should_continue = prediction["action"] == "continue"
        should_review = prediction["action"] == "review"
        debug.update(
            {
                "decision_mode": "lightweight_prediction",
                "dp_decision": f"lightweight_{prediction['action']}",
                "dp_expected_terminal_value": prediction["terminal_value"],
                "dp_expected_final_speed": prediction["expected_final_speed"],
                "dp_expected_speed_rolls": prediction["expected_speed_rolls"],
                "dp_speed_potential_set_eligible": prediction["speed_set_eligible"],
                "dp_speed_potential_threshold_blocked_probability": prediction["speed_threshold_blocked_probability"],
                "dp_expected_speed_potential_value": prediction["speed_potential_value"],
                "dp_best_target_category": prediction["target_category"],
                "reason": prediction["reason"],
                "lightweight_basis": prediction["basis"],
            }
        )
        if should_continue:
            debug["summary"] = build_summary(
                "continue",
                6,
                prediction["target_category"],
                ["轻量预测高确定性继续", prediction["reason"]],
            )
        elif should_review:
            debug["summary"] = build_summary(
                "cautious_continue",
                6,
                prediction["target_category"],
                ["轻量预测保留，待 +6 精确复核", prediction["reason"]],
            )
        else:
            debug["summary"] = build_summary("stop", 6, prediction["target_category"], [prediction["reason"]])
        return debug

    policy = policies_by_name(item_source, gear.rank)[strategy.policy_name]
    if checkpoint not in policy.dp_checkpoints:
        return debug
    from .calibration import CalibrationOptions, checkpoint_state, continuation_decision_state

    options = CalibrationOptions(item_source=item_source, gear_source=gear_source, rank=gear.rank, enable_dp_assist=enabled)
    state = checkpoint_state(gear, None, options)
    decision = continuation_decision_state(state, policy, options)
    dp_continue = bool(decision.get("dp_continue", decision["continue"]))
    final_continue = bool(decision["continue"])
    overrode = bool(decision.get("dp_overrode_baseline"))
    debug.update(
        {
            "decision_mode": "exact_dp",
            "baseline_policy": policy.base_policy_name or strategy.policy_name,
            "baseline_continue": decision.get("baseline_continue", debug["baseline_continue"]),
            "dp_decision": "continue" if dp_continue else "stop",
            "dp_expected_utility": decision.get("dp_expected_utility"),
            "dp_continue_utility": decision.get("dp_continue_utility"),
            "dp_utility_gap": decision.get("dp_utility_gap"),
            "dp_expected_formal_baili_score": decision.get("dp_expected_formal_baili_score"),
            "dp_expected_terminal_value": decision.get("dp_expected_terminal_value"),
            "dp_expected_final_speed": decision.get("dp_expected_final_speed"),
            "dp_expected_speed_rolls": decision.get("dp_expected_speed_rolls"),
            "dp_speed_potential_set_eligible": decision.get("dp_speed_potential_set_eligible"),
            "dp_speed_potential_threshold_blocked_probability": decision.get("dp_speed_potential_threshold_blocked_probability"),
            "dp_expected_speed_potential_value": decision.get("dp_expected_speed_potential_value"),
            "dp_expected_incremental_stamina": decision.get("dp_expected_incremental_stamina"),
            "dp_best_target_category": decision.get("dp_best_target_category"),
            "dp_best_source_row": decision.get("dp_best_source_row"),
            "overrode_baseline": overrode,
            "reason": "terminal_route",
        }
    )
    debug["summary"] = summary_from_strategy_decision(summary, final_continue, checkpoint, debug)
    return debug


def lightweight_prediction(gear: Gear, item_source: str, gear_source: str) -> dict:
    """Conservative +0/+3 routing without invoking early-node exact DP."""
    from .calibration import (
        expected_final_reforge_speed,
        future_hit_count,
        speed_cross_probability,
    )
    from .lightweight_calibration import (
        best_theoretical_bound,
        calibration_group,
        calibration_rule,
        evaluate_early_candidates,
        passes_continue_threshold,
        stop_threshold,
    )

    evaluation = evaluate_gear(gear)
    full_matches = full_category_matches(gear)
    category_diagnostics = full_category_diagnostics(gear)
    candidates = evaluate_early_candidates(gear, item_source)
    selected_candidate = next((item for item in candidates if item["qualified"]), None)
    qualified_candidates = [item for item in candidates if item["qualified"]]
    candidate_selection_reason = _candidate_selection_reason(selected_candidate, qualified_candidates)
    expected_speed = expected_final_reforge_speed(gear, item_source)
    speed_stat = next((stat for stat in gear.substats if stat.key == "spd"), None)
    remaining_hits = future_hit_count(gear)
    expected_speed_rolls = round((speed_stat.rolls + remaining_hits / len(gear.substats)) if speed_stat else 0, 1)
    speed_set_eligible = speed_potential_set_eligible(gear.set)
    speed_threshold_probability = (
        0.0
        if speed_stat is None
        else 1.0
        if speed_set_eligible
        else speed_cross_probability(gear, item_source, 20, expected_speed)
    )
    speed_potential_value = 0.0
    if speed_stat and expected_speed_rolls > 1 and (speed_set_eligible or expected_speed >= 20):
        speed_potential_value = round(expected_speed * (expected_speed_rolls - 1), 1)
    candidate_by_category = {item["category"]: item for item in candidates}
    for match in full_matches:
        candidate = candidate_by_category.get(match["category"], {})
        match["expected_target_score"] = float(candidate.get("expected_terminal_value") or 0.0)
    full_matches.sort(key=lambda item: (-item["expected_target_score"], item["priority"]))
    selected_full_match = full_matches[0] if full_matches else None
    selected_full_category = selected_full_match["category"] if selected_full_match else None
    selected_target_score = float(selected_candidate.get("expected_terminal_value") or 0.0) if selected_candidate else 0.0
    expected_score = float(selected_candidate.get("expected_final_gs") or 0.0) if selected_candidate else 0.0
    terminal_value = round(max(speed_potential_value, selected_target_score), 1)
    non_speed_boot = gear.slot == "boot" and gear.main_stat.key != "spd"
    speed_protection_eligible = bool(
        speed_stat
        and not non_speed_boot
        and speed_stat.rolls >= 2
        and speed_potential_value > 0
        and (speed_set_eligible or expected_speed >= 20)
    )
    speed_high_value_route = bool(
        speed_protection_eligible
        and selected_full_category in {"输出", "输出(必爆)"}
    )
    speed_boot_full_category = gear.slot == "boot" and gear.main_stat.key == "spd" and bool(full_matches)
    theoretical_bound = best_theoretical_bound(gear, item_source)
    selected_group = (
        calibration_group(
            gear,
            item_source,
            selected_candidate["set_group"],
            selected_candidate["category"],
            selected_candidate["current_valid_substat_count"],
            selected_candidate["feasible_valid_substat_count"],
        )
        if selected_candidate
        else calibration_group(
            gear,
            item_source,
            theoretical_bound["set_group"] if theoretical_bound else "none",
            theoretical_bound["category"] if theoretical_bound else "未命中",
        )
    )
    rule = calibration_rule(selected_group)
    metrics = {
        "full_category_matched": bool(selected_full_match),
        "expected_final_reforge_score": expected_score,
        "expected_final_target_score": selected_target_score,
        "current_effective_score": evaluation.effective_score,
        "remaining_hits": remaining_hits,
        "formal_cross_tier_probability": float(selected_candidate.get("terminal_reach_probability") or 0.0) if selected_candidate else 0.0,
        "terminal_reach_probability": float(selected_candidate.get("terminal_reach_probability") or 0.0) if selected_candidate else 0.0,
        "current_valid_substat_count": selected_candidate.get("current_valid_substat_count", 0) if selected_candidate else 0,
        "feasible_valid_substat_count": selected_candidate.get("feasible_valid_substat_count", 0) if selected_candidate else 0,
        "expected_final_speed": expected_speed,
        "speed": speed_stat.normalized_value if speed_stat else 0.0,
        "speed_rolls": speed_stat.rolls if speed_stat else 0,
        "speed_potential_value": speed_potential_value,
        "speed_potential_set_eligible": speed_set_eligible,
    }
    continue_by_rule = passes_continue_threshold(rule, metrics)
    upper_bound = selected_candidate["theoretical_upper_bound"] if selected_candidate else (theoretical_bound["theoretical_upper_bound"] if theoretical_bound else 0.0)
    lower_bound = selected_candidate["theoretical_lower_bound"] if selected_candidate else (theoretical_bound["theoretical_lower_bound"] if theoretical_bound else 0.0)
    configured_stop_threshold = stop_threshold(rule)

    if speed_boot_full_category:
        action, route = "continue", "速度主属性鞋完整分类继续"
        target_category = selected_full_category
        reason = f"速度主属性鞋完整命中 {selected_full_category}，不以速度副属性或数值门槛拦截"
    elif speed_high_value_route:
        action, route = "continue", "多跳速度高价值路线"
        target_category = "速度潜力"
        reason = f"速度 {speed_stat.rolls} 跳，速度潜力套装资格={speed_set_eligible}，终局速度潜力 {speed_potential_value}"
    elif continue_by_rule and selected_candidate and selected_candidate["current_valid_substat_count"] == 4:
        action, route = "continue", "完整分类校准继续"
        target_category = selected_candidate["category"]
        reason = f"四条副属性完整命中 {selected_candidate['category']}，达到分组校准继续门槛"
    elif selected_candidate:
        action, route = "review", "候选体系待 +6 精确复核"
        target_category = selected_candidate["category"]
        if selected_candidate["is_conversion_candidate"]:
            reason = (
                f"{selected_candidate['category']} 命中 {selected_candidate['current_valid_substat_count']} 条副属性，"
                f"{selected_candidate['conversion_candidate']} 为唯一未命中且可转换候选；"
                "转换不计入数值概率，待 +6 精确复核"
            )
        else:
            reason = (
                f"{selected_candidate['category']} 当前命中 {selected_candidate['current_valid_substat_count']} 条副属性，"
                "未达到四条完整命中自动继续条件；待 +6 精确复核"
            )
    elif configured_stop_threshold is not None and upper_bound < configured_stop_threshold:
        action, route = "stop", "理论上界强负证据"
        target_category = theoretical_bound["category"] if theoretical_bound else "未命中"
        reason = f"理论上界 {upper_bound} 低于分组停止门槛 {configured_stop_threshold}，且未命中完整分类或速度保护路线"
    else:
        action, route = "review", "早期保守复核"
        target_category = theoretical_bound["category"] if theoretical_bound else (evaluation.target_profile or "未命中")
        reason = "未形成高置信度继续或强负证据；继续至 +6 后使用精确 DP 复核"
    return {
        "action": action,
        "terminal_value": terminal_value,
        "expected_final_speed": expected_speed,
        "expected_speed_rolls": expected_speed_rolls,
        "speed_set_eligible": speed_set_eligible,
        "speed_threshold_blocked_probability": round(1 - speed_threshold_probability, 4) if not speed_set_eligible else 0.0,
        "speed_potential_value": speed_potential_value,
        "target_category": target_category,
        "reason": reason,
        "basis": {
            "expected_final_reforge_score": expected_score,
            "expected_final_target_score": selected_target_score,
            "expected_final_speed": expected_speed,
            "expected_speed_rolls": expected_speed_rolls,
            "remaining_hits": remaining_hits,
            "speed_threshold_probability": round(speed_threshold_probability, 4),
            "speed_potential_value": speed_potential_value,
            "formal_cross_tier_probability": round(float(metrics["formal_cross_tier_probability"]), 4),
            "valid_substat_count": evaluation.valid_profile_count,
            "classification": "高置信度继续" if action == "continue" else "待 +6 精确复核" if action == "review" else "停止",
            "candidate_evaluations": candidates,
            "selected_candidate": selected_candidate,
            "candidate_selection_reason": candidate_selection_reason,
            "full_category_matches": full_matches,
            "full_category_diagnostics": category_diagnostics,
            "selected_full_category": selected_full_category,
            "route": route,
            "speed_protection_eligible": speed_protection_eligible,
            "speed_high_value_route": speed_high_value_route,
            "calibration_group": selected_group,
            "calibration_thresholds": rule,
            "calibration_metrics": metrics,
            "theoretical_lower_bound": lower_bound,
            "theoretical_upper_bound": upper_bound,
            "theoretical_bound_category": theoretical_bound["category"] if theoretical_bound else None,
            "calibration_stop_threshold": configured_stop_threshold,
            "decision_reason": reason,
        },
    }


def _candidate_selection_reason(selected: dict | None, candidates: list[dict]) -> str:
    if selected is None:
        return "没有满足体系、部位和三条有效副属性条件的正式候选"
    same_layer = [item for item in candidates if item["priority_layer"] == selected["priority_layer"]]
    probability_order = "、".join(
        f"{item['category']}（{item['terminal_reach_probability']:.4f}）"
        for item in same_layer
    )
    reason = f"{selected['priority_layer']}候选按终局达标概率排序：{probability_order}"
    if selected["priority_layer"] == "高优先级" and any(item["priority_layer"] == "低优先级" for item in candidates):
        reason += "；低优先级候选不能覆盖合格高优先级候选"
    return reason


def policies_by_name(item_source: str, rank: str) -> dict:
    from .calibration import candidate_policies

    return {policy.name: policy for policy in candidate_policies(include_dp_assist=True, item_source=item_source, rank=rank)}


def summary_to_continue(summary: dict) -> bool:
    return summary.get("recommendation") in {"continue", "cautious_continue", "keep"}


def summary_from_strategy_decision(summary: dict, should_continue: bool, checkpoint: int, debug: dict) -> dict:
    if should_continue:
        recommendation = "continue"
        reason = "终局路线期望效用为正，建议继续"
    else:
        recommendation = "stop"
        reason = "终局路线期望效用不足，建议停止"
    reasons = [reason]
    if debug.get("dp_expected_terminal_value") is not None:
        reasons.append(f"预计终局价值 {debug['dp_expected_terminal_value']}")
    if debug.get("dp_expected_formal_baili_score") is not None:
        reasons.append(f"预计正式百里收益 {debug['dp_expected_formal_baili_score']}")
    target = debug.get("dp_best_target_category") or summary.get("target_profile") or ""
    return build_summary(recommendation, next_checkpoint(checkpoint), target, reasons)


def strategy_debug(strategy: StrategyDefault, enable_dp_assist: bool | None) -> dict:
    return {
        "item_source": strategy.item_source,
        "rank": strategy.rank,
        "gear_source": strategy.gear_source,
        "policy_name": strategy.policy_name,
        "enable_dp_assist": strategy.enable_dp_assist if enable_dp_assist is None else bool(enable_dp_assist),
        "configured_enable_dp_assist": strategy.enable_dp_assist,
    }


def analyze_roll_hits(gear: Gear, evaluation: Evaluation) -> list[dict]:
    valid_keys = set(evaluation.valid_profile_keys)
    result = []
    for hit in gear.roll_history:
        key = hit.key
        result.append(
            {
                "enhance": hit.enhance,
                "stat": STAT_KEY_LABELS.get(key, key),
                "value": hit.value,
                "valid": key in valid_keys,
            }
        )
    if gear.roll_history:
        return result
    for stat in gear.substats:
        inferred_hits = max(0, stat.rolls - 1)
        if inferred_hits:
            result.append(
                {
                    "enhance": None,
                    "stat": STAT_KEY_LABELS.get(stat.key, stat.key),
                    "value": None,
                    "valid": stat.key in valid_keys,
                    "inferred": True,
                    "hit_count": inferred_hits,
                }
            )
    return result


def summarize_recommendation(evaluation: Evaluation, roll_analysis: list[dict]) -> dict:
    gear = evaluation.gear
    enhance = nearest_checkpoint(gear.enhance)
    valid_count = len(evaluation.valid_substats)
    speed = speed_value(gear)
    bad_recent_hit = bool(roll_analysis and roll_analysis[-1]["valid"] is False)
    target = evaluation.target_profile
    reasons: list[str] = []

    if gear.enhance >= 15:
        if evaluation.rating_level >= 5 and evaluation.retention.rule_matched:
            recommendation = "keep"
            reasons.append(f"{evaluation.rating_label}，已命中 {target}")
        elif evaluation.effective_score > 0:
            recommendation = "convert"
            reasons.append("已满强化但未稳定进入保留体系，可考虑转换或当过渡装")
        else:
            recommendation = "stop"
            reasons.append("已满强化且未命中有效体系")
        return build_summary(recommendation, None, target, reasons)

    next_check = next_checkpoint(enhance)

    if enhance in (0, 3, 6, 9, 12):
        return build_summary("uncertain", next_check, target, ["早期强化节点由终局路线价值评估"])

    return build_summary("uncertain", next_check, target, ["非标准强化节点，建议先强化到下一个检查点后复算"])


def summarize_plus_12(evaluation: Evaluation, roll_analysis: list[dict], speed: float) -> dict:
    target = evaluation.target_profile
    valid_count = len(evaluation.valid_substats)
    invalid_hits = [hit for hit in roll_analysis if not hit["valid"]]

    if speed >= 22 and target in {"一速", "速度套纯速度", "非速度套速度装"}:
        return build_summary("continue", 15, target, [f"+12 速度 {speed:g}，仍是速度目标", "继续到 +15 前仍建议人工确认资源"])

    if not evaluation.retention.rule_matched and evaluation.effective_score >= 55 and valid_count >= 3:
        return build_summary("cautious_continue", 15, target, ["有效分能保留但未达百里硬门槛", "+12 后不要默认冲 +15"])

    if not evaluation.retention.rule_matched or evaluation.effective_score < 55:
        reasons = ["+12 后未稳定命中保留体系"]
        if evaluation.effective_score:
            reasons.append(f"有效分 {evaluation.effective_score} 偏低")
        return build_summary("stop", 15, target, reasons)

    if invalid_hits and len(invalid_hits) >= max(1, len(roll_analysis) // 2):
        return build_summary("stop", 15, target, ["强化命中方向偏离目标体系", "+12 是强制止损节点"])

    if evaluation.rating_level >= 6 and valid_count >= 3:
        return build_summary("continue", 15, target, [f"{evaluation.rating_label}，仍命中 {target}", "+15 前确认资源"])

    return build_summary("cautious_continue", 15, target, ["只剩理论期待，建议谨慎继续", "+12 后不要默认冲 +15"])


def build_summary(recommendation: str, next_check_at: int | None, target_profile: str, reasons: list[str]) -> dict:
    return {
        "recommendation": recommendation,
        "next_check_at": next_check_at,
        "target_profile": target_profile,
        "reasons": reasons[:3],
    }


def nearest_checkpoint(enhance: int) -> int:
    for point in reversed(CHECKPOINTS):
        if enhance >= point:
            return point
    return 0


def next_checkpoint(enhance: int) -> int | None:
    for point in CHECKPOINTS:
        if point > enhance:
            return point
    return None
