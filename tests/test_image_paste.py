import io
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.cli import main as cli_main
from jobutils.markdown.images import (
    ClipboardError,
    paste_clipboard_image,
    read_clipboard_png,
)


def completed(command, returncode=0, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess(
        command, returncode, stdout=stdout, stderr=stderr
    )


class ImagePasteTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.markdown = self.root / "guide.md"
        self.markdown.write_text("# Guide\n", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_paste_saves_png_and_returns_relative_markdown_link(self):
        result = paste_clipboard_image(
            self.markdown,
            alt_text="architecture",
            provider="xclip",
            runner=lambda command, **kwargs: completed(command, stdout=b"PNGDATA"),
            which=lambda name: "/usr/bin/xclip",
        )

        self.assertRegex(
            result["markdown"],
            r"^!\[architecture\]\(assets/guide-[0-9a-f]{8}\.png\)$",
        )
        self.assertEqual(
            (self.root / result["image_path"]).read_bytes(), b"PNGDATA"
        )
        self.assertTrue(result["absolute_path"].endswith(".png"))

    def test_provider_failure_does_not_leave_partial_file(self):
        def failed_runner(command, **kwargs):
            return completed(command, returncode=1, stderr=b"clipboard is empty")

        with self.assertRaisesRegex(ClipboardError, "clipboard is empty"):
            paste_clipboard_image(
                self.markdown,
                provider="xclip",
                runner=failed_runner,
                which=lambda name: "/usr/bin/xclip",
            )

        self.assertFalse((self.root / "assets").exists())

    def test_unsafe_alt_text_is_not_used_as_a_path(self):
        result = paste_clipboard_image(
            self.markdown,
            alt_text="../outside/name",
            provider="xclip",
            runner=lambda command, **kwargs: completed(command, stdout=b"PNGDATA"),
            which=lambda name: "/usr/bin/xclip",
        )

        self.assertTrue(result["image_path"].startswith("assets/"))
        self.assertNotIn("outside", result["image_path"])
        self.assertTrue((self.root / result["image_path"]).is_file())

    def test_linux_prefers_wayland_then_xclip(self):
        calls = []

        def recording_runner(command, **kwargs):
            calls.append(command)
            return completed(command, stdout=b"PNGDATA")

        result = read_clipboard_png(
            provider="auto",
            platform_name="linux",
            which=lambda name: "/bin/" + name
            if name in ("wl-paste", "xclip")
            else None,
            runner=recording_runner,
        )

        self.assertEqual(result, b"PNGDATA")
        self.assertEqual(calls[0][0], "/bin/wl-paste")
        self.assertIn("image/png", calls[0])

    def test_unknown_platform_reports_supported_providers(self):
        with self.assertRaisesRegex(ClipboardError, "macOS.*Windows.*Linux"):
            read_clipboard_png(
                provider="auto", platform_name="plan9", which=lambda _: None
            )

    def test_macos_pngpaste_provider_writes_a_png(self):
        calls = []

        def pngpaste_runner(command, **kwargs):
            calls.append(command)
            Path(command[1]).write_bytes(b"PNGDATA")
            return completed(command)

        result = read_clipboard_png(
            provider="pngpaste",
            platform_name="darwin",
            which=lambda name: "/usr/local/bin/pngpaste",
            runner=pngpaste_runner,
        )

        self.assertEqual(result, b"PNGDATA")
        self.assertEqual(calls[0][0], "/usr/local/bin/pngpaste")

    def test_windows_power_shell_provider_uses_noninteractive_command(self):
        destination = self.root / "clipboard.png"

        def powershell_runner(command, **kwargs):
            destination.write_bytes(b"PNGDATA")
            return completed(command)

        result = read_clipboard_png(
            provider="powershell",
            platform_name="win32",
            destination=destination,
            which=lambda name: "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            runner=powershell_runner,
        )

        self.assertEqual(result, b"PNGDATA")
        self.assertEqual(result, destination.read_bytes())

    def test_cli_prints_image_and_markdown_lines(self):
        output = io.StringIO()
        result = {
            "image_path": "assets/guide-a1b2c3d4.png",
            "markdown": "![guide](assets/guide-a1b2c3d4.png)",
        }
        with patch("jobutils.cli.paste_clipboard_image", return_value=result):
            with redirect_stdout(output):
                status = cli_main(
                    [
                        "markdown",
                        "paste-image",
                        "--repo",
                        str(self.root),
                        "--file",
                        str(self.markdown),
                        "--provider",
                        "xclip",
                    ]
                )

        self.assertEqual(status, 0)
        self.assertIn("image: assets/guide-a1b2c3d4.png", output.getvalue())
        self.assertIn(
            "markdown: ![guide](assets/guide-a1b2c3d4.png)", output.getvalue()
        )

    def test_cli_reports_missing_clipboard_provider(self):
        error = io.StringIO()
        with patch(
            "jobutils.cli.paste_clipboard_image",
            side_effect=ClipboardError("xclip is not available"),
        ):
            with redirect_stderr(error):
                status = cli_main(
                    [
                        "markdown",
                        "paste-image",
                        "--repo",
                        str(self.root),
                        "--file",
                        str(self.markdown),
                        "--provider",
                        "xclip",
                    ]
                )

        self.assertEqual(status, 1)
        self.assertIn("IMAGE: paste failed:", error.getvalue())


if __name__ == "__main__":
    unittest.main()
