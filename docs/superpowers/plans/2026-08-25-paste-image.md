# Markdown Image Paste Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cross-platform clipboard-image workflow that saves a PNG beside a Markdown document and inserts a relative image link from classic Vim.

**Architecture:** A standard-library Python module owns provider detection, clipboard extraction, safe image-file creation, and deterministic link generation. The CLI exposes that module, while a small Vim plugin calls the CLI for the current buffer and inserts the returned link. OS-specific clipboard commands remain isolated behind provider functions so tests can inject runners without accessing a real desktop clipboard.

**Tech Stack:** Python 3.8+ standard library, classic Vimscript, OS clipboard commands, unittest.

**Spec:** `spec/markdown/image-paste.md`

## Global Constraints

- Keep the GTD Markdown Repository separate from job-utils.
- Preserve the classic Vim workflow; do not require Neovim.
- Use Python 3.8-compatible syntax and standard-library dependencies only.
- Never invoke clipboard providers through a shell.
- Never overwrite an existing image and never publish, push, or upload an image.
- Keep user-supplied alt text out of filesystem paths.
- Keep lowercase Vim command aliases available.
- Run focused tests, the full test suite, and `git diff --check` before committing or opening the PR.
- Inspect the public diff for credentials, personal paths, generated files, and real Atlassian identifiers before pushing.

---

## File map

- `spec/markdown/image-paste.md` defines the cross-platform behavior and safety contract.
- `src/jobutils/markdown/images.py` contains provider detection, clipboard reads, filename/path validation, and image persistence.
- `src/jobutils/cli.py` exposes `markdown paste-image` and its stable human-readable output.
- `vim/plugin/jobutils_markdown.vim` registers `PasteImage` and the lowercase alias.
- `vim/autoload/jobutils/markdown.vim` resolves the current buffer, invokes the CLI, and inserts the returned link.
- `tests/test_image_paste.py` covers provider selection, safe paths, atomic failure behavior, and CLI output.
- `tests/test_vim_runtime.py` covers command registration and end-to-end insertion with a fake clipboard provider.
- `docs/setup/README.md` documents the command and platform prerequisites.

### Task 1: Add the failing Python image-paste tests

**Files:**
- Create: `tests/test_image_paste.py`
- Reference: `spec/markdown/image-paste.md`

**Interfaces:**
- The tests will define the required public functions `paste_clipboard_image(markdown_file, alt_text=None, provider="auto", platform_name=None, which=None, runner=None)` and `main` CLI output expectations.

- [x] **Step 1: Write the failing tests**

```python
class ImagePasteTests(unittest.TestCase):
    def test_paste_saves_png_and_returns_relative_markdown_link(self):
        result = paste_clipboard_image(
            self.root / "guide.md",
            alt_text="architecture",
            provider="xclip",
            runner=fake_runner_that_returns_png(b"PNGDATA"),
            which=lambda name: "/usr/bin/xclip",
        )
        self.assertRegex(
            result["markdown"],
            r"^!\[architecture\]\(assets/guide-[0-9a-f]{8}\.png\)$",
        )
        self.assertEqual((self.root / result["image_path"]).read_bytes(), b"PNGDATA")

    def test_provider_failure_does_not_leave_partial_file(self):
        with self.assertRaises(ClipboardError):
            paste_clipboard_image(
                self.root / "guide.md",
                provider="xclip",
                runner=fake_runner_that_fails(),
                which=lambda name: "/usr/bin/xclip",
            )
        self.assertEqual(list((self.root / "assets").glob("*.png")), [])

    def test_unsafe_alt_text_is_not_used_as_a_path(self):
        result = paste_clipboard_image(
            self.root / "guide.md",
            alt_text="../outside/name",
            provider="xclip",
            runner=fake_runner_that_returns_png(b"PNGDATA"),
            which=lambda name: "/usr/bin/xclip",
        )
        self.assertTrue(result["image_path"].startswith("assets/"))

    def test_cli_prints_image_and_markdown_lines(self):
        result = cli_main([
            "markdown", "paste-image", "--repo", str(self.root),
            "--file", str(self.root / "guide.md"), "--provider", "xclip",
        ])
        self.assertEqual(result, 0)
        self.assertIn("image:", self.stdout.getvalue())
        self.assertIn("markdown:", self.stdout.getvalue())
```

The test helper must return a `subprocess.CompletedProcess`-compatible object
with `returncode`, `stdout`, and `stderr`, and the test fixture must create
`guide.md` before each case. The filename assertion matches eight lowercase
hexadecimal characters; the suffix is intentionally unique rather than
timestamp-only.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `python3 -m unittest tests.test_image_paste -v`

Expected: FAIL because `jobutils.markdown.images` and the `markdown` CLI
subparser do not exist.

### Task 2: Implement safe clipboard extraction and image persistence

**Files:**
- Create: `src/jobutils/markdown/images.py`
- Modify: `src/jobutils/markdown/__init__.py`
- Test: `tests/test_image_paste.py`

**Interfaces:**
- Produces `ClipboardError(RuntimeError)`.
- Produces `read_clipboard_png(provider: str = "auto", platform_name: Optional[str] = None, destination: Optional[Path] = None, which: Callable[[str], Optional[str]] = shutil.which, runner: Callable[[Sequence[str]], CompletedProcess] = subprocess.run) -> bytes` and `paste_clipboard_image(markdown_file: Path, alt_text: Optional[str] = None, provider: str = "auto", platform_name: Optional[str] = None, which: Callable[[str], Optional[str]] = shutil.which, runner: Callable[[Sequence[str]], CompletedProcess] = subprocess.run) -> Dict[str, str]`.
- Provider commands return PNG bytes or write a temporary PNG; the persistence function creates `assets/`, writes a temporary file with exclusive creation, validates non-empty bytes, atomically renames it, and returns `image_path`, `absolute_path`, and `markdown`.

- [x] **Step 1: Add provider command tests**

```python
def test_linux_prefers_wayland_then_xclip(self):
    calls = []
    result = read_clipboard_png(
        provider="auto",
        platform_name="linux",
        which=lambda name: "/bin/" + name if name in ("wl-paste", "xclip") else None,
        runner=fake_runner_that_records(calls, b"PNGDATA"),
    )
    self.assertEqual(result, b"PNGDATA")
    self.assertEqual(calls[0][0], "wl-paste")

def test_unknown_platform_reports_supported_providers(self):
    with self.assertRaisesRegex(ClipboardError, "macOS.*Windows.*Linux"):
        read_clipboard_png(provider="auto", platform_name="plan9", which=lambda _: None)
```

- [x] **Step 2: Run provider tests to verify they fail**

Run: `python3 -m unittest tests.test_image_paste.ImagePasteTests.test_linux_prefers_wayland_then_xclip -v`

Expected: FAIL because the provider function is not implemented.

- [x] **Step 3: Implement provider isolation**

Implement these functions without shell evaluation:

```python
def read_clipboard_png(provider="auto", platform_name=None, which=shutil.which, runner=subprocess.run):
    candidates = (provider,) if provider != "auto" else _provider_candidates(platform_name)
    for candidate in candidates:
        command = _provider_command(candidate, destination, which)
        if command is None:
            continue
        completed = runner(command, capture_output=True, check=False)
        if completed.returncode == 0:
            return _read_provider_output(candidate, destination, completed)
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ClipboardError(detail or "clipboard did not contain a PNG image")
    raise ClipboardError("no image clipboard provider is available")

def _provider_candidates(platform_name):
    if platform_name == "darwin":
        return ("pngpaste", "osascript")
    if platform_name == "win32":
        return ("powershell", "pwsh")
    if platform_name.startswith("linux"):
        return ("wl-paste", "xclip")
    return ()
```

For macOS, `pngpaste` receives the destination path as one argument; the
`osascript` fallback writes `clipboard as «class PNGf»` to the destination.
For Windows, PowerShell loads `System.Windows.Forms`, checks
`Clipboard.ContainsImage()`, and saves the image as PNG through
`System.Drawing.Imaging.ImageFormat.Png`. For Linux, `wl-paste --no-newline
--type image/png` is attempted before `xclip -selection clipboard -t
image/png -o`.

- [x] **Step 4: Implement safe filename and atomic persistence**

Use `Path(markdown_file).resolve()` only after confirming the Markdown file is
an existing regular file. Build `assets = markdown.parent / "assets"`, use
`slug = re.sub(r"[^A-Za-z0-9_-]+", "-", markdown.stem).strip("-") or "image"`,
and create `filename = "{}-{}.png".format(slug, uuid.uuid4().hex[:8])`. Keep
the alt text separate from the path; default it to the Markdown stem. Write
clipboard bytes to `assets / ("." + filename + ".tmp")` with mode `0o600`,
reject empty bytes, and replace it into the final filename only after a
successful write. Return POSIX-style relative paths.

- [x] **Step 5: Run all Python image tests**

Run: `python3 -m unittest tests.test_image_paste -v`

Expected: PASS, including safe path and no-partial-file cases.

- [x] **Step 6: Commit the Python image boundary**

```bash
git add spec/markdown/image-paste.md src/jobutils/markdown/images.py src/jobutils/markdown/__init__.py tests/test_image_paste.py
git commit -m "feat: add cross-platform clipboard image storage"
```

### Task 3: Expose the Python CLI

**Files:**
- Modify: `src/jobutils/cli.py`
- Test: `tests/test_image_paste.py`

**Interfaces:**
- Adds parser route `markdown paste-image` with `--repo`, required `--file`, optional `--name`, and `--provider` choices `auto`, `pngpaste`, `osascript`, `powershell`, `pwsh`, `wl-paste`, `xclip`.
- The CLI calls `paste_clipboard_image(Path(args.file), args.name, args.provider)` and prints exactly one `image: assets/guide-a1b2c3d4.png`-shaped line and one `markdown: ![guide](assets/guide-a1b2c3d4.png)`-shaped line.
- It catches `ClipboardError`, prints a line beginning with `IMAGE: paste failed:` to stderr, and returns `1`.

- [x] **Step 1: Add CLI parser and failure tests**

```python
def test_cli_reports_missing_clipboard_provider(self):
    result = cli_main([
        "markdown", "paste-image", "--repo", str(self.root),
        "--file", str(self.root / "guide.md"), "--provider", "xclip",
    ])
    self.assertEqual(result, 1)
    self.assertIn("IMAGE: paste failed:", self.stderr.getvalue())
```

- [x] **Step 2: Run the CLI tests to verify the new route fails**

Run: `python3 -m unittest tests.test_image_paste.ImagePasteTests.test_cli_prints_image_and_markdown_lines -v`

Expected: FAIL because `markdown paste-image` is not registered.

- [x] **Step 3: Implement the parser and handler**

Import `ClipboardError` and `paste_clipboard_image`, add the `markdown` parser
after the existing top-level parsers, and handle it before the existing
domain dispatch. Resolve `--file` relative to `--repo` only when it is not an
absolute path. Do not modify the Markdown file from Python.

- [x] **Step 4: Run CLI tests**

Run: `python3 -m unittest tests.test_image_paste -v`

Expected: PASS.

- [x] **Step 5: Commit the CLI surface**

```bash
git add src/jobutils/cli.py tests/test_image_paste.py
git commit -m "feat: expose clipboard image paste in the CLI"
```

### Task 4: Add the classic Vim command

**Files:**
- Create: `vim/plugin/jobutils_markdown.vim`
- Create: `vim/autoload/jobutils/markdown.vim`
- Modify: `tests/test_vim_runtime.py`

**Interfaces:**
- Registers `:PasteImage` with optional one-argument alt text and lowercase `:pasteimage` abbreviation.
- `jobutils#markdown#paste_image(alt_text)` requires a Markdown buffer, saves the buffer, invokes `python -m jobutils markdown paste-image --file CURRENT_FILE --provider PROVIDER`, and inserts the parsed `markdown:` value below the cursor.
- Provider override is `g:jobutils_image_provider` and defaults to `auto`; this is for diagnostics and tests, not a required setup setting.
- Errors use the existing `GTD: paste image failed` display convention and do not alter the buffer.

- [x] **Step 1: Add failing Vim tests**

```python
def test_paste_image_command_inserts_link_and_creates_asset(self):
    # Create a fake xclip executable that writes PNGDATA to stdout, set PATH
    # and g:jobutils_image_provider='xclip', run :PasteImage architecture,
    # then assert the inserted line matches
    # ![architecture](assets/guide-[0-9a-f]{8}.png) and the PNG exists below
    # the document's assets directory.

def test_paste_image_commands_have_lowercase_alias(self):
    # Source the Markdown plugin and execute :command PasteImage plus the
    # command-line abbreviation check used by the existing runtime tests.
    # Source the Markdown plugin and execute :PasteImage plus :pasteimage
    # through Vim's command-line abbreviation. Assert neither command emits
    # E492 (unknown command).
```

The test must use a temporary executable rather than a real desktop clipboard
and must set `PYTHONPATH` to the checkout `src` directory, matching the
existing Vim runtime test pattern.

- [x] **Step 2: Run the focused Vim tests to verify they fail**

Run: `python3 -m unittest tests.test_vim_runtime.VimRuntimeTests.test_paste_image_command_inserts_link_and_creates_asset -v`

Expected: FAIL because the plugin and autoload function do not exist.

- [x] **Step 3: Implement the Markdown plugin registration**

Add:

```vim
command! -nargs=? PasteImage call jobutils#markdown#paste_image(<q-args>)
cnoreabbrev <expr> pasteimage
      \ getcmdtype() ==# ':' && getcmdline() =~# '^pasteimage\%([[:space:]]\|$\)' ? 'PasteImage' : 'pasteimage'
```

Use a load guard and do not modify the existing GTD plugin registration.

- [x] **Step 4: Implement current-buffer invocation and insertion**

The autoload function finds the nearest `gtd.md` exactly as the existing
runtime does, builds a shell-escaped command with the current absolute file,
optional alt text, and provider override, then parses only lines beginning
with `markdown: `. Insert the link using `append(line('.'), [link])`, move the
cursor to the inserted line, and call `update`. If the CLI fails or returns no
link, call the existing error helper pattern and leave the buffer unchanged.

- [x] **Step 5: Run Vim tests**

Run: `python3 -m unittest tests.test_vim_runtime -v`

Expected: PASS, including all existing runtime tests and the new image tests.

- [x] **Step 6: Commit the Vim surface**

```bash
git add vim/plugin/jobutils_markdown.vim vim/autoload/jobutils/markdown.vim tests/test_vim_runtime.py
git commit -m "feat: add Vim clipboard image command"
```

### Task 5: Document setup and user workflow

**Files:**
- Modify: `docs/setup/README.md`
- Modify: `docs/research/vim-workflow-settings.md`

**Interfaces:**
- Documents `:PasteImage`, `:pasteimage`, and `jobutils markdown paste-image`.
- Documents the platform provider matrix and the no-provider error.
- States that the image is local and is not uploaded to Jira/Confluence by the paste command.

- [x] **Step 1: Add the setup documentation**

Add a command-list entry and a short workflow:

```text
Open a Markdown buffer, copy a PNG screenshot to the system clipboard, and
run :PasteImage [alt text]. The image is saved under assets/ beside the
current Markdown file and a relative ![alt](assets/image-file.png) link is inserted below
the cursor.
```

Add the provider table: macOS uses `pngpaste` or `osascript`, Windows uses
PowerShell, and Linux uses `wl-paste` or `xclip`. State that setup does not
install these tools automatically and that the command reports the missing
provider by name.

- [x] **Step 2: Add Vim research notes**

Record why the implementation uses standard Vim commands and a Python CLI
boundary, and why the image remains local until a future explicit publishing
workflow handles it.

- [x] **Step 3: Run documentation tests**

Run: `python3 -m unittest tests.test_setup_docs -v`

Expected: PASS after updating any exact command-list assertions.

- [x] **Step 4: Commit the documentation**

```bash
git add docs/setup/README.md docs/research/vim-workflow-settings.md
git commit -m "docs: document clipboard image workflow"
```

### Task 6: Review, sanitize, verify, and prepare the PR

**Files:**
- Modify: `docs/superpowers/plans/2026-08-25-paste-image.md`

- [x] **Step 1: Run the focused and full test suites**

Run:

```bash
python3 -m unittest tests.test_image_paste tests.test_vim_runtime tests.test_setup_docs -v
python3 -m unittest discover -s tests -v
git diff --check origin/main...HEAD
```

Expected: all tests pass and `git diff --check` produces no output.

- [x] **Step 2: Inspect the public diff**

Review `git diff --unified=0 origin/main...HEAD` for credentials, personal
paths, real Jira/Confluence identifiers, generated image files, and accidental
changes to the separate GTD Repository. Only source, tests, specs, docs, and
the plan may be included.

- [x] **Step 3: Sanitize the plan and documentation**

Remove conversation-specific wording, personal environment values, and
implementation-process residue from user-facing documents. Keep the plan's
technical steps and test commands intact because it is the implementation
artifact for this feature.

- [x] **Step 4: Mark the plan complete and commit it**

Change every task checkbox to `[x]`, then run:

```bash
git add docs/superpowers/plans/2026-08-25-paste-image.md
git commit -m "docs: finalize clipboard image plan"
```

- [x] **Step 5: Push only the feature branch and open one main-targeted PR**

```bash
git push --set-upstream origin codex/paste-image
gh pr create --base main --head codex/paste-image --title "feat: add cross-platform clipboard image paste" --body-file /path/to/sanitized-pr-body.md
```

The PR body must summarize the Python CLI, Vim command, provider matrix,
tests, and the fact that no image is uploaded or pushed automatically. Do not
merge the PR.
