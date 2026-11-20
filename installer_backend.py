"""Backend for the four-game New 3DS data preparation GUI.

The original preparation/extraction implementations are kept as separate source
files and called directly. No game data is supplied by this application.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Callable

import prepare_nfs_Undercover as nfs
import Project_Gotham_Racing_prepare_game as pgr
import Resident_Evil_Degeneration_prepare_game as resident
import prepare_pandemonium as pandemonium


GAMES = {
    'nfs': {
        'title': 'Need for Speed Undercover',
        'relative_dir': '3ds/nfs_undercover/game',
        'hint': 'Requires the exact supported, community-modified N-Gage edition.',
        'inputs': [('package', 'Original .n-gage package', 'file')],
    },
    'pandemonium': {
        'title': 'Pandemonium!',
        'relative_dir': '3ds/pandemonium',
        'hint': 'Requires the exact supported N-Gage package and FFmpeg for two movies.',
        'inputs': [('package', 'Original .n-gage package', 'file')],
    },
    'resident': {
        'title': 'Resident Evil Degeneration',
        'relative_dir': '3ds/res_degene/game',
        'hint': 'Requires matching N-Gage, iOS and BREW source data; files or extracted directories are accepted.',
        'inputs': [
            ('ngage', 'N-Gage package or extracted folder', 'either'),
            ('ios', 'iOS IPA / ZIP / main.dz / folder', 'either'),
            ('brew', 'BREW main.dz / ZIP / folder', 'either'),
        ],
    },
    'pgr': {
        'title': 'Project Gotham Racing',
        'relative_dir': '3ds/pgr_mobile/game',
        'hint': 'Requires the exact supported Symbian SIS/SISX edition.',
        'inputs': [('package', 'Original .sis / .sisx package', 'file')],
    },
}


def resource_path(relative: str) -> Path:
    """File bundled with PyInstaller or located beside source tree."""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent / relative


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_no_symlinks(path: Path) -> None:
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError(f'Output location contains a symbolic link: {p}')


def _checked_destination(output_root: Path, subpath: str) -> Path:
    path = PurePosixPath(subpath)
    if not subpath or path.is_absolute() or '..' in path.parts or '\\' in subpath or ':' in subpath:
        raise ValueError('Unsafe relative output directory')
    output_root = output_root.expanduser().absolute()
    _check_no_symlinks(output_root)
    if output_root.exists() and not output_root.is_dir():
        raise ValueError('The chosen output location is not a directory')
    dest = output_root.joinpath(*path.parts)
    _check_no_symlinks(dest)
    return dest


def _check_and_stage(files: dict[str, bytes], destination: Path, log: Callable[[str], None]) -> None:
    """Write verified bytes without deleting saves, changing unrelated files or overwriting conflicts."""
    _check_no_symlinks(destination)
    for name, data in files.items():
        p = PurePosixPath(name)
        if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
            raise ValueError(f'Invalid game file path: {name}')
        target = destination.joinpath(*p.parts)
        _check_no_symlinks(target)
        if target.exists():
            if not target.is_file() or target.read_bytes() != data:
                raise ValueError(f'Existing game file differs: {target}. Choose an empty staging folder.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stage completely before writing final files; unrelated SD files are never removed.
    with tempfile.TemporaryDirectory(prefix='.3ds-prepared-', dir=destination.parent) as temp:
        stage = Path(temp)
        for name, data in files.items():
            target = stage.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for name, data in files.items():
            target = destination.joinpath(*PurePosixPath(name).parts)
            if target.is_file() and target.read_bytes() == data:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage.joinpath(*PurePosixPath(name).parts), target)
    log(f'Written and verified: {len(files)} files')


def ffmpeg_binary(chosen: str = '') -> str:
    """Find user-specified FFmpeg, a bundled copy, executable-adjacent copy, or PATH."""
    if chosen.strip():
        target = Path(chosen.strip().strip('"')).expanduser()
        if not target.is_file():
            raise ValueError('Selected FFmpeg executable does not exist.')
        return str(target.absolute())
    name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    candidates = [
        resource_path(name),
        Path(sys.executable).resolve().parent / name,
        Path(__file__).resolve().parent / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    result = shutil.which(name) or shutil.which('ffmpeg')
    if result:
        return result
    raise ValueError('FFmpeg not found. Place ffmpeg.exe alongside the program or select it in the interface.')


def _convert_pandemonium_videos(game_dir: Path, video_dir: Path, ffmpeg_path: str,
                                log: Callable[[str], None]) -> None:
    """Use the exact FFmpeg flags from supplied prepare_videos.py.

    Every input is taken from a single SHA-256-pinned N-Gage package, with
    each installed resource's SIS SHA-1 verified by prepare_pandemonium.extract.
    The optional independent source-hash manifest, if provided, is honoured too.
    """
    manifest_path = resource_path('video_source_hashes.json')
    expected = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None
    video_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    for source, target in (('in_mpg4.dz', 'intro.mpg'), ('out_mpg4.dz', 'ending.mpg')):
        original = game_dir / source
        raw = original.read_bytes()
        digest = sha256(raw)
        if expected is not None and digest != expected[source]:
            raise ValueError(f'Unexpected Pandemonium movie SHA-256: {source}')
        log(f'Converting {source} to {target} ...')
        output = video_dir / target
        temporary = output.with_suffix('.mpg.tmp')
        command = [
            ffmpeg_path, '-v', 'error', '-y', '-i', str(original),
            '-map', '0:v:0', '-map', '0:a:0', '-vf', 'fps=25',
            '-c:v', 'mpeg1video', '-q:v', '8', '-c:a', 'mp2',
            '-ar', '32000', '-ac', '1', '-b:a', '64k', '-f', 'mpeg', str(temporary),
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or b'').decode('utf-8', errors='replace').strip()[-1200:]
            raise ValueError(f'FFmpeg failed while converting {source}: {detail or error}') from error
        temporary.replace(output)
        report[target] = {
            'source_sha256': digest,
            'sha256': sha256(output.read_bytes()),
            'bytes': output.stat().st_size,
            'command': command,
        }
    (video_dir / 'conversion_manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def _prepare_pandemonium(package: Path, output_root: Path, ffmpeg_override: str,
                          log: Callable[[str], None]) -> Path:
    target = _checked_destination(output_root, GAMES['pandemonium']['relative_dir'])
    if (target / 'game').exists() or (target / 'video').exists() or (target / 'package_inventory.json').exists():
        raise ValueError('Pandemonium game/video files already exist. Use an empty staging directory.')
    ffmpeg_path = ffmpeg_binary(ffmpeg_override)
    log('Checking N-Gage package and SHA-1 inventory ...')
    with tempfile.TemporaryDirectory(prefix='pandemonium-prepare-') as temp:
        work = Path(temp)
        pandemonium.extract(package, work)
        log('Source package verified.')
        _convert_pandemonium_videos(work / 'game', work / 'video', ffmpeg_path, log)
        _check_no_symlinks(target)
        target.mkdir(parents=True, exist_ok=True)
        # The complete files are now staged. Never replace existing game/video trees.
        try:
            shutil.copytree(work / 'game', target / 'game')
            shutil.copytree(work / 'video', target / 'video')
            shutil.copy2(work / 'package_inventory.json', target / 'package_inventory.json')
        except Exception:
            # If copying fails, keep existing user files intact, but remove only
            # newly-created directories for this installation.
            for name in ('game', 'video'):
                produced = target / name
                if produced.exists() and produced.is_dir() and not produced.is_symlink():
                    shutil.rmtree(produced)
            raise
    return target


def prepare_game(game_id: str, inputs: dict[str, str], output_root: str,
                 log: Callable[[str], None] = print, ffmpeg_override: str = '') -> Path:
    """Prepare one game's data into a selected SD root/staging folder."""
    if game_id not in GAMES:
        raise ValueError('Unknown game.')
    if not output_root.strip():
        raise ValueError('Choose an output directory.')
    needed = GAMES[game_id]['inputs']
    sources: dict[str, Path] = {}
    for key, label, kind in needed:
        selected = inputs.get(key, '').strip().strip('"')
        if not selected:
            raise ValueError(f'Choose {label}.')
        path = Path(selected).expanduser()
        if not path.exists() or (kind == 'file' and not path.is_file()):
            raise ValueError(f'Input does not exist or is not a file: {path}')
        sources[key] = path
    root = Path(output_root)
    log(f'Preparing {GAMES[game_id]["title"]} ...')
    if game_id == 'nfs':
        log('Reading manifest; extracting and verifying N-Gage data ...')
        manifest = json.loads(resource_path('GAME_FILES.json').read_text(encoding='utf-8'))
        files = nfs.prepare(sources['package'].read_bytes(), manifest)
        dest = _checked_destination(root, GAMES[game_id]['relative_dir'])
        # Reuse known-good collision policy and atomic file handling.
        _check_and_stage(files, dest, log)
    elif game_id == 'pgr':
        log('Checking supported SIS version and embedded game files ...')
        files = pgr.prepare_data(sources['package'])
        dest = _checked_destination(root, GAMES[game_id]['relative_dir'])
        _check_and_stage(files, dest, log)
    elif game_id == 'resident':
        log('Loading verified restoration recipe ...')
        recipe = json.loads(zlib.decompress(resource_path('preparation/restoration_recipe.json.zlib').read_bytes()))
        log('Checking N-Gage, iOS and BREW donors; reconstructing game files ...')
        files = resident.reconstruct(sources['ngage'], sources['ios'], sources['brew'], recipe)
        dest = _checked_destination(root, GAMES[game_id]['relative_dir'])
        _check_and_stage(files, dest, log)
    elif game_id == 'pandemonium':
        dest = _prepare_pandemonium(sources['package'], root, ffmpeg_override, log)
    log(f'Finished: {dest}')
    return dest
