from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "app.js").read_text(encoding="utf-8")


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def luminance(hex_color: str) -> float:
    values = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = SiteParser()
    parser.feed(HTML)

    check(HTML.lower().count("<h1") == 1, "The page must have exactly one h1.")
    check(parser.headings and parser.headings[0] == 1, "The heading sequence must start at h1.")
    check(all(current - previous <= 1 for previous, current in zip(parser.headings, parser.headings[1:])), "Heading levels must not skip.")

    required_ids = {"main", "projects", "philosophy", "services", "about", "process", "entrance", "inquiry", "inquiry-form"}
    check(required_ids <= parser.ids, f"Missing required landmarks: {sorted(required_ids - parser.ids)}")
    for href in parser.links:
        check(bool(href), "Every link needs a destination.")
        check(not re.match(r"(?:https?:)?//", href), f"External destination is not cleared: {href}")
        if href.startswith("#"):
            check(href[1:] in parser.ids, f"Broken internal link: {href}")

    check(HTML.count("data-lightbox ") == 6, "The gallery must contain Heather's six selected images.")
    for image in parser.images:
        if image.get("id") == "viewer-image":
            continue  # Populated from the selected accessible gallery image.
        check(bool(image.get("alt", "").strip()) or (image.get('aria-hidden') == 'true' and 'alt' in image), f"Missing image alternative text: {image.get('src')}")
        source = ROOT / image["src"]
        check(source.is_file(), f"Missing image asset: {source}")

    for form in parser.forms:
        check("action" not in form and "method" not in form, "The local inquiry must have no delivery target.")
        check("novalidate" in form, "The inquiry expects the explicit accessible validation path.")
    for control in parser.controls:
        control_id = control.get("id")
        if control_id:
            check(control_id in parser.labels_for, f"Unlabelled form control: {control_id}")

    check('name="budget"' not in HTML, "Do not add an unrequested budget question.")
    check('data-placeholder="portrait"' in HTML and 'data-placeholder="logo"' in HTML, "Reserve the promised portrait and logo.")
    check('heather@kingchingaya.com' in HTML, "Keep the exact user-supplied email.")
    check('Starting at $350' in HTML, "Preserve the supplied Room Refresh price.")
    check('id="form-fields" disabled' in HTML, "With no JS the form must not submit via a default GET.")
    check('summary.replaceChildren()' in JS and 'dd.textContent = value' in JS, "Inquiry content must remain plain text.")

    unsafe_global = ("testimonial", "award-winning", "luxury interiors", "commissioned by", "photographed by")
    lower_html = HTML.lower()
    for phrase in unsafe_global:
        check(phrase not in lower_html, f"Unsafe portfolio claim found: {phrase}")

    for transport in ("fetch(", "xmlhttprequest", "sendbeacon", "localstorage", "sessionstorage", "websocket"):
        check(transport not in JS.lower(), f"The inquiry contains a disallowed data path: {transport}")
    lower_css = CSS.lower().replace("@media(", "@media (")
    if "animation:" in lower_css or "transition:" in lower_css:
        check("@media (prefers-reduced-motion: no-preference)" in lower_css, "Motion must be opt-in behind prefers-reduced-motion: no-preference.")
        reduced = lower_css.split("@media (prefers-reduced-motion: reduce)", 1)[-1]
        check("animation:none" in reduced and "transition:none" in reduced, "Reduced motion must disable animation and transition.")
        check("scroll-behavior:auto" in reduced, "Reduced motion must restore instant scrolling.")
        before_optin = lower_css.split("@media (prefers-reduced-motion: no-preference)")[0]
        check(".reveal" not in before_optin, "Reveal states must live inside the motion opt-in so content stays visible without motion or JS.")
        check("motion-ready" in JS.lower(), "Reveal styling must be gated on a class the script adds, so content is never hidden when the script fails.")
    check("@import" not in CSS.lower(), "External style imports are not allowed.")

    ink = re.search(r'--ink:(#[0-9a-f]{6})', CSS).group(1)
    paper = re.search(r'--paper:(#[0-9a-f]{6})', CSS).group(1)
    ratio = (luminance(ink) + 0.05) / (luminance(paper) + 0.05)
    if ratio < 1:
        ratio = 1 / ratio
    check(ratio >= 7, f"Core palette contrast fell below AAA: {ratio:.2f}:1")

    manifest = json.loads((ROOT / "assets" / "manifest.json").read_text(encoding="utf-8"))
    for name, record in manifest["assets"].items():
        path = ROOT / "assets" / name
        check(path.is_file(), f"Manifest asset missing: {name}")
        check(sha256(path) == record["sha256"], f"Evidence asset drift: {name}")

    brief = json.loads((ROOT / "assets/brief/manifest.json").read_text())
    check(len(brief["assets"]) == 20, "The supplied portfolio has 20 design images.")
    for name, record in brief["assets"].items():
        asset = ROOT / "assets/brief" / name
        check(sha256(asset).lower() == record["sha256"], f"Brief image drift: {name}")
        with Image.open(asset) as image:
            check(image.size == (record["width"], record["height"]), f"Image size drift: {name}")
    for name in ("fraunces-OFL.txt", "instrument-sans-OFL.txt"):
        check("SIL OPEN FONT LICENSE" in (ROOT / "assets/fonts" / name).read_text(), f"Missing font license: {name}")
    selection = json.loads((ROOT / 'assets/brand/manifest.json').read_text())['gallery_selection']
    gallery_sources = re.findall(r'<a href="(assets/brief/[^"]+)" class="study-image" data-lightbox', HTML)
    check(gallery_sources == [f'assets/brief/{name}' for name in selection['filenames']], 'Gallery image order differs from the numbered feedback selection.')
    check(selection['review_image_numbers'] == [1, 2, 8, 11, 14, 18], 'Keep the six image numbers supplied by Heather.')
    check('floor-plan' not in HTML and 'assets/brand/dallas-map.jpeg' in HTML, 'Use the Dallas map for the entry graphic.')
    with Image.open(ROOT/'assets/brand/jasmine-vines-v1.png') as image:
        check(image.mode == 'RGBA' and image.getextrema()[3][0] == 0, 'The jasmine overlay must preserve transparency.')
    check('--plum:' not in CSS and '#c4b2bc' not in CSS, 'The removed plum palette must not return.')

    print(f"PASS: semantic structure, internal navigation, evidence claims, inquiry isolation, asset hashes, and {ratio:.2f}:1 core contrast")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
