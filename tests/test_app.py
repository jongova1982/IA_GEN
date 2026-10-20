import ast
import base64
import tempfile
import unittest
import wave
from pathlib import Path

import app


class AppStructureTests(unittest.TestCase):
    def test_design_assets_exist(self):
        self.assertTrue(app.BRAND_IMAGE.is_file())
        self.assertTrue(app.BRAND_LOGO.is_file())
        self.assertTrue(app.DRONE_IMAGE.is_file())
        self.assertEqual(len(app.SPRITE_FILES), 4)
        self.assertTrue(all(path.is_file() for path in app.SPRITE_FILES))

    def test_visible_button_callbacks_exist(self):
        tree = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
        class_node = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and node.name == "LocalAIApp")
        methods = {node.name for node in class_node.body if isinstance(node, ast.FunctionDef)}
        target_methods = {"_build_chat", "_build_images", "_build_audio"}
        callbacks = set()
        for method in class_node.body:
            if isinstance(method, ast.FunctionDef) and method.name in target_methods:
                for node in ast.walk(method):
                    if isinstance(node, ast.keyword) and node.arg == "command":
                        for child in ast.walk(node.value):
                            if (isinstance(child, ast.Attribute)
                                    and isinstance(child.value, ast.Name)
                                    and child.value.id == "self"):
                                callbacks.add(child.attr)
        self.assertTrue(callbacks)
        self.assertTrue(callbacks.issubset(methods), sorted(callbacks - methods))

    def test_drone_overlay_contains_only_image_and_light(self):
        tree = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
        class_node = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and node.name == "LocalAIApp")
        method = next(node for node in class_node.body
                      if isinstance(node, ast.FunctionDef) and node.name == "_show_speaking_drone")
        calls = [node.func.attr for node in ast.walk(method)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertIn("create_image", calls)
        self.assertIn("create_oval", calls)
        self.assertNotIn("Label", calls)
        self.assertNotIn("Button", calls)


class AudioEnvelopeTests(unittest.TestCase):
    def test_raw_tts_pcm_is_wrapped_in_a_valid_wave_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tts.wav"
            pcm = b"\x00\x00" * 1200
            app.LocalAIApp._write_tts_wav(
                base64.b64encode(pcm).decode("ascii"), "audio/L16;rate=24000", path)
            with wave.open(str(path), "rb") as wav:
                self.assertEqual(wav.getframerate(), 24000)
                self.assertEqual(wav.getnframes(), 1200)
                self.assertEqual(wav.getnchannels(), 1)

    def test_reads_waveform_and_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00\xff\x7f" * 4000)
            envelope, duration = app.LocalAIApp._read_audio_envelope(path)
        self.assertTrue(envelope)
        self.assertAlmostEqual(duration, 1.0)
        self.assertAlmostEqual(max(envelope), 1.0)

    def test_invalid_audio_returns_empty_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-a-wave.wav"
            path.write_text("invalid", encoding="utf-8")
            self.assertEqual(app.LocalAIApp._read_audio_envelope(path), ([], 0.0))


if __name__ == "__main__":
    unittest.main()
