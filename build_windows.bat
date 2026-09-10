@echo off
rem
rem Compile the Smalnets Router Config Tool into a standalone Windows .exe
rem
rem Usage:
rem   build_windows.bat [VERSION] [dev|prod]
rem
rem   VERSION    optional, defaults to config_program\version.txt
rem   VARIANT    optional, prod (default) or dev. Picks the backend URL:
rem                prod -> https://smalnets.com
rem                dev  -> https://smalnets.ddns.net
rem
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VERSION=0.0.0"
if exist config_program\version.txt set /p VERSION=<config_program\version.txt
if not "%~1"=="" set "VERSION=%~1"
set "VERSION=!VERSION:v=!"
> config_program\version.txt echo !VERSION!

set "VARIANT=%~2"
if "%VARIANT%"=="" set "VARIANT=prod"
set "LABEL="
set "API_URL=https://smalnets.com"
if /i "%VARIANT%"=="dev" set "API_URL=https://smalnets.ddns.net"
if /i "%VARIANT%"=="dev" set "LABEL=-dev"
> config_program\build_config.py echo BASE_URL = '%API_URL%'
>> config_program\build_config.py echo VARIANT = '%VARIANT%'

echo ==^> Building %VARIANT% variant ^(API: %API_URL%^)

echo ==^> Creating venv
python -m venv .venv-build
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
pip install zstandard Nuitka PySide6 requests RouterOS-api imageio pillow

echo ==^> Generating Windows icon (logo.ico)
python scripts\make_icon.py

echo ==^> Compiling Windows binary (v%VERSION%)
python -m nuitka --standalone ^
    --onefile ^
    --assume-yes-for-downloads ^
    --plugin-enable=pyside6 ^
    --windows-console-mode=disable ^
    --output-dir=build ^
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
copy /y build\main.exe "dist\smalnets_%VERSION%%LABEL%_amd64.exe"
echo ==^> Done: dist\smalnets_%VERSION%%LABEL%_amd64.exe
endlocal
