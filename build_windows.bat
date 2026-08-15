@echo off
rem
rem Compile the Smalnets Router Config Tool into a standalone Windows .exe
rem
rem Usage:
rem   build_windows.bat [VERSION]     VERSION optional, defaults to config_program\version.txt
rem
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VERSION=0.0.0"
if exist config_program\version.txt set /p VERSION=<config_program\version.txt
if not "%~1"=="" set "VERSION=%~1"
set "VERSION=!VERSION:v=!"
> config_program\version.txt echo !VERSION!

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
    --follow-import-to=api ^
    --follow-import-to=controllers ^
    --follow-import-to=routeros ^
    --follow-import-to=views ^
    config_program\main.py

if not exist dist mkdir dist
copy /y build\main.exe "dist\smalnets_%VERSION%_amd64.exe"
echo ==^> Done: dist\smalnets_%VERSION%_amd64.exe
endlocal
