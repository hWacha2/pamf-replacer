"""Small JSON config stored in %APPDATA%."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


def app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "PAMFReplacer"


CONFIG_PATH = app_data_dir() / "config.json"


@dataclass
class AppConfig:
    pamf: str = ""
    ffmpeg: str = ""
    ffprobe: str = ""
    output_dir: str = ""
    last_dir: str = ""
    keep_temp: bool = False
    open_folder: bool = True
    preset: str = "medium"


def load_config() -> AppConfig:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AppConfig()
    config = AppConfig()
    for key, value in data.items():
        if hasattr(config, key):
            setattr(config, key, value)
    if config.preset not in ("fast", "medium", "slow"):
        config.preset = "medium"
    return config


def save_config(config: AppConfig) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
