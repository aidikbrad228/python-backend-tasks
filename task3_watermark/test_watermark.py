import os
import random
import tempfile
import unittest

from PIL import Image, ImageDraw

import watermark as wm


def brute_force_darkest(gray, win_w, win_h):
    """Эталон: честный перебор всех окон на полноразмерном изображении."""
    w, h = gray.size
    px = gray.load()
    best = None
    for y in range(h - win_h + 1):
        for x in range(w - win_w + 1):
            total = sum(px[i, j] for j in range(y, y + win_h) for i in range(x, x + win_w))
            if best is None or total < best:
                best = total
    return best / (win_w * win_h)


class FindDarkestTest(unittest.TestCase):
    def test_matches_brute_force_on_random_images(self):
        random.seed(7)
        for _ in range(30):
            w, h = random.randint(8, 30), random.randint(8, 30)
            gray = Image.new("L", (w, h))
            gray.putdata([random.randint(0, 255) for _ in range(w * h)])
            ww, wh = random.randint(1, w), random.randint(1, h)
            _, _, mean = wm.find_darkest_window(gray, ww, wh)
            self.assertAlmostEqual(mean, brute_force_darkest(gray, ww, wh), places=6)

    def test_finds_dark_block_in_bright_image(self):
        gray = Image.new("L", (2000, 1200), 200)
        ImageDraw.Draw(gray).rectangle([1400, 900, 1799, 1099], fill=5)
        x, y, mean = wm.find_darkest_window(gray, 300, 100)
        self.assertTrue(1400 - 8 <= x and x + 300 <= 1800 + 8, x)
        self.assertTrue(900 - 8 <= y and y + 100 <= 1100 + 8, y)
        self.assertLess(mean, 20)

    def test_window_always_inside_image(self):
        for size in ((50, 40), (999, 333), (4000, 3000)):
            gray = Image.new("L", size, 0)
            ww, wh = min(120, size[0]), min(40, size[1])
            x, y, _ = wm.find_darkest_window(gray, 120, 40)
            self.assertTrue(0 <= x and x + ww <= size[0])
            self.assertTrue(0 <= y and y + wh <= size[1])

    def test_window_larger_than_image_is_clamped(self):
        gray = Image.new("L", (20, 10), 50)
        x, y, mean = wm.find_darkest_window(gray, 500, 500)
        self.assertEqual((x, y), (0, 0))
        self.assertAlmostEqual(mean, 50)


class AddWatermarkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def make_image(self, name, size=(800, 500), mode="RGB", bg=(230, 230, 230), dark_box=(560, 330, 780, 480)):
        img = Image.new(mode, size, bg if mode != "RGBA" else bg + (255,))
        ImageDraw.Draw(img).rectangle(dark_box, fill=(10, 10, 30) if mode != "RGBA" else (10, 10, 30, 255))
        img.save(self.path(name))
        return self.path(name)

    def test_watermark_lands_in_darkest_area_and_is_readable(self):
        src = self.make_image("a.png")
        info = wm.add_watermark(src, self.path("out.png"), text="© Test")
        x, y, w, h = info["window"]
        self.assertTrue(560 - 8 <= x and x + w <= 780 + 8)
        self.assertTrue(330 - 8 <= y and y + h <= 480 + 8)
        self.assertGreater(info["contrast"], 4.5)
        with Image.open(src) as a, Image.open(self.path("out.png")) as b:
            before, after = a.convert("RGB"), b.convert("RGB")
        self.assertEqual(before.size, after.size)
        self.assertEqual(before.getpixel((10, 10)), after.getpixel((10, 10)))
        crop = after.crop((x, y, x + w, y + h)).convert("L")
        self.assertGreater(crop.getextrema()[1], 200)

    def test_original_is_not_modified(self):
        src = self.make_image("a.png")
        with open(src, "rb") as f:
            original_bytes = f.read()
        wm.add_watermark(src, self.path("out.png"))
        with open(src, "rb") as f:
            self.assertEqual(f.read(), original_bytes)

    def test_jpeg_output(self):
        src = self.make_image("a.jpg")
        wm.add_watermark(src, self.path("out.jpg"))
        with Image.open(self.path("out.jpg")) as out:
            self.assertEqual(out.format, "JPEG")

    def test_transparent_png_transparent_area_not_treated_as_dark(self):
        img = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
        ImageDraw.Draw(img).rectangle([250, 180, 390, 290], fill=(20, 20, 40, 255))
        img.save(self.path("t.png"))
        info = wm.add_watermark(self.path("t.png"), self.path("out.png"), text="WM")
        x, y, w, h = info["window"]
        self.assertTrue(x >= 250 - 4 and y >= 180 - 4, info["window"])
        with Image.open(self.path("out.png")) as out:
            self.assertEqual(out.mode, "RGBA")

    def test_palette_and_grayscale_inputs(self):
        for mode in ("L", "P", "LA"):
            Image.new("RGB", (300, 200), (100, 100, 100)).convert(mode).save(self.path(f"{mode}.png"))
            wm.add_watermark(self.path(f"{mode}.png"), self.path(f"{mode}_out.png"))

    def test_tiny_image_and_long_text_do_not_crash(self):
        Image.new("RGB", (60, 40), (0, 0, 0)).save(self.path("tiny.png"))
        wm.add_watermark(self.path("tiny.png"), self.path("tiny_out.png"),
                         text="Очень длинный текст водяного знака")

    def test_cyrillic_text(self):
        src = self.make_image("a.png")
        wm.add_watermark(src, self.path("out.png"), text="© Веб-Технологии 2026")


if __name__ == "__main__":
    unittest.main(verbosity=1)
