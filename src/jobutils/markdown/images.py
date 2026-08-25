"""Cross-platform clipboard image extraction for Markdown authoring."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Dict, Optional, Sequence
import uuid


class ClipboardError(RuntimeError):
    """Raised when a PNG cannot be read from the system clipboard."""


_FILE_PROVIDERS = {"pngpaste", "osascript", "powershell", "pwsh"}
_KNOWN_PROVIDERS = {
    "pngpaste",
    "osascript",
    "powershell",
    "pwsh",
    "wl-paste",
    "xclip",
}


def _platform_name(platform_name: Optional[str]) -> str:
    return platform_name or sys.platform


def _provider_candidates(platform_name: str) -> Sequence[str]:
    if platform_name == "darwin":
        return ("pngpaste", "osascript")
    if platform_name == "win32":
        return ("powershell", "pwsh")
    if platform_name.startswith("linux"):
        return ("wl-paste", "xclip")
    return ()


def _available_command(provider: str, which: Callable[[str], Optional[str]]) -> Optional[str]:
    command = which(provider)
    return command if command else None


def _escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_powershell_string(value: str) -> str:
    return value.replace("'", "''")


def _provider_command(provider: str, executable: str, destination: Path):
    if provider == "pngpaste":
        return [executable, str(destination)]
    if provider == "osascript":
        path = _escape_applescript_string(str(destination))
        script = (
            'set destinationPath to "{}"\n'
            "set imageData to the clipboard as «class PNGf»\n"
            "set imageFile to open for access POSIX file destinationPath with write permission\n"
            "write imageData to imageFile\n"
            "close access imageFile"
        ).format(path)
        return [executable, "-e", script]
    if provider in ("powershell", "pwsh"):
        path = _escape_powershell_string(str(destination))
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) "
            "{{ throw 'The clipboard does not contain an image.' }}; "
            "$image = [System.Windows.Forms.Clipboard]::GetImage(); "
            "$image.Save('{}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$image.Dispose()"
        ).format(path)
        return [
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]
    if provider == "wl-paste":
        return [executable, "--no-newline", "--type", "image/png"]
    if provider == "xclip":
        return [executable, "-selection", "clipboard", "-t", "image/png", "-o"]
    raise ClipboardError("unknown image clipboard provider: {}".format(provider))


def _read_destination(destination: Path) -> bytes:
    try:
        data = destination.read_bytes()
    except OSError as error:
        raise ClipboardError("clipboard provider did not create a PNG: {}".format(error))
    if not data:
        raise ClipboardError("clipboard provider returned an empty image")
    return data


def read_clipboard_png(
    provider: str = "auto",
    platform_name: Optional[str] = None,
    destination: Optional[Path] = None,
    which: Callable[[str], Optional[str]] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bytes:
    """Read PNG bytes from an available platform clipboard provider."""

    if provider != "auto" and provider not in _KNOWN_PROVIDERS:
        raise ClipboardError("unknown image clipboard provider: {}".format(provider))

    platform_key = _platform_name(platform_name)
    candidates = (
        tuple(_provider_candidates(platform_key))
        if provider == "auto"
        else (provider,)
    )
    if not candidates:
        raise ClipboardError(
            "no image clipboard provider is available. "
            "Supported platforms: macOS, Windows, Linux."
        )

    last_error = ""
    for candidate in candidates:
        executable = _available_command(candidate, which)
        if executable is None:
            last_error = "{} is not available on PATH".format(candidate)
            if provider != "auto":
                break
            continue

        temporary_directory = None
        target = destination
        if candidate in _FILE_PROVIDERS and target is None:
            temporary_directory = tempfile.TemporaryDirectory()
            target = Path(temporary_directory.name) / "clipboard.png"

        command = _provider_command(candidate, executable, target or Path("clipboard.png"))
        completed = runner(command, capture_output=True, check=False)
        if completed.returncode == 0:
            if candidate in _FILE_PROVIDERS:
                data = _read_destination(target)  # type: ignore[arg-type]
            else:
                data = completed.stdout or b""
                if not data:
                    last_error = "{} returned an empty image".format(candidate)
                    if temporary_directory is not None:
                        temporary_directory.cleanup()
                    if provider != "auto":
                        break
                    continue
            if temporary_directory is not None:
                temporary_directory.cleanup()
            return data

        detail = (completed.stderr or b"").decode("utf-8", "replace").strip()
        last_error = detail or "{} could not read a PNG from the clipboard".format(candidate)
        if temporary_directory is not None:
            temporary_directory.cleanup()
        if provider != "auto":
            break

    raise ClipboardError(last_error or "clipboard does not contain a PNG image")


def _safe_alt_text(markdown_file: Path, alt_text: Optional[str]) -> str:
    value = alt_text if alt_text is not None and alt_text.strip() else markdown_file.stem
    value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _safe_stem(markdown_file: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", markdown_file.stem).strip("-")
    return stem or "image"


def paste_clipboard_image(
    markdown_file: Path,
    alt_text: Optional[str] = None,
    provider: str = "auto",
    platform_name: Optional[str] = None,
    which: Callable[[str], Optional[str]] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Dict[str, str]:
    """Save a clipboard PNG beside a Markdown file and return its link."""

    markdown_path = Path(markdown_file).resolve()
    if not markdown_path.is_file():
        raise ClipboardError("Markdown file does not exist: {}".format(markdown_file))

    image_data = read_clipboard_png(
        provider=provider,
        platform_name=platform_name,
        which=which,
        runner=runner,
    )
    if not image_data:
        raise ClipboardError("clipboard returned an empty image")

    assets = markdown_path.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(markdown_path)
    while True:
        filename = "{}-{}.png".format(stem, uuid.uuid4().hex[:8])
        final_path = assets / filename
        if not final_path.exists():
            break

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".image-", suffix=".tmp", dir=str(assets), delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(image_data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(str(temporary_path), str(final_path))
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass
        raise ClipboardError("could not save clipboard image: {}".format(error))

    relative_path = os.path.relpath(str(final_path), str(markdown_path.parent)).replace(
        os.sep, "/"
    )
    alt = _safe_alt_text(markdown_path, alt_text)
    return {
        "image_path": relative_path,
        "absolute_path": str(final_path),
        "markdown": "![{}]({})".format(alt, relative_path),
    }
