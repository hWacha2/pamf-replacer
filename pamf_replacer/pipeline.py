"""Encoding and muxing pipeline."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .media import MediaInfo
from .tools import CREATE_NO_WINDOW, PamInfo, Toolchain, decode_console, parse_pam_info, run_capture

MPEG2_PROFILE_IDS = {
    "simple": 5,
    "main": 4,
    "snr scalable": 3,
    "spatial scalable": 2,
    "spatially scalable": 2,
    "high": 1,
    "4:2:2": 0,
}
MPEG2_LEVEL_IDS = {"low": 10, "main": 8, "high 1440": 6, "high": 4}


class PipelineError(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


@dataclass
class EncodeSettings:
    video_bitrate: float = 20.0
    max_rate: float = 25.0
    buffer_size: float = 10.0
    preset: str = "medium"
    audio_enabled: bool = True
    audio_mode: str = "lpcm"  # "lpcm", "ac3" or "original"
    ac3_bitrate: int = 448
    sample_rate: int = 48000
    channels: int = 2
    bits: int = 16
    extra_pamf_args: list[str] = field(default_factory=list)


@dataclass
class JobContext:
    tools: Toolchain
    pam: PamInfo
    source: MediaInfo | None
    output: Path
    settings: EncodeSettings
    keep_temp: bool = False
    mode: str = "replace"  # "replace" inserts a new video, "edit" re-encodes the PAM video


@dataclass
class PipelineResult:
    output: Path
    duration: float
    stream_count: int


class _Callbacks:
    def __init__(
        self,
        log: Callable[[str], None] | None,
        stage: Callable[[str], None] | None,
        progress: Callable[[int], None] | None,
    ) -> None:
        self._log = log or (lambda _message: None)
        self._stage = stage or (lambda _message: None)
        self._progress = progress or (lambda _value: None)

    def log(self, message: str) -> None:
        self._log(message)

    def stage(self, message: str) -> None:
        self._stage(message)

    def progress(self, value: float) -> None:
        self._progress(max(0, min(100, int(round(value)))))


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass


def _pump_stderr(stream, callback: Callable[[str], None]) -> None:
    try:
        for line in iter(stream.readline, ""):
            line = line.rstrip()
            if line:
                callback(line)
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


def run_ffmpeg(
    command: list[str],
    duration: float,
    callbacks: _Callbacks,
    cancel: threading.Event | None,
    start: float,
    span: float,
    on_process: Callable[[subprocess.Popen], None] | None = None,
) -> None:
    if cancel and cancel.is_set():
        raise Cancelled()

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    if on_process:
        on_process(process)

    stderr_lines: list[str] = []

    def log_error(line: str) -> None:
        stderr_lines.append(line)
        callbacks.log("ffmpeg: " + line)

    pump = threading.Thread(target=_pump_stderr, args=(process.stderr, log_error), daemon=True)
    pump.start()

    cancelled = False
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if cancel and cancel.is_set():
                cancelled = True
                _terminate(process)
                break
            if line.startswith("out_time_us="):
                try:
                    microseconds = int(line.split("=", 1)[1].strip())
                except ValueError:
                    continue
                if duration > 0:
                    callbacks.progress(start + span * min(1.0, microseconds / 1_000_000 / duration))
            elif line.startswith("out_time_ms="):
                try:
                    microseconds = int(line.split("=", 1)[1].strip())
                except ValueError:
                    continue
                if duration > 0:
                    callbacks.progress(start + span * min(1.0, microseconds / 1_000_000 / duration))
            elif line.startswith("progress=end"):
                callbacks.progress(start + span)
    finally:
        try:
            process.stdout.close()
        except (OSError, AttributeError):
            pass

    code = process.wait()
    pump.join(timeout=5)

    if cancelled or (cancel and cancel.is_set()):
        raise Cancelled()
    if code != 0:
        tail = "\n".join(stderr_lines[-30:]).strip()
        raise PipelineError(
            "FFmpeg завершился с ошибкой"
            + (f" (код {code}).\n\n{tail}" if tail else f" (код {code}).")
        )
    callbacks.progress(start + span)


def run_pamf_mux(
    pamf: Path,
    workdir: Path,
    destination: Path,
    extra_args: list[str],
    callbacks: _Callbacks,
    cancel: threading.Event | None,
    on_process: Callable[[subprocess.Popen], None] | None = None,
) -> str:
    command = [str(pamf), "-mux", str(workdir), str(destination), *extra_args]
    callbacks.log("> " + subprocess.list2cmdline(command))

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    if on_process:
        on_process(process)

    output_lines: list[str] = []
    cancelled = False
    assert process.stdout is not None
    for raw_line in process.stdout:
        if cancel and cancel.is_set():
            cancelled = True
            _terminate(process)
            break
        line = decode_console(raw_line).rstrip()
        if line:
            output_lines.append(line)
            callbacks.log(line)
    process.stdout.close()
    code = process.wait()

    if cancelled or (cancel and cancel.is_set()):
        raise Cancelled()
    text = "\n".join(output_lines)
    if code != 0:
        raise PipelineError(f"PAMFtool не смог собрать файл (код {code}).\n\n{text[-4000:]}")
    if not destination.is_file() or destination.stat().st_size < 2048:
        raise PipelineError("PAMFtool не создал выходной файл.\n\n" + text[-4000:])
    return text


def run_pamf_demux(
    pamf: Path,
    source: Path,
    destination: Path,
    callbacks: _Callbacks,
    cancel: threading.Event | None,
    on_process: Callable[[subprocess.Popen], None] | None = None,
) -> str:
    """Extract all streams of the original PAM so its audio can be reused as-is."""
    command = [str(pamf), "-demux", str(source), str(destination)]
    callbacks.log("> " + subprocess.list2cmdline(command))

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    if on_process:
        on_process(process)

    output_lines: list[str] = []
    cancelled = False
    assert process.stdout is not None
    for raw_line in process.stdout:
        if cancel and cancel.is_set():
            cancelled = True
            _terminate(process)
            break
        line = decode_console(raw_line).rstrip()
        if line:
            output_lines.append(line)
            callbacks.log(line)
    process.stdout.close()
    code = process.wait()

    if cancelled or (cancel and cancel.is_set()):
        raise Cancelled()
    text = "\n".join(output_lines)
    if code != 0:
        raise PipelineError(f"PAMFtool не смог извлечь потоки оригинала (код {code}).\n\n{text[-4000:]}")
    return text


_ORIGINAL_AUDIO_EXTENSIONS = {
    "lpcm": (".lpcm", ".wav"),
    "atrac3plus": (".at3",),
    "ac3": (".ac3",),
}

_DEMUX_VIDEO_EXTENSIONS = {
    "mpeg2": (".m2v", ".mpg", ".mpeg"),
    "avc": (".264", ".h264", ".avc"),
}

_MUX_AUDIO_NAMES = {
    "lpcm": ("lpcm", ".lpcm"),
    "atrac3plus": ("atrac3plus", ".at3"),
    "ac3": ("dolby", ".ac3"),
}


def _find_demux_stream(directory: Path, stream, allowed: tuple[str, ...], label: str) -> Path:
    pattern = re.compile(rf"\.s{stream.index:02d}_[^.]+\.(?P<ext>[^.]+)$", re.IGNORECASE)
    candidates: list[Path] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = pattern.search(path.name)
        if match and path.suffix.lower() in allowed:
            candidates.append(path)
    if not candidates:
        raise PipelineError(
            f"Не удалось найти извлечённую {label} "
            f"({stream.codec_label}, поток #{stream.index}) в папке {directory}."
        )
    return candidates[0]


def find_demux_audio(directory: Path, stream) -> Path:
    """Find the demuxed audio file that belongs to ``stream`` (for example ``.s01_lpcm.lpcm``)."""
    allowed = _ORIGINAL_AUDIO_EXTENSIONS.get(stream.kind)
    if not allowed:
        raise PipelineError(f"Неподдерживаемый кодек оригинального аудио: {stream.codec_label}")
    return _find_demux_stream(directory, stream, allowed, "аудиодорожку")


def find_demux_video(directory: Path, stream) -> Path:
    """Find the demuxed video file that belongs to ``stream`` (for example ``.s00_mpeg-2.m2v``)."""
    allowed = _DEMUX_VIDEO_EXTENSIONS.get(stream.kind)
    if not allowed:
        raise PipelineError(f"Неподдерживаемый видеокодек: {stream.codec_label}")
    return _find_demux_stream(directory, stream, allowed, "видеодорожку")


def _mpeg2_profile(stream) -> tuple[int, int]:
    profile = 4
    level = 4
    if stream.profile_name:
        profile = MPEG2_PROFILE_IDS.get(stream.profile_name.strip().lower(), profile)
    if stream.level_name:
        level = MPEG2_LEVEL_IDS.get(stream.level_name.strip().lower(), level)
    if stream.profile_idc is not None and 0 <= stream.profile_idc <= 5:
        profile = stream.profile_idc
    if stream.level_idc in (4, 6, 8, 10):
        level = stream.level_idc
    return profile, level


def build_video_command(
    ffmpeg: Path,
    source: Path,
    destination: Path,
    pam: PamInfo,
    settings: EncodeSettings,
    log: Callable[[str], None] | None = None,
) -> list[str]:
    video = pam.video
    if not video:
        raise PipelineError("В PAM-файле нет видеопотока.")
    if not video.width or not video.height:
        raise PipelineError("Не удалось определить разрешение оригинального PAM-файла.")
    if not video.fps:
        raise PipelineError("Не удалось определить частоту кадров оригинального PAM-файла.")

    command = [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-progress",
        "pipe:1",
        "-nostats",
        "-loglevel",
        "warning",
        "-i",
        str(source),
        "-map",
        "0:V:0",
        "-an",
        "-sn",
        "-dn",
    ]

    bitrate = f"{settings.video_bitrate:g}M"
    max_rate = f"{settings.max_rate:g}M"
    buffer_size = f"{settings.buffer_size:g}M"
    # mpeg2video ignores -b:v/-maxrate/-bufsize without -minrate and falls back
    # to a fixed quantizer (q=2), producing a much smaller file than requested.
    min_rate = bitrate

    if video.kind == "avc":
        profile_name = (video.profile_name or "High").strip().lower()
        if profile_name not in ("baseline", "main", "high"):
            if log:
                log(f"Профиль {video.profile_name} не поддерживается libx264, используется High.")
            profile_name = "high"

        level = 41
        if video.avc_level:
            try:
                level = int(round(float(video.avc_level) * 10))
            except ValueError:
                level = 41

        params = ["nal-hrd=vbr", "force-cfr=1"]
        if video.cavlc:
            params.append("cabac=0")
        if video.deblock is False:
            params.append("deblock=0")

        command += [
            "-c:v",
            "libx264",
            "-preset",
            settings.preset,
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            bitrate,
            "-maxrate",
            max_rate,
            "-bufsize",
            buffer_size,
            "-r",
            video.fps,
            "-s",
            f"{video.width}x{video.height}",
            "-profile:v",
            profile_name,
            "-level:v",
            str(level),
            "-x264-params",
            ":".join(params),
            "-f",
            "h264",
            str(destination),
        ]
    else:
        profile, level = _mpeg2_profile(video)
        command += [
            "-c:v",
            "mpeg2video",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            bitrate,
            "-minrate",
            min_rate,
            "-maxrate",
            max_rate,
            "-bufsize",
            buffer_size,
            "-r",
            video.fps,
            "-s",
            f"{video.width}x{video.height}",
            "-profile:v",
            str(profile),
            "-level:v",
            str(level),
            "-f",
            "mpeg2video",
            str(destination),
        ]

    return command


def build_audio_command(
    ffmpeg: Path,
    source: Path,
    destination: Path,
    settings: EncodeSettings,
) -> list[str]:
    if settings.audio_mode == "ac3":
        codec = "ac3"
        sample_rate = 48000
        channels = max(1, min(6, settings.channels))
        codec_args = ["-b:a", f"{settings.ac3_bitrate}k"]
        container = "ac3"
    else:
        codec = "pcm_s24le" if settings.bits >= 24 else "pcm_s16le"
        # PAMF LPCM is always 48 kHz; other rates would be mislabelled on playback.
        sample_rate = 48000
        channels = settings.channels
        codec_args = []
        container = "wav"
    return [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-progress",
        "pipe:1",
        "-nostats",
        "-loglevel",
        "warning",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
        "-c:a",
        codec,
        *codec_args,
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
        "-f",
        container,
        str(destination),
    ]


def run_pipeline(
    context: JobContext,
    log: Callable[[str], None] | None = None,
    stage: Callable[[str], None] | None = None,
    progress: Callable[[int], None] | None = None,
    cancel: threading.Event | None = None,
    on_process: Callable[[subprocess.Popen], None] | None = None,
) -> PipelineResult:
    callbacks = _Callbacks(log, stage, progress)
    tools = context.tools
    if not tools.ready:
        raise PipelineError("Не найдены инструменты: " + ", ".join(tools.missing))

    pam_video = context.pam.video
    if not pam_video:
        raise PipelineError("В оригинальном PAM не найден видеопоток.")
    if pam_video.kind not in ("mpeg2", "avc"):
        raise PipelineError(f"Неподдерживаемый видеокодек: {pam_video.name}")

    settings = context.settings
    mode = context.mode or "replace"
    if mode not in ("replace", "edit"):
        raise PipelineError(f"Неизвестный режим работы: {mode}")
    edit_mode = mode == "edit"
    source_info = context.source
    original_audio = context.pam.audio

    if edit_mode:
        if settings.audio_enabled and original_audio:
            audio_mode = settings.audio_mode if settings.audio_mode in ("original", "lpcm", "ac3") else "original"
        else:
            audio_mode = "none"
        if audio_mode == "original" and original_audio.kind not in _ORIGINAL_AUDIO_EXTENSIONS:
            raise PipelineError(
                f"Неподдерживаемый кодек оригинального аудио: {original_audio.codec_label}"
            )
    else:
        if source_info is None:
            raise PipelineError("Не выбрано новое видео для замены.")
        audio_mode = settings.audio_mode if settings.audio_enabled else "none"
        if audio_mode not in ("none", "lpcm", "ac3", "original"):
            raise PipelineError(f"Неизвестный режим аудио: {audio_mode}")
        if audio_mode in ("lpcm", "ac3") and not source_info.has_audio:
            raise PipelineError(
                "В выбранном видео нет аудиодорожки. Выберите LPCM/AC3 только для видео со звуком."
            )
        if audio_mode == "original":
            if not original_audio:
                raise PipelineError("В оригинальном PAM нет аудиопотока — сохранять нечего.")
            if original_audio.kind not in _ORIGINAL_AUDIO_EXTENSIONS:
                raise PipelineError(
                    f"Неподдерживаемый кодек оригинального аудио: {original_audio.codec_label}"
                )
    audio_enabled = audio_mode != "none"

    output = context.output
    if not output.name or output.is_dir():
        raise PipelineError("Некорректный путь результата: укажите имя файла PAM.")
    output.parent.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix=".pamf-replace-", dir=str(output.parent)))
    part = output.with_name(output.stem + ".part" + (output.suffix or ".pam"))

    if edit_mode:
        if audio_mode in ("lpcm", "ac3"):
            video_span = (8.0, 72.0)
            audio_span = (72.0, 90.0)
        elif audio_enabled:
            video_span = (8.0, 85.0)
            audio_span = None
        else:
            video_span = (8.0, 90.0)
            audio_span = None
        mux_start = 92.0
    elif audio_mode == "original":
        video_span = (0.0, 85.0)
        audio_span = None
        mux_start = 92.0
    elif audio_enabled:
        video_span = (0.0, 72.0)
        audio_span = (72.0, 90.0)
        mux_start = 92.0
    else:
        video_span = (0.0, 90.0)
        audio_span = None
        mux_start = 92.0

    try:
        if cancel and cancel.is_set():
            raise Cancelled()

        extension = ".m2v" if pam_video.kind == "mpeg2" else ".264"
        kind_name = "mpeg-2" if pam_video.kind == "mpeg2" else "avc"
        video_file = workdir / f"job.s00_{kind_name}{extension}"
        audio_file: Path | None = None
        audio_kind: str | None = None
        if audio_mode == "lpcm":
            audio_kind = "lpcm"
            audio_file = workdir / "job.s01_lpcm.wav"
        elif audio_mode == "ac3":
            audio_kind = "ac3"
            audio_file = workdir / "job.s01_dolby.ac3"
        elif audio_mode == "original":
            audio_kind = original_audio.kind

        demux_dir: Path | None = None
        if edit_mode:
            if cancel and cancel.is_set():
                raise Cancelled()
            callbacks.stage("Извлечение потоков PAM…")
            callbacks.progress(2)
            demux_dir = Path(tempfile.mkdtemp(prefix="demux-", dir=str(workdir)))
            run_pamf_demux(tools.pamf, context.pam.path, demux_dir, callbacks, cancel, on_process)
            video_source = find_demux_video(demux_dir, pam_video)
            callbacks.log(f"Видео из PAM: {video_source.name}")
            callbacks.progress(8)
        else:
            video_source = source_info.path

        callbacks.stage("Кодирование видео…")
        callbacks.progress(video_span[0])
        video_command = build_video_command(
            tools.ffmpeg,
            video_source,
            video_file,
            context.pam,
            context.settings,
            log=callbacks.log,
        )
        callbacks.log("> " + subprocess.list2cmdline(video_command))
        run_ffmpeg(
            video_command,
            context.pam.duration if edit_mode else source_info.duration,
            callbacks,
            cancel,
            video_span[0],
            video_span[1] - video_span[0],
            on_process,
        )

        if audio_mode == "original":
            if cancel and cancel.is_set():
                raise Cancelled()
            if demux_dir is None:
                callbacks.stage("Извлечение аудио из PAM…")
                callbacks.progress(86)
                demux_dir = Path(tempfile.mkdtemp(prefix="demux-", dir=str(workdir)))
                run_pamf_demux(tools.pamf, context.pam.path, demux_dir, callbacks, cancel, on_process)
            audio_source = find_demux_audio(demux_dir, original_audio)
            if audio_kind == "lpcm":
                audio_file = workdir / f"job.s01_lpcm{audio_source.suffix.lower()}"
            elif audio_kind == "atrac3plus":
                audio_file = workdir / "job.s01_atrac3plus.at3"
            else:
                audio_file = workdir / "job.s01_dolby.ac3"
            shutil.copy2(audio_source, audio_file)
            callbacks.log(
                f"Оригинальное аудио ({original_audio.codec_label}) сохранено без перекодирования: "
                f"{audio_source.name} → {audio_file.name}"
            )
        elif audio_enabled and audio_span and audio_file:
            if cancel and cancel.is_set():
                raise Cancelled()
            if edit_mode:
                if demux_dir is None:
                    callbacks.stage("Извлечение аудио из PAM…")
                    callbacks.progress(70)
                    demux_dir = Path(tempfile.mkdtemp(prefix="demux-", dir=str(workdir)))
                    run_pamf_demux(tools.pamf, context.pam.path, demux_dir, callbacks, cancel, on_process)
                audio_input = find_demux_audio(demux_dir, original_audio)
                audio_duration = context.pam.duration
                callbacks.log(
                    f"Аудио из PAM ({original_audio.codec_label}) перекодируется: {audio_input.name}"
                )
            else:
                audio_input = source_info.path
                audio_duration = source_info.duration
            callbacks.stage("Кодирование аудио…")
            audio_command = build_audio_command(
                tools.ffmpeg,
                audio_input,
                audio_file,
                context.settings,
            )
            callbacks.log("> " + subprocess.list2cmdline(audio_command))
            run_ffmpeg(
                audio_command,
                audio_duration,
                callbacks,
                cancel,
                audio_span[0],
                audio_span[1] - audio_span[0],
                on_process,
            )

        if cancel and cancel.is_set():
            raise Cancelled()

        callbacks.stage("Сборка PAM…")
        callbacks.progress(mux_start)
        run_pamf_mux(
            tools.pamf,
            workdir,
            part,
            context.settings.extra_pamf_args,
            callbacks,
            cancel,
            on_process,
        )

        callbacks.stage("Проверка результата…")
        code, info_text = run_capture([str(tools.pamf), "-info", str(part)], timeout=120)
        if code != 0:
            raise PipelineError("Не удалось проверить собранный PAM.\n\n" + info_text[-4000:])
        result_info = parse_pam_info(part, info_text)
        expected_streams = 2 if audio_enabled else 1
        if len(result_info.streams) != expected_streams or not result_info.video:
            raise PipelineError(
                f"После сборки получено потоков: {len(result_info.streams)}, ожидалось {expected_streams}.\n\n"
                + info_text[-4000:]
            )
        if audio_enabled:
            if not result_info.audio:
                raise PipelineError("После сборки не найден аудиопоток.\n\n" + info_text[-4000:])
            if result_info.audio.kind != audio_kind:
                raise PipelineError(
                    f"Ожидалось аудио {audio_kind}, получено {result_info.audio.kind}.\n\n"
                    + info_text[-4000:]
                )

        os.replace(part, output)
        callbacks.progress(100)
        callbacks.stage("Готово")
        callbacks.log(
            f"Готово: {output} ({output.stat().st_size:,} байт, "
            f"{result_info.duration:.2f} c, потоков: {len(result_info.streams)})"
        )
        return PipelineResult(
            output=output,
            duration=result_info.duration,
            stream_count=len(result_info.streams),
        )
    finally:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass
        if context.keep_temp:
            callbacks.log(f"Временные файлы сохранены: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)
