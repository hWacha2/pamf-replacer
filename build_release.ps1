# Builds the portable Windows release (PyInstaller onedir + bundled tools).
# Usage:
#   .\build_release.ps1
#   .\build_release.ps1 -Zip
#
# Optional environment variables:
#   PAMFTOOL_PUBLISHED  path to a self-contained PAMFtool.exe
#   FFMPEG_BIN_DIR      folder containing ffmpeg.exe and ffprobe.exe
#   PAMFTOOL_LICENSE    path to PAMFtool's LICENSE.txt

param(
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Не найдено виртуальное окружение. Сначала запустите install.bat."
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller не установлен. Выполните: .venv\Scripts\python.exe -m pip install -r requirements-build.txt"
}

$version = (Select-String -Path (Join-Path $root "pamf_replacer\__init__.py") -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "PAMF Replacer $version"

& $python (Join-Path $root "assets\make_icon.py")

Write-Host "PyInstaller..."
foreach ($path in @("build", "dist")) {
    $full = Join-Path $root $path
    if (Test-Path $full) { Remove-Item -Recurse -Force $full }
}
$previousEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $python -m PyInstaller --noconfirm --clean (Join-Path $root "PAMFReplacer.spec") 2>&1 | ForEach-Object { Write-Host $_ }
$pyiCode = $LASTEXITCODE
$ErrorActionPreference = $previousEap
if ($pyiCode -ne 0) { throw "PyInstaller завершился с ошибкой." }

$release = Join-Path $root "release\PAMF Replacer"
if (Test-Path $release) { Remove-Item -Recurse -Force $release }
New-Item -ItemType Directory -Force $release | Out-Null
Copy-Item -Path (Join-Path $root "dist\PAMF Replacer\*") -Destination $release -Recurse -Force

$tools = Join-Path $release "tools"
New-Item -ItemType Directory -Force $tools | Out-Null

$pamfCandidates = @(
    $env:PAMFTOOL_PUBLISHED,
    (Join-Path $root "vendor\PAMFtool-win-x64.exe"),
    (Join-Path $root "test\PAMFtool-win-x64.exe")
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $pamfCandidates) {
    throw "Не найден PAMFtool. Задайте PAMFTOOL_PUBLISHED или положите vendor\PAMFtool-win-x64.exe."
}
$pamf = $pamfCandidates[0]
Copy-Item $pamf (Join-Path $tools "PAMFtool-win-x64.exe") -Force
Write-Host "PAMFtool: $pamf"

$ffmpegDir = if ($env:FFMPEG_BIN_DIR) {
    $env:FFMPEG_BIN_DIR
} elseif (Test-Path (Join-Path $root "vendor\ffmpeg")) {
    Join-Path $root "vendor\ffmpeg"
} else {
    Join-Path $root "test\ffmpeg\bin"
}
foreach ($name in @("ffmpeg.exe", "ffprobe.exe")) {
    $source = Join-Path $ffmpegDir $name
    if (-not (Test-Path $source)) { throw "Не найден $source" }
    Copy-Item $source (Join-Path $tools $name) -Force
}
Write-Host "FFmpeg:  $ffmpegDir"

Copy-Item (Join-Path $root "README.md") (Join-Path $release "README.md") -Force
Copy-Item (Join-Path $root "THIRD-PARTY-NOTICES.txt") (Join-Path $release "THIRD-PARTY-NOTICES.txt") -Force

$licenses = Join-Path $release "licenses"
New-Item -ItemType Directory -Force $licenses | Out-Null
Copy-Item (Join-Path $root "licenses\GPL-3.0.txt") $licenses -Force
Copy-Item (Join-Path $root "licenses\LGPL-3.0.txt") $licenses -Force

$pamfLicense = if ($env:PAMFTOOL_LICENSE -and (Test-Path $env:PAMFTOOL_LICENSE)) {
    $env:PAMFTOOL_LICENSE
} elseif (Test-Path (Join-Path $env:TEMP "PAMFtool-src\LICENSE.txt")) {
    Join-Path $env:TEMP "PAMFtool-src\LICENSE.txt"
} else {
    $null
}
if ($pamfLicense) {
    Copy-Item $pamfLicense (Join-Path $licenses "PAMFtool-GPL-3.0.txt") -Force
}

$ffmpegLicense = Join-Path (Split-Path -Parent $ffmpegDir) "LICENSE"
if (Test-Path $ffmpegLicense) {
    Copy-Item $ffmpegLicense (Join-Path $licenses "FFmpeg-LICENSE.txt") -Force
}

$size = (Get-ChildItem $release -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ("Release: {0} ({1:N1} MB)" -f $release, ($size / 1MB))

if ($Zip) {
    $zip = Join-Path $root ("release\PAMF-Replacer-{0}-win64.zip" -f $version)
    if (Test-Path $zip) { Remove-Item -Force $zip }
    Write-Host "ZIP: $zip"
    Compress-Archive -Path (Join-Path $release "*") -DestinationPath $zip -CompressionLevel Optimal
    Write-Host ("ZIP size: {0:N1} MB" -f ((Get-Item $zip).Length / 1MB))
}
