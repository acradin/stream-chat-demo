"""Regenerate the bundled Windows/Linux SVG fallback with resvg-py 0.5.0.

Build-time only: python -m pip install resvg-py==0.5.0
Run from any OS; no browser or runtime SVG dependency is required.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
import math
import copy
import resvg_py

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "figma"
NAMES = ("header", "settings", "back", "orb-face", "welcome-face", "wordmark", "arrow", "edit", "crown")


def slider_variants():
    original = ET.parse(ASSETS / "v2-source-count-slider.svg").getroot()
    for count, stop in enumerate((9,45,89,132,169),1):
        node = copy.deepcopy(original)
        for child in list(node):
            # The original Plus-lock glyphs are retained in the source, but
            # the demo supports all five counts without a subscription.
            if child.tag.endswith("g") and child.get("clip-path"):
                node.remove(child)
            if child.get("opacity") == "0.72":
                rect = next(iter(child))
                rect.set("width",str(stop))
            if child.get("fill") == "#2DFF8F":
                child.set("transform",f"translate({stop-45} 0)")
        ET.ElementTree(node).write(ASSETS / f"v2-source-count-slider-{count}.svg",encoding="unicode")


def main():
    slider_variants()
    for name in (*NAMES,*(f"count-slider-{i}" for i in range(1,6))):
        source = ASSETS / ("v2-header.svg" if name == "header" else f"v2-source-{name}.svg")
        node = ET.parse(source).getroot()
        # Set an explicit physical viewport before parsing: zoom/width alone
        # in resvg rounds the original fractional viewport (e.g. 14.4776px).
        node.set("width",str(math.ceil(float(node.attrib["width"])*4)))
        node.set("height",str(math.ceil(float(node.attrib["height"])*4)))
        (ASSETS / f"v2-{name}@4x.png").write_bytes(resvg_py.svg_to_bytes(
            svg_string=ET.tostring(node,encoding="unicode"),skip_system_fonts=True))


if __name__ == "__main__":
    main()
