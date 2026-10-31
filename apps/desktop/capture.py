"""Explicit-trigger desktop screenshot capture. No files or network I/O."""

import io

from PIL import Image, ImageGrab


def capture_primary_screen() -> bytes:
    with ImageGrab.grab(all_screens=False) as source:
        image = source.convert("RGB")
    try:
        image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        image.save(stream, format="JPEG", quality=85)
        return stream.getvalue()
    finally:
        image.close()
