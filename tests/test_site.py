"""Static gate for the King Chingaya Design site.

Run with either:
    python3 tests/test_site.py
    python3 -m pytest tests/test_site.py
Requires Pillow.
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "app.js").read_text(encoding="utf-8")

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

# Colours that belonged to the provisional blue direction and must not return.
OLD_BLUE_TOKENS = ("#284d70", "#152a3a", "#0000ff", "#00f;", "#00f}")

RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
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


def css_var(name: str) -> str:
    match = re.search(r"--" + re.escape(name) + r":(#[0-9a-fA-F]{6})", CSS)
    if not match:
        raise AssertionError(f"Missing CSS custom property --{name}")
    return match.group(1).lower()


def resolve_color(value: str) -> str:
    value = value.strip()
    var = re.fullmatch(r"var\(--([\w-]+)\)", value)
    if var:
        return css_var(var.group(1))
    if re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", value):
        return value.lower()
    raise AssertionError(f"Unresolvable colour value: {value}")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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


def main() -> int:
    parser = SiteParser()
    parser.feed(HTML)
    tree = TreeParser()
    tree.feed(HTML)
    doc = tree.root
    lower_html = HTML.lower()

    # ---- Semantic structure and navigation (unchanged) ----
    check(lower_html.count("<h1") == 1, "The page must have exactly one h1.")
    check(parser.headings and parser.headings[0] == 1, "The heading sequence must start at h1.")
    check(all(current - previous <= 1 for previous, current in zip(parser.headings, parser.headings[1:])), "Heading levels must not skip.")

    required_ids = {"main", "projects", "philosophy", "services", "about", "process", "entrance", "inquiry", "inquiry-form", "site-footer", "entrance-title"}
    check(required_ids <= parser.ids, f"Missing required landmarks: {sorted(required_ids - parser.ids)}")
    for href in parser.links:
        check(bool(href), "Every link needs a destination.")
        check(not re.match(r"(?:https?:)?//", href), f"External destination is not cleared: {href}")
        if href.startswith("#"):
            check(href[1:] in parser.ids, f"Broken internal link: {href}")
    for href in parser.links:
        if ":" in href:
            check(href == "mailto:heather@kingchingaya.com", f"Only the supplied mailto may leave the page: {href}")

    nav = doc.find("nav")
    check(nav is not None and nav.attrs.get("aria-label") == "Primary navigation", "Primary navigation must remain labelled.")
    nav_hrefs = [a.attrs.get("href") for a in nav.find_all("a")]
    check(nav_hrefs == ["#philosophy", "#projects", "#about", "#process", "#services", "#inquiry"], f"Primary navigation changed: {nav_hrefs}")

    service_section = next(n for n in doc.find_all("section") if n.attrs.get("id") == "services")
    service_titles = [s.text().strip() for s in service_section.find_all("span", "row-title")]
    check(service_titles == ["Room Refresh", "Design Consultations", "Furnishing & Styling", "Renovations & Remodels", "New Construction", "Commercial Interior Design"], f"Services changed: {service_titles}")
    process_section = next(n for n in doc.find_all("section") if n.attrs.get("id") == "process")
    process_titles = [s.text().strip() for s in process_section.find_all("span", "row-title")]
    check(process_titles == ["Listen", "Imagine", "Refine", "Create", "Live"], f"Process steps changed: {process_titles}")

    # ---- Images: alternatives and files ----
    for image in parser.images:
        if image.get("id") == "viewer-image":
            continue  # Populated from the selected accessible gallery image.
        check(bool(image.get("alt", "").strip()) or (image.get("aria-hidden") == "true" and "alt" in image), f"Missing image alternative text: {image.get('src')}")
        source = ROOT / image["src"]
        check(source.is_file(), f"Missing image asset: {source}")

    # ---- Gallery: nine studies in the agreed order ----
    lightbox_links = [a for a in doc.find_all("a") if "data-lightbox" in a.attrs]
    check(len(lightbox_links) == 9, f"The gallery must contain exactly nine lightbox images, found {len(lightbox_links)}.")
    check(HTML.count("data-lightbox") == 9, "Unexpected extra data-lightbox markers.")
    gallery_sources = [a.attrs.get("href") for a in lightbox_links]
    check(gallery_sources == EXPECTED_GALLERY, f"Gallery image order differs from the agreed nine: {gallery_sources}")
    selection = json.loads((ROOT / "assets/brand/manifest.json").read_text(encoding="utf-8"))["gallery_selection"]
    check(selection["review_image_numbers"] == [1, 2, 8, 11, 14, 18], "Keep the six image numbers supplied by Heather.")
    check([f"assets/brief/{name}" for name in selection["filenames"]] == EXPECTED_GALLERY[:6], "The first six gallery images must remain the numbered selection.")
    check(EXPECTED_GALLERY[6:] == [f"assets/brief/{name}" for name in FEEDBACK_2_MANIFEST["assets"]], "Feedback 2 images must follow the numbered selection in PDF order.")

    brief_manifest = json.loads((ROOT / "assets/brief/manifest.json").read_text(encoding="utf-8"))
    invented_claims = ("award", "client", "completed", "delivered", "built for", "commissioned", "opened", "testimonial", "featured in", "case study")
    for index, link in enumerate(lightbox_links, start=1):
        figure = link.parent
        check(figure is not None and figure.tag == "figure" and {"study", f"study-{index}"} <= figure.classes, f"Gallery item {index} must sit in figure.study.study-{index}.")
        check("study-image" in link.classes, f"Gallery link {index} must be a.study-image.")
        imgs = link.find_all("img")
        check(len(imgs) == 1, f"Gallery link {index} must wrap exactly one image.")
        img = imgs[0]
        href = link.attrs["href"]
        check(img.attrs.get("src") == href, f"Gallery thumbnail and enlarged image differ: {href}")
        check(img.attrs.get("alt", "").strip() != "", f"Gallery image needs non-empty alt text: {href}")
        check(img.attrs.get("width", "").isdigit() and img.attrs.get("height", "").isdigit(), f"Gallery image needs width and height: {href}")
        size = (int(img.attrs["width"]), int(img.attrs["height"]))
        with Image.open(ROOT / href) as opened:
            check(opened.size == size, f"Declared size {size} differs from file {opened.size}: {href}")
        title = link.attrs.get("data-title", "").strip()
        kind = link.attrs.get("data-kind", "").strip()
        check(title and kind, f"Gallery link needs data-title and data-kind: {href}")
        check(title in link.attrs.get("aria-label", ""), f"Gallery link accessible name must include its title: {href}")
        caption = figure.find("figcaption")
        check(caption is not None and title in caption.text() and kind in caption.text(), f"Gallery caption must match viewer title/kind: {href}")
        if href.endswith(".png") and "restaurant-" in href:
            check(kind == "Spatial visualization", f"Feedback 2 renders must be described as visualizations: {href}")
            words = " ".join([title, kind, link.attrs.get("aria-label", ""), img.attrs.get("alt", ""), caption.text()]).lower()
            for claim in invented_claims:
                check(claim not in words, f"Invented claim '{claim}' in new caption: {href}")
        else:
            record = brief_manifest["assets"][Path(href).name]
            check(size == (record["width"], record["height"]), f"Gallery size differs from brief manifest: {href}")

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

    # ---- Motion (unchanged guard) ----
    lower_css = CSS.lower().replace("@media(", "@media (")
    check("@media (prefers-reduced-motion: reduce)" in lower_css, "The reduced-motion media query must remain.")
    if "animation:" in lower_css or "transition:" in lower_css:
        check("@media (prefers-reduced-motion: no-preference)" in lower_css, "Motion must be opt-in behind prefers-reduced-motion: no-preference.")
        reduced = lower_css.split("@media (prefers-reduced-motion: reduce)", 1)[-1]
        check("animation:none" in reduced and "transition:none" in reduced, "Reduced motion must disable animation and transition.")
        check("scroll-behavior:auto" in reduced, "Reduced motion must restore instant scrolling.")
        before_optin = lower_css.split("@media (prefers-reduced-motion: no-preference)")[0]
        check(".reveal" not in before_optin, "Reveal states must live inside the motion opt-in so content stays visible without motion or JS.")
        check("animation:" not in before_optin and "@keyframes" not in before_optin, "Animations must live inside the motion opt-in.")
        check("motion-ready" in JS.lower(), "Reveal styling must be gated on a class the script adds, so content is never hidden when the script fails.")
    check(".motion-paused *" in CSS and "animation-play-state:paused" in CSS, "The pause control must pause all animation.")
    check("motion-paused" in JS and "aria-pressed" in JS, "The pause control must toggle state and aria-pressed.")
    check("@import" not in CSS.lower(), "External style imports are not allowed.")

    # ---- No external resources ----
    check(not re.search(r"https?://", HTML), "HTML must not reference external URLs (mailto only).")
    check(not re.search(r"https?://", CSS), "CSS must not reference external URLs.")
    check(not re.search(r"url\(\s*['\"]?(?:https?:)?//", CSS), "CSS must not load protocol-relative resources.")
    for match in re.findall(r"url\(\s*['\"]?([^'\")]+)", CSS):
        check(not match.startswith("data:") or match.startswith("data:,"), f"No inline raster data in CSS: {match[:40]}")
        if not match.startswith("data:"):
            check((ROOT / match).is_file(), f"CSS references a missing local file: {match}")

    # ---- Palette: green ink, no blue ----
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

    # ---- Entrance: sage band, live white wordmark, vine strand ----
    entrance = next(n for n in doc.find_all("section") if n.attrs.get("id") == "entrance")
    check("dallas-map" not in lower_html, "The Dallas map must not appear in the page markup.")
    for node in entrance.iter():
        check(not any("map" in cls for cls in node.classes), f"Obsolete map markup in entrance: {node.classes}")
    band = entrance.find("div", "brand-band")
    check(band is not None, "The entrance needs the sage .brand-band.")
    title = entrance.find("p", "entrance-title")
    check(title is not None and title.attrs.get("id") == "entrance-title", "The live entrance title p#entrance-title must exist.")
    check(title.text().strip() == "King Chingaya Design", "The entrance name must be live text: King Chingaya Design.")
    check(band in list(title.ancestors()), "The entrance name must sit on the sage band.")
    check(not any(a.attrs.get("aria-hidden") == "true" for a in [title, *title.ancestors()]), "The entrance name must not be hidden from assistive technology.")
    check(not title.find_all("img") and not title.find_all("svg"), "The entrance name must be text, not an image.")
    check(entrance.attrs.get("aria-labelledby") == "entrance-title", "The entrance must be labelled by the live name.")
    check(css_var("sage-band") == "#78926d", "The sage band colour changed from #78926d.")
    band_rule = css_rule(".brand-band")
    check("background:var(--sage-band)" in band_rule, "The brand band must use the solid sage colour.")
    title_rule = css_rule(".entrance-title")
    check("color:#fff" in title_rule and "font-weight:700" in title_rule and "white-space:nowrap" in title_rule, "The entrance name must be bold white on one line.")
    check("font-family:var(--sans)" in title_rule and "Instrument" in css_var_text("sans"), "The entrance name must use the bundled Instrument face.")
    check(contrast("#ffffff", css_var("sage-band")) >= 3, "White on the sage band must meet 3:1 large-text contrast.")

    vine_imgs = [img for img in entrance.find_all("img") if "jasmine-vines" in img.classes]
    check(len(vine_imgs) == 2, "The vine must have exactly two layers (back and front).")
    layer_classes = []
    for img in vine_imgs:
        check(img.attrs.get("src") == "assets/brand/jasmine-vines-v1.png", "The vine must use only the existing jasmine PNG.")
        check(img.attrs.get("alt") == "" and img.attrs.get("aria-hidden") == "true", "Vine images are decorative.")
        wrapper = img.parent
        check(wrapper is not None and "vine-strand" in wrapper.classes and wrapper.attrs.get("aria-hidden") == "true", "Each vine image sits in an aria-hidden .vine-strand.")
        layer_classes.append(wrapper.classes & {"vine-back", "vine-front"})
    check(layer_classes == [{"vine-back"}, {"vine-front"}], "Vine layers must be back then front, around the name.")
    check("pointer-events:none" in css_rule(".vine-strand"), "The vine must not intercept pointer input.")
    check("mask-image" in css_rule(".vine-front"), "The front vine layer must be masked so the strand weaves through the letters.")
    for img in parser.images:
        src = img.get("src", "")
        if src.startswith("assets/brand/"):
            check(src in {"assets/brand/jasmine-vines-v1.png", "assets/brand/entry-floor-plan.svg"}, f"Unexpected brand image: {src}")

    # ---- Entrance: floor-plan link replaces the map ----
    plan_links = entrance.find_all("a", "enter-plan")
    check(len(plan_links) == 1, "The entrance needs exactly one a.enter-plan.")
    plan = plan_links[0]
    check(plan.attrs.get("href") == "#main", "The floor plan must link to #main so it works without JavaScript.")
    check(len(plan.attrs.get("aria-label", "").strip()) >= 10, "The floor-plan link needs a descriptive accessible name.")
    plan_img = plan.find("img", "floor-plan")
    check(plan_img is not None and plan_img.attrs.get("src") == "assets/brand/entry-floor-plan.svg", "The floor plan must use assets/brand/entry-floor-plan.svg.")
    check(plan_img.attrs.get("alt") == "" and plan_img.attrs.get("aria-hidden") == "true", "The plan image is decorative inside a named link.")
    check(plan.find(None, "plan-label") is not None, "The floor plan keeps its visible label.")
    enter = entrance.find("a", "enter-button")
    check(enter is not None and enter.attrs.get("href") == "#main" and "Step inside" in enter.text(), "Keep the Step inside button.")
    check("document.querySelector('.enter-plan')" in JS, "app.js must wire the .enter-plan link.")
    check("enter-map" not in JS and "dallas" not in JS.lower(), "app.js must not reference the removed map.")
    for removed in (".map-frame", ".dallas-map", ".enter-map"):
        check(removed not in CSS, f"Obsolete CSS rule remains: {removed}")
    plan_rule = css_rule(".enter-plan")
    check("overflow:hidden" in plan_rule and "background:var(--plan-paper)" in plan_rule, "The plan must sit on cream paper and be cropped.")
    check(re.search(r"rotate\(-?\d", css_rule(".floor-plan")) is not None, "The floor plan must be turned diagonally.")
    check(not hex_rgb(css_var("plan-paper"))[2] > hex_rgb(css_var("plan-paper"))[0], "Plan paper must be a warm cream.")
    check(".enter-plan:focus-visible" in CSS, "The plan link needs a visible focus style.")

    # ---- Floor plan SVG ----
    svg_path = ROOT / "assets/brand/entry-floor-plan.svg"
    check(svg_path.is_file(), "Missing assets/brand/entry-floor-plan.svg.")
    svg_text = svg_path.read_text(encoding="utf-8")
    try:
        svg_root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise AssertionError(f"Floor plan SVG is not well-formed XML: {exc}")
    check(svg_root.tag == "{http://www.w3.org/2000/svg}svg", "Floor plan root must be an SVG element.")
    lower_svg = svg_text.lower()
    check("<image" not in lower_svg, "The floor plan must not embed raster images.")
    check("<script" not in lower_svg and "javascript:" not in lower_svg, "The floor plan must not contain script.")
    check("<foreignobject" not in lower_svg, "The floor plan must not contain foreignObject.")
    check(not re.search(r"href\s*=\s*[\"'](?!#)", svg_text), "The floor plan may only reference internal fragments.")
    check("@import" not in lower_svg and not re.search(r"url\((?!#)", svg_text), "The floor plan must not load external resources.")
    check(not re.search(r"https?://(?!www\.w3\.org/2000/svg)", svg_text), "The floor plan must not contain external URLs.")
    for token in OLD_BLUE_TOKENS + ("blue", "navy"):
        check(token not in lower_svg, f"Blue colour in floor plan: {token}")
    strokes = [c.lower() for c in re.findall(r"stroke\s*[:=]\s*\"?(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b", svg_text)]
    check(len(strokes) >= 3, "The floor plan must declare its line colours.")
    for colour in strokes:
        check(is_green(colour), f"Floor plan line colour must be green: {colour}")
    for colour in re.findall(r"#[0-9a-fA-F]{6}\b", svg_text):
        check(not is_blue(colour), f"Blue colour in floor plan: {colour}")
    fills = [c.lower() for c in re.findall(r"fill\s*[:=]\s*\"?(#[0-9a-fA-F]{6})\b", svg_text)]
    check(css_var("plan-paper") in fills, "The floor plan paper must match --plan-paper.")
    ns = "{http://www.w3.org/2000/svg}"
    elements = list(svg_root.iter())
    count = lambda tag: sum(1 for e in elements if e.tag == ns + tag)
    check(len(elements) >= 100, f"Floor plan is not complex enough: {len(elements)} elements.")
    check(count("circle") >= 20, f"Floor plan needs tree/planting circles: {count('circle')}.")
    check(count("rect") >= 30, f"Floor plan needs furniture and openings: {count('rect')} rects.")
    check(count("path") >= 20, f"Floor plan needs wall and detail paths: {count('path')}.")
    tree_uses = [e for e in elements if e.tag == ns + "use" and e.get("href") == "#tree"]
    check(len(tree_uses) >= 6, f"Floor plan needs multiple placed trees: {len(tree_uses)}.")
    arcs = [e for e in elements if e.tag == ns + "path" and re.search(r"[Aa]\s*\d", e.get("d", ""))]
    check(len(arcs) >= 6, f"Floor plan needs door-swing arcs: {len(arcs)}.")
    labels = {"".join(e.itertext()).strip().upper() for e in elements if e.tag == ns + "text"}
    check({"COURTYARD", "TERRACE", "GARDEN"} <= labels, f"Floor plan must label exterior spaces: {sorted(labels)}")
    check(any("NOT TO SCALE" in label for label in labels), "Floor plan must state it is conceptual / not to scale.")

    # ---- Brand manifest provenance ----
    brand = json.loads((ROOT / "assets/brand/manifest.json").read_text(encoding="utf-8"))
    check("entry-floor-plan.svg" in brand, "Brand manifest must record the floor plan's provenance.")
    plan_record = brand["entry-floor-plan.svg"]
    check(all(plan_record.get(k) for k in ("source", "type", "date", "scale")), "Floor-plan provenance must include source, type, date and scale.")
    check("no external source" in plan_record["source"].lower() and "raster" in plan_record["source"].lower(), "Floor-plan provenance must state it is hand-authored with no raster/external input.")
    check(brand.get("jasmine-vines-v1.png", {}).get("sha256") == BASELINE_HASHES["assets/brand/jasmine-vines-v1.png"], "Brand manifest must keep the jasmine record.")
    check(brand.get("dallas-map.jpeg", {}).get("sha256") == BASELINE_HASHES["assets/brand/dallas-map.jpeg"], "Brand manifest must keep the (preserved, unused) Dallas map record.")
    check("gallery_selection" in brand, "Brand manifest must keep the gallery selection.")

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
        with Image.open(asset) as image:
            check(image.size == (record["width"], record["height"]), f"Image size drift: {name}")
    for name in ("fraunces-OFL.txt", "instrument-sans-OFL.txt"):
        check("SIL OPEN FONT LICENSE" in (ROOT / "assets/fonts" / name).read_text(), f"Missing font license: {name}")

    expected_rasters = (
        {f"assets/{name}" for name in manifest["assets"]}
        | {f"assets/brief/{name}" for name in brief_manifest["assets"]}
        | {f"assets/brief/{name}" for name in FEEDBACK_2_MANIFEST["assets"]}
        | {"assets/brand/jasmine-vines-v1.png", "assets/brand/dallas-map.jpeg"}
    )
    actual_rasters = {p.relative_to(ROOT).as_posix() for p in (ROOT / "assets").rglob("*") if p.suffix.lower() in RASTER_SUFFIXES}
    check(actual_rasters == expected_rasters, f"Raster asset set changed: added {sorted(actual_rasters - expected_rasters)}, missing {sorted(expected_rasters - actual_rasters)}")

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

    print(f"PASS: structure, nine-image gallery, floor-plan entry, sage wordmark, vine, footer mark, inquiry isolation, asset integrity, {ratio:.2f}:1 core contrast")
    return 0


def css_var_text(name: str) -> str:
    match = re.search(r"--" + re.escape(name) + r":([^;}]+)", CSS)
    if not match:
        raise AssertionError(f"Missing CSS custom property --{name}")
    return match.group(1)


def test_site() -> None:
    """pytest entry point."""
    assert main() == 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
