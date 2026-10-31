import unittest
from xml.etree import ElementTree as ET

from PIL import Image
from apps.desktop.branding import ASSETS
from apps.desktop.vector import source


class DesktopArtworkTests(unittest.TestCase):
    def test_shipped_fallbacks_preserve_svg_resolution_and_transparency(self):
        for name in ("header", "settings", "orb-face", "welcome-face", "wordmark", "arrow", "edit", "crown", *(f"count-slider-{i}" for i in range(1,6))):
            with self.subTest(name=name):
                svg = ET.parse(source(name)).getroot()
                with Image.open(ASSETS / "figma" / f"v2-{name}@4x.png") as image:
                    self.assertEqual(image.mode, "RGBA")
                    # resvg rounds the SVG viewport to whole physical pixels.
                    self.assertLessEqual(abs(image.width-float(svg.attrib["width"])*4), 1)
                    self.assertLessEqual(abs(image.height-float(svg.attrib["height"])*4), 1)
                    low, high = image.getchannel("A").getextrema()
                    self.assertEqual(low, 0)
                    self.assertGreater(high, 200)

    def test_header_remains_outlined_artwork_without_font_or_external_dependency(self):
        svg = ET.parse(source("header")).getroot()
        tags = {node.tag.rsplit("}",1)[-1] for node in svg.iter()}
        self.assertIn("path", tags)
        self.assertFalse({"text", "image", "foreignObject"} & tags)
        for node in svg.iter():
            self.assertNotIn("href", node.attrib)

    def test_slider_uses_figma_stops_and_does_not_advertise_demo_locks(self):
        for count,stop in enumerate((9,45,89,132,169),1):
            root = ET.parse(source(f"count-slider-{count}")).getroot()
            self.assertEqual(root.attrib["viewBox"],"0 0 178 32")
            knob = next(n for n in root if n.get("fill")=="#2DFF8F")
            self.assertEqual(knob.get("transform"),f"translate({stop-45} 0)")
            self.assertFalse(any(n.get("clip-path") for n in root))
