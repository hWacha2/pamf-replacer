# PAMF Replacer

Небольшое Windows-приложение для замены видео внутри **PAMF**-файлов PlayStation 3.
Берёт параметры оригинального `.pam` (разрешение, fps, профиль, аудио), кодирует выбранное
видео в MPEG-2 или AVC и собирает новый PAM через `PAMFtool`.

## Как это работает

1. Перетащите (или выберите) оригинальный `.pam` в первое поле.
   Приложение запускает `PAMFtool -info` и показывает параметры потоков.
2. Перетащите видео (`.mp4`, `.mkv`, `.mov` и т. п.) во второе поле.
3. Проверьте битрейт/аудио и нажмите **«Создать PAM»**.

Под капотом выполняются три шага:

```bat
ffmpeg -i video.mp4 -c:v mpeg2video -pix_fmt yuv420p -b:v 20M -maxrate 25M ^
       -bufsize 10M -r 30000/1001 -s 1280x720 -profile:v 4 -level:v 4 -an ^
       work\job.s00_mpeg-2.m2v

ffmpeg -i video.mp4 -vn -c:a pcm_s16le -ar 48000 -ac 2 ^
       work\job.s01_lpcm.wav

PAMFtool -mux work output.pam
```

Для AVC-исходников вместо MPEG-2 используется `libx264` с профилем/уровнем из PAM.
Готовый файл проверяется через `PAMFtool -info` перед сохранением.

## Запуск

Требования:

- Windows 10/11;
- Python 3.10+ (для запуска из исходников);
- [.NET 8 Runtime](https://dotnet.microsoft.com/download/dotnet/8.0) для `PAMFtool`
  (в готовом релизе не нужен — там self-contained сборка);
- `PAMFtool-win-x64.exe` и `ffmpeg`/`ffprobe`.

В папке проекта уже ожидаются инструменты:

| Инструмент | Путь по умолчанию |
|---|---|
| PAMFtool | `test\PAMFtool-win-x64.exe` |
| FFmpeg | `test\ffmpeg\bin\ffmpeg.exe` |
| ffprobe | `test\ffmpeg\bin\ffprobe.exe` |

Приложение также ищет `PAMFtool*.exe` и `ffmpeg.exe` рядом с собой и в `PATH`.
Пути можно задать вручную в окне **«Инструменты»**.

Установка зависимостей и запуск:

```bat
install.bat
run.bat
```

Если виртуальное окружение уже настроено, достаточно `run.bat`.
Для отладочного запуска с консолью — `run-console.bat`.

## Параметры

- **Битрейт / Макс. битрейт / Буфер VBV** — параметры `-b:v`, `-maxrate`, `-bufsize`.
  Значения по умолчанию зависят от высоты кадра (720p → 20/25/10 Мбит/с).
- **≈ PAM** — подставляет средний битрейт оригинального видео, вычисленный по размеру PAM
  и длительности (за вычетом аудио).
- **Скорость x264** — пресет libx264, показывается только для AVC.
- **Аудио** — три режима:
  - **LPCM — из нового видео**: PCM 16/24 бит, частота и каналы из PAM.
  - **AC3 — из нового видео**: Dolby Digital 192–640 кбит/с, 48 кГц (совместимость проверяйте в игре).
  - **Оригинал — …**: дорожка исходного PAM (ATRAC3plus/AC3/LPCM) извлекается через
    `PAMFtool -demux` и вставляется без перекодирования. Если в новом видео нет звука,
    этот режим включается автоматически.
- **Доп. аргументы PAMFtool** — например `-pace auto`, `-noep`, `-nodeblock`, `-muxrate 24000`.
- **Оставить временные файлы** — сохраняет папку с `.m2v`/`.264` и `.wav` для отладки.

## Важные замечания

- **Длительность результата** определяется новым видео. При сохранении оригинальной
  дорожки более длинное аудио может удлинить файл — приложение предупредит.
  Если длительности сильно отличаются, проверьте результат.
- **Аудио**:
  - оригинальный **LPCM** можно сохранить или закодировать заново из нового видео;
  - оригинальный **AC3** можно сохранить или закодировать заново средствами FFmpeg
    (режим AC3, экспериментальный);
  - **ATRAC3plus нельзя закодировать** свободными инструментами: в FFmpeg есть только
    декодер. Поэтому для ATRAC3+ доступно **сохранение оригинальной дорожки**;
    звук нового видео в ATRAC3+ не перекодируется — выбирайте LPCM или AC3.
  - при сохранении оригинальной дорожки аудио не растягивается и не обрезается:
    если длительности не совпадают, приложение предупредит.
- Ветка **AVC** реализована как совместимый режим (libx264, профиль/уровень/CABAC из PAM).
  Экзотические PAM (High 10, нестандартные уровни) могут потребовать ручной подстройки.
- Muxer PAMFtool экспериментальный: проверяйте результат в игре/эмуляторе.
- Оригинальный `.pam` никогда не перезаписывается: приложение блокирует совпадение путей.

## Готовая сборка (exe)

```powershell
.\build_release.ps1
```

Скрипт собирает папку `release\PAMF Replacer\`:

```
PAMF Replacer.exe        приложение (PyInstaller, onedir)
_internal\               Python, Qt и зависимости
tools\PAMFtool-win-x64.exe   self-contained .NET 8 (runtime не нужен)
tools\ffmpeg.exe
tools\ffprobe.exe
README.md
THIRD-PARTY-NOTICES.txt
licenses\
```

Всё необходимое лежит рядом с exe, установка не требуется: запустите
`release\PAMF Replacer\PAMF Replacer.exe`. Готовый архив —
`release\PAMF-Replacer-1.1.0-win64.zip`.

Для пересборки нужны зависимости из `requirements.txt`, PyInstaller
(`requirements-build.txt`) и .NET 8 SDK — только чтобы опубликовать self-contained
PAMFtool. Если SDK нет, положите готовый `PAMFtool-win-x64.exe` в `vendor\`
(или укажите `PAMFTOOL_PUBLISHED`); тогда .NET Runtime понадобится на машине пользователя.
FFmpeg можно взять из `test\ffmpeg\bin` или указать `FFMPEG_BIN_DIR`.

## Структура проекта

```
main.py                  точка входа
pamf_replacer/
  ui.py                  интерфейс PySide6
  pipeline.py            команды ffmpeg, demux/mux PAMFtool
  tools.py               поиск инструментов и разбор PAMFtool -info
  media.py               разбор ffprobe
  config.py              настройки в %APPDATA%\PAMFReplacer
run.bat / run-console.bat / install.bat
requirements.txt         PySide6-Essentials
requirements-build.txt   PyInstaller
PAMFReplacer.spec        конфигурация PyInstaller
build_release.ps1        сборка portable-релиза
assets/                  иконка и version info
licenses/                тексты GPL/LGPL
vendor/                  self-contained PAMFtool для сборки
release/                 готовый релиз (exe + tools + zip)
```
