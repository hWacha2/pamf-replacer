"""Locating the external tools and parsing ``PAMFtool -info`` output."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# ---------------------------------------------------------------------------
# subprocess helpers
# ---------------------------------------------------------------------------


def decode_console(data: bytes) -> str:
    """Decode console output of the .NET tool as best as we can.

    PAMFtool writes through the Windows OEM code page (cp866 on a Russian
    system), which contains non-breaking spaces in ``N0`` formatted numbers.
    All values we actually parse are ASCII, but decoding keeps the log tidy.
    """
    for encoding in ("utf-8-sig", "cp866", "cp1251", "mbcs"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")


def run_capture(command: list[str], cwd: Path | None = None, timeout: float = 120) -> tuple[int, str]:
    process = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
        timeout=timeout,
    )
    return process.returncode, decode_console(process.stdout or b"")


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


@dataclass
class Toolchain:
    pamf: Path | None = None
    ffmpeg: Path | None = None
    ffprobe: Path | None = None

    @property
    def ready(self) -> bool:
        return bool(self.pamf and self.ffmpeg and self.ffprobe)

    @property
    def missing(self) -> list[str]:
        names = []
        if not self.pamf:
            names.append("PAMFtool")
        if not self.ffmpeg:
            names.append("ffmpeg")
        if not self.ffprobe:
            names.append("ffprobe")
        return names


def _walk_files(root: Path, max_depth: int = 4):
    root = root.resolve()
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".idea", "site-packages"}
    base_depth = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        if len(current_path.parts) - base_depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if d.lower() not in skip and not d.startswith(".")]
        for name in files:
            yield current_path / name


def _find_named(app_dir: Path, predicate) -> Path | None:
    for path in _walk_files(app_dir):
        if predicate(path.name.lower()):
            return path
    return None


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        try:
            if path and path.is_file():
                return path.resolve()
        except OSError:
            continue
    return None


def detect_tools(
    app_dir: Path,
    pamf_override: str | Path | None = None,
    ffmpeg_override: str | Path | None = None,
    ffprobe_override: str | Path | None = None,
) -> Toolchain:
    """Find PAMFtool and FFmpeg, preferring user overrides and the app folder."""

    app_dir = Path(app_dir).resolve()
    pamf = _first_existing([Path(pamf_override)] if pamf_override else [])

    if not pamf:
        candidates = [
            app_dir / "test" / "PAMFtool-win-x64.exe",
            app_dir / "tools" / "PAMFtool-win-x64.exe",
            app_dir / "PAMFtool-win-x64.exe",
            app_dir / "test" / "PAMFtool.exe",
        ]
        pamf = _first_existing(candidates)
    if not pamf:
        pamf = _find_named(app_dir, lambda n: n.startswith("pamftool") and n.endswith(".exe"))
    if not pamf:
        found = shutil.which("PAMFtool-win-x64") or shutil.which("PAMFtool")
        pamf = Path(found).resolve() if found else None

    ffmpeg = _first_existing([Path(ffmpeg_override)] if ffmpeg_override else [])
    if not ffmpeg:
        candidates = [
            app_dir / "test" / "ffmpeg" / "bin" / "ffmpeg.exe",
            app_dir / "ffmpeg" / "bin" / "ffmpeg.exe",
            app_dir / "tools" / "ffmpeg.exe",
            app_dir / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
        ]
        ffmpeg = _first_existing(candidates)
    if not ffmpeg:
        ffmpeg = _find_named(app_dir, lambda n: n == "ffmpeg.exe")
    if not ffmpeg:
        found = shutil.which("ffmpeg")
        ffmpeg = Path(found).resolve() if found else None

    ffprobe = _first_existing([Path(ffprobe_override)] if ffprobe_override else [])
    if not ffprobe and ffmpeg:
        candidates = [
            ffmpeg.with_name("ffprobe.exe"),
            ffmpeg.parent / "ffprobe",
            app_dir / "test" / "ffmpeg" / "bin" / "ffprobe.exe",
        ]
        ffprobe = _first_existing(candidates)
    if not ffprobe:
        found = shutil.which("ffprobe")
        ffprobe = Path(found).resolve() if found else None

    return Toolchain(pamf=pamf, ffmpeg=ffmpeg, ffprobe=ffprobe)


# ---------------------------------------------------------------------------
# PAMF info model / parser
# ---------------------------------------------------------------------------


@dataclass
class StreamInfo:
    index: int
    kind: str
    name: str
    width: int | None = None
    height: int | None = None
    fps: str | None = None
    fps_float: float | None = None
    profile_idc: int | None = None
    profile_name: str | None = None
    level_name: str | None = None
    level_idc: int | None = None
    cavlc: bool | None = None
    deblock: bool | None = None
    channels: int | None = None
    sample_rate: int | None = None
    bits: int | None = None
    avc_level: str | None = None

    @property
    def is_video(self) -> bool:
        return self.kind in ("mpeg2", "avc")

    @property
    def is_audio(self) -> bool:
        return self.kind in ("lpcm", "atrac3plus", "ac3")

    @property
    def codec_label(self) -> str:
        return {
            "mpeg2": "MPEG-2 Video",
            "avc": "H.264 / AVC",
            "lpcm": "LPCM",
            "atrac3plus": "ATRAC3plus",
            "ac3": "Dolby Digital",
        }.get(self.kind, self.name)


@dataclass
class PamInfo:
    path: Path
    size: int
    duration: float
    streams: list[StreamInfo]
    raw: str = ""

    @property
    def video(self) -> StreamInfo | None:
        for stream in self.streams:
            if stream.is_video:
                return stream
        return None

    @property
    def audio(self) -> StreamInfo | None:
        for stream in self.streams:
            if stream.kind == "lpcm":
                return stream
        for stream in self.streams:
            if stream.is_audio:
                return stream
        return None

    @property
    def video_label(self) -> str:
        video = self.video
        return video.codec_label if video else "нет"

    @property
    def resolution_label(self) -> str:
        video = self.video
        if video and video.width and video.height:
            return f"{video.width} × {video.height}"
        return "—"

    @property
    def fps_label(self) -> str:
        video = self.video
        if video and video.fps_float:
            if video.fps and "/" in video.fps:
                return f"{video.fps_float:.3f} ({video.fps})"
            return f"{video.fps_float:g}"
        return "—"

    def estimated_audio_bitrate(self) -> float | None:
        """Approximate the original audio bitrate in bits per second."""
        audio = self.audio
        if not audio:
            return None
        if audio.kind == "lpcm" and audio.sample_rate and audio.channels and audio.bits:
            # PAMF stores mono LPCM padded to two channels, so the file size
            # matches a stereo track even when only one channel is reported.
            channels = max(2, audio.channels)
            return float(audio.sample_rate * channels * audio.bits)
        if audio.kind == "atrac3plus":
            return 256_000.0
        if audio.kind == "ac3":
            return 448_000.0
        return None

    def estimated_audio_bytes(self) -> float | None:
        """Approximate the size of the original audio stream in bytes."""
        bitrate = self.estimated_audio_bitrate()
        if bitrate is None or self.duration <= 0:
            return None
        return bitrate * self.duration / 8

    def estimated_video_bitrate(self) -> float | None:
        """Approximate the original video bitrate in Mbps."""
        if self.duration <= 0 or self.size <= 0:
            return None
        audio_bps = self.estimated_audio_bitrate() or 0.0
        total_bps = self.size * 8 / self.duration
        return max(0.5, (total_bps - audio_bps) / 1_000_000)


def _clean_number(value: str) -> str:
    return re.sub(r"[\s\u00a0\u202f\u2009]", "", value).replace(",", ".")


def _float_or_none(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(_clean_number(value))
    except ValueError:
        return None


def _int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_stream(index: int, name: str, block: str) -> StreamInfo:
    low_name = name.lower()
    if "mpeg-2" in low_name or "mpeg2" in low_name:
        kind = "mpeg2"
    elif "avc" in low_name or "h.264" in low_name or "h264" in low_name:
        kind = "avc"
    elif "lpcm" in low_name:
        kind = "lpcm"
    elif "atrac" in low_name:
        kind = "atrac3plus"
    elif "ac3" in low_name or "dolby" in low_name:
        kind = "ac3"
    else:
        kind = "other"

    stream = StreamInfo(index=index, kind=kind, name=name.strip())

    resolution = re.search(r"resolution\s*:\s*(\d+)\s*x\s*(\d+)", block)
    if resolution:
        stream.width = int(resolution.group(1))
        stream.height = int(resolution.group(2))

    frame_rate = re.search(r"frame_rate\s*:\s*code\s+\d+\s*\(([^)]*)", block)
    if frame_rate:
        description = frame_rate.group(1)
        rational = re.search(r"(\d+)/(\d+)", description)
        if rational and int(rational.group(2)) != 0:
            stream.fps = f"{rational.group(1)}/{rational.group(2)}"
            stream.fps_float = int(rational.group(1)) / int(rational.group(2))
        else:
            decimal = re.search(r"(\d+(?:\.\d+)?)", description)
            if decimal:
                stream.fps_float = float(decimal.group(1))
                stream.fps = f"{stream.fps_float:g}"

    if kind == "mpeg2":
        profile = re.search(r"profile_level\s*:\s*0x([0-9A-Fa-f]{2})\s*\(([^)]*)\)", block)
        if profile:
            code = int(profile.group(1), 16)
            stream.profile_idc = (code >> 4) & 0x07
            stream.level_idc = code & 0x0F
            text = profile.group(2)
            match = re.match(r"\s*(.+?)\s+Profile\s*@\s*(.+?)\s+Level", text)
            if match:
                stream.profile_name = match.group(1).strip()
                stream.level_name = match.group(2).strip()

    if kind == "avc":
        profile = re.search(
            r"profile/level\s*:\s*([A-Za-z0-9 .:]+?)\s*\(0x([0-9A-Fa-f]+)\)\s*/\s*Level\s*([\d.]+)",
            block,
        )
        if profile:
            stream.profile_name = profile.group(1).strip()
            stream.profile_idc = int(profile.group(2), 16)
            stream.avc_level = profile.group(3).strip()
        entropy = re.search(r"entropy_coding\s*:\s*(\d+)", block)
        if entropy:
            stream.cavlc = entropy.group(1) == "0"
        deblock = re.search(r"deblock_flag\s*:\s*(\d+)", block)
        if deblock:
            stream.deblock = deblock.group(1) != "0"

    channels = re.search(r"channels\s*:\s*(\d+)", block)
    if channels:
        stream.channels = int(channels.group(1))
    sample_rate = re.search(r"sample_rate\s*:\s*(\d+)\s*Hz", block)
    if sample_rate:
        stream.sample_rate = int(sample_rate.group(1))
    bits = re.search(r"bits_per_sample\s*:\s*(\d+)", block)
    if bits:
        stream.bits = int(bits.group(1))

    return stream


def parse_pam_info(path: Path, output: str) -> PamInfo:
    duration_match = re.search(r"^\s*duration\s*:\s*([0-9\s.,]+)s", output, re.MULTILINE)
    duration = _float_or_none(duration_match.group(1)) if duration_match else None

    if duration is None:
        start = re.search(r"start_pts\s*:\s*0x([0-9A-Fa-f]+)", output)
        end = re.search(r"end_pts\s*:\s*0x([0-9A-Fa-f]+)", output)
        if start and end:
            duration = (int(end.group(1), 16) - int(start.group(1), 16)) / 90_000

    header = list(re.finditer(r"^\s*Stream #(\d+)\s+--\s+(.+)$", output, re.MULTILINE))
    streams: list[StreamInfo] = []
    for number, match in enumerate(header):
        start = match.end()
        end = header[number + 1].start() if number + 1 < len(header) else len(output)
        streams.append(_parse_stream(int(match.group(1)), match.group(2), output[start:end]))

    try:
        size = path.stat().st_size
    except OSError:
        size_match = re.search(r"^\s*File size\s*:\s*([0-9\s.,]+)\s*bytes", output, re.MULTILINE)
        size = _int_or_none(size_match.group(1)) if size_match else 0

    return PamInfo(
        path=path,
        size=size or 0,
        duration=duration or 0.0,
        streams=streams,
        raw=output,
    )


def read_pam_info(pamf: Path, path: Path, timeout: float = 120) -> PamInfo:
    if not pamf or not pamf.is_file():
        raise RuntimeError("PAMFtool не найден. Укажите путь в окне «Инструменты».")
    if not path.is_file():
        raise RuntimeError(f"Файл не найден:\n{path}")

    code, output = run_capture([str(pamf), "-info", str(path)], timeout=timeout)
    if code != 0:
        raise RuntimeError(f"PAMFtool не смог прочитать файл (код {code}).\n\n{output.strip()}")
    info = parse_pam_info(path, output)
    if not info.streams:
        raise RuntimeError("В файле не найдено ни одного потока.\n\n" + output.strip())
    return info


# ---------------------------------------------------------------------------
# FFmpeg helpers
# ---------------------------------------------------------------------------


def read_ffprobe(ffprobe: Path, path: Path, timeout: float = 120) -> dict:
    if not ffprobe or not ffprobe.is_file():
        raise RuntimeError("ffprobe не найден. Укажите путь в окне «Инструменты».")
    import json

    command = [
        str(ffprobe),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    code, output = run_capture(command, timeout=timeout)
    if code != 0:
        raise RuntimeError(f"ffprobe не смог прочитать видео (код {code}).\n\n{output.strip()}")
    try:
        return json.loads(output)
    except ValueError as error:
        raise RuntimeError(f"Некорректный ответ ffprobe:\n{error}") from error
