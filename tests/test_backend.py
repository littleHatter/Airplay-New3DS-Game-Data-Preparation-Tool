"""Source-only integration checks; no copyrighted game inputs needed."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import installer_backend as b


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='game-installer-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pkg = self.root / 'owned.n-gage'
        self.pkg.write_bytes(b'example-input')
        self.logs = []

    def test_game_output_path_names(self):
        self.assertEqual(b.GAMES['nfs']['relative_dir'], '3ds/nfs_undercover/game')
        self.assertEqual(b.GAMES['pgr']['relative_dir'], '3ds/pgr_mobile/game')
        self.assertEqual(b.GAMES['resident']['relative_dir'], '3ds/res_degene/game')
        self.assertEqual(b.GAMES['pandemonium']['relative_dir'], '3ds/pandemonium')

    def test_nfs_adapter_and_collision_check(self):
        game = {'overrides/t_en': b'tutorial', 'nfsuc.xe3u': b'XE3U'}
        with patch.object(b.nfs, 'prepare', return_value=game) as stub:
            dest = b.prepare_game('nfs', {'package': str(self.pkg)}, str(self.root), self.logs.append)
            self.assertEqual(dest / 'overrides/t_en', self.root / '3ds/nfs_undercover/game/overrides/t_en')
            self.assertEqual((dest / 'nfsuc.xe3u').read_bytes(), b'XE3U')
            self.assertTrue(stub.called)
            # Re-running on identical files must leave them unchanged.
            b.prepare_game('nfs', {'package': str(self.pkg)}, str(self.root), self.logs.append)
            (dest / 'nfsuc.xe3u').write_bytes(b'unrelated data')
            with self.assertRaisesRegex(ValueError, 'Existing game file differs'):
                b.prepare_game('nfs', {'package': str(self.pkg)}, str(self.root), self.logs.append)
            self.assertEqual((dest / 'nfsuc.xe3u').read_bytes(), b'unrelated data')

    def test_pgr_adapter_preserves_unrelated_saves(self):
        save = self.root / '3ds/pgr_mobile/user/my_save.sav'
        save.parent.mkdir(parents=True)
        save.write_bytes(b'saved')
        with patch.object(b.pgr, 'prepare_data', return_value={'pgr.xe3u': b'XE3U-foo'}):
            dest = b.prepare_game('pgr', {'package': str(self.pkg)}, str(self.root), self.logs.append)
        self.assertEqual((dest / 'pgr.xe3u').read_bytes(), b'XE3U-foo')
        self.assertEqual(save.read_bytes(), b'saved')

    def test_re_adapter_with_three_donors(self):
        with patch.object(b.resident, 'reconstruct', return_value={'game.dz': b'data'}) as fake:
            dest = b.prepare_game('resident', {'ngage': str(self.pkg), 'ios': str(self.pkg), 'brew': str(self.pkg)},
                                  str(self.root), self.logs.append)
        self.assertTrue(fake.called)
        self.assertEqual((dest / 'game.dz').read_bytes(), b'data')

    def test_pand_video_conversion_uses_original_ffmpeg_settings(self):
        game = self.root / 'input'
        videos = self.root / 'videos'
        game.mkdir()
        (game / 'in_mpg4.dz').write_bytes(b'intro')
        (game / 'out_mpg4.dz').write_bytes(b'ending')
        calls = []
        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            Path(cmd[-1]).write_bytes(b'fake transcoded bytes')
        with patch.object(b.subprocess, 'run', side_effect=fake_run):
            b._convert_pandemonium_videos(game, videos, 'ffmpeg', self.logs.append)
        self.assertEqual(len(calls), 2)
        for cmd in calls:
            self.assertIn('mpeg1video', cmd)
            self.assertIn('mp2', cmd)
            self.assertIn('fps=25', cmd)
        self.assertEqual((videos / 'intro.mpg').read_bytes(), b'fake transcoded bytes')
        self.assertIn('source_sha256', json.loads((videos / 'conversion_manifest.json').read_text())['intro.mpg'])

    def test_pand_adapter_creates_both_trees(self):
        def fake_extract(_package, stage):
            (stage / 'game').mkdir()
            (stage / 'game' / 'in_mpg4.dz').write_bytes(b'a')
            (stage / 'game' / 'out_mpg4.dz').write_bytes(b'b')
            (stage / 'package_inventory.json').write_text('{}')
        def fake_convert(_game, videos, _ffmpeg, _log):
            videos.mkdir()
            (videos / 'intro.mpg').write_bytes(b'v')
            (videos / 'ending.mpg').write_bytes(b'v')
        with patch.object(b.pandemonium, 'extract', side_effect=fake_extract), \
             patch.object(b, '_convert_pandemonium_videos', side_effect=fake_convert), \
             patch.object(b, 'ffmpeg_binary', return_value='ffmpeg'):
            dest = b.prepare_game('pandemonium', {'package': str(self.pkg)}, str(self.root), self.logs.append)
            self.assertTrue((dest / 'game/in_mpg4.dz').exists())
            self.assertTrue((dest / 'video/intro.mpg').exists())
            with self.assertRaisesRegex(ValueError, 'already exist'):
                b.prepare_game('pandemonium', {'package': str(self.pkg)}, str(self.root), self.logs.append)

    def test_actual_unsupported_sources_fail(self):
        with self.assertRaises(Exception):
            b.prepare_game('pgr', {'package': str(self.pkg)}, str(self.root), self.logs.append)
        with self.assertRaises(Exception):
            b.prepare_game('nfs', {'package': str(self.pkg)}, str(self.root), self.logs.append)
        with self.assertRaises(Exception):
            b.prepare_game('pandemonium', {'package': str(self.pkg)}, str(self.root), self.logs.append)
        self.assertFalse((self.root / '3ds').exists())

    def test_unsafe_paths_fail(self):
        with self.assertRaises(ValueError):
            b._checked_destination(self.root, '../outside')
        if hasattr(Path, 'symlink_to'):
            alias = self.root / 'alias'
            try:
                alias.symlink_to(self.root, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValueError):
                b._checked_destination(alias, '3ds/test/game')


if __name__ == '__main__':
    unittest.main()
