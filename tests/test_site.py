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

    required_ids = {"main", "projects", "philosophy", "services", "about", "inquiry", "inquiry-form"}
    check(required_ids <= parser.ids, f"Missing required landmarks: {sorted(required_ids - parser.ids)}")
    for href in parser.links:
        check(bool(href), "Every link needs a destination.")
        check(not re.match(r"(?:https?:)?//", href), f"External destination is not cleared: {href}")
        if href.startswith("#"):
            check(href[1:] in parser.ids, f"Broken internal link: {href}")

    check(len(parser.images) == 5, "The evidence-safe image count changed.")
    for image in parser.images:
        check(bool(image.get("alt", "").strip()), f"Missing image alternative text: {image.get('src')}")
        source = ROOT / image["src"]
        check(source.is_file(), f"Missing image asset: {source}")

    for form in parser.forms:
        check("action" not in form and "method" not in form, "The local inquiry must have no delivery target.")
        check("novalidate" in form, "The inquiry expects the explicit accessible validation path.")
    for control in parser.controls:
        control_id = control.get("id")
        if control_id:
            check(control_id in parser.labels_for, f"Unlabelled form control: {control_id}")

    for budget in ("$500–$1,500", "$1,500–$5,000", "$5,000–$15,000", "$15,000+", "Not sure yet"):
        check(budget in HTML, f"Missing approved inquiry option: {budget}")

    unsafe_global = ("testimonial", "award-winning", "luxury interiors", "commissioned by", "photographed by")
    lower_html = HTML.lower()
    for phrase in unsafe_global:
        check(phrase not in lower_html, f"Unsafe portfolio claim found: {phrase}")

    noel_match = re.search(r'<article class="noel".*?</article>', HTML, flags=re.DOTALL)
    check(noel_match is not None, "Noel evidence section is missing.")
    noel_text = noel_match.group(0).lower()
    for phrase in ("inspired the", "translated into", "became the", "resulted in", "built", "completed", "photographed", "commissioned"):
        check(phrase not in noel_text, f"Causal or realized Noel claim found: {phrase}")

    for transport in ("fetch(", "xmlhttprequest", "sendbeacon", "localstorage", "sessionstorage", "websocket"):
        check(transport not in JS.lower(), f"The inquiry contains a disallowed data path: {transport}")
    check("animation:" not in CSS.lower() and "transition:" not in CSS.lower(), "Motion is out of scope for the static gate.")
    check("@import" not in CSS.lower(), "External style imports are not allowed.")

    ratio = (luminance("#211f1b") + 0.05) / (luminance("#eeeae2") + 0.05)
    if ratio < 1:
        ratio = 1 / ratio
    check(ratio >= 7, f"Core palette contrast fell below AAA: {ratio:.2f}:1")

    manifest = json.loads((ROOT / "assets" / "manifest.json").read_text(encoding="utf-8"))
    for name, record in manifest["assets"].items():
        path = ROOT / "assets" / name
        check(path.is_file(), f"Manifest asset missing: {name}")
        check(sha256(path) == record["sha256"], f"Evidence asset drift: {name}")

    dimensions = {
        "hero-desktop.png": (1440, 640),
        "hero-mobile.png": (390, 592),
        "hero-reflow.png": (320, 592),
        "noel-moodboard-crop.png": (684, 748),
        "noel-visualization-crop.png": (646, 760),
    }
    for name, expected in dimensions.items():
        with Image.open(ROOT / "assets" / name) as image:
            check(image.size == expected, f"Unexpected crop dimensions for {name}: {image.size}")

    print(f"PASS: semantic structure, internal navigation, evidence claims, inquiry isolation, asset hashes, and {ratio:.2f}:1 core contrast")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

