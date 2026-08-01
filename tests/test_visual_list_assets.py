from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.visual_list_assets import (
    ListFieldMapping,
    ListPageAssetError,
    build_audited_card_template_reader,
    load_card_fingerprint_templates,
    load_list_field_mapping,
    normalize_list_field_token,
)


class VisualListAssetsTest(unittest.TestCase):
    def test_repository_manifests_fail_closed_until_missing_assets_are_audited(self):
        with self.assertRaises(ListPageAssetError):
            load_list_field_mapping()
        with self.assertRaises(ListPageAssetError):
            load_card_fingerprint_templates()
        with self.assertRaises(ListPageAssetError):
            build_audited_card_template_reader()

    def test_complete_fixture_manifest_verifies_hash_and_exact_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"complete-card-fixture"
            digest = hashlib.sha256(payload).hexdigest()
            (root / "card.png").write_bytes(payload)
            (root / "card_fingerprint_manifest.json").write_text(json.dumps({
                "schema_version": 1,
                "asset_kind": "equipment_list_card_fingerprint",
                "status": "audited_complete",
                "template_scope": "full_card",
                "templates": [{
                    "id": "weapon_card",
                    "file": "card.png",
                    "sha256": digest,
                    "viewport": [170, 120],
                    "threshold": 0.98,
                    "status": "audited",
                }],
            }), encoding="utf-8")
            templates = load_card_fingerprint_templates(root / "card_fingerprint_manifest.json")
            self.assertEqual(tuple(templates), ("weapon_card",))

    def test_pending_mapping_entry_is_rejected_even_with_high_confidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "asset_kind": "equipment_list_field_mapping",
                "status": "audited_complete",
                "mappings": [{
                    "field": "substats",
                    "token": "攻击%",
                    "normalized": "AttackPercent",
                    "confidence": 0.99,
                    "source": "reference_only",
                    "status": "pending",
                }],
            }), encoding="utf-8")
            with self.assertRaises(ListPageAssetError):
                load_list_field_mapping(path)

    def test_complete_mapping_must_cover_every_list_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "asset_kind": "equipment_list_field_mapping",
                "status": "audited_complete",
                "mappings": [{
                    "field": "slot",
                    "token": "武器",
                    "normalized": "Weapon",
                    "confidence": 0.99,
                    "source": "audited_fixture",
                    "status": "audited",
                }],
            }), encoding="utf-8")
            with self.assertRaises(ListPageAssetError):
                load_list_field_mapping(path)

    def test_normalizer_rejects_unknown_token_and_accepts_audited_entry(self):
        mapping = {("slot", "武器"): ListFieldMapping("slot", "武器", "Weapon", 0.99, "fixture")}
        self.assertEqual(normalize_list_field_token(mapping, "slot", "武器"), "Weapon")
        with self.assertRaises(ListPageAssetError):
            normalize_list_field_token(mapping, "slot", "剑")


if __name__ == "__main__":
    unittest.main()
