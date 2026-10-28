PAMFtool-win-x64.exe
====================

Self-contained .NET 8 build of https://github.com/ravenDS/PAMFtool (v1.2),
published from source with:

  dotnet publish PAMFtool/PAMFtool.vbproj -c Release -r win-x64 ^
    --self-contained true -p:PublishSingleFile=true ^
    -p:IncludeNativeLibrariesForSelfExtract=true ^
    -p:EnableCompressionInSingleFile=true

The .NET runtime is included, so the target machine does not need .NET 8.
License: GPL-3.0, see licenses/PAMFtool-GPL-3.0.txt or the upstream repository.
