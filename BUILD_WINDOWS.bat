@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    set "PYCMD=py -3"
) else (
    set "PYCMD=python"
)
%PYCMD% --version || (echo Python 3.10 or later is required on the BUILD computer. & pause & exit /b 1)
%PYCMD% -m pip install --upgrade pyinstaller || (echo Could not install PyInstaller. & pause & exit /b 1)
set "FFMPEG_ARG="
if exist "ffmpeg.exe" (
    echo Found ffmpeg.exe. It will be included inside the one-file app.
    set "FFMPEG_ARG=--add-binary=ffmpeg.exe;."
) else (
    echo WARNING: No ffmpeg.exe beside this script.
    echo Pandemonium video conversion will require ffmpeg.exe beside the resulting EXE
    echo or a manually specified FFmpeg executable.
)
%PYCMD% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "AirplayNew3DSGameDataPreparationTool" ^
    --icon "app_icon.ico" ^
    --add-data "GAME_FILES.json;." ^
    --add-data "preparation\restoration_recipe.json.zlib;preparation" ^
    --add-data "app_icon.png;." ^
    --add-data "app_icon.ico;." ^
    %FFMPEG_ARG% ^
    3ds_game_data_installer.py
if errorlevel 1 (echo Build failed. & pause & exit /b 1)
echo.
echo Built: dist\AirplayNew3DSGameDataPreparationTool.exe
echo Test with your own verified game packages before sharing the EXE.
pause
