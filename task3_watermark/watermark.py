"""Водяной знак в самой тёмной области изображения.

Используется только Pillow (pip install pillow).

Примеры:
    python3 watermark.py input.png
    python3 watermark.py input.png -o result.png -t "© Моя компания"
    python3 watermark.py input.jpg --font /path/to/font.ttf

Как это работает:
 1. Размер водяного знака определяет размер искомой области (текст + поля).
 2. Изображение переводится в яркость (оттенки серого) и уменьшается
    усреднением (BOX) — так поиск быстрый даже для больших картинок.
 3. По уменьшенной копии строится интегральное изображение (таблица
    префиксных сумм): сумма яркости любого прямоугольника — 4 обращения
    к таблице. Перебираются все положения окна, выбирается то, где
    средняя яркость минимальна.
 4. В найденное окно рисуется светлый текст с мягкой тенью.
 5. Результат сохраняется отдельным файлом, исходник не меняется.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

DEFAULT_TEXT = "© Watermark"

FONT_CANDIDATES = [
    "arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def find_darkest_window(gray: Image.Image, win_w: int, win_h: int, max_side: int = 400):
    """Ищет окно win_w x win_h с минимальной средней яркостью.

    gray — изображение в режиме "L". Возвращает (x, y, средняя_яркость_0_255)
    в координатах исходного изображения (x, y — левый верхний угол окна).
    """
    width, height = gray.size
    win_w, win_h = min(win_w, width), min(win_h, height)

    scale = min(1.0, max_side / max(width, height))
    small_w = max(1, round(width * scale))
    small_h = max(1, round(height * scale))
    small = gray.resize((small_w, small_h), Image.BOX) if scale < 1 else gray
    ww = max(1, min(small_w, round(win_w * scale)))
    wh = max(1, min(small_h, round(win_h * scale)))
    data = small.tobytes()

    integral = [[0] * (small_w + 1) for _ in range(small_h + 1)]
    for y in range(small_h):
        row_sum = 0
        above, current = integral[y], integral[y + 1]
        base = y * small_w
        for x in range(small_w):
            row_sum += data[base + x]
            current[x + 1] = above[x + 1] + row_sum

    best_sum, best_x, best_y = None, 0, 0
    for y in range(small_h - wh + 1):
        top, bottom = integral[y], integral[y + wh]
        for x in range(small_w - ww + 1):
            total = bottom[x + ww] - top[x + ww] - bottom[x] + top[x]
            if best_sum is None or total < best_sum:
                best_sum, best_x, best_y = total, x, y

    mean = best_sum / (ww * wh)
    x = min(round(best_x / scale), width - win_w)
    y = min(round(best_y / scale), height - win_h)
    return x, y, mean


def load_font(size: int, font_path: str = None) -> ImageFont.FreeTypeFont:
    if font_path:
        return ImageFont.truetype(font_path, size)
    for candidate in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    print("Предупреждение: не найден шрифт с кириллицей, используется встроенный "
          "(только латиница). Укажите шрифт через --font.", file=sys.stderr)
    return ImageFont.load_default(size)


def flatten_on_white(img: Image.Image) -> Image.Image:
    """RGBA -> RGB на белом фоне: прозрачные места не считаются «тёмными»."""
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.getchannel("A"))
    return background


def relative_luminance(gray_value: float) -> float:
    """Относительная яркость по WCAG для серого значения 0..255."""
    c = gray_value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(text_gray: float, background_gray: float) -> float:
    a, b = relative_luminance(text_gray), relative_luminance(background_gray)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def add_watermark(src_path: str, dst_path: str, text: str = DEFAULT_TEXT,
                  font_path: str = None, font_ratio: float = 1 / 28) -> dict:
    """Накладывает текстовый водяной знак в самую тёмную область.

    font_ratio — размер шрифта как доля ширины изображения.
    Возвращает словарь с информацией о результате.
    """
    with Image.open(src_path) as opened:
        img = ImageOps.exif_transpose(opened).convert("RGBA")
        original_format = opened.format

    width, height = img.size

    font_size = max(12, int(width * font_ratio))
    font = load_font(font_size, font_path)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    while right - left > width * 0.9 and font_size > 8:
        font_size -= 2
        font = load_font(font_size, font_path)
        left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    text_w, text_h = right - left, bottom - top
    pad = max(6, font_size // 2)
    win_w, win_h = text_w + 2 * pad, text_h + 2 * pad

    gray = flatten_on_white(img).convert("L")
    win_x, win_y, mean_brightness = find_darkest_window(gray, win_w, win_h)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    tx = win_x + (win_w - text_w) // 2 - left
    ty = win_y + (win_h - text_h) // 2 - top
    shadow = max(1, font_size // 16)
    draw.text((tx + shadow, ty + shadow), text, font=font, fill=(0, 0, 0, 150))
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 235))
    result = Image.alpha_composite(img, layer)

    save_format = (original_format or "PNG").upper()
    if save_format in ("JPEG", "JPG") or dst_path.lower().endswith((".jpg", ".jpeg")):
        result = result.convert("RGB")
        result.save(dst_path, quality=95)
    else:
        result.save(dst_path)

    return {
        "window": (win_x, win_y, win_w, win_h),
        "mean_brightness": mean_brightness,
        "contrast": contrast_ratio(235, mean_brightness),
        "font_size": font_size,
        "output": dst_path,
    }


def main():
    parser = argparse.ArgumentParser(description="Водяной знак в самой тёмной области изображения")
    parser.add_argument("input", help="путь к исходному изображению")
    parser.add_argument("-o", "--output", help="куда сохранить (по умолчанию <имя>_watermarked.<расширение>)")
    parser.add_argument("-t", "--text", default=DEFAULT_TEXT, help=f'текст знака (по умолчанию "{DEFAULT_TEXT}")')
    parser.add_argument("--font", help="путь к .ttf/.otf шрифту")
    args = parser.parse_args()

    output = args.output
    if not output:
        root, ext = os.path.splitext(args.input)
        output = f"{root}_watermarked{ext}"
    if os.path.abspath(output) == os.path.abspath(args.input):
        parser.error("выходной файл не должен совпадать с исходным")

    info = add_watermark(args.input, output, text=args.text, font_path=args.font)
    x, y, w, h = info["window"]
    print(f"Готово: {info['output']}")
    print(f"Самая тёмная область: x={x}, y={y}, {w}x{h} px, "
          f"средняя яркость {info['mean_brightness']:.1f}/255")
    print(f"Контраст текста с фоном: {info['contrast']:.1f}:1 (норма WCAG для текста ≥ 4.5:1)")


if __name__ == "__main__":
    main()
