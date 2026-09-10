@echo off
rem
rem Compile the Smalnets Router Config Tool into a standalone Windows .exe
rem
rem Usage:
rem   build_windows.bat [OPTIONS]
rem
rem Options:
rem   --env prod|dev|both Backend variant(s) to build (default: prod)
rem                         prod -> https://smalnets.com
rem                         dev  -> https://smalnets.ddns.net
rem                         both -> prod + dev binaries
rem   --upload            Upload the built binary(ies) to the matching server's
rem                       release folders (releases/<tag>/ and releases/latest/).
rem                       Reads SSH credentials from deploy_config
rem                       (see deploy_config.sample).
rem   --version X.Y.Z     Override the version instead of auto-incrementing it.
rem   --no-tag            Do not create/push a vX.Y.Z git tag.
rem   -h, --help          Show this help.
rem
rem Version handling:
rem   * With no --version flag the script reads the most recent vX.Y.Z git tag
rem     and auto-increments the patch number (0.0.6 -> 0.0.7).
rem   * The version is written to config_program\version.txt and embedded into
rem     the binary file name (smalnets_<version>[-dev]_amd64.exe).
rem   * Unless --no-tag is given, the script creates a vX.Y.Z tag from the
rem     current HEAD and pushes it (mirrors the GitHub Actions flow).
rem
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VARIANT=prod"
set "UPLOAD=0"
set "DO_TAG=1"
set "VERSION="

:parse_args
if "%~1"=="" goto :parsed
if /i "%~1"=="--env" (
    set "VARIANT=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--upload" set "UPLOAD=1" & shift & goto :parse_args
if /i "%~1"=="--version" (
    set "VERSION=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--no-tag" set "DO_TAG=0" & shift & goto :parse_args
if /i "%~1"=="-h" goto :usage
if /i "%~1"=="/?" goto :usage
echo ERROR: unknown option: %~1
exit /b 1
:parsed

set "TARGETS=prod"
if /i "%VARIANT%"=="dev" set "TARGETS=dev"
if /i "%VARIANT%"=="both" set "TARGETS=prod dev"
if /i not "%VARIANT%"=="prod" if /i not "%VARIANT%"=="dev" if /i not "%VARIANT%"=="both" (
    echo ERROR: VARIANT must be 'dev', 'prod' or 'both' ^(got '%VARIANT%'^)
    exit /b 1
)

rem ---------------------------------------------------------------- version
if "%VERSION%"=="" goto :bump_version
goto :version_done

:bump_version
for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "$t=(git tag --sort=-v:refname ^| Select-Object -First 1); if (-not $t) { $t='v0.0.0' }; $t=$t -replace '^v',''; $p=$t -split '\.'; '{0}.{1}.{2}' -f $p[0], $p[1], ([int]$p[2]+1)"`) do set "_V=%%v"
if "!_V!"=="" set "_V=0.0.1"
set "VERSION=!_V!"

:version_done
set "VERSION=!VERSION:v=!"
set "TAG=v%VERSION%"

> config_program\version.txt echo !VERSION!
echo ==^> Building v!VERSION! for: !TARGETS!

rem ------------------------------------------------------------------ build
echo ==^> Creating venv
python -m venv .venv-build
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
pip install zstandard Nuitka PySide6 requests RouterOS-api imageio pillow

echo ==^> Generating Windows icon (logo.ico)
python scripts\make_icon.py

for %%t in (%TARGETS%) do call :build_one %%t

rem -------------------------------------------------------------------- tag
if "%DO_TAG%"=="1" (
    git rev-parse -q --verify "refs/tags/!TAG!" >nul 2>nul
    if errorlevel 1 (
        git tag "!TAG!"
        git push origin "!TAG!"
        echo ==^> Created and pushed tag !TAG!
    ) else (
        echo ==^> Tag !TAG! already exists ^(not re-tagging^)
    )
)

rem ------------------------------------------------------------------ upload
if "%UPLOAD%"=="1" (
    powershell -NoProfile -Command "Get-Command ssh,scp | Out-Null" >nul 2>nul
    if errorlevel 1 (
        echo ERROR: ssh/scp not found; cannot use --upload
        exit /b 1
    )
    if not exist deploy_config (
        echo ERROR: deploy_config not found.
        echo Copy deploy_config.sample to deploy_config and set your SSH credentials.
        exit /b 1
    )
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("deploy_config") do set "%%a=%%b"
    set "BASE=!UPLOAD_BASE!"
    if "!BASE!"=="" set "BASE=/var/www/smalnets/storage/app/public/releases"
    for %%t in (%TARGETS%) do call :upload_one %%t
)

endlocal
exit /b 0

:build_one
set "T=%~1"
set "API_URL=https://smalnets.com"
set "LABEL="
set "OUT_DIR=build"
if /i "%T%"=="dev" (
    set "API_URL=https://smalnets.ddns.net"
    set "LABEL=-dev"
    set "OUT_DIR=build\dev"
)
> config_program\build_config.py echo BASE_URL = '%API_URL%'
>> config_program\build_config.py echo VARIANT = '%T%'
echo ==^> Building %T% variant v!VERSION! ^(API: %API_URL%^)
if exist "%OUT_DIR%\main.build" rd /s /q "%OUT_DIR%\main.build"
if exist "%OUT_DIR%\main.dist" rd /s /q "%OUT_DIR%\main.dist"
if exist "%OUT_DIR%\main.onefile-build" rd /s /q "%OUT_DIR%\main.onefile-build"
if exist "%OUT_DIR%\main.bin" del /q "%OUT_DIR%\main.bin"
python -m nuitka --standalone ^
    --onefile ^
    --assume-yes-for-downloads ^
    --plugin-enable=pyside6 ^
    --windows-console-mode=disable ^
    --output-dir="%OUT_DIR%" ^
    --windows-icon-from-ico=assets\images\logo.ico ^
    --include-data-files=assets\images\logo.png=assets\images\logo.png ^
    --include-data-files=config_program\version.txt=version.txt ^
    --include-module=build_config ^
    --follow-import-to=api ^
    --follow-import-to=controllers ^
    --follow-import-to=routeros ^
    --follow-import-to=views ^
    config_program\main.py
if not exist dist mkdir dist
copy /y "%OUT_DIR%\main.exe" "dist\smalnets_!VERSION!%LABEL%_amd64.exe"
echo ==^> Done: dist\smalnets_!VERSION!%LABEL%_amd64.exe
goto :eof

:upload_one
set "T=%~1"
if /i "%T%"=="dev" (
    set "SSH_USER=!DEV_USER!"
    set "SSH_HOST=!DEV_HOST!"
    set "LABEL=-dev"
) else (
    set "SSH_USER=!PROD_USER!"
    set "SSH_HOST=!PROD_HOST!"
    set "LABEL="
)
if "!SSH_USER!"=="" (
    if /i "%VARIANT%"=="both" (
        echo ==^> Skipping %T% upload ^(%T%_USER not set in deploy_config^)
        goto :eof
    )
    echo ERROR: %T%_USER not set in deploy_config
    exit /b 1
)
if "!SSH_HOST!"=="" (
    if /i "%VARIANT%"=="both" (
        echo ==^> Skipping %T% upload ^(%T%_HOST not set in deploy_config^)
        goto :eof
    )
    echo ERROR: %T%_HOST not set in deploy_config
    exit /b 1
)
set "OUT=dist\smalnets_!VERSION!%LABEL%_amd64.exe"
echo ==^> Uploading !OUT! to !SSH_USER!@!SSH_HOST!
ssh -o StrictHostKeyChecking=no !SSH_USER!@!SSH_HOST! "mkdir -p !BASE!/!TAG! !BASE!/latest"
scp -o StrictHostKeyChecking=no "!OUT!" !SSH_USER!@!SSH_HOST!:!BASE!/!TAG!/
scp -o StrictHostKeyChecking=no "!OUT!" !SSH_USER!@!SSH_HOST!:!BASE!/latest/
echo ==^> Uploaded %T% ^(releases/!TAG!/ and releases/latest/^)
echo     URL: https://!SSH_HOST!/releases/!TAG!/smalnets_!VERSION!%LABEL%_amd64.exe
goto :eof

:usage
echo Usage: build_windows.bat [OPTIONS]
echo.
echo Options:
echo   --env prod^|dev^|both Backend variant^(s^) to build ^(default: prod^)
echo                         prod -^> https://smalnets.com
echo                         dev  -^> https://smalnets.ddns.net
echo                         both -^> prod + dev binaries
echo   --upload            Upload the built binary^(ies^) to the matching server's
echo                       release folders ^(releases/^<tag^>/ and releases/latest/^).
echo                       Reads SSH credentials from deploy_config
echo                       ^(see deploy_config.sample^).
echo   --version X.Y.Z     Override the version instead of auto-incrementing it.
echo   --no-tag            Do not create/push a vX.Y.Z git tag.
echo   -h, --help          Show this help.
echo.
echo Version handling:
echo   * With no --version flag the script reads the most recent vX.Y.Z git tag
echo     and auto-increments the patch number ^(0.0.6 -^> 0.0.7^).
echo   * The version is written to config_program\version.txt and embedded into
echo     the binary file name ^(smalnets_^<version^>[^[-dev^]]_amd64.exe^).
echo   * Unless --no-tag is given, the script creates a vX.Y.Z tag from the
echo     current HEAD and pushes it ^(mirrors the GitHub Actions flow^).
endlocal
exit /b 0
