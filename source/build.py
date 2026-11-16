import base64
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
THEME_NAME = "Dither Live"
CSS_LIMIT = 20_000
ART_SIZE = (320, 180)
ART_BYTE_LIMIT = 7_000
HIGHLIGHT_PERCENTILE = 0.995
SCENE_BACKGROUND = "#020306"
AREA_BACKGROUND = (3, 4, 7)
DITHER_OPACITY = 0.55
OVERLAY_ALPHA = 0.56
BODY_TEXT = "#e8ecf4"
MUTED_TEXT = "#aab2c3"
ACCENT_FOREGROUND = "#0a0c10"
TEXT_MINIMUM = 4.5
HOVER_LIGHTEN = 0.18
MUTED_ROLES = ("textMuted", "mutedForeground", "secondaryLabel", "sidebarMutedForeground")

SVG_PATTERN = re.compile(r"url\(data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)\)")
SCENE_PATTERN = re.compile(r"<g id='s'>.*?</g></svg></g>", re.S)
BASE_ART_RULE = re.compile(r'^\.dark \[data-workspace-area="conversation"\]\{[^}]*\}\n?')


def highlight_level(image: Image.Image) -> int:
    histogram = image.convert("L").histogram()
    target = sum(histogram) * HIGHLIGHT_PERCENTILE
    seen = 0
    for level, count in enumerate(histogram):
        seen += count
        if seen >= target:
            return max(level, 1)
    return 255


def tone_map(image: Image.Image, gamma: float) -> Image.Image:
    peak = highlight_level(image)
    curve = [round(255 * min(level / peak, 1) ** gamma) for level in range(256)]
    return image.point(curve * 3)


def encode_art(slug: str, gamma: float) -> bytes:
    photo = Image.open(ROOT / "photos" / f"{slug}.jpg").convert("RGB")
    art = tone_map(photo.resize(ART_SIZE, Image.Resampling.LANCZOS), gamma)
    for quality in range(70, 9, -5):
        buffer = io.BytesIO()
        art.save(buffer, "WEBP", quality=quality, method=6)
        if buffer.tell() <= ART_BYTE_LIMIT:
            return buffer.getvalue()
    sys.exit(f"{slug}: art does not fit in {ART_BYTE_LIMIT} bytes")


def scene_markup(art: bytes) -> str:
    href = "data:image/webp;base64," + base64.b64encode(art).decode()
    return (
        f"<g id='s'><rect width='100%' height='100%' fill='{SCENE_BACKGROUND}'/>"
        f"<image href='{href}' width='100%' height='100%' preserveAspectRatio='xMidYMid slice'/></g>"
    )


def channel_luminance(value: float) -> float:
    scaled = value / 255
    return scaled / 12.92 if scaled <= 0.04045 else ((scaled + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[float, ...]) -> float:
    red, green, blue = (channel_luminance(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def hex_rgb(value: str) -> tuple[int, ...]:
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def contrast(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def brightest_dither_pixel() -> tuple[float, ...]:
    lit = tuple(255 * DITHER_OPACITY + base * (1 - DITHER_OPACITY) for base in AREA_BACKGROUND)
    return tuple(
        channel * (1 - OVERLAY_ALPHA) + base * OVERLAY_ALPHA
        for channel, base in zip(lit, AREA_BACKGROUND)
    )


def lighten(color: str) -> str:
    mixed = (round(channel + (255 - channel) * HOVER_LIGHTEN) for channel in hex_rgb(color))
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def minify(css: str) -> str:
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,])\s*", r"\1", css)
    css = re.sub(r":\s+", ":", css)
    css = re.sub(r"\s*!important", "!important", css)
    return css.replace(";}", "}").strip()


def art_url(base_css: str, art: bytes | None) -> str:
    svg = base64.b64decode(SVG_PATTERN.search(base_css).group(1)).decode()
    if art is not None:
        svg, scenes = SCENE_PATTERN.subn(lambda _: scene_markup(art), svg)
        if scenes != 1:
            sys.exit("base theme scene markup changed")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def accent_colors(accent: str) -> dict[str, str]:
    return {
        "accentForeground": ACCENT_FOREGROUND,
        "focus": accent,
        "messageAction": accent,
        "messageActionForeground": ACCENT_FOREGROUND,
        "messageActionHover": lighten(accent),
        "terminalCursor": accent,
    }


def build_theme(base: dict, source: dict, art: bytes | None) -> dict:
    remaining_css, removed = BASE_ART_RULE.subn("", base["css"])
    if removed != 1:
        sys.exit("base theme no longer starts with the conversation background rule")
    accent = source.get("accent", base["accent"])
    layout = (
        minify((ROOT / "layout.css").read_text())
        .replace("__OVERLAY__", str(OVERLAY_ALPHA))
        .replace("__ACCENT__", accent)
        .replace("__ART__", art_url(base["css"], art))
    )
    css = f"{layout}\n{remaining_css}"
    if len(css) > CSS_LIMIT:
        sys.exit(f"theme css is {len(css)} characters; T3 accepts at most {CSS_LIMIT}")
    colors = {**base["colors"], **{role: MUTED_TEXT for role in MUTED_ROLES}}
    if "accent" in source:
        colors.update(accent_colors(accent))
    return {**base, "name": THEME_NAME, "accent": accent, "colors": colors, "css": css}


def check_contrast(base: dict, sources: list[dict]) -> None:
    brightest = brightest_dither_pixel()
    muted = contrast(hex_rgb(MUTED_TEXT), brightest)
    body = contrast(hex_rgb(BODY_TEXT), brightest)
    print(f"against the brightest dither pixel: body text {body:.2f}:1, muted text {muted:.2f}:1")
    if muted < TEXT_MINIMUM:
        sys.exit("muted text contrast is below the minimum")
    canvas = hex_rgb(base["canvas"])
    for source in sources:
        if "accent" not in source:
            continue
        accent = hex_rgb(source["accent"])
        on_canvas = contrast(accent, canvas)
        on_accent = contrast(hex_rgb(ACCENT_FOREGROUND), accent)
        print(f"{source['slug']:8} accent {source['accent']}: on canvas {on_canvas:.2f}:1, button label {on_accent:.2f}:1")
        if min(on_canvas, on_accent) < TEXT_MINIMUM:
            sys.exit(f"{source['slug']}: accent contrast is below the minimum")


if __name__ == "__main__":
    base = json.loads((ROOT / "base.json").read_text())
    sources = json.loads((ROOT / "sources.json").read_text())
    check_contrast(base, sources)
    selected = sys.argv[1:]
    for index, source in enumerate(sources, start=1):
        if selected and source["slug"] not in selected:
            continue
        art = None if source.get("original") else encode_art(source["slug"], source["gamma"])
        theme = build_theme(base, source, art)
        out = ROOT.parent / "themes" / f"{index:02d}-{source['slug']}.json"
        out.write_text(json.dumps(theme, indent=2) + "\n")
        print(f"{out.name}: css {len(theme['css'])} characters")
