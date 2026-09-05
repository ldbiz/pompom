"""Tests for managed custom sound file helpers."""

import tempfile
import unittest
from pathlib import Path

from pompom.constants import _DING_PATH, _TICKTOCK_PATH
from pompom.services.sound_files import (
    SoundKind,
    has_custom,
    install_custom,
    managed_path,
    reset_all_custom,
    reset_custom,
    resolve_sound_path,
)


class SoundFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.custom_dir = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_resolve_uses_factory_when_no_custom(self) -> None:
        self.assertEqual(
            resolve_sound_path(SoundKind.TICK, custom_dir=self.custom_dir),
            _TICKTOCK_PATH,
        )
        self.assertEqual(
            resolve_sound_path(SoundKind.BELL, custom_dir=self.custom_dir),
            _DING_PATH,
        )

    def test_install_and_resolve_custom(self) -> None:
        source = self.custom_dir / "source.wav"
        source.write_bytes(b"RIFF")
        install_custom(SoundKind.TICK, source, custom_dir=self.custom_dir)

        managed = managed_path(SoundKind.TICK, custom_dir=self.custom_dir)
        self.assertTrue(managed.is_file())
        self.assertEqual(
            resolve_sound_path(SoundKind.TICK, custom_dir=self.custom_dir),
            managed,
        )
        self.assertTrue(has_custom(SoundKind.TICK, custom_dir=self.custom_dir))

        source.unlink()
        self.assertTrue(managed.is_file())
        self.assertEqual(managed.read_bytes(), b"RIFF")

    def test_failed_install_preserves_existing_custom(self) -> None:
        existing = self.custom_dir / "ticktock.wav"
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"KEEP")

        missing = self.custom_dir / "missing.wav"
        with self.assertRaises(ValueError):
            install_custom(SoundKind.TICK, missing, custom_dir=self.custom_dir)

        self.assertEqual(existing.read_bytes(), b"KEEP")

    def test_rejects_non_wav(self) -> None:
        source = self.custom_dir / "note.mp3"
        source.write_bytes(b"ID3")
        with self.assertRaises(ValueError) as ctx:
            install_custom(SoundKind.BELL, source, custom_dir=self.custom_dir)
        self.assertIn("WAV", str(ctx.exception))

    def test_reset_single_leaves_other_custom(self) -> None:
        tick_source = self.custom_dir / "tick.wav"
        bell_source = self.custom_dir / "bell.wav"
        tick_source.write_bytes(b"TICK")
        bell_source.write_bytes(b"BELL")
        install_custom(SoundKind.TICK, tick_source, custom_dir=self.custom_dir)
        install_custom(SoundKind.BELL, bell_source, custom_dir=self.custom_dir)

        reset_custom(SoundKind.TICK, custom_dir=self.custom_dir)

        self.assertFalse(has_custom(SoundKind.TICK, custom_dir=self.custom_dir))
        self.assertTrue(has_custom(SoundKind.BELL, custom_dir=self.custom_dir))
        self.assertEqual(
            resolve_sound_path(SoundKind.TICK, custom_dir=self.custom_dir),
            _TICKTOCK_PATH,
        )

    def test_reset_all_clears_both(self) -> None:
        tick_source = self.custom_dir / "tick.wav"
        bell_source = self.custom_dir / "bell.wav"
        tick_source.write_bytes(b"TICK")
        bell_source.write_bytes(b"BELL")
        install_custom(SoundKind.TICK, tick_source, custom_dir=self.custom_dir)
        install_custom(SoundKind.BELL, bell_source, custom_dir=self.custom_dir)

        reset_all_custom(custom_dir=self.custom_dir)

        self.assertFalse(has_custom(SoundKind.TICK, custom_dir=self.custom_dir))
        self.assertFalse(has_custom(SoundKind.BELL, custom_dir=self.custom_dir))


if __name__ == "__main__":
    unittest.main()
