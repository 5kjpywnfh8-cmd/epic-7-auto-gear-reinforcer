from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .enhance_policy import advise_gear
from .models import Gear, validate_gear_source_rank, validate_gear_structure
from .rules import SET_CODE_TO_NAME
from .strategy_defaults import DEFAULT_GEAR_SOURCE


DEFAULT_SUBSTATS = [
    {"type": "Speed", "value": 0, "rolls": 0},
    {"type": "CriticalHitChancePercent", "value": 0, "rolls": 0},
    {"type": "CriticalHitDamagePercent", "value": 0, "rolls": 0},
    {"type": "AttackPercent", "value": 0, "rolls": 0},
]

DEFAULT_GEAR_FORM: dict[str, Any] = {
    "set": "Speed",
    "slot": "Weapon",
    "main_type": "Attack",
    "main_value": 525,
    "enhance": 0,
    "level": 85,
    "rank": "Epic",
    "substats": DEFAULT_SUBSTATS,
    "rollHistory": [],
    "code": "",
    "instance_id": "",
    "item_source": "normal_85",
    "gear_source": DEFAULT_GEAR_SOURCE,
    "enable_dp_assist": None,
}

FRIBBELS_SET_TO_FORM_VALUE = {
    "AttackSet": "Attack",
    "CounterSet": "Counter",
    "CriticalSet": "Critical",
    "DestructionSet": "Destruction",
    "HealthSet": "Health",
    "HitSet": "Hit",
    "ImmunitySet": "Immunity",
    "ProtectionSet": "Protection",
    "ResistSet": "Resist",
    "ReversalSet": "ReversalSet",
    "RiposteSet": "Riposte",
    "SpeedSet": "Speed",
    "TorrentSet": "Torrent",
    "UnitySet": "UnitySet",
    "set_chase": "Chase",
    "set_opener": "Opener",
}

FRIBBELS_SLOT_TO_FORM_VALUE = {
    "Weapon": "Weapon",
    "Helmet": "Helmet",
    "Armor": "Armor",
    "Necklace": "Necklace",
    "Ring": "Ring",
    "Boots": "Boots",
}

RECOMMENDATION_LABELS = {
    "stop": "停止",
    "continue": "继续",
    "cautious_continue": "谨慎继续",
    "keep": "保留",
    "convert": "转换/过渡",
    "uncertain": "不确定",
}

DEBUG_FIELD_LABELS = {
    "official_score": "官方分",
    "effective_score": "有效分",
    "strategy_version": "策略版本",
    "strategy_name": "策略名称",
    "enable_dp_assist": "启用 DP 辅助",
    "baseline_recommendation": "基础建议",
    "decision_mode": "决策模式",
    "dp_decision": "DP 决策",
    "lightweight_decision": "轻量预测决策",
    "dp_utility": "DP 效用",
    "dp_continue_utility": "继续效用",
    "dp_expected_terminal_value": "终局期望价值",
    "dp_expected_final_speed": "终局预期速度",
    "dp_expected_speed_rolls": "终局预期速度跳数",
    "dp_speed_potential_set_eligible": "速度潜力套装资格",
    "dp_speed_potential_threshold_blocked_probability": "速度潜力 20 门槛拦截率",
    "dp_expected_speed_potential_value": "终局速度潜力价值",
    "dp_best_target_category": "终局目标类别",
    "dp_best_source_row": "终局来源规则",
    "dp_override_applied": "DP 是否覆盖基础建议",
    "heroic_speed22_rescue": "紫装中后期22速M1救回",
    "heroic_speed22_checkpoint": "当前节点",
    "heroic_speed22_p22": "精确P22（终局22速以上概率）",
    "heroic_speed22_baseline_action": "基础动作",
    "heroic_speed22_rescued": "是否M1救回",
    "heroic_speed22_reason": "救回原因",
    "heroic_speed22_scope": "适用范围",
    "epic_early_stop": "Epic 非速度 +0/+3 均衡止损",
    "lightweight_basis": "轻量预测依据",
    "lightweight_route": "轻量预测路线",
    "lightweight_full_categories": "完整命中分类",
    "lightweight_full_category_diagnostics": "完整分类诊断",
    "lightweight_selected_category": "选择分类",
    "lightweight_calibration_group": "校准分组",
    "lightweight_calibration_thresholds": "校准门槛",
    "lightweight_theoretical_lower_bound": "理论下界",
    "lightweight_theoretical_upper_bound": "理论上界",
    "lightweight_decision_reason": "轻量预测决策依据",
    "baili_score": "百里分",
    "target_score": "目标分",
    "rating_level": "当前静态评分等级",
    "rating_semantics": "评分语义",
    "fit_status": "命中状态",
    "valid_substats": "有效副属性",
    "invalid_substats": "无效副属性",
    "roll_hit_analysis": "强化命中分析",
    "resource_calibration_status": "资源校准状态",
    "resource_calibration_cost": "资源校准体力/百里分",
    "resource_calibration_lambda": "资源校准 lambda",
    "resource_calibration_message": "资源校准说明",
    "resource_material": "强化材料与来源记账",
    "set": "套装",
    "slot": "部位",
    "mainStat": "主属性",
    "type": "属性",
    "value": "数值",
    "enhance": "强化等级",
    "level": "装备等级",
    "rank": "品质",
    "substats": "副属性",
    "rolls": "强化次数",
    "rollHistory": "强化记录",
    "code": "装备编号",
    "instanceId": "装备实例编号",
    "reforgeEligible": "默认可重铸",
    "itemSource": "装备来源",
    "gearSource": "装备来源规则",
    "category": "分类",
    "set_group": "套装组",
    "source_row": "来源规则",
    "full_matched": "完整命中",
    "set_matched": "套装命中",
    "main_matched": "主属性命中",
    "special_matched": "特殊条件命中",
    "substats_matched": "副属性命中",
    "substat_diagnostics": "副属性诊断",
    "valid_keys": "有效副属性",
    "decision_reason": "决策依据",
    "calibration_group": "校准分组",
    "calibration_thresholds": "校准门槛",
    "full_category_matches": "完整命中分类",
    "full_category_diagnostics": "完整分类诊断",
    "priority": "优先级",
    "has_valid_substat": "存在有效副属性",
    "category_gate_matched": "分类条件命中",
    "required_any_matched": "必需属性命中",
    "mutual_exclusion_matched": "互斥条件命中",
    "stat": "副属性",
    "key": "属性编号",
    "matched": "命中",
    "valid": "有效",
    "inferred": "推定强化",
    "hit_count": "命中次数",
}

DISPLAY_VALUE_LABELS = {
    "normal_85": "普通 85",
    "rift_85": "异界 85（仅红装）",
    "Epic": "红装",
    "Heroic": "紫装",
    "Rare": "蓝装",
    "lightweight_prediction": "轻量预测",
    "exact_dp": "精确 DP",
    "lightweight_continue": "继续",
    "lightweight_review": "待 +6 精确复核",
    "lightweight_stop": "停止",
    "formal_category": "正式体系",
    "future_75_fallback": "未来可期 75+ 后备",
    "continue": "继续",
    "stop": "停止",
    "cautious_continue": "谨慎继续",
    "keep": "保留",
    "convert": "转换/过渡",
    "uncertain": "不确定",
    "normal_epic_dp_assisted": "普通 85 红装 DP 策略",
    "normal_heroic_dp_assisted": "普通 85 紫装 DP 策略",
    "rift_epic_dp_assisted": "异界 85 红装 DP 策略",
    "baili-formal-dp-v1": "百里正式 DP v1",
    "baili-formal-dp-v1-epic-balanced": "百里正式 DP v1（Epic 均衡止损）",
    "current_static": "当前静态评分",
    "weapon": "武器",
    "Weapon": "武器",
    "helmet": "头盔",
    "helm": "头盔",
    "Helmet": "头盔",
    "armor": "衣服",
    "Armor": "衣服",
    "necklace": "项链",
    "neck": "项链",
    "Necklace": "项链",
    "ring": "戒指",
    "Ring": "戒指",
    "boot": "鞋子",
    "Boots": "鞋子",
    "left_fixed": "左三固定主属性",
    "right": "右三主属性",
    "output": "输出套装组",
    "critless": "必爆输出套装组",
    "tankRes": "抗性坦克套装组",
    "pureTank": "纯肉套装组",
    "hitTank": "命中坦克套装组",
    "dual": "双效套装组",
    "bruiserHpDef": "血防半肉套装组",
    "bruiser": "通用半肉套装组",
    "bruiserFlat": "白字半肉套装组",
    "atkFlat": "攻击",
    "atkPct": "攻击%",
    "defFlat": "防御",
    "defPct": "防御%",
    "hpFlat": "生命",
    "hpPct": "生命%",
    "spd": "速度",
    "crit": "暴击率",
    "cdmg": "暴击伤害",
    "eff": "效果命中",
    "res": "效果抗性",
    "Speed": "速度",
    "Critical": "暴击",
    "Destruction": "暴伤",
    "Attack": "攻击",
    "Defense": "防御",
    "Health": "生命",
    "Immunity": "免疫",
    "Counter": "反击",
    "Lifesteal": "吸血",
    "Penetration": "穿透",
    "Torrent": "激流",
    "Resist": "抵抗",
    "Hit": "命中",
    "Injury": "伤口",
    "Protection": "保护",
    "Riposte": "回击",
    "Opener": "先手",
    "Chase": "追击",
    "ReversalSet": "逆袭",
    "set_revenant": "逆袭",
    "UnitySet": "夹攻",
    "AttackPercent": "攻击%",
    "DefensePercent": "防御%",
    "HealthPercent": "生命%",
    "CriticalHitChancePercent": "暴击率%",
    "CriticalHitDamagePercent": "暴击伤害%",
    "EffectivenessPercent": "效果命中%",
    "EffectResistancePercent": "效果抗性%",
    "rift_new_1_32": "异界新版本来源规则 1.32",
}
DISPLAY_VALUE_LABELS.update(SET_CODE_TO_NAME)


def load_gear_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"), strict=False)
    if not isinstance(data, dict):
        raise ValueError("gear JSON must be an object")
    gear_data = data.get("gear") if isinstance(data.get("gear"), dict) else data
    strategy = ((data.get("suggestion") or {}).get("debug") or {}).get("default_strategy") or {}
    item_source = data.get("item_source") or data.get("itemSource") or strategy.get("item_source") or gear_data.get("item_source") or gear_data.get("itemSource") or "normal_85"
    form = form_from_gear_dict(gear_data, item_source=str(item_source))
    form["item_source"] = str(item_source)
    form["gear_source"] = data.get("gear_source") or data.get("gearSource") or strategy.get("gear_source") or form["gear_source"]
    return form


def load_gear_collection(path: Path) -> list[dict[str, Any]]:
    forms, _ = load_gear_collection_with_report(path)
    return forms


def load_gear_collection_with_report(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if is_fribbels_export(data):
        return _load_fribbels_collection(data)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("items") or data.get("gears") or data.get("equipment")
        if items is None:
            items = [data]
    else:
        raise ValueError("gear collection JSON must be an object or array")
    if not isinstance(items, list):
        raise ValueError("gear collection must contain an items/gears list")
    forms = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_source = item.get("item_source") or item.get("itemSource") or "normal_85"
        form = form_from_gear_dict(item, item_source=str(item_source))
        form["item_source"] = str(item_source)
        form["gear_source"] = item.get("gear_source") or item.get("gearSource") or form.get("gear_source") or DEFAULT_GEAR_SOURCE
        forms.append(form)
    if not forms:
        raise ValueError("gear collection contains no valid gear objects")
    skipped_items = len(items) - len(forms)
    report = {
        "source_format": "native",
        "total_items": len(items),
        "loaded_items": len(forms),
        "skipped_items": skipped_items,
        "skipped_by_reason": {"非装备对象": skipped_items} if skipped_items else {},
    }
    return forms, report


def is_fribbels_export(data: Any) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return False
    items = data["items"]
    has_export_metadata = "export_time" in data and ("item_count" in data or "heroes" in data)
    has_fribbels_item = any(
        isinstance(item, dict) and "gear" in item and "main" in item and "raw" in item
        for item in items
    )
    return has_export_metadata and (not items or has_fribbels_item)


def _load_fribbels_collection(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items = data.get("items") or []
    forms: list[dict[str, Any]] = []
    skipped_by_reason: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1

    for item in items:
        if not isinstance(item, dict):
            skip("非装备对象")
            continue
        if int(as_number(item.get("enhance"), -1)) not in {0, 3}:
            skip("强化等级不是+0/+3")
            continue
        if int(as_number(item.get("level"), 0)) != 85:
            skip("装备等级不是85级")
            continue
        if str(item.get("rank") or "") not in {"Epic", "Heroic"}:
            skip("品质不是红装/紫装")
            continue
        try:
            form = form_from_gear_dict(_fribbels_item_to_gear_dict(item), item_source="normal_85")
        except ValueError:
            skip("装备字段不符合当前规则")
            continue
        form["item_source"] = "normal_85"
        form["gear_source"] = DEFAULT_GEAR_SOURCE
        forms.append(form)

    if not forms:
        raise ValueError("Fribbels 导出中没有可导入的85级 +0/+3 红装或紫装。")

    return forms, {
        "source_format": "fribbels",
        "total_items": len(items),
        "loaded_items": len(forms),
        "skipped_items": sum(skipped_by_reason.values()),
        "skipped_by_reason": skipped_by_reason,
    }


def _fribbels_item_to_gear_dict(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    raw_set = str(item.get("set") or raw.get("f") or "")
    raw_slot = str(item.get("gear") or raw.get("type") or "")
    return {
        "set": FRIBBELS_SET_TO_FORM_VALUE.get(raw_set, raw_set),
        "slot": FRIBBELS_SLOT_TO_FORM_VALUE.get(raw_slot, raw_slot),
        "mainStat": item.get("main") or {},
        "enhance": item.get("enhance", 0),
        "level": item.get("level", 85),
        "rank": item.get("rank", "Epic"),
        "substats": list(item.get("substats") or []),
        "rollHistory": list(item.get("rollHistory") or []),
        "code": str(item.get("code") or raw.get("code") or item.get("id") or ""),
        "instanceId": str(item.get("ingameId") or item.get("id") or "").strip(),
        "reforgeEligible": True,
    }


def form_from_gear_dict(data: dict[str, Any], item_source: str = "normal_85") -> dict[str, Any]:
    gear = Gear.from_dict(data)
    validate_gear_structure(gear)
    validate_gear_source_rank(gear, item_source)
    form = deepcopy(DEFAULT_GEAR_FORM)
    main = data.get("mainStat") or data.get("main") or {}
    form.update(
        {
            "set": data.get("set") or gear.set,
            "slot": data.get("slot") or gear.slot,
            "main_type": main.get("type") if isinstance(main, dict) else gear.main_stat.type,
            "main_value": main.get("value") if isinstance(main, dict) else gear.main_stat.value,
            "enhance": gear.enhance,
            "level": gear.level,
            "rank": gear.rank,
            "substats": [stat_to_form(item) for item in data.get("substats", [])],
            "rollHistory": data.get("rollHistory", []),
            "code": data.get("code", ""),
            "instance_id": str(data.get("instanceId") or data.get("instance_id") or "").strip(),
            "reforge_eligible": gear.level == 85,
        }
    )
    while len(form["substats"]) < 4:
        form["substats"].append({"type": "", "value": 0, "rolls": 0})
    form["substats"] = form["substats"][:4]
    return form


def stat_to_form(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": str(data.get("type") or data.get("key") or ""),
        "value": as_number(data.get("value"), 0),
        "rolls": int(as_number(data.get("rolls"), 0)),
    }


def build_gear_dict(form: dict[str, Any]) -> dict[str, Any]:
    substats = []
    for item in form.get("substats", []):
        stat_type = str(item.get("type") or "").strip()
        if not stat_type:
            continue
        substats.append(
            {
                "type": stat_type,
                "value": as_number(item.get("value"), 0),
                "rolls": int(as_number(item.get("rolls"), 0)),
            }
        )
    return {
        "set": str(form.get("set") or ""),
        "slot": str(form.get("slot") or ""),
        "mainStat": {
            "type": str(form.get("main_type") or ""),
            "value": as_number(form.get("main_value"), 0),
        },
        "enhance": int(as_number(form.get("enhance"), 0)),
        "level": int(as_number(form.get("level"), 85)),
        "rank": str(form.get("rank") or "Epic"),
        "substats": substats,
        "rollHistory": list(form.get("rollHistory") or []),
        "code": str(form.get("code") or ""),
        "instanceId": str(form.get("instance_id") or "").strip(),
        "reforgeEligible": int(as_number(form.get("level"), 85)) == 85,
        "itemSource": str(form.get("item_source") or "normal_85"),
        "gearSource": str(form.get("gear_source") or DEFAULT_GEAR_SOURCE),
    }


def suggest_from_form(form: dict[str, Any]) -> dict[str, Any]:
    gear = Gear.from_dict(build_gear_dict(form))
    return advise_gear(
        gear,
        item_source=str(form.get("item_source") or "normal_85"),
        gear_source=str(form.get("gear_source") or DEFAULT_GEAR_SOURCE),
        enable_dp_assist=form.get("enable_dp_assist"),
    )


def summary_view_model(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("summary") or {}
    recommendation = summary.get("recommendation") or "uncertain"
    return {
        "recommendation": recommendation,
        "recommendation_label": RECOMMENDATION_LABELS.get(recommendation, recommendation),
        "next_check_at": summary.get("next_check_at"),
        "target_profile": summary.get("target_profile") or "-",
        "reasons": list(summary.get("reasons") or []),
    }


def debug_view_model(result: dict[str, Any]) -> dict[str, Any]:
    debug = result.get("debug") or {}
    strategy = debug.get("default_strategy") or {}
    dp = debug.get("dp_assist") or {}
    decision_mode = dp.get("decision_mode")
    decision_mode_label = {
        "lightweight_prediction": "轻量预测（+0/+3）：+0/+3 使用单件轻量预测；+6 后按实际强化分支进行精确 DP。",
        "exact_dp": "精确 DP（+6/+9/+12）",
        "heroic_speed22_rescue": "紫装中后期22速M1救回（基础百里边际低档策略）",
    }.get(decision_mode, decision_mode)
    lightweight = dp.get("lightweight_basis") or {}
    exact_dp_ran = decision_mode == "exact_dp"
    next_check_at = (result.get("summary") or {}).get("next_check_at")
    lightweight_decision = {
        "lightweight_continue": "轻量预测：继续",
        "lightweight_review": f"轻量预测：待 +{next_check_at} 复核" if next_check_at is not None else "轻量预测：待下一节点复核",
        "lightweight_stop": "轻量预测：停止",
    }.get(dp.get("dp_decision")) if decision_mode == "lightweight_prediction" else None
    lightweight_group = lightweight.get("calibration_group") or {}
    raw_thresholds = lightweight.get("calibration_thresholds") or {}
    raw_continue = raw_thresholds.get("continue") or {}
    raw_stop = raw_thresholds.get("stop") or {}
    threshold_view = {
        "样本支持": raw_thresholds.get("support"),
        "继续门槛": {
            "预期终局重铸有效分下限": raw_continue.get("expected_final_reforge_score_min"),
            "预期终局目标分下限": raw_continue.get("expected_final_target_score_min"),
            "当前有效分下限": raw_continue.get("current_effective_score_min"),
            "剩余强化次数下限": raw_continue.get("remaining_hits_min"),
            "正式分类跨档概率下限": raw_continue.get("formal_cross_tier_probability_min"),
            "终局预期速度下限": raw_continue.get("expected_final_speed_min"),
            "速度跳数下限": raw_continue.get("speed_rolls_min"),
            "速度潜力价值下限": raw_continue.get("speed_potential_value_min"),
            "要求速度潜力套装资格": raw_continue.get("speed_potential_set_eligible"),
        } if raw_continue else None,
        "停止门槛": {"理论上界必须低于": raw_stop.get("theoretical_upper_bound_lt")} if raw_stop else None,
    } if raw_thresholds else None
    candidate_views = [
        {
            "体系": item.get("category"),
            "优先级层": item.get("priority_layer"),
            "当前命中副属性": item.get("matched_substats"),
            "当前未命中副属性": item.get("unmatched_substats"),
            "当前有效副属性数": item.get("current_valid_substat_count"),
            "部位可行有效副属性数": item.get("feasible_valid_substat_count"),
            "部位最大合法有效副属性数": item.get("max_legal_valid_substat_count"),
            "三条合法属性部位路径": item.get("slot_limited_three_valid_path"),
            "终局低档 GS 门槛": item.get("formal_terminal_gs_threshold"),
            "当前重铸前有效 GS（按候选体系）": item.get("current_pre_reforge_gs"),
            "当前重铸后有效 GS（按候选体系）": item.get("current_reforged_gs"),
            "当前重铸后 GS": item.get("current_reforged_gs"),
            "终局预期有效 GS（未转换）": item.get("expected_final_gs_native"),
            "终局预期有效 GS（按转换满值）": item.get("expected_final_gs_after_max_conversion") if item.get("expected_final_gs_after_max_conversion") is not None else "不适用",
            "终局预期 GS": item.get("expected_final_gs"),
            "理论下界": item.get("theoretical_lower_bound"),
            "理论上界": item.get("theoretical_upper_bound"),
            "未转换正式体系低档达标概率": item.get("terminal_reach_probability_native"),
            "正式体系低档达标概率": item.get("terminal_reach_probability"),
            "转换候选": item.get("is_conversion_candidate"),
            "待转换副属性": item.get("conversion_candidate"),
            "转换目标副属性": item.get("conversion_target_stat"),
            "转换满值": item.get("conversion_max_value") if item.get("conversion_max_value") is not None else "不适用",
            "转换满值 GS 增益": item.get("conversion_max_gs_gain") if item.get("is_conversion_candidate") else "不适用",
            "转换满值来源": item.get("conversion_max_value_source") or "不适用",
            "待转换副属性终局强化次数分布": item.get("conversion_terminal_roll_distribution") or "不适用",
            "是否合格候选": item.get("qualified"),
            "拒绝原因": item.get("rejection_reasons"),
        }
        for item in lightweight.get("candidate_evaluations", [])
    ]
    future_75_view = {
        "终局全部副属性预期 GS（未转换）": lightweight.get("expected_final_total_substat_gs_native"),
        "终局 75+ 未来可期门槛": lightweight.get("future_75_gs_threshold"),
        "未转换终局 75+ 未来可期概率": lightweight.get("terminal_future_75_probability_native"),
        "终局全部副属性预期 GS（按转换满值）": lightweight.get("expected_final_total_substat_gs_after_max_conversion") if lightweight.get("expected_final_total_substat_gs_after_max_conversion") is not None else "不适用",
        "满值转换后终局 75+ 未来可期概率": lightweight.get("terminal_future_75_probability_after_max_conversion") if lightweight.get("terminal_future_75_probability_after_max_conversion") is not None else "不适用",
        "当前终局 75+ 未来可期概率": lightweight.get("terminal_future_75_probability"),
        "当前终局目标": DISPLAY_VALUE_LABELS.get(lightweight.get("terminal_goal_type"), lightweight.get("terminal_goal_type")),
        "当前终局目标概率": lightweight.get("terminal_goal_probability"),
    }
    early_speed_gamble = lightweight.get("early_speed_gamble") or {}
    rescue = dp.get("heroic_speed22_rescue") or {}
    rescue_view = {
        "当前节点": rescue.get("checkpoint"),
        "精确P22": rescue.get("p22"),
        "基础动作": rescue.get("baseline_action"),
        "是否救回": rescue.get("rescued"),
        "救回原因": rescue.get("reason"),
        "适用范围": rescue.get("scope"),
    } if rescue else None
    epic_stop = dp.get("epic_early_stop") or {}
    epic_stop_features = epic_stop.get("features") or {}
    epic_stop_checks = epic_stop.get("checks") or {}
    epic_stop_view = {
        "候选": epic_stop.get("candidate_key"),
        "规则版本": epic_stop.get("rule_version"),
        "是否适用": epic_stop.get("eligible"),
        "适用范围": epic_stop.get("scope_reason"),
        "当前节点": epic_stop.get("checkpoint"),
        "体系": epic_stop.get("category"),
        "体系组": epic_stop.get("system_group"),
        "GS 止损门槛": epic_stop.get("threshold"),
        "终局概率上限": epic_stop.get("terminal_probability_max"),
        "当前有效 GS": epic_stop_features.get("effective_gs"),
        "当前有效词条数": epic_stop_features.get("current_valid"),
        "终局达标概率": epic_stop_features.get("probability"),
        "满值转换价值": epic_stop_features.get("conversion_value"),
        "满值转换 GS 增益（正式判定量）": epic_stop_features.get("conversion_gs_gain"),
        "四项止损条件": epic_stop_checks or None,
        "原正式二元动作": epic_stop.get("baseline_action"),
        "最终二元动作": epic_stop.get("final_action"),
        "是否新增止损": epic_stop.get("added_stop"),
        "原因": epic_stop.get("reason"),
    } if epic_stop else None
    early_speed_gamble_view = {
        "路线资格": early_speed_gamble.get("eligible"),
        "是否进入速度路线": early_speed_gamble.get("continue_route"),
        "部位资格": early_speed_gamble.get("slot_eligible"),
        "品质初始速度阈值": early_speed_gamble.get("rank_threshold"),
        "Epic 硬门槛": early_speed_gamble.get("rank_threshold") if early_speed_gamble.get("rank") == "Epic" else "不适用",
        "当前速度": early_speed_gamble.get("current_speed"),
        "速度跳数": early_speed_gamble.get("speed_rolls"),
        "+3 是否命中速度": early_speed_gamble.get("plus3_hit_speed"),
        "未命中后普通策略结果": RECOMMENDATION_LABELS.get(
            early_speed_gamble.get("fallback_recommendation", ""),
            "不适用",
        ),
        "未命中后普通策略路线": early_speed_gamble.get("fallback_route") or "不适用",
        "路线结束原因": early_speed_gamble.get("route_end_reason"),
        "下一检查点": early_speed_gamble.get("next_check_at"),
    } if early_speed_gamble else None
    lightweight_basis_view = {
        "命中的完整分类": [item.get("category") for item in lightweight.get("full_category_matches", [])],
        "选择分类": lightweight.get("selected_full_category"),
        "决策路线": lightweight.get("route"),
        "校准分组": {
            "来源": lightweight_group.get("item_source"),
            "品质": lightweight_group.get("rank"),
            "部位": lightweight_group.get("slot"),
            "主属性类别": lightweight_group.get("main_stat_class"),
            "套装组": lightweight_group.get("set_group"),
            "分类": lightweight_group.get("selected_category"),
        } if lightweight_group else None,
        "校准门槛": threshold_view,
        "理论下界": lightweight.get("theoretical_lower_bound"),
        "理论上界": lightweight.get("theoretical_upper_bound"),
        "早期赌速度": early_speed_gamble_view,
        "终局 75+ 未来可期": future_75_view,
        "候选体系评估": candidate_views,
        "候选排序依据": lightweight.get("candidate_selection_reason"),
        "决策依据": lightweight.get("decision_reason"),
    } if lightweight else None
    return {
        "official_score": debug.get("official_score"),
        "effective_score": debug.get("effective_score"),
        "strategy_version": debug.get("strategy_version"),
        "strategy_name": strategy.get("policy_name"),
        "enable_dp_assist": strategy.get("enable_dp_assist"),
        "resource_calibration_status": strategy.get("resource_calibration_status"),
        "resource_calibration_cost": strategy.get("resource_calibration_cost_per_baili_score"),
        "resource_calibration_lambda": strategy.get("resource_calibration_lambda"),
        "resource_calibration_message": dp.get("resource_calibration_message"),
        "resource_material": dp.get("resource_material"),
        "baseline_recommendation": dp.get("baseline_recommendation"),
        "decision_mode": decision_mode_label,
        "dp_decision": dp.get("dp_decision") if exact_dp_ran else "未运行精确 DP",
        "lightweight_decision": lightweight_decision,
        "dp_utility": dp.get("dp_expected_utility"),
        "dp_expected_terminal_value": dp.get("dp_expected_terminal_value"),
        "dp_expected_final_speed": dp.get("dp_expected_final_speed"),
        "dp_expected_speed_rolls": dp.get("dp_expected_speed_rolls"),
        "dp_speed_potential_set_eligible": dp.get("dp_speed_potential_set_eligible"),
        "dp_speed_potential_threshold_blocked_probability": dp.get("dp_speed_potential_threshold_blocked_probability"),
        "dp_expected_speed_potential_value": dp.get("dp_expected_speed_potential_value"),
        "dp_continue_utility": dp.get("dp_continue_utility"),
        "dp_best_target_category": dp.get("dp_best_target_category"),
        "dp_best_source_row": dp.get("dp_best_source_row"),
        "dp_override_applied": dp.get("overrode_baseline"),
        "heroic_speed22_rescue": rescue_view,
        "epic_early_stop": epic_stop_view,
        "lightweight_basis": lightweight_basis_view,
        "lightweight_route": lightweight.get("route"),
        "lightweight_full_categories": [item.get("category") for item in lightweight.get("full_category_matches", [])],
        "lightweight_selected_category": lightweight.get("selected_full_category"),
        "lightweight_calibration_group": lightweight_basis_view.get("校准分组") if lightweight_basis_view else None,
        "lightweight_calibration_thresholds": threshold_view,
        "lightweight_theoretical_lower_bound": lightweight.get("theoretical_lower_bound"),
        "lightweight_theoretical_upper_bound": lightweight.get("theoretical_upper_bound"),
        "lightweight_decision_reason": lightweight.get("decision_reason"),
        "baili_score": debug.get("baili_score"),
        "target_score": debug.get("target_score"),
        "rating_level": debug.get("rating_level"),
        "rating_semantics": debug.get("rating_semantics"),
        "fit_status": debug.get("fit_status"),
        "valid_substats": debug.get("valid_substats"),
        "invalid_substats": debug.get("invalid_substats"),
        "roll_hit_analysis": debug.get("roll_hit_analysis"),
    }


def format_debug_details(result: dict[str, Any], gear_data: dict[str, Any]) -> str:
    """Render all debug data as Chinese, width-wrappable plain text for the GUI."""
    view = debug_view_model(result)
    lightweight = ((result.get("debug") or {}).get("dp_assist") or {}).get("lightweight_basis") or {}
    view["lightweight_full_category_diagnostics"] = lightweight.get("full_category_diagnostics")
    sections = [
        ("策略与评分", [
            "strategy_version", "strategy_name", "enable_dp_assist", "official_score", "effective_score",
            "baili_score", "target_score", "rating_level", "rating_semantics", "fit_status",
        ]),
        ("资源与校准", [
            "resource_calibration_status", "resource_calibration_cost", "resource_calibration_lambda",
            "resource_calibration_message", "resource_material",
        ]),
        ("决策", [
            "baseline_recommendation", "decision_mode", "dp_decision", "lightweight_decision",
            "dp_utility", "dp_continue_utility", "dp_override_applied", "dp_best_target_category",
            "dp_best_source_row",
            "heroic_speed22_rescue",
            "epic_early_stop",
        ]),
        ("终局速度与价值", [
            "dp_expected_terminal_value", "dp_expected_final_speed", "dp_expected_speed_rolls",
            "dp_speed_potential_set_eligible", "dp_speed_potential_threshold_blocked_probability",
            "dp_expected_speed_potential_value",
        ]),
        ("轻量预测", [
            "lightweight_route", "lightweight_full_categories", "lightweight_selected_category",
            "lightweight_calibration_group", "lightweight_calibration_thresholds",
            "lightweight_theoretical_lower_bound", "lightweight_theoretical_upper_bound",
            "lightweight_decision_reason", "lightweight_basis", "lightweight_full_category_diagnostics",
        ]),
        ("副属性与强化", ["valid_substats", "invalid_substats", "roll_hit_analysis"]),
    ]
    lines: list[str] = []
    for title, keys in sections:
        section_lines: list[str] = []
        for key in keys:
            value = view.get(key)
            if value is not None:
                section_lines.extend(_format_debug_entry(DEBUG_FIELD_LABELS[key], value, 0))
        if section_lines:
            lines.append(title)
            lines.extend(section_lines)
            lines.append("")
    lines.append("当前装备输入")
    lines.extend(_format_debug_mapping(gear_data, 0))
    return "\n".join(lines).rstrip()


def _format_debug_entry(label: str, value: Any, indent: int) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines = [f"{prefix}{label}："]
        lines.extend(_format_debug_mapping(value, indent + 1))
        return lines
    if isinstance(value, list):
        lines = [f"{prefix}{label}："]
        lines.extend(_format_debug_list(value, indent + 1))
        return lines
    return [f"{prefix}{label}：{_format_debug_scalar(value)}"]


def _format_debug_mapping(value: dict[str, Any], indent: int) -> list[str]:
    lines: list[str] = []
    for key, nested_value in value.items():
        key_text = str(key)
        label = DEBUG_FIELD_LABELS.get(key_text)
        if label is None:
            label = key_text if not key_text.isascii() else "附加信息"
        lines.extend(_format_debug_entry(label, nested_value, indent))
    return lines


def _format_debug_list(value: list[Any], indent: int) -> list[str]:
    prefix = "  " * indent
    lines: list[str] = []
    for item in value:
        if isinstance(item, dict):
            lines.append(f"{prefix}-")
            lines.extend(_format_debug_mapping(item, indent + 1))
        elif isinstance(item, list):
            lines.append(f"{prefix}-")
            lines.extend(_format_debug_list(item, indent + 1))
        else:
            lines.append(f"{prefix}- {_format_debug_scalar(item)}")
    return lines or [f"{prefix}- 无"]


def _format_debug_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "-"
    if isinstance(value, str):
        display = DISPLAY_VALUE_LABELS.get(value, value)
        display = re.sub(r"^R(\d+)-R(\d+)$", r"规则第 \1-\2 行", display)
        return display.replace("=True", "＝是").replace("=False", "＝否")
    return str(value)


def save_gear_file(path: Path, form: dict[str, Any]) -> None:
    gear = Gear.from_dict(build_gear_dict(form))
    validate_gear_structure(gear)
    validate_gear_source_rank(gear, str(form.get("item_source") or "normal_85"))
    payload = gear.to_dict()
    payload["instanceId"] = str(form.get("instance_id") or "").strip()
    payload["itemSource"] = str(form.get("item_source") or "normal_85")
    payload["gearSource"] = str(form.get("gear_source") or DEFAULT_GEAR_SOURCE)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_suggestion_file(path: Path, form: dict[str, Any], result: dict[str, Any]) -> None:
    payload = {
        "gear": build_gear_dict(form),
        "suggestion": result,
        "summary_view": summary_view_model(result),
        "debug_view": debug_view_model(result),
        "manual_review": {
            "工具建议": summary_view_model(result)["recommendation_label"],
            "人工判断": "",
            "是否一致": "",
            "分歧原因": "",
            "备注": "",
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def as_number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
