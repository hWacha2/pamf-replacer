"""Entry point for PAMF Replacer."""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from pamf_replacer.ui import APP_DIR, MainWindow, make_app_icon


def _install_excepthook() -> None:
    def handle(exc_type, exc_value, exc_traceback) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            if sys.stderr is not None:
                print(text, file=sys.stderr)
        except Exception:
            pass
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Необработанная ошибка")
        box.setText("Приложение столкнулось с ошибкой.")
        box.setDetailedText(text)
        box.exec()

    sys.excepthook = handle


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PAMF Replacer")
    app.setApplicationDisplayName("PAMF Replacer")
    app.setOrganizationName("PAMFReplacer")
    app.setWindowIcon(make_app_icon())
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    _install_excepthook()

    window = MainWindow()
    window.show()
    if "--smoke-test" in sys.argv:
        tools = window.tools
        report = (
            f"frozen={getattr(sys, 'frozen', False)}\n"
            f"app_dir={APP_DIR}\n"
            f"ready={tools.ready}\n"
            f"pamf={tools.pamf}\n"
            f"ffmpeg={tools.ffmpeg}\n"
            f"ffprobe={tools.ffprobe}\n"
            f"pam_zone={'ok' if window.pam_zone is not None else 'missing'}\n"
        )
        try:
            (Path(tempfile.gettempdir()) / "pamf-replacer-smoke.txt").write_text(report, encoding="utf-8")
        except OSError:
            pass
        QTimer.singleShot(1500, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
