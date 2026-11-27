#!/usr/bin/env python3
"""Render a Markdown carousel as photo-led, Instagram-ready JPEG slides.

Optional dependency: Pillow (pip install -r skills/ig-carousel/requirements.txt)
The source stays in Markdown; this tool handles layout and image export only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - exercised on a missing optional dependency
    raise SystemExit(
        "Carousel rendering needs Pillow. Install it with: "
        "python3 -m pip install -r skills/ig-carousel/requirements.txt"
    ) from exc

WIDTH, HEIGHT = 1080, 1350
SAFE = 84
DEFAULT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEFAULT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DEFAULT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


def clean_md(value: str) -> str:
    value = value.replace("\\\n", " ")
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip().rstrip("\\").strip()


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:55] or "carousel"


def parse_carousels(markdown: str) -> list[dict[str, Any]]:
    sections = re.split(r"(?=^## Carrusel\s+\d+)", markdown, flags=re.M)
    carousels: list[dict[str, Any]] = []
    for section in sections:
        if not section.lstrip().startswith("## Carrusel"):
            continue
        lines = section.lstrip().splitlines()
        heading = clean_md(lines[0].lstrip("# "))
        title_match = re.search(r"Carrusel\s+(\d+)\s*[·|:-]\s*(.*)", heading, re.I)
        number = int(title_match.group(1)) if title_match else len(carousels) + 1
        title = title_match.group(2).strip() if title_match else heading
        alt_match = re.search(r"^\*\*Portada, texto alternativo:\*\*\s*(.+)$", section, re.M)
        alt = clean_md(alt_match.group(1)) if alt_match else title
        caption_match = re.search(r"^\*\*Caption\*\*\\?[ \t]*\n(.*?)(?=^\s*---\s*$|\Z)", section, re.M | re.S)
        caption = caption_match.group(1).strip() if caption_match else ""
        body = section[:caption_match.start()] if caption_match else section
        slide_headers = list(re.finditer(r"^(\d+)\.\s+\*\*(.*?)\*\*\\?\s*$", body, re.M))
        slides: list[dict[str, Any]] = []
        for i, match in enumerate(slide_headers):
            end = slide_headers[i + 1].start() if i + 1 < len(slide_headers) else len(body)
            parts = [clean_md(line) for line in body[match.end():end].splitlines() if line.strip()]
            label = clean_md(match.group(2))
            if label.lower() == "portada":
                slide_title = parts[0] if parts else title
                copy = " ".join(parts[1:])
            else:
                slide_title = label
                copy = " ".join(parts)
            slides.append({
                "number": int(match.group(1)),
                "label": label,
                "title": slide_title,
                "body": re.sub(r"\s+", " ", copy).strip(),
            })
        if slides:
            carousels.append({
                "number": number,
                "title": title,
                "alt": alt,
                "caption": caption,
                "slides": slides,
            })
    return carousels


def load_font(size: int, path: str | None, fallback: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (path, fallback):
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and text_width(draw, trial, font) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def draw_text_block(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], max_width: int,
                    font: ImageFont.ImageFont, fill: str, line_gap: int = 12,
                    max_lines: int | None = None) -> tuple[int, list[str]]:
    lines = wrap_lines(draw, text, font, max_width)
    if max_lines is not None and len(lines) > max_lines:
        raise ValueError(
            f"Text needs {len(lines)} lines but this layout allows {max_lines}; "
            f"shorten the copy or choose a roomier composition: {text[:100]!r}"
        )
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        box = draw.textbbox((x, y), line, font=font)
        y = box[3] + line_gap
    return y, lines


def round_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int,
               fill: str | tuple[int, int, int, int], outline: str | None = None, width: int = 2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def crop_fill(photo: Image.Image, box: tuple[int, int, int, int], focal: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    photo = photo.convert("RGB")
    ratio = max(width / photo.width, height / photo.height)
    resized = photo.resize((round(photo.width * ratio), round(photo.height * ratio)), Image.Resampling.LANCZOS)
    max_x, max_y = resized.width - width, resized.height - height
    left = round(max_x * max(0, min(1, focal[0])))
    top = round(max_y * max(0, min(1, focal[1])))
    return resized.crop((left, top, left + width, top + height))


def overlay_gradient(image: Image.Image, start_y: int, color: tuple[int, int, int], max_alpha: int = 235) -> Image.Image:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(start_y, image.height):
        amount = (y - start_y) / max(1, image.height - start_y)
        alpha = int(max_alpha * amount)
        draw.line((0, y, image.width, y), fill=(*color, alpha))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def palette_for(config: dict[str, Any]) -> dict[str, str]:
    required = {"paper", "ink", "accent", "accent2", "muted", "dark", "panel", "line"}
    palette = config.get("palette", {})
    if not isinstance(palette, dict):
        raise ValueError("Brand config 'palette' must be an object of color strings")
    missing = required - set(palette)
    if missing:
        raise ValueError(f"Brand config is missing palette keys: {', '.join(sorted(missing))}")
    invalid = [key for key in required if not isinstance(palette[key], str)]
    if invalid:
        raise ValueError(f"Palette values must be color strings: {', '.join(sorted(invalid))}")
    return palette


def resolve_asset_path(value: str, base_dir: Path) -> str:
    path = Path(value).expanduser()
    return str(path if path.is_absolute() else (base_dir / path).resolve())


def draw_wordmark(draw: ImageDraw.ImageDraw, config: dict[str, Any], p: dict[str, str],
                  font: ImageFont.ImageFont, x: int, y: int, color: str | None = None) -> None:
    # Text-only wordmark avoids inventing an unofficial icon or logo.
    draw.text((x, y), config.get("name", "BRAND").upper(), font=font, fill=color or p["ink"])


def footer(draw: ImageDraw.ImageDraw, config: dict[str, Any], p: dict[str, str],
           slide_no: int, total: int, font_bold: ImageFont.ImageFont, dark: bool = False) -> None:
    color = p["panel"] if dark else p["muted"]
    accent = p["accent2"] if dark else p["accent"]
    y = HEIGHT - 74
    draw.text((SAFE, y), config.get("handle", ""), font=font_bold, fill=color)
    counter = f"{slide_no:02d} / {total:02d}"
    draw.text((WIDTH - SAFE - text_width(draw, counter, font_bold), y), counter, font=font_bold, fill=accent)
    bar_y = HEIGHT - 30
    draw.rounded_rectangle((SAFE, bar_y, WIDTH - SAFE, bar_y + 7), radius=4, fill=p["dark"] if not dark else p["muted"])
    end = SAFE + int((WIDTH - 2 * SAFE) * slide_no / total)
    draw.rounded_rectangle((SAFE, bar_y, end, bar_y + 7), radius=4, fill=accent)


def header(draw: ImageDraw.ImageDraw, config: dict[str, Any], p: dict[str, str],
           deck_no: int, slide_no: int, total: int, font_bold: ImageFont.ImageFont,
           light: bool = False) -> None:
    color = p["panel"] if light else p["ink"]
    draw_wordmark(draw, config, p, font_bold, SAFE, 55, color)
    label = f"CARRUSEL {deck_no:02d}"
    draw.text((WIDTH - SAFE - text_width(draw, label, font_bold), 57), label, font=font_bold, fill=p["accent2"] if light else p["accent"])
    draw.line((SAFE, 112, WIDTH - SAFE, 112), fill=p["line"], width=2)


def draw_cover(slide: dict[str, Any], image: Image.Image, config: dict[str, Any], p: dict[str, str],
               deck_no: int, total: int, fonts: dict[str, ImageFont.ImageFont]) -> Image.Image:
    bg = crop_fill(image, (0, 0, WIDTH, HEIGHT), (0.58, 0.5)).convert("RGBA")
    bg = overlay_gradient(bg, 360, ImageColor.getrgb(p["dark"]), 238)
    bg = overlay_gradient(bg, 0, ImageColor.getrgb(p["dark"]), 120)
    draw = ImageDraw.Draw(bg)
    draw_wordmark(draw, config, p, fonts["bold_small"], SAFE, 58, p["panel"])
    draw.text((SAFE, 178), f"CARRUSEL {deck_no:02d}  ·  GUÍA", font=fonts["label"], fill=p["accent2"])
    title_size = 112 if len(slide["title"]) < 20 else 96
    title_font = load_font(title_size, config.get("fonts", {}).get("serif_bold"), DEFAULT_SERIF_BOLD)
    title_end, _ = draw_text_block(draw, slide["title"], (SAFE, 580), 900, title_font, p["panel"], 4, 3)
    if slide["body"]:
        body_font = fonts["body_light"]
        draw_text_block(draw, slide["body"], (SAFE, title_end + 28), 820, body_font, p["panel"], 10, 4)
    # Category chip reflects the deck title but stays small and legible.
    tag = deck_tag(slide.get("deck_title", ""))
    round_rect(draw, (SAFE, 1200, SAFE + 320, 1260), 25, p["accent"])
    draw.text((SAFE + 24, 1215), tag, font=fonts["label"], fill=p["panel"])
    footer(draw, config, p, slide["number"], total, fonts["bold_small"], dark=True)
    return bg.convert("RGB")


def deck_tag(title: str) -> str:
    lower = title.lower()
    if "google" in lower or "maps" in lower or "perfil" in lower:
        return "PERFIL Y VISIBILIDAD"
    if "contratar" in lower or "web" in lower or "sitio" in lower:
        return "WEB CON ALCANCE CLARO"
    return "ELIGE LO QUE NECESITAS"


def fit_title(draw: ImageDraw.ImageDraw, text: str, width: int, max_size: int = 76,
              min_size: int = 56, path: str | None = None) -> ImageFont.ImageFont:
    for size in range(max_size, min_size - 1, -2):
        candidate = load_font(size, path, DEFAULT_SERIF_BOLD)
        lines = wrap_lines(draw, text, candidate, width)
        if len(lines) <= 3:
            return candidate
    return load_font(min_size, path, DEFAULT_SERIF_BOLD)


def draw_recap(slide: dict[str, Any], p: dict[str, str],
               config: dict[str, Any], deck_no: int, total: int, fonts: dict[str, ImageFont.ImageFont]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), p["dark"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 18, HEIGHT), fill=p["accent2"])
    draw_wordmark(draw, config, p, fonts["bold_small"], SAFE, 58, p["panel"])
    draw.text((SAFE, 178), f"GUÁRDALO  ·  {deck_no:02d}", font=fonts["label"], fill=p["accent2"])
    title_font = fit_title(draw, slide["title"], WIDTH - 2 * SAFE, 82, 62, config.get("fonts", {}).get("serif_bold"))
    end, _ = draw_text_block(draw, slide["title"], (SAFE, 250), WIDTH - 2 * SAFE, title_font, p["panel"], 8, 3)
    body_font = fonts["body_light"]
    draw_text_block(draw, slide["body"], (SAFE, end + 34), WIDTH - 2 * SAFE - 34, body_font, p["panel"], 15, 8)
    footer(draw, config, p, slide["number"], total, fonts["bold_small"], dark=True)
    return image


def draw_cta(slide: dict[str, Any], image: Image.Image, config: dict[str, Any], p: dict[str, str],
             deck_no: int, total: int, fonts: dict[str, ImageFont.ImageFont]) -> Image.Image:
    bg = crop_fill(image, (0, 0, WIDTH, HEIGHT), (0.54, 0.5)).convert("RGBA")
    bg = overlay_gradient(bg, 0, ImageColor.getrgb(p["dark"]), 130)
    bg = overlay_gradient(bg, 400, ImageColor.getrgb(p["dark"]), 245)
    draw = ImageDraw.Draw(bg)
    draw_wordmark(draw, config, p, fonts["bold_small"], SAFE, 58, p["panel"])
    draw.text((SAFE, 520), f"SIGUIENTE PASO  ·  {deck_no:02d}", font=fonts["label"], fill=p["accent2"])
    title_font = fit_title(draw, slide["title"], 860, 104, 68, config.get("fonts", {}).get("serif_bold"))
    end, _ = draw_text_block(draw, slide["title"], (SAFE, 635), 850, title_font, p["panel"], 4, 3)
    draw_text_block(draw, slide["body"], (SAFE, end + 25), 820, fonts["body_light"], p["panel"], 10, 4)
    round_rect(draw, (SAFE, 1130, WIDTH - SAFE, 1216), 36, p["accent"])
    center_text(draw, "PRESENCIAALDIA.PRO", (SAFE + 20, 1140, WIDTH - SAFE - 20, 1205), fonts["label"], p["panel"])
    footer(draw, config, p, slide["number"], total, fonts["bold_small"], dark=True)
    return bg.convert("RGB")


def center_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], font: ImageFont.ImageFont, fill: str) -> None:
    x1, y1, x2, y2 = box
    width = text_width(draw, text, font)
    box_h = draw.textbbox((0, 0), text, font=font)[3]
    draw.text((x1 + max(0, (x2 - x1 - width) // 2), y1 + max(0, (y2 - y1 - box_h) // 2)), text, font=font, fill=fill)


def draw_content(slide: dict[str, Any], image: Image.Image, config: dict[str, Any], p: dict[str, str],
                 deck_no: int, total: int, fonts: dict[str, ImageFont.ImageFont]) -> Image.Image:
    number = slide["number"]
    label = slide["label"]
    mode = (number + deck_no) % 4
    if mode == 0:
        # Asymmetric split: text takes priority, photograph anchors the right third.
        canvas = Image.new("RGB", (WIDTH, HEIGHT), p["paper"])
        photo = crop_fill(image, (632, 0, WIDTH, HEIGHT), (0.64, 0.5))
        canvas.paste(photo, (632, 0))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, 20, HEIGHT), fill=p["accent"])
        text_width_px = 492
        x = SAFE + 6
        dark = False
    elif mode == 1:
        # Broad photo band above an editorial copy area.
        canvas = Image.new("RGB", (WIDTH, HEIGHT), p["paper"])
        photo = crop_fill(image, (0, 0, WIDTH, 390), (0.52, min(0.85, 0.28 + number * 0.08)))
        canvas.paste(photo, (0, 0))
        draw = ImageDraw.Draw(canvas)
        overlay = Image.new("RGBA", (WIDTH, 390), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle((0, 0, WIDTH, 390), fill=(*ImageColor.getrgb(p["dark"]), 78))
        canvas.paste(Image.alpha_composite(photo.convert("RGBA"), overlay).convert("RGB"), (0, 0))
        draw = ImageDraw.Draw(canvas)
        text_width_px = WIDTH - 2 * SAFE
        x = SAFE
        dark = False
    elif mode == 2:
        # Oversized numbered editorial panel with a small photo window.
        canvas = Image.new("RGB", (WIDTH, HEIGHT), p["dark"])
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((700, 215, 1185, 700), fill=p["accent"])
        photo = crop_fill(image, (690, 210, 1000, 630), (0.62, 0.45))
        mask = Image.new("L", photo.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, photo.width, photo.height), radius=32, fill=255)
        canvas.paste(photo, (690, 210), mask)
        draw = ImageDraw.Draw(canvas)
        text_width_px = 565
        x = SAFE
        dark = True
    else:
        # Color-blocked layout with a crop at the bottom; no repetitive card stack.
        canvas = Image.new("RGB", (WIDTH, HEIGHT), p["paper"])
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, WIDTH, 245), fill=p["accent"])
        photo = crop_fill(image, (590, 760, 1010, 1255), (0.62, 0.58))
        mask = Image.new("L", photo.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, photo.width, photo.height), radius=30, fill=255)
        canvas.paste(photo, (590, 760), mask)
        draw = ImageDraw.Draw(canvas)
        text_width_px = 830
        x = SAFE
        dark = False

    title_color = p["panel"] if dark else p["ink"]
    body_color = p["panel"] if dark else p["muted"]
    if mode == 1:
        draw_wordmark(draw, config, p, fonts["bold_small"], SAFE, 48, p["panel"])
        draw.text((SAFE, 310), f"{number:02d}  ·  {label.upper()[:34]}", font=fonts["label"], fill=p["panel"])
        title_y = 470
    elif mode == 2:
        draw_wordmark(draw, config, p, fonts["bold_small"], SAFE, 58, p["panel"])
        draw.text((SAFE, 188), f"{number:02d}", font=fonts["number"], fill=p["accent2"])
        draw.text((SAFE, 700), label.upper()[:32], font=fonts["label"], fill=p["accent2"])
        title_y = 770
    elif mode == 3:
        draw_wordmark(draw, config, p, fonts["bold_small"], SAFE, 48, p["ink"])
        draw.text((SAFE, 154), f"{number:02d}  ·  {label.upper()[:34]}", font=fonts["label"], fill=p["panel"])
        title_y = 320
    else:
        draw_wordmark(draw, config, p, fonts["bold_small"], x, 55, p["ink"])
        draw.text((x, 175), f"{number:02d}  ·  {label.upper()[:32]}", font=fonts["label"], fill=p["accent"])
        title_y = 265

    title_path = config.get("fonts", {}).get("serif_bold")
    title_font = fit_title(draw, slide["title"], text_width_px, 76 if mode != 2 else 66, 52, title_path)
    end, _ = draw_text_block(draw, slide["title"], (x, title_y), text_width_px, title_font, title_color, 9, 3)
    body_size = 38 if len(slide["body"].split()) <= 16 else 34
    body_font = load_font(body_size, config.get("fonts", {}).get("regular"), DEFAULT_REGULAR)
    body_y = end + 28
    max_body_width = text_width_px
    if mode == 2:
        max_body_width = 545
    draw_text_block(draw, slide["body"], (x, body_y), max_body_width, body_font, body_color, 10, 7)
    footer(draw, config, p, number, total, fonts["bold_small"], dark=dark)
    return canvas


def render_deck(deck: dict[str, Any], deck_index: int, image_path: Path, config: dict[str, Any],
                output: Path, quality: int) -> list[Path]:
    p = palette_for(config)
    with Image.open(image_path) as source:
        photo = source.convert("RGB")
    fonts_cfg = config.get("fonts", {})
    fonts = {
        "regular": load_font(38, fonts_cfg.get("regular"), DEFAULT_REGULAR),
        "bold_small": load_font(24, fonts_cfg.get("bold"), DEFAULT_BOLD),
        "label": load_font(22, fonts_cfg.get("bold"), DEFAULT_BOLD),
        "body_light": load_font(38, fonts_cfg.get("regular"), DEFAULT_REGULAR),
        "number": load_font(176, fonts_cfg.get("serif_bold"), DEFAULT_SERIF_BOLD),
    }
    deck_dir = output / f"carrusel-{deck_index:02d}-{slugify(deck['title'])}"
    deck_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    total = len(deck["slides"])
    for i, raw_slide in enumerate(deck["slides"]):
        slide = dict(raw_slide)
        slide["deck_title"] = deck["title"]
        if i == 0:
            image = draw_cover(slide, photo, config, p, deck_index, total, fonts)
        elif i == total - 1 or "cierre" in slide["label"].lower():
            image = draw_cta(slide, photo, config, p, deck_index, total, fonts)
        elif any(word in slide["label"].lower() for word in ("lista", "guarda", "recap", "checklist")):
            image = draw_recap(slide, p, config, deck_index, total, fonts)
        else:
            image = draw_content(slide, photo, config, p, deck_index, total, fonts)
        path = deck_dir / f"{slide['number']:02d}-{slugify(slide['title'])[:36]}.jpg"
        image.save(path, "JPEG", quality=quality, optimize=True, progressive=True, subsampling=0)
        rendered.append(path)
    (deck_dir / "caption.txt").write_text(deck["caption"].strip() + "\n", encoding="utf-8")
    (deck_dir / "alt-text.txt").write_text(deck["alt"].strip() + "\n", encoding="utf-8")
    (deck_dir / "README.txt").write_text(
        f"{config.get('name', 'Brand')} · {deck['title']}\n"
        f"{total} JPG, 1080 × 1350 px, 4:5.\n"
        f"{config.get('asset_note', 'Confirma permisos y contexto de las fotos antes de publicar.')}\n"
        f"Wordmark tipográfico; no reemplaza el logotipo oficial.\n",
        encoding="utf-8",
    )
    preview = deck_dir / "preview.pdf"
    pages: list[Image.Image] = []
    for path in rendered:
        with Image.open(path) as source:
            pages.append(source.convert("RGB"))
    try:
        pages[0].save(preview, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    finally:
        for page in pages:
            page.close()
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path, help="Markdown carousel copy; one file may contain multiple carousels")
    parser.add_argument("--brand", required=True, type=Path, help="JSON brand tokens and a photo path for each carousel")
    parser.add_argument("--out", required=True, type=Path, help="Output directory for JPG slides and previews")
    parser.add_argument("--quality", type=int, default=94, help="JPEG quality (default: 94)")
    args = parser.parse_args()
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")
    brand_path = args.brand.expanduser().resolve()
    try:
        config = json.loads(brand_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"Cannot read brand JSON {brand_path}: {exc}")
    if not isinstance(config, dict):
        parser.error("Brand JSON must contain an object")
    for key in ("name", "handle", "asset_note"):
        if key in config and not isinstance(config[key], str):
            parser.error(f"Brand config '{key}' must be a string")
    try:
        palette_for(config)
    except ValueError as exc:
        parser.error(str(exc))

    photos = config.get("photos", [])
    if not isinstance(photos, list) or not all(isinstance(photo, str) for photo in photos):
        parser.error("Brand JSON 'photos' must be a list of image paths")
    config["photos"] = [resolve_asset_path(photo, brand_path.parent) for photo in photos]
    fonts = config.get("fonts", {})
    if not isinstance(fonts, dict):
        parser.error("Brand JSON 'fonts' must be an object")
    invalid_fonts = [key for key, path in fonts.items() if path is not None and not isinstance(path, str)]
    if invalid_fonts:
        parser.error(f"Font paths must be strings or null: {', '.join(sorted(invalid_fonts))}")
    config["fonts"] = {
        key: resolve_asset_path(path, brand_path.parent) if path else None
        for key, path in fonts.items()
    }

    try:
        carousels = parse_carousels(args.markdown.read_text(encoding="utf-8"))
    except OSError as exc:
        parser.error(f"Cannot read Markdown source {args.markdown}: {exc}")
    if not carousels:
        parser.error("No '## Carrusel N · title' sections with numbered slides were found")
    if len(config["photos"]) < len(carousels):
        parser.error(f"Brand JSON must list {len(carousels)} photo paths, one per carousel")
    args.out.mkdir(parents=True, exist_ok=True)
    for index, deck in enumerate(carousels, start=1):
        photo_path = Path(config["photos"][index - 1])
        if not photo_path.is_file():
            parser.error(f"Photo not found for carousel {index}: {photo_path}")
        try:
            rendered = render_deck(deck, index, photo_path, config, args.out, args.quality)
        except (OSError, ValueError) as exc:
            parser.error(f"Cannot render carousel {index} ({deck['title']}): {exc}")
        print(f"{deck['title']}: {len(rendered)} slides -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
