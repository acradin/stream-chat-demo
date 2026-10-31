import unittest

from apps.desktop.panel import FILLS, GLASS_FILL, composite, paint_layers


class DesktopPanelTests(unittest.TestCase):
    def test_screen_black_is_neutral_but_normal_black_dims_the_backdrop(self):
        backdrop = (100, 150, 200)
        self.assertEqual(composite(backdrop, GLASS_FILL), backdrop)
        self.assertEqual(composite(backdrop, FILLS[1]), (80, 120, 160))
        self.assertEqual(composite((85, 170, 255), FILLS[0]), (100, 200, 255))

    def test_rounded_panel_and_glass_do_not_fade_content_or_shadow_inside(self):
        shadow, base, glass = paint_layers(278, 448)
        self.assertEqual(base.getpixel((139, 224))[3], 255)
        self.assertEqual(base.getpixel((0, 0))[3], 0)
        self.assertEqual(shadow.getpixel((139, 224))[3], 0)
        self.assertEqual(glass.getpixel((139, 224))[3], 0)
