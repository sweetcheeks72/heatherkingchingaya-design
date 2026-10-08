"""Static gate for the King Chingaya Design site — latest revision (Feedback 1.pdf, 3 October 2026).

Run with either:
    python3 tests/test_site.py
    python3 -m pytest tests/test_site.py
Requires Pillow.

Floor-plan integration
----------------------
The entrance floor plan is produced by a separate plan workflow:
  scripts/build_floor_plan.py          deterministic generator (supports --check)
  assets/brand/floor-plan-model.json   editable plan model
  assets/brand/entry-floor-plan.svg    static external SVG
The generator replaces the block between <!-- FLOOR_PLAN_START --> and <!-- FLOOR_PLAN_END -->
in index.html with an inline <svg class="floor-plan" aria-hidden="true" focusable="false">
that has its own viewBox and the stage groups .plan-shell, .plan-fixtures, .plan-furniture.

Until any of those artifacts exists the block still holds the placeholder <img>. In that state the
inline-SVG, generator and model checks are reported as INTEGRATION PENDING (not passed, not
failed). As soon as the generator, the model or an inline SVG appears, the full contract is
enforced strictly. Set REQUIRE_PLAN_INTEGRATION=1 to make pending items fail.
"""
from __future__ import annotations

import colorsys
import hashlib
import importlib.util
import json
import math
import os
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

try:
    from PIL import Image, ImageStat
except ImportError:
    Image = ImageStat = None


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "app.js").read_text(encoding="utf-8")

PLAN_GENERATOR = ROOT / "scripts" / "build_floor_plan.py"
PLAN_MODEL = ROOT / "assets" / "brand" / "floor-plan-model.json"
PLAN_SVG = ROOT / "assets" / "brand" / "entry-floor-plan.svg"
STRICT_PLAN = os.environ.get("REQUIRE_PLAN_INTEGRATION") == "1"
PLAN_STAGES = ("plan-shell", "plan-fixtures", "plan-furniture")
MAX_REVEAL_SECONDS = 4.5

# Rooms the latest brief and the user's confirmed Dallas program require. Matched as words in the
# model's keys/strings only; no deeper schema is assumed until the model file exists.
REQUIRED_MODEL_ROOMS = {
    "courtyard": ("courtyard",),
    "kitchen": ("kitchen",),
    "pantry": ("pantry",),
    "dining room": ("dining",),
    "living room": ("living",),
    "entry": ("entry", "foyer"),
    "coat closet": ("coat",),
    "primary bedroom": ("primary bed",),
    "guest bedroom": ("guest bed",),
    "hallway / sitting area": ("hall", "sitting"),
}

# The pre-redesign snapshot taken before this task. Optional: if it is not next to the
# site (e.g. in a fresh checkout) the hardcoded hashes below are used instead.
BASELINE_MANIFEST = ROOT.parent / "baseline-manifest.json"

# Hashes copied from ../baseline-manifest.json (lower-case hex SHA256).
BASELINE_HASHES = {
    "assets/brand/jasmine-vines-v1.png": "f734c989778db6688070e29e97e7229296c471a01352c18da17bb54da81b3f63",
    "assets/brand/dallas-map.jpeg": "b333cd2003e3330f1d204f557bafad7764a687b9886a1a71bd7ceadad2c67ffc",
    "assets/brief/architectural-model.webp": "37347bcfc083275137887ade64dfb0375d15e3cb6de641cc7d3159ea41e5d957",
    "assets/brief/sunken-living-room.webp": "732783d3c2afde793a738cb70c3f77f07e2662002484923d32bc7a6b392381a3",
    "assets/brief/hospitality-elevation.webp": "8f8fdf1fb80d08ea09d3b2c47e28da72c8d6c4f96a586473d037a0352503c51b",
    "assets/brief/bedroom-terrace.webp": "1df6949e6ec3a388d0d33849187dd80825fdc7d9536decfb683b2a224c7d9dfc",
    "assets/brief/bedroom-artwork.webp": "96fceca283d5f7ed2d5a179a2ec9442f78aa0acacefeecab6784b2fd1ac4507f",
    "assets/brief/bathroom.webp": "124eced56cb2489232ad989f0c914e6ab515ee23b273d772d8129e5031cef571",
    "assets/fonts/fraunces-latin-full-italic.woff2": "04a14ea380db53a35a3ec651934b21061234685bb604d30aac82663b5d9e539b",
    "assets/fonts/fraunces-latin-full-normal.woff2": "7e744849028e2219e2aa1bc467dc4032980dc4487c9c3da3010081cd72d3b103",
    "assets/fonts/instrument-sans-latin-wght-normal.woff2": "2ee17598a98d8a59e4df8152d015bec9ab8e4d5672cc0ab42bef806b568e3971",
    "assets/fonts/instrument-sans-OFL.txt": "c27a3c53c3beed7f5c26853afa15991478ff7145d3754a36b0382f84e10c0d03",
    "assets/fonts/fraunces-OFL.txt": "cd3384cafac6f2bddc3955273958a2e029f97027c8037ac539ef5744a77b579e",
}
# Baseline files that this redesign is allowed to change.
BASELINE_MUTABLE_ASSETS = {"assets/brand/manifest.json"}

# Feedback 2 restaurant images: the baseline predates them, so their provenance record
# (assets/brief/feedback-2-manifest.json) is pinned here verbatim.
FEEDBACK_2_MANIFEST = {
    "source": {
        "library_file_id": "libfile_c995d2cdade88191b4ccdd1534fec23e",
        "file_id": "file_0000000073ac8230acaff44ec5c6f5fb",
        "filename": "Feedback 2.pdf",
        "version": 0,
        "sha256": "1e77c5cda44d416d86a21a5602856c9d59fe14cbccb6c0e6a20bd17a8577af8e",
    },
    "assets": {
        "restaurant-window.png": {
            "source_page": 2, "source_image": 2, "width": 1597, "height": 1291,
            "sha256": "27b8b8e7b58ec4e8e17c656020166b9583c03fe015d1bc1c1e04dca9d4317da5",
            "operation": "Original embedded PNG extracted from supplied PDF without resizing or retouching",
        },
        "restaurant-booths.png": {
            "source_page": 2, "source_image": 3, "width": 1721, "height": 1252,
            "sha256": "2c15b5863cb85b2c9dae2d1234bb18053c90646e6d176a8e9d66c3d52fdefe4c",
            "operation": "Original embedded PNG extracted from supplied PDF without resizing or retouching",
        },
        "restaurant-counter.png": {
            "source_page": 3, "source_image": 1, "width": 1000, "height": 727,
            "sha256": "69b2ffd35b1854720ed5a955ae7257bec7026a25942cb8fe34a791011963caf7",
            "operation": "Original embedded PNG extracted from supplied PDF without resizing or retouching",
        },
    },
}
RESTAURANT_SIZES = {
    "restaurant-window.png": (1597, 1291),
    "restaurant-booths.png": (1721, 1252),
    "restaurant-counter.png": (1000, 727),
}

EXPECTED_GALLERY = [
    "assets/brief/architectural-model.webp",
    "assets/brief/sunken-living-room.webp",
    "assets/brief/hospitality-elevation.webp",
    "assets/brief/bedroom-terrace.webp",
    "assets/brief/bedroom-artwork.webp",
    "assets/brief/bathroom.webp",
    "assets/brief/restaurant-window.png",
    "assets/brief/restaurant-booths.png",
    "assets/brief/restaurant-counter.png",
]

# Latest brief: plain, large, unnumbered section headings, in page order.
SECTION_TITLES = [
    ("philosophy", "Design philosophy"),
    ("projects", "Gallery"),
    ("about", "About me"),
    ("process", "Working together"),
    ("services", "Services"),
    ("inquiry", "Start a project"),
]
# Copy the latest brief removed (philosophy taglines and the large poetic sub-headings).
REMOVED_COPY = (
    "grounded in people", "considered in every detail", "made to become your own",
    "a love of people", "a lifelong love of design",
)
# Feedback 3 element heights before the latest "more green" request (styles.css, Feedback 3).
F3_BAND_TOP_PADDING = (28, 7.0)        # padding-top: max(28px, 7vw)
F3_STRAND_ASPECT = 369 / 1933           # full-width strand box, height / width

# Colours that belonged to the provisional blue direction and must not return.
OLD_BLUE_TOKENS = ("#284d70", "#152a3a", "#0000ff", "#00f;", "#00f}")

RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}

# Affirmative certification claims the plan and review artifacts must never make.
COMPLIANCE_CLAIM = re.compile(
    r"(?<!not )(?<!never )(?<!no )\b(code[- ]compliant|meets (?:the )?(?:building )?code|permit[- ]ready|"
    r"construction[- ]ready|approved for construction|guaranteed compliance)\b"
)

PENDING: list[str] = []


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.id_list: list[str] = []
        self.links: list[str] = []
        self.images: list[dict[str, str]] = []
        self.headings: list[int] = []
        self.forms: list[dict[str, str]] = []
        self.labels_for: set[str] = set()
        self.controls: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if data.get("id"):
            self.ids.add(data["id"])
            self.id_list.append(data["id"])
        if tag == "a":
            self.links.append(data.get("href", ""))
        if tag == "img":
            self.images.append(data)
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag == "form":
            self.forms.append(data)
        if tag == "label" and data.get("for"):
            self.labels_for.add(data["for"])
        if tag in {"input", "textarea", "select"}:
            self.controls.append(data)


VOID_TAGS = {"img", "input", "br", "hr", "meta", "link", "source", "area", "base", "col", "embed", "wbr"}


class Node:
    def __init__(self, tag: str, attrs: dict[str, str], parent: "Node | None") -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[Node | str] = []

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def text(self) -> str:
        return "".join(child if isinstance(child, str) else child.text() for child in self.children)

    def iter(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(self, tag: str | None = None, cls: str | None = None) -> list["Node"]:
        return [n for n in self.iter() if (tag is None or n.tag == tag) and (cls is None or cls in n.classes)]

    def find(self, tag: str | None = None, cls: str | None = None) -> "Node | None":
        found = self.find_all(tag, cls)
        return found[0] if found else None

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent


class TreeParser(HTMLParser):
    """Minimal DOM tree, sufficient for this hand-written, well-formed page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None)
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v or "" for k, v in attrs}, self.current)
        self.current.children.append(node)
        if tag not in VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, {k: v or "" for k, v in attrs}, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def png_ihdr_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise AssertionError(f"Not a PNG with a leading IHDR chunk: {path.name}")
    return struct.unpack(">II", head[16:24])


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def luminance(hex_color: str) -> float:
    values = [channel / 255 for channel in hex_rgb(hex_color)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def is_green(hex_color: str) -> bool:
    r, g, b = hex_rgb(hex_color)
    return g > r and g > b


def is_blue(hex_color: str) -> bool:
    """True for a perceptibly saturated blue (hue 190-250 degrees). Purples and near-greys pass."""
    r, g, b = (channel / 255 for channel in hex_rgb(hex_color))
    hue, saturation, _ = colorsys.rgb_to_hsv(r, g, b)
    return 190 <= hue * 360 <= 250 and saturation >= 0.15


def css_rule(selector: str) -> str:
    """Return the declaration block of the first top-level rule that is exactly `selector`."""
    match = re.search(r"(?:^|[}\s])" + re.escape(selector) + r"\{([^}]*)\}", CSS)
    if not match:
        raise AssertionError(f"Missing CSS rule: {selector}")
    return match.group(1)


def css_blocks(css: str | None = None) -> list[tuple[str, str, str]]:
    """Every style rule as (context, selector list, declarations).

    `context` is the space-joined chain of enclosing at-rule preludes (normalised to
    "@media (...)"), or "" for a top-level rule. Comments are stripped first.
    """
    text = re.sub(r"/\*.*?\*/", "", CSS if css is None else css, flags=re.S)
    blocks: list[tuple[str, str, str]] = []
    stack: list[str] = []
    prelude = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "{":
            head = " ".join(prelude.split()).replace("@media(", "@media (")
            prelude = ""
            if head.startswith(("@media", "@supports", "@keyframes")):
                stack.append(head)
                i += 1
                continue
            end = text.index("}", i)
            blocks.append((" ".join(stack), head, text[i + 1:end]))
            i = end + 1
            continue
        if ch == "}":
            if stack:
                stack.pop()
            prelude = ""
            i += 1
            continue
        prelude += ch
        i += 1
    return blocks


def css_rules_with(selector: str, context: str | None = "") -> list[str]:
    """Declarations of every rule whose selector list contains exactly `selector`.

    context="" means top level only; None means any context.
    """
    return [
        decls for ctx, head, decls in css_blocks()
        if (context is None or ctx == context) and selector in [part.strip() for part in head.split(",")]
    ]


def visible_text(node: "Node", skip=lambda n: False) -> str:
    """Text that is painted on screen: skips .sr-only and [hidden] subtrees (aria-hidden text is still visible)."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif "sr-only" not in child.classes and "hidden" not in child.attrs and not skip(child):
            parts.append(visible_text(child, skip))
    return "".join(parts)


def css_var(name: str) -> str:
    match = re.search(r"--" + re.escape(name) + r":(#[0-9a-fA-F]{6})", CSS)
    if not match:
        raise AssertionError(f"Missing CSS custom property --{name}")
    return match.group(1).lower()


def css_var_text(name: str) -> str:
    match = re.search(r"--" + re.escape(name) + r":([^;}]+)", CSS)
    if not match:
        raise AssertionError(f"Missing CSS custom property --{name}")
    return match.group(1)


def resolve_color(value: str) -> str:
    value = value.strip()
    var = re.fullmatch(r"var\(--([\w-]+)\)", value)
    if var:
        return css_var(var.group(1))
    if re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", value):
        return value.lower()
    if value.lower() in {"#fff", "#ffffff", "white"}:
        return "#ffffff"
    raise AssertionError(f"Unresolvable colour value: {value}")


def decl_color(decls: str, prop: str) -> str:
    match = re.search(r"(?:^|;)" + prop + r":([^;}!]+)", decls)
    if not match:
        raise AssertionError(f"Missing {prop} in: {decls[:80]}")
    return resolve_color(match.group(1))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def pending(message: str) -> None:
    """An integration-dependent check that cannot run yet. Fails only under REQUIRE_PLAN_INTEGRATION=1."""
    if STRICT_PLAN:
        raise AssertionError(f"Plan integration required (REQUIRE_PLAN_INTEGRATION=1): {message}")
    PENDING.append(message)


def baseline_hashes() -> dict[str, str]:
    hashes = dict(BASELINE_HASHES)
    if BASELINE_MANIFEST.is_file():
        files = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))["files"]
        for rel, expected in BASELINE_HASHES.items():
            check(files.get(rel, {}).get("sha256") == expected, f"Hardcoded baseline hash disagrees with baseline-manifest.json: {rel}")
        for rel, record in files.items():
            if rel.startswith("assets/") and rel not in BASELINE_MUTABLE_ASSETS:
                hashes[rel] = record["sha256"]
    return hashes


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_viewbox(value: str | None) -> tuple[float, float, float, float]:
    parts = re.split(r"[\s,]+", (value or "").strip())
    check(len(parts) == 4, f"SVG viewBox must have four numbers: {value!r}")
    try:
        x, y, w, h = (float(p) for p in parts)
    except ValueError:
        raise AssertionError(f"SVG viewBox must be numeric: {value!r}")
    check(w > 0 and h > 0, f"SVG viewBox needs a positive size: {value!r}")
    return x, y, w, h


def svg_safety(svg_text: str, root, where: str) -> None:
    """Shared safety rules for the inline and external plan SVGs: vector only, no script, no external refs, no SMIL, no blue."""
    lower = svg_text.lower()
    names = {local(e.tag).lower() for e in root.iter()}
    for banned in ("script", "foreignobject", "image", "iframe", "a", "animate", "animatetransform", "animatemotion", "set"):
        check(banned not in names, f"{where}: <{banned}> is not allowed in the floor plan.")
    for e in root.iter():
        for key, value in e.attrib.items():
            name = local(key).lower()
            check(not name.startswith("on"), f"{where}: inline event handler {name} is not allowed.")
            if name == "href":
                check(value.startswith("#"), f"{where}: only internal fragment references are allowed: {value}")
    check("javascript:" not in lower and "@import" not in lower, f"{where}: no javascript: URLs or @import.")
    check(not re.search(r"url\(\s*['\"]?(?!#)", svg_text), f"{where}: url() may only reference internal fragments.")
    check(not re.search(r"https?://(?!www\.w3\.org/)", svg_text), f"{where}: no external URLs.")
    for token in OLD_BLUE_TOKENS + ("blue", "navy"):
        check(token not in lower, f"{where}: blue colour token {token}.")
    for colour in re.findall(r"#[0-9a-fA-F]{6}\b", svg_text):
        check(not is_blue(colour), f"{where}: blue colour {colour}.")


def main() -> int:
    parser = SiteParser()
    parser.feed(HTML)
    tree = TreeParser()
    tree.feed(HTML)
    doc = tree.root
    lower_html = HTML.lower()
    # Inline SVG roots legitimately carry the SVG namespace URI; that is not a network reference.
    html_no_ns = re.sub(r"\sxmlns(?::\w+)?=\"http://www\.w3\.org/[^\"]*\"", "", HTML)

    # ---- Semantic structure and navigation ----
    check(lower_html.count("<h1") == 1, "The page must have exactly one h1.")
    check(parser.headings and parser.headings[0] == 1, "The heading sequence must start at h1.")
    check(all(current - previous <= 1 for previous, current in zip(parser.headings, parser.headings[1:])), "Heading levels must not skip.")
    duplicates = sorted({i for i in parser.id_list if parser.id_list.count(i) > 1})
    check(not duplicates, f"Duplicate ids (including any inline SVG ids): {duplicates}")

    required_ids = {"main", "projects", "philosophy", "services", "about", "process", "entrance", "inquiry", "inquiry-form", "site-footer", "entrance-title"}
    check(required_ids <= parser.ids, f"Missing required landmarks: {sorted(required_ids - parser.ids)}")
    for href in parser.links:
        check(bool(href), "Every link needs a destination.")
        check(not re.match(r"(?:https?:)?//", href), f"External destination is not cleared: {href}")
        if href.startswith("#"):
            check(href[1:] in parser.ids, f"Broken internal link: {href}")
        elif ":" not in href:
            check((ROOT / href.split("#", 1)[0]).is_file(), f"Relative link points to a missing file: {href}")
    for href in parser.links:
        if ":" in href:
            check(href == "mailto:heather@kingchingaya.com", f"Only the supplied mailto may leave the page: {href}")

    nav = doc.find("nav")
    check(nav is not None and nav.attrs.get("aria-label") == "Primary navigation", "Primary navigation must remain labelled.")
    nav_links = nav.find_all("a")
    nav_hrefs = [a.attrs.get("href") for a in nav_links]
    check(nav_hrefs == ["#philosophy", "#projects", "#about", "#process", "#services", "#inquiry"], f"Primary navigation changed: {nav_hrefs}")
    nav_text = [" ".join(a.text().replace("↗", "").split()) for a in nav_links]
    check(nav_text == ["Philosophy", "Gallery", "About", "Working together", "Services", "Start a project"], f"Navigation labels changed (the work section is named Gallery): {nav_text}")

    sections = {n.attrs.get("id"): n for n in doc.find_all("section") if n.attrs.get("id")}
    service_titles = [s.text().strip() for s in sections["services"].find_all("span", "row-title")]
    check(service_titles == ["Room Refresh", "Design Consultations", "Furnishing & Styling", "Renovations & Remodels", "New Construction", "Commercial Interior Design"], f"Services changed: {service_titles}")
    process_titles = [s.text().strip() for s in sections["process"].find_all("span", "row-title")]
    check(process_titles == ["Listen", "Imagine", "Refine", "Create", "Live"], f"Process steps changed: {process_titles}")

    # ---- Latest brief: plain, large, unnumbered section headings; taglines removed ----
    for section_id, expected in SECTION_TITLES:
        section = sections.get(section_id)
        check(section is not None, f"Missing section #{section_id}.")
        h2s = section.find_all("h2")
        check(len(h2s) == 1, f"#{section_id} must have exactly one heading (no extra poetic sub-heading): {len(h2s)}")
        h2 = h2s[0]
        check("section-title" in h2.classes, f"#{section_id} heading must use the large .section-title style.")
        check(all(isinstance(c, str) for c in h2.children), f"#{section_id} heading must be plain text, with no number or decorative span.")
        check(" ".join(h2.text().split()) == expected, f"#{section_id} heading must read {expected!r}: {h2.text()!r}")
        check(section.attrs.get("aria-labelledby") == h2.attrs.get("id"), f"#{section_id} must be labelled by its heading.")
        check(not section.find_all("h3") or section_id == "inquiry", f"#{section_id} must not carry sub-headings.")
        for node in section.iter():
            check(not any(re.search(r"(?:^|-)(?:number|index|count|numeral|kicker|tagline)(?:$|-)", c) for c in node.classes),
                  f"#{section_id}: numbering/tagline markup is removed: {sorted(node.classes)}")
            if node.children and all(isinstance(c, str) for c in node.children):
                check(not re.fullmatch(r"\s*[\(\[]?\d{1,2}[.)\]/]?\s*", node.text()), f"#{section_id}: number marker found: {node.text()!r}")
    check([sections[s].attrs.get("id") for s, _ in SECTION_TITLES] == [s for s, _ in SECTION_TITLES], "Section ids changed.")
    order = [HTML.index(f'id="{s}"') for s, _ in SECTION_TITLES]
    check(order == sorted(order), "Sections must stay in the order philosophy, gallery, about, process, services, inquiry.")
    for summary in doc.find_all("summary"):
        kids = [c for c in summary.children if isinstance(c, Node)]
        check([sorted(k.classes) for k in kids] == [["row-title"], ["plus"]], f"Accordion rows hold only the title and the plus icon (no number markers): {[sorted(k.classes) for k in kids]}")
        check(not re.search(r"\d", kids[0].text()), f"Accordion title must not be numbered: {kids[0].text()!r}")
    for phrase in REMOVED_COPY:
        check(phrase not in lower_html, f"Removed copy returned: {phrase!r}")
    title_rule = css_rule(".section-title")
    size = re.search(r"font-size:clamp\((\d+)px,([\d.]+)vw,(\d+)px\)", title_rule)
    h2_size = re.search(r"h2\{font-size:clamp\((\d+)px,([\d.]+)vw,(\d+)px\)", CSS)
    check(size is not None and h2_size is not None, "Section titles and h2 need clamp() font sizes.")
    check(int(size.group(1)) > int(h2_size.group(1)) and int(size.group(3)) > int(h2_size.group(3)),
          f"Section titles must be larger than the former h2 size: {size.group(0)} vs {h2_size.group(0)}")

    # ---- Images: alternatives and files ----
    for image in parser.images:
        if image.get("id") == "viewer-image":
            continue  # Populated from the selected accessible gallery image.
        check(bool(image.get("alt", "").strip()) or (image.get("aria-hidden") == "true" and "alt" in image), f"Missing image alternative text: {image.get('src')}")
        source = ROOT / image["src"]
        check(source.is_file(), f"Missing image asset: {source}")

    # ---- Intro / Hero section: architectural-model.webp with Blender-rendered scanned walkers and simplified caption ----
    no_pref_ctx = "@media (prefers-reduced-motion: no-preference)"

    def attr(node: Node, name: str) -> str:
        # html.parser lower-cases every attribute name, SVG camelCase included (viewBox -> viewbox, preserveAspectRatio
        # -> preserveaspectratio). Browsers tokenise the same way and only restore the SVG casing afterwards, so the
        # lower-cased key is the correct one to read; a camelCase lookup can never match and would fail silently.
        return node.attrs.get(name.lower(), "")
    hero_fig = doc.find("figure", "hero-model")
    check(hero_fig is not None, "Hero model figure is present.")
    hero_img = hero_fig.find("img")
    check(hero_img is not None and hero_img.attrs.get("src") == "assets/brief/architectural-model.webp", "Hero uses architectural-model.webp.")
    hero_cap = hero_fig.find("figcaption")
    check(hero_cap is not None, "Hero has figcaption.")
    cap_spans = [s.text().strip() for s in hero_cap.find_all("span")]
    check(cap_spans == ["Architecture in miniature", "Architectural model"], f"Hero caption must read 'Architecture in miniature' / 'Architectural model': {cap_spans}")
    check((hero_img.attrs.get("width"), hero_img.attrs.get("height")) == ("1800", "1092"), "Hero image declares the raster's 1800x1092 size.")
    stage = hero_fig.find("div", "hero-image-stage")
    check(stage is not None and hero_img in list(stage.iter()), "The hero image sits in .hero-image-stage.")
    for legacy in ("hero-walkers", "walker-active", "walker-group", "walker-frames", "walker-cross", "walker-stride"):
        check(legacy not in HTML and legacy not in CSS and legacy not in JS, f"The hand-written hero walker overlay is replaced by the generated scene overlays (all nine scenes + hero): {legacy}")

    # ---- Scene people (user request, 3 October 2026): animated real scanned people in EVERY scene ----
    # Shared contract (research-people/all-scenes-contract.txt): assets/people/scenes.json lists the nine studies with,
    # per actor, a Blender-rendered RGBA strip under assets/people/scenes/ plus its measured metadata. The render workflow
    # owns the manifest and the strips; scripts/build_scene_overlays.py (owned here) turns them into one static,
    # decorative inline <svg class="scene-overlay"> per gallery study and one for the hero (study-1), and this gate
    # verifies the manifest, every strip, the generated markup, the CSS/JS runtime wiring and the generator's --check.
    people_dir = ROOT / "assets/people"
    scenes_path = people_dir / "scenes.json"
    scene_generator = ROOT / "scripts" / "build_scene_overlays.py"
    render_hint = "render the scene strips first (render workflow), then run: python3 scripts/build_scene_overlays.py --write"
    check(scenes_path.is_file(), f"assets/people/scenes.json is missing; {render_hint}")
    scenes_manifest = json.loads(scenes_path.read_text(encoding="utf-8"))
    check(scenes_manifest.get("version") == 1 and scenes_manifest.get("duration") == 8.8, f"scenes.json must be contract version 1 with duration 8.8: {scenes_manifest.get('version')} / {scenes_manifest.get('duration')}")
    scene_seconds = float(scenes_manifest["duration"])
    scenes = scenes_manifest.get("scenes")
    check(isinstance(scenes, list) and [s.get("id") for s in scenes] == [f"study-{i}" for i in range(1, 10)], "scenes.json must list study-1 .. study-9 in order.")
    check([s.get("source") for s in scenes] == EXPECTED_GALLERY, f"Scene sources must be the nine gallery originals in order: {[s.get('source') for s in scenes]}")
    base_hashes = baseline_hashes()
    for scene in scenes:
        name = Path(scene["source"]).name
        expected_sha = base_hashes.get(scene["source"]) or FEEDBACK_2_MANIFEST["assets"][name]["sha256"]
        check(str(scene.get("source_sha256")).lower() == expected_sha.lower() == sha256(ROOT / scene["source"]).lower(),
              f"{scene['id']}: source_sha256 must equal the unchanged original's hash ({name}); the photos are never edited, people are overlaid.")
        check(isinstance(scene.get("description"), str) and len(scene["description"].split()) >= 3, f"{scene['id']}: description must say what the people do.")
        check(isinstance(scene.get("actors"), list) and scene["actors"], f"{scene['id']}: every scene has at least one actor.")
    provenance_path = people_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
    for file, record in provenance.get("outputs", {}).items():  # legacy hero strips, if still recorded, must be real and current
        check((people_dir / file).is_file() and sha256(people_dir / file).lower() == str(record.get("sha256")).lower(), f"provenance.json records a strip that is missing or changed: {file}")
    check(all(p.suffix.lower() in {".png", ".json"} for p in people_dir.rglob("*") if p.is_file()), "Only rendered PNG sprites and JSON records may live in assets/people; raw model data stays in research-people.")

    def check_strip(actor: dict, scene_id: str) -> dict:
        """Every strip is a genuine Blender render of the named scan: measured per profile, never assumed from another strip."""
        rel = actor.get("strip", "")
        strip = ROOT / rel
        meta_path = strip.with_suffix(".json")
        check(rel.startswith("assets/people/scenes/") and rel.endswith(".png") and "/" not in rel[len("assets/people/scenes/"):] and actor.get("metadata") == rel[:-4] + ".json",
              f"{scene_id}/{actor.get('id')}: strip must be assets/people/scenes/<name>.png with metadata <name>.json: {rel} / {actor.get('metadata')}")
        check(strip.is_file() and meta_path.is_file(), f"{rel} or its metadata is missing; {render_hint}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        file = strip.name
        check(meta.get("file") == file and meta.get("person") == actor.get("person") in ("Nathan", "Carla"), f"{meta_path.name} must describe {file} for {actor.get('person')}: {meta.get('file')} / {meta.get('person')}")
        fw, fh, n = meta["frame_width"], meta["frame_height"], meta["frame_count"]
        expected_n = 160 if scene_id == "study-1" else 96
        check(n == expected_n, f"{file}: {scene_id} strips hold exactly {expected_n} frames (hero walk/sit 160, interior motion 96): {n}")
        check(fw >= 128 and fh >= 192 and meta["strip_width"] == fw * n and meta["strip_height"] == fh, f"{file}: metadata must describe one horizontal strip of {n} frames: {fw}x{fh}, {meta['strip_width']}x{meta['strip_height']}")
        check(png_ihdr_size(strip) == (fw * n, fh), f"{file}: strip PNG header must be {fw * n}x{fh}: {png_ihdr_size(strip)}")
        check(sha256(strip).lower() == str(meta.get("sha256")).lower(), f"{file}: the strip's SHA-256 must match its metadata (re-run the render/pack step after any change).")
        facts = json.dumps(meta).lower()
        check("blender" in facts and "renderpeople" in facts, f"{file}: metadata must record its provenance: the Blender render and the licensed Renderpeople scan.")
        body = meta["body"]
        check(2 <= body["top"] < body["bottom"] <= fh - 3 and 2 <= body["left"] < body["right"] <= fw - 3, f"{file}: the union body box must sit inside the frame with a margin (no clipped head or feet): {body}")
        check(meta["visible_body_height"] == body["bottom"] - body["top"] + 1 and abs(meta["foot_anchor"] - (body["bottom"] + 1)) <= 1, f"{file}: visible_body_height/foot_anchor must derive from the body box: {meta['visible_body_height']} {meta['foot_anchor']} {body}")
        check(0.5 * fh <= meta["visible_body_height"] <= 0.95 * fh, f"{file}: the figure should fill most of the frame height: {meta['visible_body_height']} of {fh}")
        check(len(meta["frames"]) == n and all(2 <= f["top"] < f["bottom"] <= fh - 3 and 2 <= f["left"] < f["right"] <= fw - 3 for f in meta["frames"]), f"{file}: every frame's body box must stay inside the frame with a margin.")
        check(all(f["bottom"] - f["top"] + 1 >= 0.6 * meta["visible_body_height"] for f in meta["frames"]), f"{file}: no frame collapses or cuts the body (first and last frames are both safe rest poses).")
        if "seat_anchor" in meta:
            check(isinstance(meta["seat_anchor"], list) and len(meta["seat_anchor"]) == 2 and 0 <= meta["seat_anchor"][0] <= fw and 0 <= meta["seat_anchor"][1] <= fh, f"{file}: seat_anchor must be [x,y] inside the frame: {meta['seat_anchor']}")
        if Image is not None:
            with Image.open(strip) as im:
                check(im.mode == "RGBA" and im.size == (fw * n, fh), f"{file}: the strip must be an RGBA PNG of {fw * n}x{fh}: {im.mode} {im.size}")
                check(im.getchannel("A").getextrema() == (0, 255), f"{file}: the strip needs a fully transparent background and fully opaque body pixels.")
                frames = [im.crop((i * fw, 0, (i + 1) * fw, fh)) for i in range(n)]
                boxes = [f.getchannel("A").point(lambda a: 255 if a > 25 else 0).getbbox() for f in frames]
                check(all(boxes), f"{file}: every frame of the strip must contain a figure.")
                for i, (box, rec) in enumerate(zip(boxes, meta["frames"])):
                    check(box[0] >= 2 and box[1] >= 2 and box[2] <= fw - 2 and box[3] <= fh - 2, f"{file} frame {i}: the figure touches the frame edge (clipped head, hand or foot): {box}")
                    check(max(abs(box[0] - rec["left"]), abs(box[1] - rec["top"]), abs(box[2] - 1 - rec["right"]), abs(box[3] - 1 - rec["bottom"])) <= 1, f"{file} frame {i}: metadata box {rec} differs from the actual alpha box {box}")
                distinct_count = len({f.tobytes() for f in frames})
                check(distinct_count >= min(80, math.ceil(0.8 * n)), f"{file}: at least 80 distinct frames (or 80% for shorter strips) required ({distinct_count}/{n}): real motion allowing natural stride cycles and neutral pauses, not a repeated still.")
                centres, feet, widths = [(b[0] + b[2]) / 2 for b in boxes], [b[3] for b in boxes], [b[2] - b[0] for b in boxes]
                check(max(centres) - min(centres) <= 0.25 * fw and max(feet) - min(feet) <= (0.18 if scene_id == "study-1" else 0.1) * fh, f"{file}: motion remains in place; hero permits projected foot advance when knees bend into the seat (travel is applied by the overlay path): centres {centres[:4]}.. feet {feet[:4]}..")
                if any(actor["travel"]):
                    check(max(widths) - min(widths) >= 0.08 * fw, f"{file}: a travelling actor's stride must open and close (limb spread varies): {widths}")
                saturation = [ImageStat.Stat(f.convert("RGB").convert("HSV").getchannel("S"), f.getchannel("A").point(lambda a: 255 if a > 128 else 0)).mean[0] for f in frames]
                check(max(saturation) <= 140, f"{file}: opaque pixels must be the textured, muted figure (a magenta missing-texture render would be fully saturated): {saturation[:4]}")
        return meta

    # Generated overlays: one per gallery study inside its link (meet, image at natural aspect) and one hero copy of
    # study-1 (slice, matching object-fit: cover). Every actor is placed from ITS OWN metadata (scale = body_height /
    # visible_body_height, feet or seat anchor), carries its own frame count and travel as custom properties, has a
    # shadow under its foot anchor and, optionally, a stationary evenodd clip (visible_path) OUTSIDE the moving group.
    gallery_links = [a for a in doc.find_all("a") if "data-lightbox" in a.attrs]
    check(len(gallery_links) == 9, f"Nine gallery links are expected before the scene checks: {len(gallery_links)}")
    scene_marker = lambda instance, sid, kind: f"<!-- SCENE:{instance}:{sid}:{kind} -->"
    strip_metas: dict[str, dict] = {}
    persons_seen: set[str] = set()
    actor_counts: dict[str, int] = {}
    css_num = lambda value: float(re.fullmatch(r"(-?[\d.]+)(?:px|s)?", value).group(1))

    def style_vars(node: Node) -> dict[str, str]:
        return dict(re.findall(r"--([\w-]+):([^;]+)", node.attrs.get("style", "")))

    def check_overlay(overlay: Node, scene: dict, instance: str) -> list[dict]:
        sid, W, H = scene["id"], scene["width"], scene["height"]
        where = f"{instance}/{sid}"
        check(overlay.attrs.get("data-scene") == sid and overlay.attrs.get("aria-hidden") == "true" and overlay.attrs.get("focusable") == "false",
              f"{where}: the overlay is decorative (aria-hidden, not focusable) and names its scene: {overlay.attrs}")
        check(attr(overlay, "viewBox").split() == ["0", "0", str(W), str(H)], f"{where}: the overlay viewBox is the source image's {W}x{H} pixel space: {attr(overlay, 'viewBox')}")
        check(attr(overlay, "preserveAspectRatio") == ("xMidYMid slice" if instance == "hero" else "xMidYMid meet"),
              f"{where}: hero overlays use xMidYMid slice (cover), gallery/viewer overlays xMidYMid meet: {attr(overlay, 'preserveAspectRatio')}")
        actors = [g for g in overlay.find_all("g", "scene-actor")]
        check(len(actors) == len(scene["actors"]), f"{where}: the overlay must hold exactly the manifest's {len(scene['actors'])} actors: {len(actors)}")
        clip_ids = {c.attrs.get("id") for c in overlay.find_all("clippath")}
        check(all(cid and cid.startswith(f"{instance}-{sid}-") for cid in clip_ids), f"{where}: every clipPath id carries the instance/scene prefix so copies never collide: {sorted(clip_ids)}")
        placed = []
        for g, spec in zip(actors, scene["actors"]):
            aid = spec["id"]
            awhere = f"{where}/{aid}"
            meta = strip_metas.setdefault(spec["strip"], check_strip(spec, sid))
            fw, fh, n = meta["frame_width"], meta["frame_height"], meta["frame_count"]
            check(g.attrs.get("data-actor") == aid and g.attrs.get("data-person") == spec["person"] == meta["person"], f"{awhere}: actor group names its actor and person: {g.attrs}")
            v = style_vars(g)
            check(set(v) >= {"frames", "rest", "tx", "ty", "scene-seconds", "move-seconds"}, f"{awhere}: actor group must carry --frames/--rest/--tx/--ty/--scene-seconds/--move-seconds: {v}")
            check(int(v["frames"]) == n and css_num(v["rest"]) == -(n - 1) * fw, f"{awhere}: --frames/--rest must come from this strip's metadata ({n} frames of {fw}px): {v}")
            check(abs(css_num(v["tx"]) - spec["travel"][0]) <= 0.01 and abs(css_num(v["ty"]) - spec["travel"][1]) <= 0.01, f"{awhere}: --tx/--ty must equal the manifest travel {spec['travel']}: {v}")
            check(abs(css_num(v["scene-seconds"]) - spec["duration"]) <= 0.01 and abs(css_num(v["move-seconds"]) - spec["duration"] * spec["move_until"]) <= 0.01 and 0 < spec["move_until"] <= 1,
                  f"{awhere}: duration and travel follow the actor's activity timing: {v}")
            check(abs(css_num(v["scene-delay"])-spec["delay"]) <= .01 and css_num(v["scene-seconds"])+css_num(v["scene-delay"]) <= 8.801 and css_num(v["move-seconds"]) <= css_num(v["scene-seconds"]), f"{awhere}: delay plus take finishes within 8.8s: {v}")
            check(("filter:grayscale(1)" in g.attrs.get("style", "")) == (spec["filter"] == "grayscale(1)") and ("opacity" in g.attrs) == (spec["opacity"] != 1), f"{awhere}: filter/opacity follow the manifest: {g.attrs}")
            move = g.find("g", "actor-move")
            sprite = g.find("svg", "actor-sprite")
            frames = g.find("g", "actor-frames")
            image = g.find("image", "actor-strip")
            check(move is not None and sprite is not None and frames is not None and image is not None and move in list(g.iter()) and sprite in list(move.iter()) and frames in list(sprite.iter()) and image in list(frames.iter()),
                  f"{awhere}: actor = g.scene-actor > g.actor-move > svg.actor-sprite > g.actor-frames > image.actor-strip")
            check(attr(sprite, "viewBox").split() == ["0", "0", str(fw), str(fh)], f"{awhere}: the sprite viewport shows exactly one {fw}x{fh} frame: {sprite.attrs}")
            x, y, wd, ht = (float(attr(sprite, k)) for k in ("x", "y", "width", "height"))
            s = spec["body_height"] / meta["visible_body_height"]
            check(abs(wd - fw * s) <= 0.02 and abs(ht - fh * s) <= 0.02, f"{awhere}: viewport size = frame x (body_height / visible_body_height): {wd}x{ht} vs {fw * s:.2f}x{fh * s:.2f}")
            ax, ay = (fw / 2, meta["foot_anchor"]) if spec["anchor"] == "feet" else tuple(meta["seat_anchor"])
            check(abs(x - (spec["position"][0] - ax * s)) <= 0.02 and abs(y - (spec["position"][1] - ay * s)) <= 0.02,
                  f"{awhere}: the {spec['anchor']} anchor must sit at position {spec['position']}: viewport at ({x},{y}), expected ({spec['position'][0] - ax * s:.2f},{spec['position'][1] - ay * s:.2f})")
            check(attr(image, "href") == spec["strip"] and attr(image, "width") == str(fw * n) and attr(image, "height") == str(fh) and attr(image, "x") == "0" and attr(image, "y") == "0",
                  f"{awhere}: the strip image is the local render at its declared {fw * n}x{fh} size: {image.attrs}")
            check((ROOT / attr(image, "href")).is_file(), f"{awhere}: strip file missing: {attr(image, 'href')}")
            body = meta["body"]
            box = (x + body["left"] * s, y + body["top"] * s, x + (body["right"] + 1) * s, y + (body["bottom"] + 1) * s)
            end = (box[0] + spec["travel"][0], box[1] + spec["travel"][1], box[2] + spec["travel"][0], box[3] + spec["travel"][1])
            check(0 <= end[0] and end[2] <= W and 0 <= end[1] and end[3] <= H, f"{awhere}: the body must finish inside the {W}x{H} image: {tuple(round(c) for c in end)}")
            check(min(box[2], W) - max(box[0], 0) > 0 and min(box[3], H) - max(box[1], 0) > 0, f"{awhere}: the body must start on the image: {tuple(round(c) for c in box)}")
            check(0.04 * H <= spec["body_height"] <= 0.9 * H, f"{awhere}: body_height {spec['body_height']} is implausible for a {W}x{H} image")
            shadow = g.find("ellipse", "actor-shadow")
            if spec["shadow"] is None:
                check(shadow is None, f"{awhere}: no shadow was requested")
            else:
                check(shadow is not None and shadow in list(move.iter()), f"{awhere}: the shadow moves with the actor (inside .actor-move)")
                cx, cy = float(attr(shadow, "cx")), float(attr(shadow, "cy"))
                fill = re.fullmatch(r"rgba\(30,42,28,([\d.]+)\)", attr(shadow, "fill"))
                check(abs(cx - (x + meta.get("ground_anchor", [fw / 2, meta["foot_anchor"]])[0] * s)) <= 0.02 and abs(cy - (y + meta.get("ground_anchor", [fw / 2, meta["foot_anchor"]])[1] * s)) <= 0.02 and abs(float(attr(shadow, "rx")) - spec["shadow"]["rx"]) <= 0.01
                      and abs(float(attr(shadow, "ry")) - spec["shadow"]["ry"]) <= 0.01 and fill is not None and abs(float(fill.group(1)) - spec["shadow"]["opacity"]) <= 0.01
                      and (rot := re.match(r"rotate\((-?[\d.]+) ", attr(shadow, "transform"))) is not None and abs(float(rot.group(1)) - spec["shadow"]["rotate"]) <= 0.01,
                      f"{awhere}: the shadow ellipse sits under the foot anchor with the manifest's rx/ry/opacity/rotate: {shadow.attrs}")
            clip = g.attrs.get("clip-path", "")
            if spec["visible_path"] is None:
                check(not clip, f"{awhere}: no visible_path, so no clip")
            else:
                cid = f"{instance}-{sid}-{aid}-visible"
                clip_node = next((c for c in overlay.find_all("clippath") if c.attrs.get("id") == cid), None)
                path = clip_node.find("path") if clip_node is not None else None
                check(clip == f"url(#{cid})" and path is not None and path.attrs.get("clip-rule") == "evenodd" and " ".join(path.attrs.get("d", "").split()) == " ".join(spec["visible_path"].split())
                      and attr(clip_node, "clipPathUnits") == "userSpaceOnUse",
                      f"{awhere}: visible_path becomes an evenodd clipPath in source coordinates, referenced as {cid}: {clip} / {clip_node.attrs if clip_node else None}")
                check("clip-path" not in move.attrs and "clip-path" not in sprite.attrs, f"{awhere}: the clip stays outside the moving group so foreground occluders remain stationary")
            persons_seen.add(spec["person"])
            placed.append({"id": aid, "person": spec["person"], "strip": spec["strip"], "n": n, "box": box, "end": end, "attrs": {k: re.sub(r"^url\(#(?:hero|gallery)-", "url(#", val) for k, val in g.attrs.items()}})
        return placed

    for index, scene in enumerate(scenes, start=1):
        sid = scene["id"]
        link = gallery_links[index - 1]
        img = link.find("img")
        check(link.attrs.get("href") == scene["source"] and img is not None and (img.attrs.get("width"), img.attrs.get("height")) == (str(scene["width"]), str(scene["height"])),
              f"{sid}: scene size must match the gallery image's declared size and source: {scene['source']} {scene['width']}x{scene['height']}")
        overlays = link.find_all("svg", "scene-overlay")
        check(len(overlays) == 1, f"{sid}: exactly one scene overlay inside a.study-image: {len(overlays)}")
        order = list(link.iter())
        check(order.index(img) < order.index(overlays[0]) and link.find("span", "image-open") is not None and order.index(overlays[0]) < order.index(link.find("span", "image-open")),
              f"{sid}: the overlay follows the original image and precedes the open arrow inside the link")
        check(HTML.count(scene_marker("gallery", sid, "START")) == 1 and HTML.count(scene_marker("gallery", sid, "END")) == 1, f"{sid}: exactly one managed SCENE:gallery block")
        actor_counts[sid] = len(check_overlay(overlays[0], scene, "gallery"))
        strips = {a["strip"] for a in scene["actors"]}
        check(len(strips) >= 1 and all(strip_metas[s]["frame_count"] >= 32 for s in strips), f"{sid}: at least one distinct real render asset with moving frames: {sorted(strips)}")
    check(persons_seen == {"Nathan", "Carla"}, f"Across the nine scenes both scanned people appear (realistic, diverse group): {sorted(persons_seen)}")
    hero_overlays = stage.find_all("svg", "scene-overlay")
    check(len(hero_overlays) == 1 and hero_overlays[0].attrs.get("data-scene") == "study-1", f"The hero shows the study-1 scene configuration: {[o.attrs.get('data-scene') for o in hero_overlays]}")
    check(HTML.count(scene_marker("hero", "study-1", "START")) == 1 and HTML.count(scene_marker("hero", "study-1", "END")) == 1, "Exactly one managed SCENE:hero block.")
    hero_actors = check_overlay(hero_overlays[0], scenes[0], "hero")
    gallery_one = check_overlay(gallery_links[0].find("svg", "scene-overlay"), scenes[0], "gallery")
    check([a["attrs"] for a in hero_actors] == [a["attrs"] for a in gallery_one], "Hero and gallery study-1 use the same actor configuration (only the id prefix differs).")
    check("Renderpeople" in HTML and "Blender" in HTML and "Nathan" in HTML and "Carla" in HTML, "The generated markup states that the people are Blender renders of licensed Renderpeople scans (Nathan and Carla).")
    # Hero: walk INTO the backyard (travel during the first half, move_until 0.5), then stop, turn and chat for the rest.
    hero_specs = scenes[0]["actors"]
    check(len(hero_specs) == 2 and {a["person"] for a in hero_specs} == {"Nathan", "Carla"}, f"The hero scene shows Nathan and Carla together: {[a['person'] for a in hero_specs]}")
    for spec in hero_specs:
        check(math.hypot(*spec["travel"]) >= 40 and spec["move_until"] == 0.5, f"study-1/{spec['id']}: arrives by walking (travel >= 40 source px) during exactly the first half: {spec['travel']} / {spec['move_until']}")
        check(re.search(r"chat|talk|convers|turn", spec["motion_note"], re.I) is not None, f"study-1/{spec['id']}: motion_note must describe the stop/turn/chat: {spec['motion_note']!r}")
        meta = strip_metas[spec["strip"]]
        check(meta["frame_count"] == 160, f"study-1/{spec['id']}: 160-frame walk/turn/sit strip: {meta['frame_count']}")
        contact = meta.get("contact_validation", {})
        check(contact.get("max_planted_ankle_error_m", 1) < .003, f"{spec['id']}: planted ankle stays within 3mm of ground-contact target")
        check(contact.get("max_planted_foot_matrix_difference", 1) < .001, f"{spec['id']}: planted shoe orientation stays fixed")
        soles = {row["frame"]: row["soles"] for row in contact.get("sole_checks", [])}
        check(all(f in soles for f in range(80,107)), f"{spec['id']}: every turning frame has evaluated shoe-contact evidence")
        check(all(abs(min(soles[f].values())) < .005 for f in range(80,107) if f in soles), f"{spec['id']}: at least one shoe supports every turning frame within 5mm")
        check(all(f in soles and all(abs(z) < .005 for z in soles[f].values()) for f in [106,118,130,142,160]), f"{spec['id']}: both shoe soles remain grounded during lowering and seated hold")
        half = meta["frames"][80:]
        check(len({json.dumps(f) for f in half}) >= 2, f"study-1/{spec['id']}: the chat half still moves (frame boxes differ after the stop)")
    check(len({a["strip"] for a in hero_specs}) == 2 and len({strip_metas[a["strip"]]["sha256"] for a in hero_specs}) == 2, "The two hero people are two different renders, never one strip under two names.")
    for a, b in zip(hero_actors, hero_actors[1:]):
        check(a["end"][2] <= b["end"][0] or b["end"][2] <= a["end"][0] or abs(a["end"][3] - b["end"][3]) > 8, f"Hero people must not end up on top of each other: {a['end']} / {b['end']}")

    # Managed block safety (the same rules as the plan SVG, plus local strip hrefs only) and generator determinism.
    for instance, sid in [("hero", "study-1")] + [("gallery", s["id"]) for s in scenes]:
        a, b = HTML.index(scene_marker(instance, sid, "START")), HTML.index(scene_marker(instance, sid, "END"))
        block = HTML[a:b]
        svg_text = block[block.index("<svg"):]
        try:
            root_el = ET.fromstring(svg_text)
        except ET.ParseError as exc:
            raise AssertionError(f"{instance}/{sid}: the overlay must be well-formed generator output: {exc}")
        names = {local(e.tag).lower() for e in root_el.iter()}
        for banned in ("script", "foreignobject", "iframe", "a", "animate", "animatetransform", "animatemotion", "set", "style", "use"):
            check(banned not in names, f"{instance}/{sid}: <{banned}> is not allowed in a scene overlay.")
        for e in root_el.iter():
            for key, value in e.attrib.items():
                name = local(key).lower()
                check(not name.startswith("on"), f"{instance}/{sid}: inline event handler {name} is not allowed.")
                if name == "href":
                    check(value.startswith("assets/people/scenes/") and value.endswith(".png") and (ROOT / value).is_file(), f"{instance}/{sid}: only local rendered strips may be referenced: {value}")
                if name == "clip-path":
                    ref = re.fullmatch(r"url\(#([\w-]+)\)", value)
                    check(ref is not None and any(x.get("id") == ref.group(1) for x in root_el.iter()), f"{instance}/{sid}: clip-path must reference a clipPath defined in the same overlay: {value}")
        check("javascript:" not in svg_text.lower() and not re.search(r"https?://(?!www\.w3\.org/)", svg_text) and "<a " not in block, f"{instance}/{sid}: no scripts, external URLs or links in the overlay.")
    check(scene_generator.is_file(), "Missing scripts/build_scene_overlays.py.")
    result = subprocess.run([sys.executable, str(scene_generator), "--check"], cwd=ROOT, capture_output=True, text=True, timeout=180)
    check(result.returncode == 0, f"build_scene_overlays.py --check failed (index.html stale or manifest/strips invalid?): {(result.stdout + result.stderr).strip()[-600:]}")
    spec_mod = importlib.util.spec_from_file_location("build_scene_overlays", scene_generator)
    gen = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(gen)
    try:
        gen_manifest, gen_metas = gen.load_manifest()
    except gen.SceneError as exc:
        raise AssertionError(f"Generator rejects the manifest: {exc}")
    check(gen.render_blocks(gen_manifest, gen_metas) == gen.render_blocks(gen_manifest, gen_metas), "The generator is deterministic (two renders are byte-identical).")
    check(gen.apply_all(HTML, gen.render_blocks(gen_manifest, gen_metas)) == HTML, "Re-applying the generated blocks to index.html changes nothing (idempotent, byte-identical).")

    # Runtime wiring: finite single sequence inside the motion opt-in, gated on .motion-ready and the observer class; the
    # base (no JS / reduced motion) transforms rest on the last frame at the end position; nothing is ever hidden.
    blocks = css_blocks()
    scene_motion = [(ctx, head, d) for ctx, head, d in blocks if re.search(r"\.actor-(?:move|frames)\b", head) and re.search(r"(?:^|;)animation:", d)]
    check(scene_motion and all(ctx == no_pref_ctx and ".motion-ready" in head and ".scene-active" in head for ctx, head, _ in scene_motion),
          f"Scene animations live only in the motion opt-in and need .motion-ready and .scene-active: {[(c, h) for c, h, _ in scene_motion]}")
    frames_rule = next((d for _, head, d in scene_motion if ".actor-frames" in head), "")
    frames_anim = re.search(r"animation:scene-frames var\(--scene-seconds,([\d.]+)s\) steps\(var\(--frames,\d+\),jump-none\) both", frames_rule)
    check(frames_anim is not None and abs(float(frames_anim.group(1)) - scene_seconds) < 0.01, f"Frames advance once over the scene duration with steps(frames, jump-none), first to last frame, never a blank column: {frames_rule}")
    move_rule = next((d for _, head, d in scene_motion if ".actor-move" in head), "")
    move_anim = re.search(r"animation:scene-travel var\(--move-seconds,([\d.]+)s\) [^;]* both", move_rule)
    check(move_anim is not None and abs(float(move_anim.group(1)) - scene_seconds * 0.5) < 0.01, f"The travel runs once over move_until x duration and then holds (fill both): {move_rule}")
    kf = {head: d for ctx, head, d in blocks if ctx.endswith("@keyframes scene-travel")}
    check(kf.get("from") == "transform:translate(0,0)" and kf.get("to") == "transform:translate(var(--tx,0px),var(--ty,0px))", f"scene-travel moves from the start position to position + travel without fading: {kf}")
    kf = {head: d for ctx, head, d in blocks if ctx.endswith("@keyframes scene-frames")}
    check(kf.get("from") == "transform:translateX(0)" and kf.get("to") == "transform:translateX(var(--rest,0px))", f"scene-frames shifts the strip from frame 0 to the last frame: {kf}")
    check("transform:translate(var(--tx,0px),var(--ty,0px))" in css_rule(".actor-move") and "transform:translateX(var(--rest,0px))" in css_rule(".actor-frames"),
          "Without JS or with reduced motion the actors rest on their LAST frame at their END position (base transforms).")
    overlay_rule = css_rule(".scene-overlay")
    check("position:absolute" in overlay_rule and "inset:0" in overlay_rule and "pointer-events:none" in overlay_rule, f"The overlay covers its image box and never intercepts input: {overlay_rule}")
    check(any(ctx == no_pref_ctx and head == ".motion-ready .scene-overlay:not(.scene-active) .actor-move" and d == "transform:none" for ctx, head, d in blocks)
          and any(ctx == no_pref_ctx and head == ".motion-ready .scene-overlay:not(.scene-active) .actor-frames" and d == "transform:none" for ctx, head, d in blocks),
          "While motion is live but not yet triggered the actors wait on their first frame at the start position (no jump when the sequence begins).")
    check(not any(re.search(r"scene-|actor-", head) and re.search(r"opacity:0(?![.\d])|visibility:hidden|display:none", d) for _, head, d in blocks), "Scene people are never hidden by CSS.")
    zoom_heads = [head for _, head, d in blocks if re.search(r"\.study-image:hover (?:img|\.scene-overlay)\b", head) and "transform:scale" in d]
    check(all({".study-image:hover img", ".study-image:hover .scene-overlay"} <= {p.strip() for p in head.split(",")} for head in zoom_heads),
          f"The gallery hover zoom scales the photo and its people overlay together, never the photo alone: {zoom_heads}")
    check("position:relative" in css_rule(".viewer-stage"), "The lightbox stage positions the cloned overlay over #viewer-image.")
    check(any(head == ".document-hidden *" and "animation-play-state:paused!important" in d for _, head, d in blocks) and "visibilitychange" in JS and "'document-hidden'" in JS,
          "A hidden page pauses every running animation in place (app.js toggles .document-hidden on visibilitychange).")
    check("IntersectionObserver" in JS and "'.hero-image-stage .scene-overlay, .study-image .scene-overlay'" in JS and "classList.toggle('scene-paused', !isIntersecting)" in JS and "sceneObserver.unobserve" not in JS
          and JS.count("classList.add('scene-active')") == 2 and "scene-active" not in HTML,
          "Every overlay (hero and nine studies) starts once when app.js observes it intersecting (no entry-time or timer trigger); the lightbox clone is the only other start.")
    check("copy.classList.remove('scene-active', 'scene-paused')" in JS and "animation-delay:var(--scene-delay,0s)" in CSS,
          "Viewer clones clear offscreen pause state; both frame and travel animations use actor delay.")
    check("cloneNode(true)" in JS and "clearViewerScene()" in JS and "viewerStage.append(copy)" in JS and "`viewer-${" in JS and "dialog.addEventListener('close', () => { clearViewerScene();" in JS,
          "The lightbox clones the trusted generated overlay, re-prefixes its ids, replays it, and removes it on close.")
    check(JS.count("innerHTML") == 1 and "menu.innerHTML = open ?" in JS, "Only the menu label is written as markup; scene overlays are DOM clones, never innerHTML.")
    viewer_stage = next((n for n in doc.find_all("div", "viewer-stage")), None)
    check(viewer_stage is not None and any(n.attrs.get("id") == "viewer-image" for n in viewer_stage.iter()) and not viewer_stage.find_all("svg"),
          "#viewer-image sits in .viewer-stage, which holds no overlay until app.js clones one.")

    # Gallery arrow affordance: see-through disc (alpha .30-.40), no blur, 44px target, thin glyph.
    open_rule = css_rule(".image-open")
    arrow_bg = re.search(r"(?:^|;)background:rgba\(248,245,238,(0?\.\d+)\)", open_rule)
    check(arrow_bg is not None and 0.30 <= float(arrow_bg.group(1)) <= 0.40, f"Gallery arrow disc must be see-through (alpha .30-.40): {open_rule[:160]}")
    check("backdrop-filter" not in CSS, "The heavy blur behind the gallery arrow is removed.")
    check("width:44px" in open_rule and "height:44px" in open_rule and "font-weight:300" in open_rule, "Gallery arrow keeps its 44px target and thin glyph.")

    # ---- Gallery: nine studies, title-only captions, descriptions in alt text ----
    work = sections["projects"]
    lightbox_links = [a for a in doc.find_all("a") if "data-lightbox" in a.attrs]
    check(len(lightbox_links) == 9, f"The gallery must contain exactly nine lightbox images, found {len(lightbox_links)}.")
    check(HTML.count("data-lightbox") == 9, "Unexpected extra data-lightbox markers.")
    check(all(work in list(a.ancestors()) for a in lightbox_links), "All nine studies sit in the Gallery section.")
    gallery_sources = [a.attrs.get("href") for a in lightbox_links]
    check(gallery_sources == EXPECTED_GALLERY, f"Gallery image order differs from the agreed nine: {gallery_sources}")
    selection = json.loads((ROOT / "assets/brand/manifest.json").read_text(encoding="utf-8"))["gallery_selection"]
    check(selection["review_image_numbers"] == [1, 2, 8, 11, 14, 18], "Keep the six image numbers supplied by Heather.")
    check([f"assets/brief/{name}" for name in selection["filenames"]] == EXPECTED_GALLERY[:6], "The first six gallery images must remain the numbered selection.")
    check(EXPECTED_GALLERY[6:] == [f"assets/brief/{name}" for name in FEEDBACK_2_MANIFEST["assets"]], "Feedback 2 images must follow the numbered selection in PDF order.")
    check("data-kind" not in HTML and "dataset.kind" not in JS, "Latest brief: gallery items carry a title only (no kind/description field).")

    brief_manifest = json.loads((ROOT / "assets/brief/manifest.json").read_text(encoding="utf-8"))
    invented_claims = ("award", "client", "completed", "delivered", "built for", "commissioned", "opened", "testimonial", "featured in", "case study")
    titles = []
    for index, link in enumerate(lightbox_links, start=1):
        figure = link.parent
        check(figure is not None and figure.tag == "figure" and {"study", f"study-{index}"} <= figure.classes, f"Gallery item {index} must sit in figure.study.study-{index}.")
        check("study-image" in link.classes, f"Gallery link {index} must be a.study-image.")
        imgs = link.find_all("img")
        check(len(imgs) == 1, f"Gallery link {index} must wrap exactly one image.")
        img = imgs[0]
        href = link.attrs["href"]
        check(img.attrs.get("src") == href, f"Gallery thumbnail and enlarged image differ: {href}")
        check(img.attrs.get("width", "").isdigit() and img.attrs.get("height", "").isdigit(), f"Gallery image needs width and height: {href}")
        size = (int(img.attrs["width"]), int(img.attrs["height"]))
        if Image is not None:
            with Image.open(ROOT / href) as opened:
                check(opened.size == size, f"Declared size {size} differs from file {opened.size}: {href}")
        title = link.attrs.get("data-title", "").strip()
        check(title, f"Gallery link needs data-title: {href}")
        titles.append(title)
        alt = " ".join(img.attrs.get("alt", "").split())
        check(len(alt) >= 30 and alt.lower() != title.lower() and len(alt.split()) >= 6, f"Gallery alt text must carry the description (meaningful, not the title): {href}: {alt!r}")
        check(title in link.attrs.get("aria-label", ""), f"Gallery link accessible name must include its title: {href}")
        caption = figure.find("figcaption")
        check(caption is not None, f"Gallery item needs a caption: {href}")
        check(" ".join(caption.text().split()) == title, f"Latest brief: caption is the title only: {href}: {caption.text()!r}")
        check(len([c for c in caption.iter()]) <= 1, f"Caption holds the title only, no kind/description element: {href}")
        if href.endswith(".png") and "restaurant-" in href:
            check("spatial visualization" in link.attrs.get("aria-label", "").lower(), f"Feedback 2 renders must be described as visualizations: {href}")
            words = " ".join([title, link.attrs.get("aria-label", ""), alt, caption.text()]).lower()
            for claim in invented_claims:
                check(claim not in words, f"Invented claim '{claim}' in gallery text: {href}")
        else:
            record = brief_manifest["assets"][Path(href).name]
            check(size == (record["width"], record["height"]), f"Gallery size differs from brief manifest: {href}")
    check(len(set(titles)) == 9, f"Gallery titles must be unique: {titles}")
    viewer = next((n for n in doc.find_all("dialog") if n.attrs.get("id") == "study-viewer"), None)
    check(viewer is not None and viewer.attrs.get("aria-labelledby") == "viewer-title", "Keep dialog#study-viewer labelled by #viewer-title.")
    viewer_ids = {n.attrs.get("id") for n in viewer.iter() if n.attrs.get("id")}
    check({"viewer-title", "viewer-image", "viewer-prev", "viewer-next", "viewer-count"} <= viewer_ids, f"Viewer controls missing: {viewer_ids}")
    check(not any(re.search(r"kind|desc|caption", i) for i in viewer_ids), f"The viewer shows the title only, with no kind/description element: {viewer_ids}")
    check("viewerTitle.textContent = link.dataset.title" in JS, "The viewer title must come from data-title only.")
    css_no_comments = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    check(not re.search(r"\.study-\d[^{]*\{[^}]*margin-left:-4%", css_no_comments), "The old uniform pairwise -4% overlap must not return (overlaps vary).")

    # ---- Latest brief: full-plan link and pause/resume control removed from the website ----
    js_no_comments = re.sub(r"/\*.*?\*/|^\s*//.*$", "", JS, flags=re.S | re.M)
    for token in ("motion-toggle", "floor-plan-link", "motion-paused", "floor-plan.html"):
        # Comments may mention floor-plan.html (the unlinked review page); rules and code may not.
        check(token not in HTML and token not in css_no_comments and token not in js_no_comments, f"Removed control remains: {token}")
    for phrase in ("full floor plan", "pause motion", "resume motion", "pause", "aria-pressed"):
        check(phrase not in lower_html, f"Removed control text/state remains in index.html: {phrase}")
    check("aria-pressed" not in JS, "No toggle state may remain in app.js.")

    # ---- Inquiry: local preview only (unchanged) ----
    for form in parser.forms:
        check("action" not in form and "method" not in form, "The local inquiry must have no delivery target.")
        check("novalidate" in form, "The inquiry expects the explicit accessible validation path.")
    for control in parser.controls:
        control_id = control.get("id")
        if control_id:
            check(control_id in parser.labels_for, f"Unlabelled form control: {control_id}")

    check('name="budget"' not in HTML, "Do not add an unrequested budget question.")
    check('data-placeholder="portrait"' in HTML and 'data-placeholder="logo"' in HTML, "Reserve the promised portrait and logo.")
    check("heather@kingchingaya.com" in HTML, "Keep the exact user-supplied email.")
    check(HTML.count('href="mailto:heather@kingchingaya.com"') >= 2, "Keep the direct mail links.")
    check("Starting at $350" in HTML, "Preserve the supplied Room Refresh price.")
    check('id="form-fields" disabled' in HTML, "With no JS the form must not submit via a default GET.")
    check("summary.replaceChildren()" in JS and "dd.textContent = value" in JS, "Inquiry content must remain plain text.")
    for privacy in (
        "This form is a preview. Nothing entered here is sent or stored. To get in touch now, email me directly.",
        "Local preview only. No message will be sent.",
        "This is a local preview. Confirming will not send or store your information.",
        "No message was sent and no information was stored. You can email me directly when you’re ready to talk.",
    ):
        check(privacy in HTML, f"Privacy/preview copy changed: {privacy}")
    for sent_claim in ("has been sent", "sent successfully", "successfully sent", "message sent", "we received", "submitted successfully", "thank you for your message"):
        check(sent_claim not in lower_html and sent_claim not in JS.lower(), f"The prototype must never claim delivery: {sent_claim}")

    unsafe_global = ("testimonial", "award-winning", "luxury interiors", "commissioned by", "photographed by")
    for phrase in unsafe_global:
        check(phrase not in lower_html, f"Unsafe portfolio claim found: {phrase}")

    for transport in ("fetch(", "xmlhttprequest", "sendbeacon", "localstorage", "sessionstorage", "websocket", "eventsource", "navigator.serviceworker", "import("):
        check(transport not in JS.lower(), f"The inquiry contains a disallowed data path: {transport}")

    # ---- Motion guard: opt-in, gated on .motion-ready, finite, reduced-motion safe ----
    lower_css = CSS.lower().replace("@media(", "@media (")
    no_pref = "@media (prefers-reduced-motion: no-preference)"
    reduce_q = "@media (prefers-reduced-motion: reduce)"
    check(reduce_q in lower_css, "The reduced-motion media query must remain.")
    check(no_pref in lower_css, "Motion must be opt-in behind prefers-reduced-motion: no-preference.")
    reduced = lower_css.split(reduce_q, 1)[-1]
    check("animation:none" in reduced and "transition:none" in reduced, "Reduced motion must disable animation and transition.")
    check("scroll-behavior:auto" in reduced, "Reduced motion must restore instant scrolling.")
    before_optin = lower_css.split(no_pref)[0]
    check(".reveal" not in before_optin, "Reveal states must live inside the motion opt-in so content stays visible without motion or JS.")
    check("animation:" not in before_optin and "@keyframes" not in before_optin, "Animations must live inside the motion opt-in.")
    check("motion-ready" in JS.lower(), "Reveal styling must be gated on a class the script adds, so content is never hidden when the script fails.")
    check("@import" not in lower_css, "External style imports are not allowed.")
    check("infinite" not in lower_css and "animation-iteration-count" not in lower_css, "Latest brief: no looping animation; every animation is finite (the old sway is removed).")
    check("jasmine-sway" not in lower_css, "The continuous vine sway was removed; motion settles.")

    blocks = css_blocks()
    for name in ("vine-grow", "cluster-bloom", "plan-layer", "scene-travel", "scene-frames"):
        frames = [ctx for ctx, _, _ in blocks if ctx.endswith(f"@keyframes {name}")]
        check(frames, f"Missing @keyframes {name}.")
        check(all(ctx.startswith(no_pref) for ctx in frames), f"@keyframes {name} must live inside the no-preference block.")
        users = [(ctx, head) for ctx, head, decls in blocks if re.search(r"animation(?:-name)?:[^;}]*\b" + name + r"\b", decls)]
        check(users, f"Keyframes {name} are defined but never used.")
        check(all(ctx == no_pref for ctx, _ in users), f"{name} may only be applied inside the no-preference block: {users}")
        check(all("motion-ready" in head for _, head in users), f"{name} must be gated on .motion-ready so nothing is hidden without JS: {users}")
    grow = [decls for ctx, head, decls in blocks if ctx.startswith(no_pref) and "@keyframes vine-grow" in ctx]
    check(any("clip-path:inset(0 100% 0 0)" in d for d in grow) and any(re.search(r"clip-path:inset\(0(?: 0){0,3}\)", d) for d in grow),
          "vine-grow must reveal the strand left to right with clip-path and end fully visible.")
    layer_frames = " ".join(d for ctx, _, d in blocks if "@keyframes plan-layer" in ctx)
    check("opacity:0" in layer_frames and "opacity:1" in layer_frames, "plan-layer must fade a layer in and end fully visible.")
    for ctx, head, decls in blocks:
        if not ctx.startswith(no_pref):
            check("clip-path:inset(0 100%" not in decls, f"A hidden vine clip outside the motion opt-in would hide the vine without motion: {head}")
        if any(stage in head for stage in PLAN_STAGES) and not ctx.startswith(no_pref):
            check(not re.search(r"opacity:0(?![.\d])|visibility:hidden|display:none", decls), f"Plan layers may only start hidden inside the motion opt-in: {head}")
    # Every literal animation shorthand ends within the reveal budget: duration x iteration count + delay.
    for ctx, head, decls in blocks:
        for shorthand in re.findall(r"(?:^|;)animation:([^;}]+)", decls):
            if shorthand.strip() == "none!important" or "calc(" in shorthand:
                continue
            secs = [float(v) / (1000 if u == "ms" else 1) for v, u in re.findall(r"(\d*\.?\d+)(ms|s)\b", shorthand)]
            counts = [int(c) for c in re.findall(r"(?<![\w.%-])(\d+)(?![\w.%])", re.sub(r"\([^)]*\)", "", shorthand))]
            check("infinite" not in shorthand and len(counts) <= 1, f"Animation needs a single finite iteration count: {head} {{animation:{shorthand}}}")
            iterations = counts[0] if counts else 1
            check(secs and secs[0] * iterations + (secs[1] if len(secs) > 1 else 0) <= (8.8 if "scene-frames" in shorthand else MAX_REVEAL_SECONDS),
                  f"Animation must end within {MAX_REVEAL_SECONDS}s (duration x iterations + delay): {head} {{animation:{shorthand}}}")
    # Staged plan reveal: walls/trees (.plan-shell) never animate; fixtures/flooring, then furniture.
    stage_timing = {}
    for ctx, head, decls in blocks:
        m = re.search(r"(?:^|;)animation:([^;}]*\bplan-layer\b[^;}]*)", decls)
        if not m:
            continue
        secs = [float(v) / (1000 if u == "ms" else 1) for v, u in re.findall(r"(\d*\.?\d+)(ms|s)\b", m.group(1))]
        check(len(secs) >= 2, f"plan-layer rules need an explicit duration and delay: {head}")
        check(".floor-plan" in head, f"plan-layer must be scoped to the .floor-plan root: {head}")
        for stage in PLAN_STAGES:
            if stage in head:
                stage_timing[stage] = (secs[1], secs[0] + secs[1])
    check("plan-shell" not in stage_timing, "Walls and trees (.plan-shell) must be visible at once, not animated.")
    check({"plan-fixtures", "plan-furniture"} <= set(stage_timing), f"Both later plan stages must be staged: {stage_timing}")
    check(0 < stage_timing["plan-fixtures"][0] < stage_timing["plan-furniture"][0], f"Fixtures/flooring follow the walls, furniture comes last: {stage_timing}")
    check(max(end for _, end in stage_timing.values()) <= MAX_REVEAL_SECONDS, f"The plan reveal must end within {MAX_REVEAL_SECONDS}s: {stage_timing}")

    # ---- No external resources ----
    check(not re.search(r"https?://", html_no_ns), "HTML must not reference external URLs (mailto only).")
    check(not re.search(r"https?://", CSS), "CSS must not reference external URLs.")
    check(not re.search(r"url\(\s*['\"]?(?:https?:)?//", CSS), "CSS must not load protocol-relative resources.")
    for match in re.findall(r"url\(\s*['\"]?([^'\")]+)", CSS):
        check(not match.startswith("data:") or match.startswith("data:,"), f"No inline raster data in CSS: {match[:40]}")
        if not match.startswith("data:"):
            check((ROOT / match).is_file(), f"CSS references a missing local file: {match}")

    # ---- Palette and calculated contrast ----
    ink = css_var("ink")
    paper = css_var("paper")
    check(is_green(ink), f"--ink must be a dark green, not {ink}.")
    for token in OLD_BLUE_TOKENS:
        check(token not in CSS.lower(), f"Old blue colour token returned: {token}")
    for value in re.findall(r"#[0-9a-fA-F]{6}\b", CSS):
        check(not is_blue(value), f"Blue colour found in CSS: {value}")
    ratio = contrast(ink, paper)
    check(ratio >= 7, f"Core palette contrast fell below AAA: {ratio:.2f}:1")
    check("--plum:" not in CSS and "#c4b2bc" not in CSS, "The removed plum palette must not return.")
    header_rule = css_rule(".site-header")
    header_bg = decl_color(header_rule, "background")
    header_ink = decl_color(header_rule, "color")
    sage_band = css_var("sage-band")
    check(sage_band == "#78926d", f"The sage band colour changed from #78926d: {sage_band}")
    check(header_bg == sage_band, "Latest brief: the whole top navigation bar is the same sage green as the band.")
    nav_ratio = contrast(header_ink, header_bg)
    check(nav_ratio >= 4.5, f"Header/nav text (normal size) needs 4.5:1 on sage: {header_ink} on {header_bg} = {nav_ratio:.2f}:1")
    check(not re.search(r"(?:^|;)color:", css_rule(".site-nav a")), "Nav links inherit the dark header ink.")
    focus_rules = [d for ctx, head, d in blocks if ctx == "" and ".site-header :focus-visible" in [p.strip() for p in head.split(",")]]
    check(focus_rules and contrast(decl_color(focus_rules[0], "outline-color"), header_bg) >= 3, "Header focus outlines need 3:1 against the sage bar.")
    band_title_ratio = contrast("#ffffff", sage_band)
    check(band_title_ratio >= 3, f"The very large white name needs 3:1 (large text) on sage: {band_title_ratio:.2f}:1")
    for section_sel, bg_var in ((".process", "sage"), (".services", "olive")):
        bg = css_var(bg_var)
        check(contrast(ink, bg) >= 4.5, f"{section_sel} body text needs 4.5:1: {ink} on {bg} = {contrast(ink, bg):.2f}:1")
    check(contrast("#6b4794", paper) >= 3, "The default focus outline needs 3:1 on paper.")

    # ---- Entrance: plan only, with the Enter cursor (Step inside button removed) ----
    entrance = sections["entrance"]
    main_el = next(n for n in doc.find_all("main") if n.attrs.get("id") == "main")
    check(main_el not in list(entrance.ancestors()) and entrance not in list(main_el.ancestors()), "The entrance must sit outside #main.")
    check("dallas-map" not in lower_html, "The Dallas map must not appear in the page markup.")
    for node in entrance.iter():
        check(not any(c.endswith("map") or "-map" in c for c in node.classes), f"Obsolete map markup in entrance: {node.classes}")
    check(entrance.attrs.get("aria-labelledby") == "entrance-label", "The entrance must be labelled by its screen-reader label p#entrance-label.")
    entrance_labels = [n for n in entrance.iter() if n.attrs.get("id") == "entrance-label"]
    check(len(entrance_labels) == 1 and entrance_labels[0].tag == "p" and "sr-only" in entrance_labels[0].classes
          and entrance_labels[0].text().strip(), "The entrance label must be a non-empty p.sr-only#entrance-label.")
    # Visible text excludes the plan drawing's own labels and the Enter cursor (display:none until shown by a mouse pointer).
    shown = " ".join(visible_text(entrance, lambda n: n.tag == "svg" or bool(n.classes & {"floor-plan", "enter-cursor"})).split())
    check(shown.replace("↗", "").strip() == "", f"No visible marketing copy on entrance: {shown!r}")
    check("chingaya" not in visible_text(entrance).lower(), "The opening screen shows no company name (including plan labels).")
    for removed in ("brand-band", "brand-lockup", "entrance-title", "jasmine-vines", "vine-strand", "entrance-caption", "entrance-footer", "plan-label", "motion-toggle", "floor-plan-link", "enter-button"):
        check(entrance.find(None, removed) is None, f".{removed} must not be on the entrance.")
    entrance_links = entrance.find_all("a")
    check([sorted(a.classes) for a in entrance_links] == [["enter-plan"]], "The entrance holds only a.enter-plan (Step inside button removed).")
    check(all(a.attrs.get("href") == "#main" for a in entrance_links), "The entrance link must point to #main so entry works without JavaScript.")
    plan = entrance_links[0]
    check(len(plan.attrs.get("aria-label", "").strip()) >= 10, "The floor-plan link needs a descriptive accessible name.")
    check(any("height:100svh" in d for d in css_rules_with(".entrance")), "The entrance should fill the first screen (height:100svh).")
    plan_rule = css_rule(".enter-plan")
    check("overflow:hidden" in plan_rule and "background:var(--plan-paper)" in plan_rule, "The plan must sit on cream paper and be cropped.")
    floor_rule = css_rule(".floor-plan")
    check(re.search(r"rotate\(-?\d", floor_rule) is not None and "pointer-events:none" in floor_rule, "The floor plan is turned diagonally and never intercepts the link's pointer input.")
    check("height:auto" in floor_rule and "aspect-ratio" not in floor_rule and "1040" not in floor_rule, "The plan's aspect ratio comes from its own viewBox, not a fixed 1600x1040.")
    check(not hex_rgb(css_var("plan-paper"))[2] > hex_rgb(css_var("plan-paper"))[0], "Plan paper must be a warm cream.")
    check(".enter-plan:focus-visible" in CSS, "The plan link needs a visible focus style.")
    check("document.querySelector('.enter-plan')" in JS, "app.js must wire the .enter-plan link.")
    check("enter-map" not in JS and "dallas" not in JS.lower(), "app.js must not reference the removed map.")

    # Custom Enter cursor: decorative, outside the link, hidden by default; native cursor hidden only while it is live.
    cursors = entrance.find_all("span", "enter-cursor")
    check(len(cursors) == 1, "The entrance needs exactly one span.enter-cursor.")
    cursor = cursors[0]
    check(cursor.attrs.get("aria-hidden") == "true" and cursor.text().strip().startswith("Enter"), "The Enter cursor is aria-hidden decoration reading 'Enter'.")
    check(not any(a.tag in {"a", "button"} for a in cursor.ancestors()), "The Enter cursor must not sit inside the link or button.")
    cursor_rule = css_rule(".enter-cursor")
    check("display:none" in cursor_rule and "pointer-events:none" in cursor_rule, "The Enter cursor is hidden by default and never intercepts input.")
    for ctx, head, decls in blocks:
        if re.search(r"(?:^|;)cursor:none", decls):
            check(ctx == "" and all(".cursor-live" in part for part in head.split(",")), f"The native cursor may be hidden only while the custom cursor is live: {head}")
        if ctx.startswith(reduce_q) and ".enter-cursor" in head:
            check("display:none" in decls, "Reduced motion must hide the custom cursor.")
    check(any(".enter-cursor" in head and "display:none" in d for ctx, head, d in blocks if ctx.startswith(reduce_q)), "Reduced motion must hide the custom cursor.")
    check(any(re.search(r"\.cursor-live \.enter-cursor", head) and "display:flex" in d for _, head, d in blocks), "The cursor is shown only under .cursor-live.")
    check("(pointer: fine)" in JS and "pointerType" in JS and "pointerleave" in JS, "The custom cursor is limited to a fine mouse pointer and hides on leave.")

    # Header: hidden only while app.js marks the entry state; never in markup, so it is visible without JS.
    header_hides = []
    for ctx, head, decls in blocks:
        if re.search(r"(?:^|;)display:none", decls):
            header_hides += [part.strip() for part in head.split(",") if part.strip().endswith(".site-header")]
    check(".entry-active .site-header" in header_hides, "The header must be hidden during the entry state (.entry-active .site-header{display:none}).")
    check(all(sel.startswith(".entry-active ") for sel in header_hides), f"The header may only be hidden under .entry-active: {header_hides}")
    check("entry-active" not in HTML and "is-entrance" not in HTML, "The entry state must be set only by app.js, so the header and site stay visible without JS.")
    check("'entry-active'" in JS and "'is-entrance'" in JS, "app.js must set html.entry-active and body.is-entrance.")
    check("hashchange" in JS and "location.hash" in JS, "app.js must honour deep links and hash changes (skip the entrance).")

    # ---- Brand band: first section of main, more green, taller name low in the band ----
    brand = sections.get("brand")
    check(brand is not None and "brand-section" in brand.classes, "Missing section.brand-section#brand.")
    check(main_el in list(brand.ancestors()), "#brand must sit inside #main (seen after entering).")
    first_child = next(c for c in main_el.children if isinstance(c, Node))
    check(first_child is brand, "#brand must be the first section of main.")
    check(brand.attrs.get("aria-labelledby") == "entrance-title", "#brand must be labelled by the live name.")
    band = brand.find("div", "brand-band")
    check(band is not None, "#brand needs the sage .brand-band.")
    lockup = band.find("div", "brand-lockup")
    check(lockup is not None, "The band needs .brand-lockup.")
    check(sum(1 for n in doc.iter() if n.attrs.get("id") == "entrance-title") == 1, "There must be exactly one #entrance-title.")
    title = lockup.find("p", "entrance-title")
    check(title is not None and title.attrs.get("id") == "entrance-title", "The live title p#entrance-title must sit in .brand-lockup.")
    check(title.text().strip() == "King Chingaya Design", "The brand name must be live text: King Chingaya Design.")
    check(not any(a.attrs.get("aria-hidden") == "true" or "hidden" in a.attrs for a in [title, *title.ancestors()]), "The brand name must not be hidden.")
    check(not title.find_all("img") and not title.find_all("svg"), "The brand name must be text, not an image.")
    band_rule = css_rule(".brand-band")
    check("background:var(--sage-band)" in band_rule, "The brand band must use the solid sage colour.")
    title_css = css_rule(".entrance-title")
    check("color:#fff" in title_css and "font-weight:700" in title_css and "white-space:nowrap" in title_css, "The brand name must be bold white on one line.")
    check("font-family:var(--sans)" in title_css and "Instrument" in css_var_text("sans"), "The brand name must use the bundled Instrument face.")
    scale = re.search(r"transform:scaleY\(([\d.]+)\)", title_css)
    check(scale is not None and float(scale.group(1)) >= 1.15, "The letters must stay taller (transform:scaleY >= 1.15).")
    check(re.search(r"transform-origin:(?:50% 100%|center bottom|bottom)", title_css) is not None, "The taller letters grow upward from the bottom.")
    check("place-items:end" in css_rule(".brand-lockup"), "The name sits toward the bottom of the band (place-items:end).")
    pad = re.search(r"padding:max\((\d+)px,([\d.]+)vw\) 0 max\((\d+)px,([\d.]+)vw\)", band_rule)
    check(pad is not None and int(pad.group(1)) > int(pad.group(3)) and float(pad.group(2)) > float(pad.group(4)),
          "The band needs more space above the name than below it.")
    check(int(pad.group(1)) > F3_BAND_TOP_PADDING[0] and float(pad.group(2)) > F3_BAND_TOP_PADDING[1],
          f"Latest brief: the green band is larger than in Feedback 3 (padding-top max({F3_BAND_TOP_PADDING[0]}px,{F3_BAND_TOP_PADDING[1]}vw)): {pad.group(0)}")

    # Vine: one finer strand (back and front layers) plus clusters, all from the unmodified jasmine PNG.
    band_imgs = band.find_all("img")
    check(len(band_imgs) >= 3, f"The brand band must hold the 2 vine strand layers plus at least one cluster, found {len(band_imgs)} images.")
    for img in band_imgs:
        check(img.attrs.get("src") == "assets/brand/jasmine-vines-v1.png", "The vine must use only the existing jasmine PNG.")
    if Image is not None:
        with Image.open(ROOT / "assets/brand/jasmine-vines-v1.png") as jasmine:
            raster_w, raster_h = jasmine.size
    else:
        raster_w, raster_h = png_ihdr_size(ROOT / "assets/brand/jasmine-vines-v1.png")
    check(all((img.attrs.get("width"), img.attrs.get("height")) == (str(raster_w), str(raster_h)) for img in band_imgs), "Vine images must declare the PNG's real size.")
    vine_imgs = [img for img in band_imgs if "jasmine-vines" in img.classes]
    check(len(vine_imgs) == 2, "The vine strand must have exactly two layers (back and front).")
    layer_classes = []
    for img in vine_imgs:
        wrapper = img.parent
        check(wrapper is not None and "vine-strand" in wrapper.classes and wrapper.attrs.get("aria-hidden") == "true", "Each vine strand image sits in an aria-hidden .vine-strand.")
        layer_classes.append(wrapper.classes & {"vine-back", "vine-front"})
    check(layer_classes == [{"vine-back"}, {"vine-front"}], "Vine layers must be back then front, around the name.")
    strand_decls = " ".join(css_rules_with(".vine-strand"))
    strand_width = re.search(r"(?:^|;)width:([\d.]+)%", strand_decls)
    strand_aspect = re.search(r"aspect-ratio:([\d.]+)/([\d.]+)", strand_decls)
    check(strand_width is not None and float(strand_width.group(1)) < 100, f"Latest brief: the vine is finer, drawn narrower than the full band: {strand_decls[:120]}")
    check(strand_aspect is not None and float(strand_aspect.group(2)) / float(strand_aspect.group(1)) < F3_STRAND_ASPECT,
          "Latest brief: the strand slice is thinner than the Feedback 3 strand.")
    cluster_wrap = lockup.find("div", "vine-clusters")
    check(cluster_wrap is not None and cluster_wrap.attrs.get("aria-hidden") == "true", "Clusters need an aria-hidden div.vine-clusters.")
    clusters = cluster_wrap.find_all("span", "vine-cluster")
    check(len(clusters) >= 1, "The vine needs at least one hanging flower cluster (span.vine-cluster); the count is a design choice.")
    check(len(band_imgs) == 2 + len(clusters), f"Every band image must be a strand layer or a cluster crop: {len(band_imgs)} images, {len(clusters)} clusters.")
    cluster_names = []
    for c in clusters:
        imgs = c.find_all("img")
        check(len(imgs) == 1 and "jasmine-cluster" in imgs[0].classes, "Each cluster wraps exactly one img.jasmine-cluster.")
        names = sorted(cls for cls in c.classes if re.fullmatch(r"cluster-\d+", cls))
        check(len(names) == 1, f"Each cluster needs exactly one cluster-N modifier class for its crop: {sorted(c.classes)}")
        cluster_names.append(names[0])
    check(len(set(cluster_names)) == len(cluster_names), f"Cluster modifier classes must be unique: {cluster_names}")
    for name in cluster_names:
        decls = " ".join(css_rules_with(f".{name}"))
        crop = {k: float(v) for k, v in re.findall(r"--(cx|cy|cw|ch):([\d.]+)", decls)}
        check(set(crop) == {"cx", "cy", "cw", "ch"}, f".{name} needs its crop rectangle (--cx/--cy/--cw/--ch).")
        check(crop["cw"] > 0 and crop["ch"] > 0 and crop["cx"] + crop["cw"] <= raster_w and crop["cy"] + crop["ch"] <= raster_h,
              f".{name} crop must lie inside the {raster_w}x{raster_h} PNG: {crop}")
        check(crop["cw"] <= raster_w / 2, f".{name} must be a small crop of the raster, not the whole vine: {crop}")
    check(any("overflow:hidden" in d for d in css_rules_with(".vine-cluster")), "Each cluster must crop the raster (.vine-cluster overflow:hidden).")
    check(any("pointer-events:none" in d for d in css_rules_with(".vine-strand")), "The vine must not intercept pointer input.")
    check(any("pointer-events:none" in d for d in css_rules_with(".vine-cluster")), "Vine clusters must not intercept pointer input.")
    check(any("mask-image" in d for d in css_rules_with(".vine-front")), "The front vine layer must be masked so the strand weaves through the letters.")
    for img in parser.images:
        src = img.get("src", "")
        if src.startswith("assets/brand/"):
            check(src in {"assets/brand/jasmine-vines-v1.png", "assets/brand/entry-floor-plan.svg"}, f"Unexpected brand image: {src}")

    # ---- Entrance floor plan: inline SVG contract (generator-owned marker block) ----
    check(HTML.count("<!-- FLOOR_PLAN_START -->") == 1 and HTML.count("<!-- FLOOR_PLAN_END -->") == 1, "index.html needs exactly one FLOOR_PLAN_START/END marker pair.")
    plan_open = re.search(r"<a\b[^>]*\bclass=\"enter-plan\"[^>]*>", HTML)
    check(plan_open is not None, "Missing <a class=\"enter-plan\">.")
    start = HTML.index("<!-- FLOOR_PLAN_START -->")
    end = HTML.index("<!-- FLOOR_PLAN_END -->")
    close_a = HTML.find("</a>", plan_open.end())
    check(plan_open.end() <= start < end <= close_a, "The FLOOR_PLAN markers must sit inside a.enter-plan.")
    block = HTML[start + len("<!-- FLOOR_PLAN_START -->"):end].strip()
    check("<a " not in block and "<a>" not in block, "The plan block must not contain links (it already sits inside one).")
    inline_svg = block.startswith("<svg")
    integration_started = inline_svg or PLAN_GENERATOR.exists() or PLAN_MODEL.exists()
    plan_in_link = plan.find(None, "floor-plan")
    check(plan_in_link is not None and plan_in_link.attrs.get("aria-hidden") == "true", "The plan root (.floor-plan) is decorative inside the named link.")

    if integration_started or STRICT_PLAN:
        check(inline_svg and block.endswith("</svg>"), "Plan integration: the marker block must hold exactly one inline <svg> root (no <img> placeholder).")
        check("<img" not in block and "entry-floor-plan.svg" not in block, "Plan integration: the entrance plan is inline SVG, not an external image.")
        try:
            svg_root = ET.fromstring(block)
        except ET.ParseError as exc:
            raise AssertionError(f"Inline plan SVG must be well-formed generator output: {exc}")
        check(local(svg_root.tag) == "svg", "Inline plan root must be <svg>.")
        check("floor-plan" in (svg_root.get("class") or "").split(), "Inline plan root needs class floor-plan.")
        check(svg_root.get("aria-hidden") == "true" and svg_root.get("focusable") == "false", "Inline plan root must be aria-hidden=\"true\" focusable=\"false\".")
        _, _, vb_w, vb_h = parse_viewbox(svg_root.get("viewBox"))
        check((svg_root.get("preserveAspectRatio") or "").strip() != "none", "The plan must not be distorted (preserveAspectRatio none).")
        if svg_root.get("width") and svg_root.get("height"):
            w, h = float(svg_root.get("width")), float(svg_root.get("height"))
            check(abs(w / h - vb_w / vb_h) <= 0.01 * vb_w / vb_h, f"Inline plan width/height must match its own viewBox ratio: {w}x{h} vs {vb_w}x{vb_h}")
        svg_safety(block, svg_root, "inline plan")
        all_elements = list(svg_root.iter())
        position = {e: i for i, e in enumerate(all_elements)}
        parent_of = {child: node for node in svg_root.iter() for child in node}
        stages = {}
        for stage in PLAN_STAGES:
            found = [e for e in all_elements if stage in (e.get("class") or "").split()]
            check(len(found) == 1 and local(found[0].tag) == "g", f"Inline plan needs exactly one <g class=\"{stage}\">: {len(found)}")
            check(len(list(found[0])) >= 1, f".{stage} must contain drawing elements.")
            g = found[0]
            style = (g.get("style") or "").replace(" ", "").lower()
            check(g.get("opacity") not in ("0", "0.0") and g.get("display") != "none" and g.get("visibility") != "hidden"
                  and not re.search(r"opacity:0(?![.\d])|display:none|visibility:hidden", style),
                  f".{stage} must be visible in markup; only the motion opt-in may stage it.")
            stages[stage] = g
        for a in PLAN_STAGES:
            node = stages[a]
            while node in parent_of:
                node = parent_of[node]
                check(node not in [stages[b] for b in PLAN_STAGES if b != a], f".{a} must not be nested inside another stage group.")
        check(position[stages["plan-shell"]] < position[stages["plan-fixtures"]] < position[stages["plan-furniture"]],
              "Stage groups are painted walls/trees, then fixtures/flooring, then furniture on top.")
        for style_el in [e for e in all_elements if local(e.tag) == "style"]:
            text = (style_el.text or "").lower()
            check(not re.search(r"animation|transition|@keyframes", text), "Inline plan <style> must not add motion; staging lives in styles.css under the opt-in.")
        check("chingaya" not in "".join(svg_root.itertext()).lower(), "The plan drawing shows no company name on the opening screen.")
        colours = [c.lower() for c in re.findall(r"(?:stroke|fill)\s*[:=]\s*\"?(#[0-9a-fA-F]{6})\b", block)]
        check(any(is_green(c) for c in colours), "The plan keeps green linework/planting colours.")
        check(not COMPLIANCE_CLAIM.search(" ".join("".join(svg_root.itertext()).lower().split())), "The plan must not claim code compliance or construction readiness.")

        check(PLAN_GENERATOR.is_file(), f"Plan integration: missing generator {PLAN_GENERATOR.relative_to(ROOT)}.")
        result = subprocess.run([sys.executable, str(PLAN_GENERATOR), "--check"], cwd=ROOT, capture_output=True, text=True, timeout=180)
        check(result.returncode == 0, f"Plan generator --check failed (index.html/SVG out of date with the model?): {(result.stdout + result.stderr).strip()[-600:]}")

        check(PLAN_MODEL.is_file(), f"Plan integration: missing model {PLAN_MODEL.relative_to(ROOT)}.")
        model = json.loads(PLAN_MODEL.read_text(encoding="utf-8"))
        check(isinstance(model, dict) and model, "The plan model must be a non-empty JSON object.")
        words: list[str] = []

        def collect(value) -> None:
            if isinstance(value, dict):
                for k, v in value.items():
                    words.append(str(k))
                    collect(v)
            elif isinstance(value, list):
                for v in value:
                    collect(v)
            elif isinstance(value, str):
                words.append(value)

        collect(model)
        model_text = " " + " ".join(re.sub(r"[_\-/]+", " ", w.lower()) for w in words) + " "
        missing = [room for room, keys in REQUIRED_MODEL_ROOMS.items() if not any(k in model_text for k in keys)]
        check(not missing, f"The plan model must name the required spaces: missing {missing}")
        check(not COMPLIANCE_CLAIM.search(" ".join(model_text.split())), "The plan model must not claim code compliance or construction readiness.")

        # Independent floor plan geometry validation (areas, non-overlap, containment, openings, routes)
        # Note: Independent model geometry check. Does not certify CAD tolerances, swept door clearances, or full building code compliance.
        def rect(b):
            return (b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"])

        def overlap(a, b):
            return min(a[2], b[2]) - max(a[0], b[0]) > 0.001 and min(a[3], b[3]) - max(a[1], b[1]) > 0.001

        spaces = {x["id"]: x for x in model.get("spaces", [])}
        walls = {x["id"]: x for x in model.get("walls", [])}

        for i, a in enumerate(model.get("spaces", [])):
            b = a["bounds"]
            check(b["width"] > 0 and b["height"] > 0, f"Positive room dimensions: {a['id']}")
            check(abs(a["area_sqft"] - b["width"] * b["height"]) < 0.11, f"Room area calculation: {a['id']}")
            for c in model["spaces"][i + 1:]:
                check(not overlap(rect(b), rect(c["bounds"])), f"Rooms do not overlap: {a['id']} / {c['id']}")

        for group in ["fixtures", "furniture"]:
            for item in model.get(group, []):
                b = rect(item["bounds"])
                rb = rect(spaces[item["room_id"]]["bounds"])
                check(b[0] >= rb[0] - 0.01 and b[1] >= rb[1] - 0.01 and b[2] <= rb[2] + 0.01 and b[3] <= rb[3] + 0.01,
                      f"Item {item['id']} contained in room {item['room_id']}")

        for op in model.get("openings", []):
            w = walls[op["wall_id"]]
            length = ((w["end"][0] - w["start"][0]) ** 2 + (w["end"][1] - w["start"][1]) ** 2) ** 0.5
            check(op["offset_ft"] >= 0 and op["width_ft"] > 0 and op["offset_ft"] + op["width_ft"] <= length + 0.001,
                  f"Opening inside wall: {op['id']}")

        # Route centerline must pass through an opening whenever it crosses a wall centerline.
        # Disclosed limitation: Does not certify swept-width clearance, door swing, or building code compliance.
        for route in model.get("circulation", []):
            for pt_a, pt_b in zip(route["points"], route["points"][1:]):
                for w in walls.values():
                    s, e = w["start"], w["end"]
                    vertical = abs(s[0] - e[0]) < 0.001
                    axis = 0 if vertical else 1
                    other = 1 - axis
                    if abs(pt_b[axis] - pt_a[axis]) < 1e-8:
                        continue
                    t = (s[axis] - pt_a[axis]) / (pt_b[axis] - pt_a[axis])
                    if not -0.0001 <= t <= 1.0001:
                        continue
                    cross = pt_a[other] + t * (pt_b[other] - pt_a[other])
                    lo, hi = sorted([s[other], e[other]])
                    if not lo + 0.001 < cross < hi - 0.001:
                        continue
                    offset = abs(cross - s[other])
                    openings = [op for op in model.get("openings", []) if op["wall_id"] == w["id"] and op["offset_ft"] - 0.001 <= offset <= op["offset_ft"] + op["width_ft"] + 0.001]
                    check(bool(openings), f"Circulation route {route['id']} crosses opening in {w['id']}")
    else:
        imgs = [n for n in plan.iter() if n.tag == "img"]
        check(len(imgs) == 1 and "floor-plan" in imgs[0].classes and imgs[0].attrs.get("alt") == "", "Until integration the marker block holds the single decorative .floor-plan placeholder.")
        pending("inline <svg class=\"floor-plan\"> between FLOOR_PLAN markers (placeholder <img> still present)")
        pending(f"{PLAN_GENERATOR.relative_to(ROOT)} --check (generator not present yet)")
        pending(f"{PLAN_MODEL.relative_to(ROOT)} required rooms (model not present yet)")

    # ---- External plan SVG (static review artifact) ----
    check(PLAN_SVG.is_file(), "Missing assets/brand/entry-floor-plan.svg.")
    ext_text = PLAN_SVG.read_text(encoding="utf-8")
    try:
        ext_root = ET.fromstring(ext_text)
    except ET.ParseError as exc:
        raise AssertionError(f"External plan SVG is not well-formed XML: {exc}")
    check(ext_root.tag == "{http://www.w3.org/2000/svg}svg", "External plan root must be a namespaced SVG element.")
    _, _, ext_w, ext_h = parse_viewbox(ext_root.get("viewBox"))
    svg_safety(ext_text, ext_root, "external plan SVG")
    check(not COMPLIANCE_CLAIM.search(" ".join(ext_text.lower().split())), "The external plan must not claim code compliance or construction readiness.")

    # ---- floor-plan.html: unlinked standalone review artifact ----
    plan_page_path = ROOT / "floor-plan.html"
    check(plan_page_path.is_file(), "Missing floor-plan.html (standalone review artifact).")
    check("floor-plan.html" not in HTML, "floor-plan.html is unlinked from the website.")
    plan_html = plan_page_path.read_text(encoding="utf-8")
    lower_plan = plan_html.lower()
    plan_parser = SiteParser()
    plan_parser.feed(plan_html)
    plan_tree = TreeParser()
    plan_tree.feed(plan_html)
    pdoc = plan_tree.root
    check('<html lang="en">' in plan_html and "<title>" in lower_plan and 'name="viewport"' in plan_html, "floor-plan.html needs lang, title and viewport.")
    check("<script" not in lower_plan and "javascript:" not in lower_plan and not re.search(r"\son[a-z]+\s*=", lower_plan), "floor-plan.html must contain no scripts or inline handlers.")
    plan_no_ns = re.sub(r"\sxmlns(?::\w+)?=\"http://www\.w3\.org/[^\"]*\"", "", plan_html)
    check(not re.search(r"https?://", plan_no_ns) and not re.search(r"(?:src|href)\s*=\s*[\"']//", plan_html), "floor-plan.html must not reference external URLs.")
    check('<link rel="stylesheet" href="styles.css">' in plan_html, "floor-plan.html must use the local stylesheet.")
    body = pdoc.find("body")
    check(body is not None and "plan-page" in body.classes, "floor-plan.html body needs class plan-page.")
    check(lower_plan.count("<h1") == 1, "floor-plan.html must have exactly one h1.")
    check(all(current - previous <= 1 for previous, current in zip(plan_parser.headings, plan_parser.headings[1:])), "floor-plan.html heading levels must not skip.")
    plan_main = pdoc.find("main")
    check(plan_main is not None and plan_main.attrs.get("id") == "plan", "floor-plan.html needs main#plan.")
    for href in plan_parser.links:
        check(bool(href) and ":" not in href, f"floor-plan.html links must be local: {href!r}")
        if href.startswith("#"):
            check(href[1:] in plan_parser.ids, f"floor-plan.html broken internal link: {href}")
        else:
            check((ROOT / href.split("#", 1)[0]).is_file(), f"floor-plan.html links to a missing file: {href}")
    plan_imgs = [n for n in plan_main.find_all("img") if n.attrs.get("src") == "assets/brand/entry-floor-plan.svg"]
    plan_svgs = plan_main.find_all("svg")
    check(len(plan_imgs) + len(plan_svgs) == 1, "floor-plan.html must show the plan exactly once inside main.")
    if plan_imgs:
        full_plan = plan_imgs[0]
        w, h = full_plan.attrs.get("width", ""), full_plan.attrs.get("height", "")
        check(w.isdigit() and h.isdigit() and abs(int(w) / int(h) - ext_w / ext_h) <= 0.01 * ext_w / ext_h,
              f"floor-plan.html must declare the plan's own aspect ratio (viewBox {ext_w:g}x{ext_h:g}): {w}x{h}")
        check(len(full_plan.attrs.get("alt", "").strip()) >= 20 and full_plan.attrs.get("aria-hidden") != "true", "The full plan is content here and needs descriptive alt text.")
        check("floor-plan" not in full_plan.classes and "style" not in full_plan.attrs, "The full plan must not use the rotated .floor-plan class or inline styles.")
    else:
        full_plan = plan_svgs[0]
        check("floor-plan" not in full_plan.classes, "The full plan must not use the rotated .floor-plan class.")
    check(not any(set(a.classes) & {"enter-plan", "floor-plan"} for a in full_plan.ancestors()), "The full plan must not sit in the rotated/cropped entry wrapper.")
    for ctx, head, decls in blocks:
        if any(token in head for token in (".plan-page", ".plan-main", ".plan-figure")):
            check("rotate" not in decls and "transform" not in decls and "scale(" not in decls, f"The full plan page must not rotate or transform the plan: {head}")
            check("overflow:hidden" not in decls, f"The full plan page must not crop the plan: {head}")
    return_links = [a for a in pdoc.find_all("a") if a.attrs.get("href") == "index.html#main"]
    check(any("plan-return" in a.classes and "Return to site" in a.text() for a in return_links), "floor-plan.html needs a.plan-return 'Return to site' to index.html#main.")
    for text in (lower_html, lower_plan):
        check(not COMPLIANCE_CLAIM.search(" ".join(text.split())), "Pages must not claim code compliance, permit or construction readiness.")

    # ---- Brand manifest provenance ----
    brand_manifest = json.loads((ROOT / "assets/brand/manifest.json").read_text(encoding="utf-8"))
    check(brand_manifest.get("jasmine-vines-v1.png", {}).get("sha256") == BASELINE_HASHES["assets/brand/jasmine-vines-v1.png"], "Brand manifest must keep the jasmine record.")
    check(brand_manifest.get("dallas-map.jpeg", {}).get("sha256") == BASELINE_HASHES["assets/brand/dallas-map.jpeg"], "Brand manifest must keep the (preserved, unused) Dallas map record.")
    check("gallery_selection" in brand_manifest, "Brand manifest must keep the gallery selection.")
    check("entry-floor-plan.svg" in brand_manifest, "Brand manifest must record the floor plan's provenance.")

    # ---- Asset integrity ----
    for rel, expected in baseline_hashes().items():
        path = ROOT / rel
        check(path.is_file(), f"Baseline asset missing: {rel}")
        check(sha256(path).lower() == expected.lower(), f"Asset drift from baseline: {rel}")

    f2_path = ROOT / "assets/brief/feedback-2-manifest.json"
    check(json.loads(f2_path.read_text(encoding="utf-8")) == FEEDBACK_2_MANIFEST, "Feedback 2 provenance manifest was altered.")
    for name, record in FEEDBACK_2_MANIFEST["assets"].items():
        path = ROOT / "assets/brief" / name
        check(path.is_file(), f"Missing Feedback 2 image: {name}")
        check(sha256(path).lower() == record["sha256"], f"Feedback 2 image drift: {name}")
        check(png_ihdr_size(path) == RESTAURANT_SIZES[name] == (record["width"], record["height"]), f"Feedback 2 image dimensions drift: {name}")

    manifest = json.loads((ROOT / "assets" / "manifest.json").read_text(encoding="utf-8"))
    for name, record in manifest["assets"].items():
        path = ROOT / "assets" / name
        check(path.is_file(), f"Manifest asset missing: {name}")
        check(sha256(path) == record["sha256"], f"Evidence asset drift: {name}")

    check(len(brief_manifest["assets"]) == 20, "The supplied portfolio has 20 design images.")
    for name, record in brief_manifest["assets"].items():
        asset = ROOT / "assets/brief" / name
        check(sha256(asset).lower() == record["sha256"], f"Brief image drift: {name}")
        if Image is not None:
            with Image.open(asset) as image:
                check(image.size == (record["width"], record["height"]), f"Image size drift: {name}")
    for name in ("fraunces-OFL.txt", "instrument-sans-OFL.txt"):
        check("SIL OPEN FONT LICENSE" in (ROOT / "assets/fonts" / name).read_text(), f"Missing font license: {name}")

    expected_rasters = (
        {f"assets/{name}" for name in manifest["assets"]}
        | {f"assets/brief/{name}" for name in brief_manifest["assets"]}
        | {f"assets/brief/{name}" for name in FEEDBACK_2_MANIFEST["assets"]}
        | {"assets/brand/jasmine-vines-v1.png", "assets/brand/dallas-map.jpeg"}
        | {f"assets/people/{name}" for name in provenance.get("outputs", {})}  # legacy hero sprites, if still recorded in provenance.json
        | {a["strip"] for s in scenes for a in s["actors"]}  # Blender-rendered scene strips listed in assets/people/scenes.json
    )
    actual_rasters = {p.relative_to(ROOT).as_posix() for p in (ROOT / "assets").rglob("*") if p.suffix.lower() in RASTER_SUFFIXES}
    check(actual_rasters == expected_rasters, f"Raster asset set changed: added {sorted(actual_rasters - expected_rasters)}, missing {sorted(expected_rasters - actual_rasters)}")

    if Image is not None:
        with Image.open(ROOT / "assets/brand/jasmine-vines-v1.png") as image:
            check(image.mode == "RGBA" and image.getextrema()[3][0] == 0, "The jasmine overlay must preserve transparency.")

    # ---- Footer: contact first, then the cropped two-green name ----
    footer = next(n for n in doc.find_all("footer") if n.attrs.get("id") == "site-footer")
    top_level = [c for c in footer.children if isinstance(c, Node)]
    check(len(top_level) == 2 and top_level[0].tag == "div" and "footer-inner" in top_level[0].classes
          and top_level[1].tag == "div" and "footer-mark" in top_level[1].classes,
          "Footer must be div.footer-inner followed by div.footer-mark.")
    inner, mark = top_level
    check("section-wrap" in inner.classes, "Footer content keeps the page gutter.")
    inner_hrefs = [a.attrs.get("href") for a in inner.find_all("a")]
    check("mailto:heather@kingchingaya.com" in inner_hrefs and "#top" in inner_hrefs, "Footer keeps email and back-to-top.")
    check("© King Chingaya Design" in inner.text(), "Footer keeps the copyright line.")
    check("@king_chingaya_design" in inner.text() and "@heatherkingchingaya" in inner.text(), "Footer keeps the supplied social handles.")
    mark_text = mark.find("p", "footer-mark-text")
    check(mark_text is not None, "Footer needs p.footer-mark-text.")
    span_a = mark_text.find("span", "footer-mark-a")
    span_b = mark_text.find("span", "footer-mark-b")
    check(span_a is not None and span_a.text() == "King Chingaya", "Footer mark first span must read King Chingaya.")
    check(span_b is not None and span_b.text() == "Design", "Footer mark second span must read Design.")
    check(" ".join(mark_text.text().split()) == "King Chingaya Design", "Footer mark must read King Chingaya Design as live text.")
    check(not mark_text.find_all("img") and not mark_text.find_all("svg"), "Footer mark must be text, not an image.")
    for node in (mark, mark_text, span_a, span_b):
        check(node.attrs.get("aria-hidden") != "true", "Footer mark must not be aria-hidden.")
    check("overflow:hidden" in css_rule(".footer-mark"), "The footer mark wrapper must crop the oversized name.")
    check("white-space:nowrap" in css_rule(".footer-mark-text"), "The footer name must stay on one line.")
    colour_a = resolve_color(re.search(r"color:([^;}]+)", css_rule(".footer-mark-a")).group(1))
    colour_b = resolve_color(re.search(r"color:([^;}]+)", css_rule(".footer-mark-b")).group(1))
    check(colour_a != colour_b and is_green(colour_a) and is_green(colour_b), f"Footer name must use two different greens: {colour_a}, {colour_b}")

    summary = (f"structure, plain section headings, title-only gallery, removed controls, sage header {nav_ratio:.2f}:1, "
               f"band name {band_title_ratio:.2f}:1, finer vine, Enter cursor, staged/finite motion, {sum(actor_counts.values())} Blender people over 9 scenes + hero (generator --check), floor-plan.html, footer, "
               f"inquiry isolation, asset integrity, {ratio:.2f}:1 core contrast")
    if PENDING:
        print(f"PASS (current UI): {summary}")
        print("INTEGRATION PENDING (not verified, not failed):")
        for item in PENDING:
            print(f"  - {item}")
    else:
        print(f"PASS: {summary}; inline SVG plan contract, generator --check and model rooms")
    return 0


def test_site() -> None:
    """pytest entry point."""
    assert main() == 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
