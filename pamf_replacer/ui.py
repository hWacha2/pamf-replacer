"""PySide6 user interface for PAMF Replacer."""

from __future__ import annotations

import datetime as _dt
import shlex
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QLocale, Qt, QThread, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .config import AppConfig, load_config, save_config
from .media import MediaInfo, probe_media
from .pipeline import Cancelled, EncodeSettings, JobContext, PipelineResult, run_pipeline
from .tools import PamInfo, Toolchain, detect_tools, read_pam_info

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)
VIDEO_SUFFIXES = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
    ".m4v",
    ".ts",
    ".m2ts",
    ".mts",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".flv",
    ".vob",
    ".3gp",
}

DARK_QSS = """
QMainWindow, QDialog { background-color: #0f1116; }
QWidget { color: #e7ecf5; font-family: "Segoe UI"; font-size: 10pt; }
QWidget#root { background-color: #0f1116; }
QWidget#body { background-color: #0f1116; }
QFrame#panel { background-color: #171a21; border: 1px solid #252b37; border-radius: 14px; }
QFrame#modeBar { background-color: #141821; border: 1px solid #252b37; border-radius: 12px; }
QRadioButton { spacing: 8px; color: #c8d2e3; }
QRadioButton:disabled { color: #5f6a7e; }
QFrame#footer { background-color: #101319; border-top: 1px solid #252b37; }
QLabel#appTitle { font-size: 19pt; font-weight: 700; color: #f3f6fc; }
QLabel#subtitle { color: #7f8ba1; font-size: 9.5pt; }
QLabel#muted { color: #7f8ba1; }
QLabel#fieldLabel { color: #7f8ba1; font-size: 8.5pt; }
QLabel#value { color: #f1f5fc; font-weight: 600; }
QLabel#zoneTitle { font-size: 12pt; font-weight: 600; color: #f1f5fc; }
QLabel#zoneFile { font-size: 11pt; font-weight: 600; color: #f1f5fc; }
QLabel#zoneDetails { color: #8d99ae; font-size: 9pt; }
QLabel#warning { color: #f0b45a; font-size: 9pt; }
QLabel#stage { color: #dfe7f6; font-weight: 600; }
QLabel#status { color: #8d99ae; }
QLabel#progressText { color: #8d99ae; font-weight: 600; }
QLabel#chip { color: #7f8ba1; font-size: 8.5pt; }
QGroupBox {
    background-color: transparent;
    border: 1px solid #252b37;
    border-radius: 10px;
    margin-top: 15px;
    padding: 10px 12px 8px 12px;
    font-weight: 600;
    color: #aeb8cc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background-color: #171a21;
}
QPushButton {
    background-color: #232a36;
    border: 1px solid #303848;
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 600;
    color: #e9eef8;
}
QPushButton:hover { background-color: #2b3443; border-color: #3b4659; }
QPushButton:pressed { background-color: #1e2531; }
QPushButton:disabled { color: #5f6a7e; background-color: #1b212b; border-color: #252b37; }
QPushButton#primary {
    background-color: #4f7cff;
    border: 1px solid #4f7cff;
    color: #ffffff;
    padding: 11px 24px;
    font-size: 10.5pt;
}
QPushButton#primary:hover { background-color: #628bff; border-color: #628bff; }
QPushButton#primary:disabled { background-color: #2b3345; border-color: #2b3345; color: #66718a; }
QPushButton#ghost { background-color: transparent; border: 1px solid #2b3342; color: #9aa7bd; }
QPushButton#ghost:hover { background-color: #1b202a; color: #dbe4f4; }
QPushButton#danger { background-color: transparent; border: 1px solid #6a3a44; color: #f0a3ae; }
QPushButton#danger:hover { background-color: #2a1a1f; }
QPushButton#danger:disabled { color: #6a4a51; border-color: #3a2a2f; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #0e1117;
    border: 1px solid #2b3342;
    border-radius: 8px;
    padding: 6px 9px;
    color: #e9eef8;
    selection-background-color: #4f7cff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #5b8cff; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #6a7488;
    background-color: #12161d;
    border-color: #232a36;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: #151a22;
    border: 1px solid #2b3342;
    selection-background-color: #2b3b60;
    outline: 0;
}
QCheckBox { spacing: 8px; color: #c8d2e3; }
QCheckBox:disabled { color: #5f6a7e; }
QPlainTextEdit#log {
    background-color: #0b0e13;
    border: 1px solid #232936;
    border-radius: 10px;
    padding: 8px;
    color: #b9c2d4;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9pt;
    selection-background-color: #33508f;
}
QProgressBar { background-color: #1d222c; border: none; border-radius: 4px; }
QProgressBar::chunk { background-color: #4f7cff; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2c3444; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #39445a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #2c3444; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #39445a; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QToolTip { background-color: #1b212b; color: #e9eef8; border: 1px solid #303848; padding: 5px; }
QMessageBox QLabel { color: #e7ecf5; }
QDialogButtonBox QPushButton { min-width: 84px; }
"""


# ---------------------------------------------------------------------------
# Small widgets
# ---------------------------------------------------------------------------


def make_app_icon() -> QIcon:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, 256, 256)
    gradient.setColorAt(0.0, QColor("#5b8cff"))
    gradient.setColorAt(1.0, QColor("#7a5cff"))
    path = QPainterPath()
    path.addRoundedRect(16, 16, 224, 224, 48, 48)
    painter.fillPath(path, gradient)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#ffffff"))
    play = QPainterPath()
    play.moveTo(102, 82)
    play.lineTo(102, 174)
    play.lineTo(176, 128)
    play.closeSubpath()
    painter.drawPath(play)

    painter.setBrush(QColor(255, 255, 255, 70))
    for y in (58, 82, 174, 198):
        painter.drawRoundedRect(52, y, 14, 6, 3, 3)
    painter.end()
    return QIcon(pixmap)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._refresh()

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        self._full_text = text
        self.setToolTip(text)
        self._refresh()

    def _refresh(self) -> None:
        if not self._full_text:
            super().setText("")
            return
        width = max(20, self.width())
        metrics: QFontMetrics = self.fontMetrics()
        super().setText(metrics.elidedText(self._full_text, Qt.ElideMiddle, width))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()


class DropZone(QFrame):
    fileDropped = Signal(str, str)
    browseRequested = Signal()

    def __init__(
        self,
        role: str,
        step: str,
        title: str,
        hint: str,
        button_text: str,
        accent: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.role = role
        self.accent = QColor(accent)
        self.title_text = title
        self.button_text = button_text
        self._hover = False
        self._loaded = False
        self._busy = False
        self.setAcceptDrops(True)
        self.setMinimumHeight(176)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 17, 20, 17)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.badge = QLabel(step)
        self.badge.setFixedSize(22, 22)
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet(
            f"background-color: {accent}; color: white; border-radius: 11px; "
            "font-weight: 700; font-size: 9pt;"
        )
        top.addWidget(self.badge, 0, Qt.AlignTop)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("zoneTitle")
        hint_label = QLabel(hint)
        hint_label.setObjectName("muted")
        title_box.addWidget(title_label)
        title_box.addWidget(hint_label)
        top.addLayout(title_box)
        top.addStretch(1)
        layout.addLayout(top)

        layout.addSpacing(8)
        self.file_label = ElidedLabel("Перетащите файл сюда")
        self.file_label.setObjectName("zoneFile")
        self.file_label.setStyleSheet("color:#8d99ae;")
        layout.addWidget(self.file_label)

        self.details_label = QLabel("или нажмите, чтобы выбрать")
        self.details_label.setObjectName("zoneDetails")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("warning")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        layout.addWidget(self.warning_label)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        self.browse_button = QPushButton(button_text)
        self.browse_button.setObjectName("ghost")
        self.browse_button.setCursor(Qt.PointingHandCursor)
        self.browse_button.clicked.connect(self.browseRequested)
        button_row.addWidget(self.browse_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

    def _set_file_title(self, text: str, muted: bool) -> None:
        self.file_label.setText(text)
        self.file_label.setStyleSheet("color:#8d99ae;" if muted else "color:#f1f5fc;")

    def set_busy(self, message: str, path: Path | None = None) -> None:
        self._busy = True
        self._loaded = False
        self._set_file_title(message, True)
        self.details_label.setText(str(path) if path else "")
        self.warning_label.hide()
        self.browse_button.show()
        self.update()

    def set_loaded(self, path: Path, details: str, warning: str | None = None) -> None:
        self._busy = False
        self._loaded = True
        self._set_file_title(path.name, False)
        self.file_label.setToolTip(str(path))
        self.details_label.setText(details)
        if warning:
            self.warning_label.setText(warning)
            self.warning_label.show()
        else:
            self.warning_label.hide()
        self.browse_button.show()
        self.update()

    def set_error(self, message: str) -> None:
        self._busy = False
        self._loaded = False
        self._set_file_title("Не удалось прочитать файл", True)
        self.details_label.setText(message)
        self.warning_label.hide()
        self.browse_button.show()
        self.update()

    def set_inactive(self, title: str, details: str) -> None:
        self._busy = False
        self._loaded = False
        self._set_file_title(title, True)
        self.file_label.setToolTip("")
        self.details_label.setText(details)
        self.warning_label.hide()
        self.browse_button.hide()
        self.update()

    def clear(self) -> None:
        self._busy = False
        self._loaded = False
        self._set_file_title("Перетащите файл сюда", True)
        self.file_label.setToolTip("")
        self.details_label.setText("или нажмите, чтобы выбрать")
        self.warning_label.hide()
        self.browse_button.show()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        if not self.isEnabled():
            fill = QColor("#12151b")
            border = QColor("#242a35")
        elif self._hover:
            fill = QColor("#1a2231")
            border = self.accent
        elif self._loaded:
            fill = QColor("#151a23")
            border = QColor("#3a4761")
        elif self._busy:
            fill = QColor("#171c26")
            border = self.accent
        else:
            fill = QColor("#151922")
            border = QColor("#2b3342")

        painter.fillPath(path, fill)
        pen = QPen(border, 1.4)
        if not self._loaded:
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.drawPath(path)

        if self._loaded:
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.accent if self.isEnabled() else QColor("#3a4761"))
            painter.drawRoundedRect(rect.left() + 5, rect.top() + 24, 3, rect.height() - 48, 1.5, 1.5)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    self._hover = True
                    self.update()
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.fileDropped.emit(url.toLocalFile(), self.role)
                event.acceptProposedAction()
                return
        event.ignore()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.browseRequested.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------


class CallWorker(QThread):
    ok = Signal(object)
    fail = Signal(str)

    def __init__(self, function, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._function = function

    def run(self) -> None:
        try:
            self.ok.emit(self._function())
        except Exception as error:  # noqa: BLE001 - shown to the user
            self.fail.emit(str(error))


class PipelineWorker(QThread):
    log = Signal(str)
    stage = Signal(str)
    progress = Signal(int)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, context: JobContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self._cancel = threading.Event()
        self._process: subprocess.Popen | None = None

    def _register_process(self, process: subprocess.Popen) -> None:
        self._process = process

    def cancel(self) -> None:
        self._cancel.set()
        process = self._process
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def run(self) -> None:
        try:
            result = run_pipeline(
                self.context,
                log=self.log.emit,
                stage=self.stage.emit,
                progress=self.progress.emit,
                cancel=self._cancel,
                on_process=self._register_process,
            )
            self.succeeded.emit(result)
        except Cancelled:
            self.cancelled.emit()
        except Exception as error:  # noqa: BLE001 - shown to the user
            self.failed.emit(str(error))


# ---------------------------------------------------------------------------
# Tools dialog
# ---------------------------------------------------------------------------


class ToolsDialog(QDialog):
    def __init__(self, tools: Toolchain, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Инструменты")
        self.setMinimumWidth(680)
        self.tools = tools

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(14)

        title = QLabel("Пути к внешним программам")
        title.setObjectName("zoneTitle")
        layout.addWidget(title)

        description = QLabel(
            "PAMFtool нужен для чтения и сборки .pam, FFmpeg — для кодирования видео и звука. "
            "Обычно программа находит их автоматически."
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.pamf_edit = self._add_row(layout, "PAMFtool", tools.pamf, "PAMFtool*.exe")
        self.ffmpeg_edit = self._add_row(layout, "FFmpeg", tools.ffmpeg, "ffmpeg.exe")
        self.ffprobe_edit = self._add_row(layout, "ffprobe", tools.ffprobe, "ffprobe.exe")

        auto_row = QHBoxLayout()
        auto_button = QPushButton("Найти автоматически")
        auto_button.setObjectName("ghost")
        auto_button.clicked.connect(self._auto_detect)
        auto_row.addWidget(auto_button)
        auto_row.addStretch(1)
        layout.addLayout(auto_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_row(self, layout: QVBoxLayout, label: str, value: Path | None, name: str) -> QLineEdit:
        box = QVBoxLayout()
        box.setSpacing(4)
        caption = QLabel(label)
        caption.setObjectName("fieldLabel")
        box.addWidget(caption)
        row = QHBoxLayout()
        edit = QLineEdit(str(value) if value else "")
        edit.setPlaceholderText(f"Найти {name}…")
        browse = QPushButton("Обзор…")
        browse.setObjectName("ghost")
        browse.clicked.connect(lambda: self._browse(edit, name))
        row.addWidget(edit, 1)
        row.addWidget(browse)
        box.addLayout(row)
        layout.addLayout(box)
        return edit

    def _browse(self, edit: QLineEdit, name: str) -> None:
        start = edit.text().strip() or str(APP_DIR)
        path, _ = QFileDialog.getOpenFileName(self, "Выберите исполняемый файл", start, f"{name} (*.exe);;Все файлы (*.*)")
        if path:
            edit.setText(path)

    def _auto_detect(self) -> None:
        found = detect_tools(APP_DIR)
        if found.pamf:
            self.pamf_edit.setText(str(found.pamf))
        if found.ffmpeg:
            self.ffmpeg_edit.setText(str(found.ffmpeg))
        if found.ffprobe:
            self.ffprobe_edit.setText(str(found.ffprobe))

    def _save(self) -> None:
        for edit, label in (
            (self.pamf_edit, "PAMFtool"),
            (self.ffmpeg_edit, "FFmpeg"),
            (self.ffprobe_edit, "ffprobe"),
        ):
            value = edit.text().strip()
            if value and not Path(value).is_file():
                QMessageBox.warning(self, "Инструменты", f"{label} не найден по пути:\n{value}")
                return

        self.tools = detect_tools(
            APP_DIR,
            self.pamf_edit.text().strip() or None,
            self.ffmpeg_edit.text().strip() or None,
            self.ffprobe_edit.text().strip() or None,
        )
        if not self.tools.ready:
            QMessageBox.warning(
                self,
                "Инструменты",
                "Не удалось найти: " + ", ".join(self.tools.missing) + ".\n"
                "Сборка будет недоступна, пока пути не будут указаны.",
            )
        self.accept()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"PAMF Replacer {__version__} — замена видео в PAMF")
        self.setWindowIcon(make_app_icon())
        self.resize(1240, 940)
        self.setMinimumSize(1024, 720)
        self.setAcceptDrops(True)

        self.config: AppConfig = load_config()
        self.tools: Toolchain = detect_tools(
            APP_DIR,
            self.config.pamf or None,
            self.config.ffmpeg or None,
            self.config.ffprobe or None,
        )
        self.pam_info: PamInfo | None = None
        self.source_info: MediaInfo | None = None
        self.pam_path: Path | None = None
        self.job_mode = "replace"  # "replace" or "edit"
        self._replace_audio_mode: str | None = None
        self._original_bitrate: float | None = None
        self._last_output: Path | None = None
        self._worker: PipelineWorker | None = None
        self._threads: list[CallWorker] = []
        self._pam_generation = 0
        self._source_generation = 0
        self._running = False

        self._build_ui()
        self.setStyleSheet(DARK_QSS)
        self._apply_config_to_ui()
        self._update_tool_status()
        self._sync_ui()

        for keys, slot in (
            ("Ctrl+O", self._choose_pam),
            ("Ctrl+Shift+O", self._choose_source),
            ("Ctrl+R", self._start_job),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(slot)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QWidget()
        body.setObjectName("body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 18, 24, 14)
        body_layout.setSpacing(12)

        body_layout.addLayout(self._build_header())
        body_layout.addWidget(self._build_mode_bar())

        zones = QHBoxLayout()
        zones.setSpacing(10)
        self.pam_zone = DropZone(
            "pam",
            "1",
            "Оригинальный PAM",
            "Откуда взять параметры видео",
            "Выбрать PAM…",
            "#5b8cff",
        )
        self.video_zone = DropZone(
            "video",
            "2",
            "Новое видео",
            "Чем заменить картинку и звук",
            "Выбрать видео…",
            "#4fd6a5",
        )
        self.pam_zone.fileDropped.connect(self._route_drop)
        self.video_zone.fileDropped.connect(self._route_drop)
        self.pam_zone.browseRequested.connect(self._choose_pam)
        self.video_zone.browseRequested.connect(self._choose_source)
        zones.addWidget(self.pam_zone, 1)
        arrow = QLabel("→")
        arrow.setObjectName("muted")
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedWidth(22)
        zones.addWidget(arrow)
        zones.addWidget(self.video_zone, 1)
        body_layout.addLayout(zones)

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_settings(), 11)
        content.addWidget(self._build_log(), 9)
        body_layout.addLayout(content, 1)

        root_layout.addWidget(body, 1)
        root_layout.addWidget(self._build_footer())

    def _build_mode_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("modeBar")
        self.mode_bar = bar
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(18)
        caption = QLabel("Что сделать с видео")
        caption.setObjectName("fieldLabel")
        self.edit_radio = QRadioButton("Изменить существующее")
        self.replace_radio = QRadioButton("Заменить на новое")
        self.replace_radio.setChecked(True)
        self.edit_radio.toggled.connect(
            lambda checked: self._set_job_mode("edit") if checked else None
        )
        self.replace_radio.toggled.connect(
            lambda checked: self._set_job_mode("replace") if checked else None
        )
        self.edit_radio.setToolTip(
            "Перекодировать видео, которое уже находится в PAM. Второй файл не нужен."
        )
        self.replace_radio.setToolTip("Взять картинку из выбранного видеофайла.")
        top.addWidget(caption)
        top.addWidget(self.edit_radio)
        top.addWidget(self.replace_radio)
        top.addStretch(1)
        layout.addLayout(top)

        self.mode_hint = QLabel("")
        self.mode_hint.setObjectName("muted")
        self.mode_hint.setWordWrap(True)
        layout.addWidget(self.mode_hint)
        self._update_mode_hint()
        return bar

    def _update_mode_hint(self) -> None:
        if self.job_mode == "edit":
            self.mode_hint.setText(
                "Второй файл не нужен: видео из PAM будет перекодировано с текущими "
                "настройками. Звук можно сохранить без изменений или перекодировать в AC3/LPCM."
            )
        else:
            self.mode_hint.setText(
                "Второй файл заменит картинку. Звук можно взять из него или сохранить оригинальный."
            )

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(14)

        icon = QLabel()
        icon.setPixmap(make_app_icon().pixmap(44, 44))
        icon.setFixedSize(44, 44)
        header.addWidget(icon)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("PAMF Replacer")
        title.setObjectName("appTitle")
        subtitle = QLabel("Замена видео в PAMF для PlayStation 3 · MPEG-2 / AVC + LPCM")
        subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch(1)

        self.tool_chip = QLabel("")
        self.tool_chip.setObjectName("chip")
        header.addWidget(self.tool_chip, 0, Qt.AlignVCenter)

        self.tools_button = QPushButton("Инструменты")
        self.tools_button.setObjectName("ghost")
        self.tools_button.clicked.connect(self._open_tools)
        header.addWidget(self.tools_button, 0, Qt.AlignVCenter)
        return header

    def _field(self, title: str, widget: QWidget) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(title)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)
        return box

    def _build_settings(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        self.settings_panel = panel
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        title = QLabel("Параметры сборки")
        title.setObjectName("zoneTitle")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setContentsMargins(0, 0, 4, 0)
        form.setSpacing(8)

        video_group = QGroupBox("Видео")
        video_layout = QVBoxLayout(video_group)
        video_layout.setContentsMargins(12, 10, 12, 10)
        video_layout.setSpacing(10)

        meta = QHBoxLayout()
        meta.setSpacing(18)
        self.res_value = QLabel("—")
        self.res_value.setObjectName("value")
        self.fps_value = QLabel("—")
        self.fps_value.setObjectName("value")
        self.codec_value = QLabel("—")
        self.codec_value.setObjectName("value")
        meta.addWidget(self._field("Разрешение", self.res_value))
        meta.addWidget(self._field("Частота кадров", self.fps_value))
        meta.addWidget(self._field("Кодек", self.codec_value))
        meta.addStretch(1)
        video_layout.addLayout(meta)

        rates = QGridLayout()
        rates.setHorizontalSpacing(8)
        rates.setVerticalSpacing(8)
        self.bitrate_spin = QDoubleSpinBox()
        self.bitrate_spin.setRange(0.5, 100.0)
        self.bitrate_spin.setDecimals(1)
        self.bitrate_spin.setSingleStep(1.0)
        self.bitrate_spin.setValue(20.0)
        self.maxrate_spin = QDoubleSpinBox()
        self.maxrate_spin.setRange(0.5, 120.0)
        self.maxrate_spin.setDecimals(1)
        self.maxrate_spin.setSingleStep(1.0)
        self.maxrate_spin.setValue(25.0)
        self.buffer_spin = QDoubleSpinBox()
        self.buffer_spin.setRange(0.5, 100.0)
        self.buffer_spin.setDecimals(1)
        self.buffer_spin.setSingleStep(1.0)
        self.buffer_spin.setValue(10.0)
        for spin in (self.bitrate_spin, self.maxrate_spin, self.buffer_spin):
            spin.setMinimumWidth(72)
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))

        self.preset_combo = QComboBox()
        for label, value in (
            ("fast — быстрее", "fast"),
            ("medium — баланс", "medium"),
            ("slow — качество", "slow"),
        ):
            self.preset_combo.addItem(label, value)
        self.preset_combo.setMinimumWidth(100)
        self.preset_field = self._field("Скорость x264", self.preset_combo)
        self.preset_field.hide()

        orig_button = QPushButton("≈ PAM")
        orig_button.setObjectName("ghost")
        orig_button.setToolTip("Подставить битрейт оригинального видео из PAM")
        orig_button.setFixedWidth(84)
        orig_button.setEnabled(False)
        orig_button.clicked.connect(self._apply_original_bitrate)
        self.orig_button = orig_button

        rates.addWidget(self._field("Битрейт, Мбит/с", self.bitrate_spin), 0, 0)
        rates.addWidget(self._field("Макс. битрейт", self.maxrate_spin), 0, 1)
        rates.addWidget(self._field("Буфер VBV, Мбит", self.buffer_spin), 0, 2)
        rates.addWidget(orig_button, 0, 3, Qt.AlignBottom)
        for column in range(4):
            rates.setColumnStretch(column, 1 if column < 3 else 0)
        video_layout.addLayout(rates)
        meta.addWidget(self.preset_field)
        form.addWidget(video_group)

        audio_group = QGroupBox("Аудио")
        audio_layout = QVBoxLayout(audio_group)
        audio_layout.setContentsMargins(12, 10, 12, 10)
        audio_layout.setSpacing(8)

        audio_top = QHBoxLayout()
        audio_top.setSpacing(8)
        self.audio_mode_combo = QComboBox()
        self.audio_mode_combo.setMinimumWidth(280)
        self.audio_mode_combo.currentIndexChanged.connect(self._update_audio_controls)
        self.audio_check = QCheckBox("Добавить аудио")
        self.audio_check.setChecked(True)
        self.audio_check.toggled.connect(self._update_audio_controls)
        audio_top.addWidget(self._field("Режим", self.audio_mode_combo), 1)
        audio_top.addWidget(self.audio_check, 0, Qt.AlignBottom)
        audio_layout.addLayout(audio_top)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(8)

        self.rate_combo = QComboBox()
        for rate in (48000,):
            self.rate_combo.addItem(f"{rate} Гц", rate)
        self.rate_combo.setMinimumWidth(108)
        self.rate_combo.setToolTip("PAMF поддерживает LPCM только с частотой 48 кГц.")

        self.channels_spin = QSpinBox()
        self.channels_spin.setRange(1, 8)
        self.channels_spin.setValue(2)
        self.channels_spin.setMinimumWidth(78)

        self.bits_combo = QComboBox()
        for bits in (16, 24):
            self.bits_combo.addItem(f"{bits} бит", bits)
        self.bits_combo.setMinimumWidth(92)

        self.ac3_bitrate_combo = QComboBox()
        for bitrate in (192, 256, 384, 448, 512, 640):
            self.ac3_bitrate_combo.addItem(f"{bitrate} кбит/с", bitrate)
        self.ac3_bitrate_combo.setCurrentIndex(self.ac3_bitrate_combo.findData(448))
        self.ac3_bitrate_combo.setMinimumWidth(120)

        self.rate_field = self._field("Частота", self.rate_combo)
        self.channels_field = self._field("Каналы", self.channels_spin)
        self.bits_field = self._field("Битность", self.bits_combo)
        self.ac3_field = self._field("Битрейт AC3", self.ac3_bitrate_combo)

        audio_row.addWidget(self.rate_field)
        audio_row.addWidget(self.channels_field)
        audio_row.addWidget(self.bits_field)
        audio_row.addWidget(self.ac3_field)
        audio_row.addStretch(1)
        audio_layout.addLayout(audio_row)
        form.addWidget(audio_group)

        output_group = QGroupBox("Результат")
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(12, 8, 12, 8)
        output_layout.setSpacing(6)

        output_row_widget = QWidget()
        output_row = QHBoxLayout(output_row_widget)
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(8)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Куда сохранить .pam")
        self.browse_output_button = QPushButton("Обзор…")
        self.browse_output_button.setObjectName("ghost")
        self.browse_output_button.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.browse_output_button)
        output_layout.addWidget(self._field("Файл PAM", output_row_widget))

        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("например: -pace auto -noep")
        output_layout.addWidget(self._field("Доп. аргументы PAMFtool", self.extra_edit))

        options = QHBoxLayout()
        options.setSpacing(18)
        self.open_check = QCheckBox("Открыть папку после сборки")
        self.open_check.setChecked(True)
        self.keep_check = QCheckBox("Оставить временные файлы")
        options.addWidget(self.open_check)
        options.addWidget(self.keep_check)
        options.addStretch(1)
        output_layout.addLayout(options)
        form.addWidget(output_group)
        form.addStretch(1)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        self._refresh_audio_modes("lpcm")
        return panel

    def _build_log(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Журнал")
        title.setObjectName("zoneTitle")
        clear = QPushButton("Очистить")
        clear.setObjectName("ghost")
        clear.clicked.connect(self._clear_log)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(clear)
        layout.addLayout(header)

        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(6000)
        self.log.setPlaceholderText("Здесь появятся команды FFmpeg и отчёт PAMFtool.")
        self.log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        layout.addWidget(self.log, 1)

        hint = QLabel("Журнал очищается при запуске новой сборки.")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        return panel

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("footer")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(24, 12, 24, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.stage_label = QLabel("Готов к работе")
        self.stage_label.setObjectName("stage")
        self.progress_text = QLabel("0%")
        self.progress_text.setObjectName("progressText")
        top.addWidget(self.stage_label)
        top.addStretch(1)
        top.addWidget(self.progress_text)
        layout.addLayout(top)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.status_label = QLabel("Добавьте оригинальный PAM и видео для замены.")
        self.status_label.setObjectName("status")
        bottom.addWidget(self.status_label, 1)

        self.open_button = QPushButton("Открыть папку")
        self.open_button.setObjectName("ghost")
        self.open_button.hide()
        self.open_button.clicked.connect(self._open_output_folder)
        bottom.addWidget(self.open_button)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self._cancel_job)
        bottom.addWidget(self.cancel_button)

        self.create_button = QPushButton("Создать PAM")
        self.create_button.setObjectName("primary")
        self.create_button.setEnabled(False)
        self.create_button.clicked.connect(self._start_job)
        bottom.addWidget(self.create_button)
        layout.addLayout(bottom)
        return footer

    # -------------------------------------------------------------- config
    def _apply_config_to_ui(self) -> None:
        self.keep_check.setChecked(bool(self.config.keep_temp))
        self.open_check.setChecked(bool(self.config.open_folder))
        index = self.preset_combo.findData(self.config.preset)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

    def _save_config(self) -> None:
        self.config.keep_temp = self.keep_check.isChecked()
        self.config.open_folder = self.open_check.isChecked()
        self.config.preset = str(self.preset_combo.currentData() or "medium")
        if self.tools.pamf:
            self.config.pamf = str(self.tools.pamf)
        if self.tools.ffmpeg:
            self.config.ffmpeg = str(self.tools.ffmpeg)
        if self.tools.ffprobe:
            self.config.ffprobe = str(self.tools.ffprobe)
        save_config(self.config)

    # ---------------------------------------------------------------- tools
    def _open_tools(self) -> None:
        dialog = ToolsDialog(self.tools, self)
        if dialog.exec() == QDialog.Accepted:
            self.tools = dialog.tools
            self._save_config()
            self._update_tool_status()
            self._sync_ui()

    def _update_tool_status(self) -> None:
        if self.tools.ready:
            self.tool_chip.setText("PAMFtool ✓   FFmpeg ✓")
            self.tool_chip.setStyleSheet("color:#5fcf9a;")
            self.tool_chip.setToolTip(
                f"PAMFtool: {self.tools.pamf}\nFFmpeg: {self.tools.ffmpeg}\nffprobe: {self.tools.ffprobe}"
            )
        else:
            missing = ", ".join(self.tools.missing)
            self.tool_chip.setText(f"Не найдено: {missing}")
            self.tool_chip.setStyleSheet("color:#f0b45a;")
            self.tool_chip.setToolTip("Нажмите «Инструменты», чтобы указать пути вручную.")

    # ----------------------------------------------------------- file input
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self._route_file(Path(url.toLocalFile()), "")
                event.acceptProposedAction()
                return
        event.ignore()

    def _route_drop(self, path_text: str, role: str) -> None:
        self._route_file(Path(path_text), role)

    def _route_file(self, path: Path, role: str) -> None:
        suffix = path.suffix.lower()
        if suffix in (".pam", ".pamf"):
            self._set_pam(path)
        elif suffix in VIDEO_SUFFIXES or role == "video":
            self._set_source(path)
        elif role == "pam":
            self._set_pam(path)
        else:
            self._set_source(path)

    def _choose_pam(self) -> None:
        start = self.config.last_dir or str(APP_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите оригинальный PAM",
            start,
            "PAMF (*.pam *.pamf *.PAM *.PAMF);;Все файлы (*.*)",
        )
        if path:
            self.config.last_dir = str(Path(path).parent)
            self._set_pam(Path(path))

    def _choose_source(self) -> None:
        start = self.config.last_dir or str(APP_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите видео для замены",
            start,
            "Видео (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.m2ts *.mpg *.mpeg *.wmv *.flv *.vob);;"
            "Все файлы (*.*)",
        )
        if path:
            self.config.last_dir = str(Path(path).parent)
            self._set_source(Path(path))

    def _set_pam(self, path: Path) -> None:
        if self._running:
            return
        if not path.is_file():
            QMessageBox.warning(self, "Файл не найден", f"Не удалось найти файл:\n{path}")
            return
        if not self.tools.pamf:
            QMessageBox.warning(
                self,
                "PAMFtool не найден",
                "Сначала укажите путь к PAMFtool в окне «Инструменты».",
            )
            self._open_tools()
            return

        self._pam_generation += 1
        generation = self._pam_generation
        self.pam_info = None
        self.pam_path = path
        self.pam_zone.set_busy("Читаю структуру PAM…", path)
        self.status_label.setText(f"Читаю {path.name}…")
        self.orig_button.setEnabled(False)
        self._append_log(f"Чтение PAM: {path}")
        self._sync_ui()

        worker = CallWorker(lambda: read_pam_info(self.tools.pamf, path), self)
        self._track_thread(worker)
        worker.ok.connect(lambda info, g=generation: self._on_pam_loaded(info) if g == self._pam_generation else None)
        worker.fail.connect(lambda message, g=generation: self._on_pam_failed(message) if g == self._pam_generation else None)
        worker.start()

    def _on_pam_loaded(self, info: PamInfo) -> None:
        video = info.video
        if not video:
            self._on_pam_failed("В PAM не найден видеопоток.")
            return
        if video.kind not in ("mpeg2", "avc"):
            self._on_pam_failed(f"Неподдерживаемый видеокодек: {video.name}.")
            return

        self.pam_info = info
        self.pam_path = info.path
        audio = info.audio
        details = (
            f"{info.duration:.2f} с · {info.resolution_label} · "
            f"{video.codec_label} + {audio.codec_label if audio else 'без аудио'}"
        )
        if audio:
            details += f" {audio.channels or '?'} ch / {audio.sample_rate or '?'} Гц"
        self.pam_zone.set_loaded(info.path, details)

        self.res_value.setText(info.resolution_label)
        self.fps_value.setText(info.fps_label)
        self.codec_value.setText(video.codec_label)
        self.preset_field.setVisible(video.kind == "avc")
        self._original_bitrate = info.estimated_video_bitrate()
        if hasattr(self, "orig_button"):
            self.orig_button.setEnabled(bool(self._original_bitrate))

        self._apply_bitrate_defaults(video.height or 720)
        self._apply_audio_defaults(audio)
        self._update_audio_availability()
        self._update_audio_controls()
        self._suggest_output(info.path)

        if video.kind == "avc":
            self._append_log("Обнаружен AVC/H.264: используется libx264 (режим совместимости).")
        if audio and audio.kind != "lpcm":
            if self.job_mode == "edit":
                self._append_log(
                    f"Оригинальное аудио — {audio.codec_label}; "
                    "при пересборке сохраняется без перекодирования."
                )
            else:
                self._append_log(
                    f"Оригинальное аудио — {audio.codec_label}. "
                    "По умолчанию сохраняется без перекодирования; можно выбрать LPCM/AC3 из нового видео."
                )
            self._update_audio_availability()

        self._append_log(
            f"PAM: {info.duration:.2f} c, {info.resolution_label}, "
            f"{mode_fps(info)}, {video.codec_label}, потоков: {len(info.streams)}"
        )
        if self._original_bitrate:
            self._append_log(f"Ориентировочный битрейт оригинала: {self._original_bitrate:.2f} Мбит/с")
        self._sync_ui()

    def _on_pam_failed(self, message: str) -> None:
        self.pam_info = None
        self._original_bitrate = None
        if hasattr(self, "orig_button"):
            self.orig_button.setEnabled(False)
        self.pam_zone.set_error(message.splitlines()[0] if message else "Ошибка чтения")
        self._append_log("Ошибка PAM: " + message)
        self.status_label.setText("Не удалось прочитать PAM.")
        self._sync_ui()
        self._show_error("Не удалось прочитать PAM", message)

    def _set_source(self, path: Path) -> None:
        if self._running:
            return
        if self.job_mode == "edit":
            self._set_job_mode("replace")
        if not path.is_file():
            QMessageBox.warning(self, "Файл не найден", f"Не удалось найти файл:\n{path}")
            return
        if not self.tools.ffprobe:
            QMessageBox.warning(
                self,
                "ffprobe не найден",
                "Сначала укажите путь к ffprobe в окне «Инструменты».",
            )
            self._open_tools()
            return

        self._source_generation += 1
        generation = self._source_generation
        self.source_info = None
        self.video_zone.set_busy("Читаю параметры видео…", path)
        self.status_label.setText(f"Читаю {path.name}…")
        self._append_log(f"Чтение видео: {path}")
        self._sync_ui()

        worker = CallWorker(lambda: probe_media(self.tools.ffprobe, path), self)
        self._track_thread(worker)
        worker.ok.connect(
            lambda info, g=generation: self._on_source_loaded(info) if g == self._source_generation else None
        )
        worker.fail.connect(
            lambda message, g=generation: self._on_source_failed(message) if g == self._source_generation else None
        )
        worker.start()

    def _on_source_loaded(self, info: MediaInfo) -> None:
        self.source_info = info
        details = self._source_details(info)
        warning = None
        if not info.has_audio:
            if self.pam_info and self.pam_info.audio:
                warning = "В новом видео нет аудио — будет сохранена оригинальная дорожка PAM."
                self.audio_check.setEnabled(True)
                self.audio_check.setChecked(True)
                self._refresh_audio_modes("original")
            else:
                warning = "В этом видео нет аудиодорожки — будет собран PAM только с видео."
                self.audio_check.setChecked(False)
                self.audio_check.setEnabled(False)
                self.audio_mode_combo.setEnabled(False)
            self._append_log(warning)
        else:
            self.audio_check.setEnabled(True)
            if not self.audio_check.isChecked():
                self.audio_check.setChecked(True)

        if self.pam_info and info.duration and self.pam_info.duration:
            difference = abs(info.duration - self.pam_info.duration)
            if difference > 0.5:
                note = (
                    f"Длительность нового видео {info.duration:.2f} c "
                    f"(в PAM {self.pam_info.duration:.2f} c) — результат будет {info.duration:.2f} c."
                )
                self._append_log(note)
                warning = (warning + "\n" if warning else "") + (
                    f"Длительность {info.duration:.2f} c вместо {self.pam_info.duration:.2f} c."
                )

        self.video_zone.set_loaded(info.path, details, warning)
        self._append_log(f"Видео: {details}")
        self._sync_ui()

    def _on_source_failed(self, message: str) -> None:
        self.source_info = None
        self.video_zone.set_error(message.splitlines()[0] if message else "Ошибка чтения")
        self._append_log("Ошибка видео: " + message)
        self.status_label.setText("Не удалось прочитать видео.")
        self._sync_ui()
        self._show_error("Не удалось прочитать видео", message)

    def _track_thread(self, worker: CallWorker) -> None:
        self._threads.append(worker)
        worker.finished.connect(lambda: self._forget_thread(worker))

    def _forget_thread(self, worker: CallWorker) -> None:
        if worker in self._threads:
            self._threads.remove(worker)

    # ------------------------------------------------------------- defaults
    def _apply_bitrate_defaults(self, height: int) -> None:
        if height >= 1080:
            bitrate = 24.0
        elif height >= 720:
            bitrate = 20.0
        elif height >= 576:
            bitrate = 12.0
        else:
            bitrate = 8.0
        self.bitrate_spin.setValue(bitrate)
        self.maxrate_spin.setValue(round(bitrate * 1.25, 1))
        self.buffer_spin.setValue(round(bitrate * 0.5, 1))

    def _apply_original_bitrate(self) -> None:
        if not self._original_bitrate:
            return
        bitrate = round(self._original_bitrate, 1)
        self.bitrate_spin.setValue(max(0.5, min(100.0, bitrate)))
        self.maxrate_spin.setValue(max(0.5, min(120.0, round(bitrate * 1.25, 1))))
        self.buffer_spin.setValue(max(0.5, min(100.0, round(bitrate * 0.5, 1))))
        self._append_log(f"Битрейт выставлен по оригиналу: {bitrate:.1f} Мбит/с")

    def _apply_audio_defaults(self, stream) -> None:
        if stream and stream.kind == "lpcm":
            if stream.sample_rate:
                index = self.rate_combo.findData(stream.sample_rate)
                if index < 0:
                    self.rate_combo.addItem(f"{stream.sample_rate} Гц", stream.sample_rate)
                    index = self.rate_combo.count() - 1
                self.rate_combo.setCurrentIndex(index)
            if stream.channels:
                self.channels_spin.setValue(max(1, min(8, stream.channels)))
            if stream.bits:
                index = self.bits_combo.findData(stream.bits)
                if index >= 0:
                    self.bits_combo.setCurrentIndex(index)
        else:
            index = self.rate_combo.findData(48000)
            self.rate_combo.setCurrentIndex(max(0, index))
            self.channels_spin.setValue(2)
            self.bits_combo.setCurrentIndex(0)
        if self.job_mode == "edit":
            preferred = "original"
        else:
            preferred = "original" if stream and stream.kind in ("atrac3plus", "ac3") else "lpcm"
        self._refresh_audio_modes(preferred)

    def _refresh_audio_modes(self, preferred: str | None = None) -> None:
        audio = self.pam_info.audio if self.pam_info else None
        if self.job_mode == "edit":
            current = preferred or "original"
            self.audio_mode_combo.blockSignals(True)
            self.audio_mode_combo.clear()
            if audio:
                self.audio_mode_combo.addItem(f"Оригинал — {audio.codec_label}", "original")
                self.audio_mode_combo.setItemData(
                    0,
                    "Дорожка берётся из оригинального PAM без перекодирования.",
                    Qt.ToolTipRole,
                )
                self.audio_mode_combo.addItem("AC3 — из PAM", "ac3")
                self.audio_mode_combo.setItemData(
                    1,
                    "Перекодировать звук из PAM в AC3. Меньше битрейт — меньше размер.",
                    Qt.ToolTipRole,
                )
                self.audio_mode_combo.addItem("LPCM — из PAM", "lpcm")
                self.audio_mode_combo.setItemData(
                    2,
                    "Перекодировать звук из PAM в LPCM с выбранными каналами и разрядностью.",
                    Qt.ToolTipRole,
                )
            else:
                self.audio_mode_combo.addItem("В PAM нет аудио", "none")
            index = self.audio_mode_combo.findData(current)
            self.audio_mode_combo.setCurrentIndex(max(0, index))
            self.audio_mode_combo.blockSignals(False)
            self._update_audio_controls()
            return

        current = preferred or self.audio_mode_combo.currentData()
        self.audio_mode_combo.blockSignals(True)
        self.audio_mode_combo.clear()
        if audio:
            self.audio_mode_combo.addItem(f"Оригинал — {audio.codec_label}", "original")
            original_index = self.audio_mode_combo.count() - 1
            self.audio_mode_combo.setItemData(
                original_index,
                "Дорожка берётся из оригинального PAM без перекодирования.",
                Qt.ToolTipRole,
            )
        self.audio_mode_combo.addItem("LPCM — из нового видео", "lpcm")
        self.audio_mode_combo.addItem("AC3 — из нового видео", "ac3")
        self.audio_mode_combo.setItemData(
            self.audio_mode_combo.count() - 1,
            "AC3-энкодер FFmpeg. Совместимость с конкретной игрой проверяйте отдельно.",
            Qt.ToolTipRole,
        )
        index = self.audio_mode_combo.findData(current)
        if index < 0 and audio and audio.kind in ("atrac3plus", "ac3"):
            index = self.audio_mode_combo.findData("original")
        if index < 0:
            index = self.audio_mode_combo.findData("lpcm")
        self.audio_mode_combo.setCurrentIndex(max(0, index))
        self.audio_mode_combo.blockSignals(False)
        self._update_audio_controls()

    def _update_audio_availability(self) -> None:
        if self.job_mode == "edit":
            available = bool(self.pam_info and self.pam_info.audio)
        else:
            available = bool(
                (self.pam_info and self.pam_info.audio)
                or (self.source_info and self.source_info.has_audio)
            )
        self.audio_check.setEnabled(available)
        if not available:
            self.audio_check.setChecked(False)
        else:
            self.audio_check.setChecked(True)

    def _update_audio_controls(self) -> None:
        mode = self.audio_mode_combo.currentData()
        active = self.audio_check.isChecked()
        is_lpcm = mode == "lpcm"
        is_ac3 = mode == "ac3"

        self.audio_mode_combo.setEnabled(active and self.audio_mode_combo.count() > 0)
        for field in (self.rate_field, self.channels_field, self.bits_field):
            field.setVisible(is_lpcm)
        self.ac3_field.setVisible(is_ac3)

        if is_ac3:
            index = self.rate_combo.findData(48000)
            if index >= 0:
                self.rate_combo.setCurrentIndex(index)
            self.channels_spin.setMaximum(6)
            if self.channels_spin.value() > 6:
                self.channels_spin.setValue(6)
        else:
            self.channels_spin.setMaximum(8)

        self.rate_combo.setEnabled(False)
        self.channels_spin.setEnabled(active and (is_lpcm or is_ac3))
        self.bits_combo.setEnabled(active and is_lpcm)
        self.ac3_bitrate_combo.setEnabled(active and is_ac3)

    def _suggest_output(self, pam_path: Path) -> None:
        folder = Path(self.config.output_dir) if self.config.output_dir else pam_path.parent
        if not folder.is_dir():
            folder = pam_path.parent
        self.output_edit.setText(str(folder / f"{pam_path.stem}_new.pam"))

    def _browse_output(self) -> None:
        start = self.output_edit.text().strip()
        if not start and self.pam_path:
            start = str(self.pam_path.parent / f"{self.pam_path.stem}_new.pam")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Куда сохранить PAM",
            start or str(APP_DIR),
            "PAMF (*.pam *.pamf);;Все файлы (*.*)",
        )
        if path:
            if not Path(path).suffix:
                path += ".pam"
            self.output_edit.setText(path)
            self.config.output_dir = str(Path(path).parent)

    # ---------------------------------------------------------------- state
    def _set_job_mode(self, mode: str) -> None:
        if mode not in ("replace", "edit") or mode == self.job_mode or self._running:
            return
        if mode == "edit":
            self._replace_audio_mode = str(self.audio_mode_combo.currentData() or "lpcm")
        self.job_mode = mode
        for radio, value in ((self.edit_radio, "edit"), (self.replace_radio, "replace")):
            radio.blockSignals(True)
            radio.setChecked(value == mode)
            radio.blockSignals(False)
        self._refresh_video_zone()
        self._update_audio_availability()
        self._refresh_audio_modes(self._replace_audio_mode if mode == "replace" else None)
        self._update_mode_hint()
        self._append_log(
            "Режим: изменение видео из PAM (второй файл не нужен)."
            if mode == "edit"
            else "Режим: замена видео новым файлом."
        )
        self._sync_ui()

    def _refresh_video_zone(self) -> None:
        if self.job_mode == "edit":
            self.video_zone.setEnabled(False)
            self.video_zone.set_inactive(
                "Видео берётся из PAM",
                "Второй файл не нужен — текущее видео будет перекодировано.",
            )
            return
        self.video_zone.setEnabled(True)
        if self.source_info:
            self.video_zone.set_loaded(self.source_info.path, self._source_details(self.source_info))
        else:
            self.video_zone.clear()

    def _source_details(self, info: MediaInfo) -> str:
        details = f"{info.duration_label} · {info.resolution_label} · {info.video_codec or '?'}"
        if info.audio_codec:
            details += f" / {info.audio_codec}"
            if info.channels:
                details += f", {info.channels} ch"
        else:
            details += " · без аудио"
        return details

    def _sync_ui(self) -> None:
        if self._running:
            return
        edit_mode = self.job_mode == "edit"
        ready = bool(self.pam_info and self.tools.ready and (edit_mode or self.source_info))
        self.create_button.setText("Пересобрать PAM" if edit_mode else "Создать PAM")
        self.create_button.setEnabled(ready)

        if not self.tools.ready:
            self.status_label.setText("Не найдены инструменты: " + ", ".join(self.tools.missing) + ".")
            self.status_label.setStyleSheet("color:#f0b45a;")
        elif not self.pam_info:
            self.status_label.setText("Добавьте оригинальный PAM (шаг 1).")
            self.status_label.setStyleSheet("")
        elif edit_mode:
            output = Path(self.output_edit.text()).name if self.output_edit.text().strip() else "—"
            self.status_label.setText(f"Готово к пересборке → {output}")
            self.status_label.setStyleSheet("")
        elif not self.source_info:
            self.status_label.setText("Теперь добавьте видео для замены (шаг 2).")
            self.status_label.setStyleSheet("")
        else:
            output = Path(self.output_edit.text()).name if self.output_edit.text().strip() else "—"
            self.status_label.setText(f"Готово к сборке → {output}")
            self.status_label.setStyleSheet("")
        if not self._running:
            self.progress_text.setText(f"{self.progress_bar.value()}%")

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.pam_zone.setEnabled(not running)
        self.mode_bar.setEnabled(not running)
        self.video_zone.setEnabled(not running and self.job_mode != "edit")
        self.settings_panel.setEnabled(not running)
        self.tools_button.setEnabled(not running)
        self.cancel_button.setVisible(running)
        self.cancel_button.setEnabled(running)
        self.open_button.setVisible(bool(self._last_output) and not running)
        edit_mode = self.job_mode == "edit"
        self.create_button.setEnabled(
            not running
            and bool(self.pam_info and self.tools.ready and (edit_mode or self.source_info))
        )
        if running:
            self.progress_bar.setValue(0)
            self.progress_text.setText("0%")
            self.stage_label.setText("Подготовка…")
        else:
            self._sync_ui()

    # ----------------------------------------------------------------- log
    def _append_log(self, message: str) -> None:
        timestamp = _dt.datetime.now().strftime("%H:%M:%S")
        for index, line in enumerate(str(message).splitlines() or [""]):
            prefix = f"[{timestamp}] " if index == 0 else "           "
            self.log.appendPlainText(prefix + line)

    def _clear_log(self) -> None:
        self.log.clear()

    # ----------------------------------------------------------------- job
    def _start_job(self) -> None:
        if self._running:
            return
        if not self.pam_info:
            return
        edit_mode = self.job_mode == "edit"
        if not edit_mode and not self.source_info:
            return
        if not self.tools.ready:
            QMessageBox.warning(
                self,
                "Инструменты не найдены",
                "Укажите PAMFtool, FFmpeg и ffprobe в окне «Инструменты».",
            )
            self._open_tools()
            return

        raw_output = self.output_edit.text().strip().strip('"')
        if not raw_output:
            QMessageBox.warning(self, "Не указан результат", "Выберите, куда сохранить PAM-файл.")
            return
        output = Path(raw_output).expanduser()
        if not output.is_absolute():
            output = (Path.cwd() / output).resolve()

        if output.is_dir() or not output.name:
            QMessageBox.warning(
                self,
                "Некорректный путь",
                "Укажите путь к файлу PAM, а не к папке.",
            )
            return

        if not output.suffix:
            output = Path(str(output) + ".pam")
            self.output_edit.setText(str(output))

        if self.pam_info.path.exists() and output.resolve() == self.pam_info.path.resolve():
            QMessageBox.critical(
                self,
                "Нельзя перезаписать оригинал",
                "Выходной файл совпадает с оригинальным PAM.\nВыберите другое имя или папку.",
            )
            return
        if self.source_info and self.source_info.path.exists() and output.resolve() == self.source_info.path.resolve():
            QMessageBox.critical(
                self,
                "Нельзя перезаписать видео",
                "Выходной файл совпадает с исходным видео.\nВыберите другое имя.",
            )
            return

        if output.exists():
            answer = QMessageBox.question(
                self,
                "Файл уже существует",
                f"Перезаписать файл?\n{output}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать папку:\n{error}")
            return

        try:
            extra_args = self._parse_extra_args(self.extra_edit.text())
        except ValueError as error:
            QMessageBox.warning(self, "Аргументы PAMFtool", str(error))
            return

        audio_enabled = self.audio_check.isChecked()
        if edit_mode:
            if audio_enabled and not self.pam_info.audio:
                audio_enabled = False
            audio_mode = str(self.audio_mode_combo.currentData() or "original") if audio_enabled else "none"
            if audio_mode not in ("original", "lpcm", "ac3"):
                audio_mode = "original"
        else:
            audio_mode = str(self.audio_mode_combo.currentData() or "lpcm") if audio_enabled else "none"
            if audio_enabled:
                if audio_mode == "original":
                    if not self.pam_info.audio:
                        QMessageBox.warning(
                            self,
                            "Нет оригинального аудио",
                            "В исходном PAM нет аудиодорожки — сохранять нечего.",
                        )
                        return
                    if (
                        self.pam_info.duration
                        and self.source_info.duration
                        and abs(self.pam_info.duration - self.source_info.duration) > 1.0
                    ):
                        answer = QMessageBox.question(
                            self,
                            "Длительность аудио",
                            "Оригинальная дорожка не подгоняется по длительности.\n"
                            f"Аудио в PAM: {self.pam_info.duration:.2f} с\n"
                            f"Новое видео: {self.source_info.duration:.2f} с\n\n"
                            "Продолжить?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No,
                        )
                        if answer != QMessageBox.Yes:
                            return
                elif not self.source_info.has_audio:
                    QMessageBox.warning(
                        self,
                        "В видео нет аудио",
                        "Выбранный режим требует аудиодорожку в новом видео.\n"
                        "Выберите «Оригинал» или снимите галочку «Добавить аудио».",
                    )
                    return

        settings = EncodeSettings(
            video_bitrate=self.bitrate_spin.value(),
            max_rate=self.maxrate_spin.value(),
            buffer_size=self.buffer_spin.value(),
            preset=str(self.preset_combo.currentData() or "medium"),
            audio_enabled=audio_enabled,
            audio_mode=audio_mode,
            ac3_bitrate=int(self.ac3_bitrate_combo.currentData() or 448),
            sample_rate=int(self.rate_combo.currentData() or 48000),
            channels=self.channels_spin.value(),
            bits=int(self.bits_combo.currentData() or 16),
            extra_pamf_args=extra_args,
        )
        context = JobContext(
            tools=self.tools,
            pam=self.pam_info,
            source=self.source_info if not edit_mode else None,
            output=output,
            settings=settings,
            keep_temp=self.keep_check.isChecked(),
            mode=self.job_mode,
        )

        self._last_output = None
        self.open_button.hide()
        self._set_running(True)
        self.log.clear()
        self._append_log(f"=== Новая задача · PAMF Replacer {__version__} ===")
        self._append_log(f"PAM:    {self.pam_info.path}")
        if edit_mode:
            self._append_log("Видео:  из PAM (перекодирование текущего потока)")
        else:
            self._append_log(f"Видео:  {self.source_info.path}")
        self._append_log(f"Выход:  {output}")
        self._append_log(
            f"Видео: {self.pam_info.resolution_label}, {mode_fps(self.pam_info)}, "
            f"{settings.video_bitrate:g}/{settings.max_rate:g} Мбит/с, буфер {settings.buffer_size:g} Мбит"
        )
        if audio_enabled:
            if audio_mode == "original" and self.pam_info.audio:
                self._append_log(
                    f"Аудио:  оригинал {self.pam_info.audio.codec_label} (без перекодирования)"
                )
            elif audio_mode == "ac3":
                self._append_log(
                    f"Аудио:  AC3 {'из PAM' if edit_mode else 'из нового видео'}, "
                    f"{settings.ac3_bitrate} кбит/с, 48 кГц, {min(6, settings.channels)} ch"
                )
            else:
                self._append_log(
                    f"Аудио:  LPCM {'из PAM' if edit_mode else 'из нового видео'}, "
                    f"48000 Гц, {settings.channels} ch, {settings.bits} бит"
                )
        else:
            self._append_log("Аудио: без звука")

        worker = PipelineWorker(context, self)
        self._worker = worker
        worker.log.connect(self._append_log)
        worker.stage.connect(self._on_stage)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(lambda: self._worker_finished(worker))
        worker.start()

    def _parse_extra_args(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        try:
            tokens = shlex.split(text, posix=False)
        except ValueError as error:
            raise ValueError(f"Не удалось разобрать аргументы: {error}") from error
        result = []
        for token in tokens:
            if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
                token = token[1:-1]
            result.append(token)
        return result

    def _on_stage(self, message: str) -> None:
        self.stage_label.setText(message)

    def _on_progress(self, value: int) -> None:
        self.progress_bar.setValue(max(0, min(100, value)))
        self.progress_text.setText(f"{self.progress_bar.value()}%")

    def _on_success(self, result: PipelineResult) -> None:
        self._last_output = result.output
        self._set_running(False)
        self.progress_bar.setValue(100)
        self.progress_text.setText("100%")
        self.stage_label.setText("Готово")
        self.status_label.setText(f"Готово: {result.output.name}")
        self.status_label.setStyleSheet("color:#5fcf9a;")
        self._append_log(f"Успешно: {result.output}")
        self.open_button.show()
        self.config.output_dir = str(result.output.parent)
        self._save_config()

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("PAM создан")
        box.setText(
            "PAM пересобран из исходного видео."
            if self.job_mode == "edit"
            else "Новый PAM успешно собран."
        )
        box.setInformativeText(
            f"{result.output.name}\n\n"
            f"Длительность: {result.duration:.2f} c\n"
            f"Потоков: {result.stream_count}"
        )
        box.setDetailedText(str(result.output))
        box.exec()

        if self.open_check.isChecked():
            self._open_output_folder()

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.stage_label.setText("Ошибка")
        self.status_label.setText("Сборка не удалась.")
        self.status_label.setStyleSheet("color:#f0a3ae;")
        self._append_log("ОШИБКА: " + message)
        self._show_error("Не удалось создать PAM", message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.stage_label.setText("Отменено")
        self.status_label.setText("Сборка отменена.")
        self.status_label.setStyleSheet("color:#f0b45a;")
        self.progress_bar.setValue(0)
        self.progress_text.setText("0%")
        self._append_log("Задача отменена пользователем.")

    def _worker_finished(self, worker: PipelineWorker) -> None:
        if self._worker is worker:
            self._worker = None

    def _cancel_job(self) -> None:
        if self._worker and self._worker.isRunning():
            self.status_label.setText("Отмена…")
            self.cancel_button.setEnabled(False)
            self._append_log("Отмена задачи…")
            self._worker.cancel()

    def _show_error(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText("Подробности — ниже.")
        box.setDetailedText(message)
        box.exec()

    def _open_output_folder(self) -> None:
        if self._last_output and self._last_output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output.parent)))
        elif self.output_edit.text().strip():
            folder = Path(self.output_edit.text().strip()).parent
            if folder.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # --------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker and self._worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Идёт сборка",
                "Кодирование ещё не завершено. Отменить и закрыть программу?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.cancel()
            if not self._worker.wait(8000):
                self._worker.terminate()
                self._worker.wait(2000)
        for worker in list(self._threads):
            if worker.isRunning():
                worker.wait(5000)
        self._save_config()
        event.accept()


def mode_fps(info: PamInfo) -> str:
    return f"{info.fps_label} fps"
