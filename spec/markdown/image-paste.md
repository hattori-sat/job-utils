# Markdown Image Paste

## Purpose

Provide a classic Vim and Python CLI workflow for inserting an image from the
system clipboard into the current Markdown document.

## Behavior

- The command reads a PNG image from the system clipboard; it does not capture
  or upload the clipboard contents to an external service.
- The image is stored below an `assets/` directory next to the Markdown file.
- The generated filename is safe, unique, and derived from the Markdown file
  stem plus a short unique suffix.
- The command returns a repository-relative Markdown image link such as
  `![guide](assets/guide-a1b2c3d4.png)`.
- Vim inserts that link on the line immediately after the cursor and leaves the
  image file in place for Git to track.
- Existing files are never overwritten. A failed clipboard read must not leave
  a partial image file.
- The workflow supports macOS, Windows, and Linux without requiring a Python
  package outside the standard library.

## Clipboard providers

The implementation detects the host platform and an available provider:

- macOS: `pngpaste` when available, otherwise an AppleScript PNG clipboard
  reader through `osascript`.
- Windows: Windows PowerShell or PowerShell 7 using `System.Windows.Forms` and
  `System.Drawing`.
- Linux: Wayland `wl-paste` first, then X11 `xclip`.

If no provider is available, the error names the commands that can be
installed or enabled. Provider selection is injectable in tests and can be
selected explicitly by the CLI.

## Interfaces

Python CLI:

```text
jobutils markdown paste-image --repo REPO --file MARKDOWN_FILE [--name ALT_TEXT]
    [--provider auto|pngpaste|osascript|powershell|wl-paste|xclip]
```

The command prints `image:` and `markdown:` lines for humans and Vim. It exits
non-zero for an unavailable provider, an empty clipboard, an invalid Markdown
path, or an image write failure.

Classic Vim:

- `:PasteImage [alt text]`
- `:pasteimage [alt text]`

The Vim command uses the current Markdown buffer, calls the Python CLI, and
inserts the returned Markdown link. It must not require manual virtualenv
activation when the normal job-utils setup has been completed.

## Security and privacy

- Provider commands are invoked without a shell.
- The output path is resolved below the Markdown file's `assets/` directory;
  user-supplied alt text is never used as a path.
- The image remains local. No Jira, Confluence, or Git push is performed by
  this command.
- The image link is ordinary Markdown so existing document conversion can
  process it later.
