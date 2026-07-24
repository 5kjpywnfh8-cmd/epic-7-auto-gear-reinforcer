# 单件人工确认强化结果离线汇总

- 汇总状态：`verified`
- 操作包数量：`1`
- 证据内部一致：`1`
- fail closed：`0`
- 范围：仅离线校验操作证据，不代表正式策略、DP、评分或自动化发布结论。
- 正式策略是否修改：`false`

## 记录

### 1. batch 013 / 4182712419

- 状态：`verified`
- 装备：85级 SpeedSet Necklace，`Epic`
- 复核节点：`+0 -> +3`
- 影子建议：`{"decision": "continue", "next_check_at": 3, "target": "speed_potential"}`
- 资源闸门：`True`，消耗：`{"actual_material_delta": {"equipment_enhancement_powder": 2, "greater_equipment_charm": 0, "lesser_equipment_charm": 1}, "allowed_material_sources": ["equipment_enhancement_powder", "lesser_equipment_charm", "greater_equipment_charm"], "authorized_limits": {"equipment_enhancement_powder": 2, "gold": 17600, "greater_equipment_charm": 0, "lesser_equipment_charm": 1}, "gold": {"after": 346652575, "authorized_limit": 17600, "before": 346670175, "consumed": 17600}, "selected_materials": {"equipment_enhancement_powder": 2, "greater_equipment_charm": 0, "lesser_equipment_charm": 1}, "within_limits": true}`
- 停止原因：`review_checkpoint_plus3_reached; no further operation sent`

| 字段 | 基线 | 实际结果 |
| --- | --- | --- |
| 强化等级 | 0 | 3 |
| 主属性（生命值） | {"type": "HealthPercent", "value": 12} | {"type": "HealthPercent", "value": 19} |
| 副属性 | [{"type": "DefensePercent", "value": 8}, {"type": "Speed", "value": 3}, {"type": "EffectResistancePercent", "value": 6}, {"type": "EffectivenessPercent", "value": 6}] | [{"type": "DefensePercent", "value": 8}, {"type": "Speed", "value": 7}, {"type": "EffectResistancePercent", "value": 6}, {"type": "EffectivenessPercent", "value": 6}] |
| 游戏官方展示装备分数（仅作记录） | 30 | 41 |

- 变化字段：`[{"after": 19, "before": 12, "field": "main.value", "type": "HealthPercent"}, {"after": 7, "before": 3, "field": "substats[Speed].value", "type": "Speed"}, {"after": 41, "before": 30, "field": "gear_score"}]`
- 关键检查：`{"advice_hash_gate": true, "attribute_change_observed": true, "attribute_types_unchanged": true, "checkpoint_reached": true, "device_gate": true, "ocr_confidence_gate": true, "operation_authorization": true, "operation_status_completed": true, "page_gate": true, "pair_advice_hash_gate": true, "pair_snapshot_identity": true, "pairing_candidate_gate": true, "pairing_file_gate": true, "resource_gate": true, "schema_version": true, "shadow_checkpoint_matches": true, "single_action_gate": true, "snapshot_gate": true, "stop_reason_gate": true, "target_matches_baseline": true, "trusted_snapshot_identity": true}`
- fail-closed 原因：`[]`
