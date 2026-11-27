"""Tests for Markdown parsing and an end-to-end photo carousel render."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_carousel as renderer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PALETTE = {
    "paper": "#F6F1E6",
    "ink": "#123244",
    "accent": "#0E8178",
    "accent2": "#E9A95E",
    "muted": "#5B6B71",
    "dark": "#102C3A",
    "panel": "#FFF8EB",
    "line": "#CCD9D4",
}


class CarouselParserTests(unittest.TestCase):
    def test_hard_breaks_and_caption_are_parsed_separately(self) -> None:
        markdown = """# Carousels

## Carrusel 1 · A useful guide

**Portada, texto alternativo:** A cover with a short question.

1. **Portada**\\
   **A useful question?**\\
   One short supporting line.

2. **Cierre**\\
   Ask for one next step.

**Caption**\\
A caption that adds context.

#UsefulTag

---
"""
        decks = renderer.parse_carousels(markdown)
        self.assertEqual(len(decks), 1)
        self.assertEqual(len(decks[0]["slides"]), 2)
        self.assertEqual(decks[0]["slides"][0]["title"], "A useful question?")
        self.assertEqual(decks[0]["caption"], "A caption that adds context.\n\n#UsefulTag")
        self.assertNotIn("Caption", decks[0]["slides"][-1]["body"])
        self.assertNotIn("#UsefulTag", decks[0]["slides"][-1]["body"])

    def test_campaign_sources_have_all_nine_nonempty_captions(self) -> None:
        source_dir = ROOT / "entregables" / "presencia-al-dia"
        if not source_dir.is_dir():
            self.skipTest("Campaign sources are not present in this checkout")
        sources = sorted(source_dir.glob("0*-*/carruseles.md"))
        self.assertEqual(len(sources), 3)
        for source in sources:
            decks = renderer.parse_carousels(source.read_text(encoding="utf-8"))
            self.assertEqual([len(deck["slides"]) for deck in decks], [7, 8, 8])
            for deck in decks:
                self.assertTrue(deck["caption"].strip(), f"empty caption: {source} / {deck['title']}")
                self.assertTrue(deck["alt"].strip(), f"empty alt text: {source} / {deck['title']}")
                self.assertNotIn("Caption", deck["slides"][-1]["body"])
                self.assertNotIn("#PaginasWeb", deck["slides"][-1]["body"])

    def test_relative_asset_paths_resolve_from_brand_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            expected = (base / "assets" / "cover.jpg").resolve()
            self.assertEqual(renderer.resolve_asset_path("assets/cover.jpg", base), str(expected))

    def test_cli_renders_with_photo_relative_to_brand_json(self) -> None:
        markdown = """## Carrusel 1 · A small guide

**Portada, texto alternativo:** A cover with a useful headline.

1. **Portada**\\
   **A useful headline**\\
   One clear promise.

2. **Cierre**\\
   One useful next step.

**Caption**\\
A caption that adds context.
"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "assets").mkdir()
            Image.new("RGB", (320, 480), "#78948d").save(base / "assets" / "cover.jpg")
            source = base / "copy.md"
            source.write_text(markdown, encoding="utf-8")
            brand = {
                "name": "Test brand",
                "handle": "@testbrand",
                "palette": PALETTE,
                "photos": ["assets/cover.jpg"],
            }
            brand_path = base / "brand.json"
            brand_path.write_text(json.dumps(brand), encoding="utf-8")
            output = base / "rendered"
            argv = ["render_carousel.py", str(source), "--brand", str(brand_path), "--out", str(output)]
            with patch.object(sys, "argv", argv):
                self.assertEqual(renderer.main(), 0)
            self.assertEqual(len(list(output.glob("carrusel-*/*.jpg"))), 2)


class CarouselRenderTests(unittest.TestCase):
    def test_render_outputs_jpegs_preview_caption_and_alt_text(self) -> None:
        deck = {
            "number": 1,
            "title": "A useful guide",
            "alt": "A cover with a useful guide title.",
            "caption": "A caption with one clear next step.",
            "slides": [
                {"number": 1, "label": "Portada", "title": "A useful guide", "body": "One promise."},
                {"number": 2, "label": "The key point", "title": "The key point", "body": "One specific, readable idea."},
                {"number": 3, "label": "Cierre", "title": "Take the next step", "body": "Choose one helpful action."},
            ],
        }
        config = {
            "name": "Test brand",
            "handle": "@testbrand",
            "palette": PALETTE,
            "fonts": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_path = root / "photo.jpg"
            photo = Image.new("RGB", (640, 900), "#79958e")
            draw = ImageDraw.Draw(photo)
            draw.ellipse((130, 130, 510, 510), fill="#e9a95e")
            photo.save(photo_path, quality=90)

            rendered = renderer.render_deck(deck, 1, photo_path, config, root / "out", 90)
            deck_dir = rendered[0].parent
            self.assertEqual(len(rendered), 3)
            for path in rendered:
                with Image.open(path) as slide:
                    self.assertEqual(slide.size, (1080, 1350))
            self.assertTrue((deck_dir / "preview.pdf").is_file())
            self.assertGreater((deck_dir / "preview.pdf").stat().st_size, 1_000)
            self.assertEqual((deck_dir / "caption.txt").read_text(encoding="utf-8").strip(), deck["caption"])
            self.assertEqual((deck_dir / "alt-text.txt").read_text(encoding="utf-8").strip(), deck["alt"])


if __name__ == "__main__":
    unittest.main()
