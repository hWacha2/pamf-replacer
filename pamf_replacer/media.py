"""Source video probing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tools import read_ffprobe


def _fraction_to_float(value: str | None) -> float | None:
    if not value or "/" not in value:
        return None
    numerator, denominator = value.split("/", 1)
    try:
        num = float(numerator)
        den = float(denominator)
    except ValueError:
        return None
    if den == 0:
        return None
    return num / den


@dataclass
class MediaInfo:
    path: Path
    duration: float
    size: int
    width: int | None = None
    height: int | None = None
    fps: str | None = None
    fps_float: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    channels: int | None = None
    sample_rate: int | None = None
    bit_rate: int | None = None

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None

    @property
    def resolution_label(self) -> str:
        if self.width and self.height:
            return f"{self.width} × {self.height}"
        return "—"

    @property
    def duration_label(self) -> str:
        total = max(0, int(round(self.duration)))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


def probe_media(ffprobe: Path, path: Path) -> MediaInfo:
    data = read_ffprobe(ffprobe, path)
    streams = data.get("streams") or []
    fmt = data.get("format") or {}

    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video"
            and not (s.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )
    if video is None:
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video:
        raise RuntimeError("В выбранном файле нет видеодорожки.")

    duration = 0.0
    for candidate in (fmt.get("duration"), (video or {}).get("duration"), (audio or {}).get("duration")):
        try:
            duration = float(candidate)
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue

    fps_value = None
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = video.get(key)
        parsed = _fraction_to_float(raw)
        if parsed and parsed > 0.01:
            fps_value = raw
            fps_float = parsed
            break
    else:
        fps_float = None

    if fps_value and "/" in fps_value:
        numerator, denominator = fps_value.split("/", 1)
        try:
            if int(numerator) % int(denominator) == 0:
                fps_value = f"{int(numerator) // int(denominator)}"
        except (ValueError, ZeroDivisionError):
            pass

    return MediaInfo(
        path=path,
        duration=duration,
        size=_safe_int(fmt.get("size")) or _safe_size(path),
        width=_safe_int(video.get("width")),
        height=_safe_int(video.get("height")),
        fps=fps_value,
        fps_float=fps_float,
        video_codec=video.get("codec_name"),
        audio_codec=(audio or {}).get("codec_name"),
        channels=_safe_int((audio or {}).get("channels")),
        sample_rate=_safe_int((audio or {}).get("sample_rate")),
        bit_rate=_safe_int(fmt.get("bit_rate")),
    )


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
