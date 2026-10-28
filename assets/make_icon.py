"""Render the application icon used by PyInstaller."""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pamf_replacer.ui import make_app_icon  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(icon, size: int) -> bytes:
    pixmap = icon.pixmap(size, size)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    if not pixmap.save(buffer, "PNG"):
        raise RuntimeError(f"Could not render the {size}x{size} icon")
    data = bytes(buffer.data())
    buffer.close()
    return data


def main() -> int:
    app = QApplication([])  # noqa: F841 - required for QPixmap
    icon = make_app_icon()
    images = [png_bytes(icon, size) for size in SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = []
    for size, data in zip(SIZES, images):
        dimension = 0 if size >= 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        offset += len(data)

    destination = ROOT / "assets" / "app.ico"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + b"".join(entries) + b"".join(images))
    print(f"Wrote {destination} ({destination.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
