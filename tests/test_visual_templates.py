from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from src.e7_enhance.visual_templates import VisualTemplateError, load_set_icon_templates


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "visual" / "set_icons" / "fribbels" / "manifest.json"


class VisualSetIconTemplatesTest(unittest.TestCase):
    def test_default_bundle_is_complete_and_contains_hit_template(self):
        templates = load_set_icon_templates()

        self.assertEqual(len(templates), 26)
        self.assertIn("hit", templates)
        self.assertEqual(templates["hit"].path.name, "sethit.png")
        self.assertEqual(templates["hit"].viewport, (44, 44))
        self.assertEqual(templates["hit"].byte_size, 5808)
        self.assertTrue(all(item.path.is_file() for item in templates.values()))
        self.assertTrue(all(item.source_url.startswith("https://raw.githubusercontent.com/") for item in templates.values()))

    def test_missing_icon_fails_closed_as_a_complete_bundle(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-icons-") as directory:
            temporary = Path(directory)
            bundle = temporary / "bundle"
            shutil.copytree(MANIFEST.parent, bundle)
            (bundle / "sethit.png").unlink()
            with self.assertRaises(VisualTemplateError):
                load_set_icon_templates(bundle / "manifest.json")

    def test_hash_mismatch_and_invalid_png_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-icons-") as directory:
            temporary = Path(directory)
            bundle = temporary / "bundle"
            shutil.copytree(MANIFEST.parent, bundle)
            payload = bytearray((bundle / "sethit.png").read_bytes())
            payload[-1] ^= 1
            (bundle / "sethit.png").write_bytes(payload)
            with self.assertRaises(VisualTemplateError):
                load_set_icon_templates(bundle / "manifest.json")

            shutil.copytree(MANIFEST.parent, temporary / "invalid")
            invalid_manifest = temporary / "invalid" / "manifest.json"
            data = json.loads(invalid_manifest.read_text(encoding="utf-8"))
            data["templates"][0]["filename"] = "../../outside.png"
            invalid_manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(VisualTemplateError):
                load_set_icon_templates(invalid_manifest)

    def test_source_url_is_pinned_to_manifest_commit_and_path(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-icons-") as directory:
            temporary = Path(directory)
            bundle = temporary / "bundle"
            shutil.copytree(MANIFEST.parent, bundle)
            manifest = bundle / "manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["templates"][0]["source_url"] = "https://raw.githubusercontent.com/fribbels/Fribbels-Epic-7-Optimizer/main/app/assets/setattack.png"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(VisualTemplateError):
                load_set_icon_templates(manifest)

    def test_loader_is_filesystem_only_and_does_not_require_network(self):
        templates = load_set_icon_templates(MANIFEST)

        self.assertTrue(all(item.path.parent == MANIFEST.parent for item in templates.values()))
        self.assertTrue(all(item.source_blob_sha and item.sha256 for item in templates.values()))


if __name__ == "__main__":
    unittest.main()
