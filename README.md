# Airplay-New3DS-Game-Data-Preparation-Tool
A simpler way to convert data to use with the Airplay/Marmalade to New 3DS ports, as found in my other repos.
Releases include a standalone EXE that should run on modern windows, consider installing FFMPEG if you plan on setting up Pandemonium! in particular.

## Supported games and inputs

| Game | User-provided inputs | Output relative to the destination folder |
|---|---|---|
| Need for Speed Undercover | Cracked `.n-gage` package | `3ds/nfs_undercover/game/` |
| Pandemonium! | New cracked `.n-gage` package and FFmpeg | `3ds/pandemonium/game/` and `3ds/pandemonium/video/` |
| Resident Evil Degeneration | Tested N-Gage package (or extracted folder), iOS IPA/ZIP or extracted `main.dz`, and BREW ZIP/folder or `main.dz` | `3ds/res_degene/game/` |
| Project Gotham Racing | Tested Symbian SIS/SISX edition | `3ds/pgr_mobile/game/` |

**The `.3dsx` homebrew launchers are not included.** Copy the appropriate port `.3dsx` from its release separately. Output directory refers to the **root of your SD-card**, not the individual `game` folder. Of course you can extract it anywhere, just ensure you copy the output to the right place.

Files with incorrect hashes or unsupported original editions should fail validation and not attempt an extraction. The application doesn't download games, bypass protections, overwrite differing files, or remove save directories if you extract over an existing extraction. Existing matching game files are reused; for Pandemonium, use a fresh staging folder if game/video already exist to prevent issues with the FFMPEG process.

## Use directly with Python (for development)

Install Python 3.10+ with Tkinter and run:

```
python 3ds_game_data_installer.py
```

No third-party Python packages are needed to run from source. `ffmpeg` is needed for Pandemonium!'s video conversion. You can select an FFmpeg binary inside the UI.

## Build a standalone Windows 10/11 executable

Build on a **Windows x64 PC** with Python 3.10+ installed (only on the build machine). Optionally place a matching Windows `ffmpeg.exe` in the **same folder as `BUILD_WINDOWS.bat`** to embed it into the single-file output. Then double-click:

```
BUILD_WINDOWS.bat
```

It installs PyInstaller in the build environment and writes `dist/3DSGameDataInstaller.exe`. End users do not need Python. If you omit FFmpeg during building, Pandemonium video conversion requires a copy of `ffmpeg.exe` beside the published EXE, in PATH, or chosen manually via the GUI. This executable has been validated on Windows hardware running Windows 11. PyInstaller is not a cross-compiler; building on Linux does not produce a Windows `.exe`.

## Contents

- `3ds_game_data_installer.py` — Tkinter GUI.
- `installer_backend.py` — adapters, output safety, logging and FFmpeg conversion.
- The supplied original Python preparation scripts, unchanged (apart from renaming `sis_support(1).py` to `sis_support.py` so imports resolve).
- `preparation/restoration_recipe.json.zlib` and `GAME_FILES.json` — verified baseline metadata.
- `BUILD_WINDOWS.bat` — builds a portable one-file Windows EXE.

## About redistribution

Several original scripts declare GPL-2.0-or-later licensing and refer to their project's LICENSE file. Preserve those notices and include the appropriate GPL licence and corresponding source when redistributing. This prototype carries the original script source as supplied, but is not an assertion that every embedded recipe literal or donor fragment can be freely redistributed. See each project's original distribution terms.
