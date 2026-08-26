# Vim editing workflow research

## Scope

This note records the basis for the Vim defaults used by job-utils. The
repository supports classic Vim, not Neovim, and should avoid requiring an
external plugin for common source and document formats.

## Findings

- Vim's standard filetype detection is enabled with `:filetype on`. The
  standard combined form, `:filetype plugin indent on`, enables detection,
  filetype plugins, and filetype-specific indentation.
- `:syntax enable` loads syntax highlighting without forcing a user's existing
  syntax color choice to be replaced.
- Vim's shipped runtime recognizes Markdown extensions such as `.md`, JSON,
  XML, C, C++, CMakeLists.txt, and Makefile naming patterns. The repository
  uses these built-in detections instead of duplicating them in custom
  autocommands.
- Yocto and OpenEmbedded metadata uses the `bitbake` filetype. The local
  runtime adds detection for recipe fragments and configuration files that
  are not covered consistently by a Vim installation.
- `expandtab` converts inserted tabs to spaces. Make recipes are a deliberate
  exception: the Makefile filetype uses `noexpandtab` and an eight-column tab
  stop so recipe indentation remains a literal tab.

Primary sources:

- [Vim filetype help](https://vimhelp.org/filetype.txt.html)
- [Vim syntax help](https://vimhelp.org/syntax.txt.html)
- [Vim options help](https://vimhelp.org/options.txt.html)
- [Vim's shipped filetype detection](https://github.com/vim/vim/blob/master/runtime/filetype.vim)
- [Official Vim repository](https://github.com/vim/vim)

## Implemented policy

job-utils enables standard filetype, syntax, and indent support, then applies
small local defaults:

- Markdown and JSON/XML use two-column indentation.
- C, C++, and CMake use four-column indentation.
- Makefiles retain literal tabs and use an eight-column display width.
- BitBake metadata uses four-column indentation, `#` comments, and common
  recipe filename suffixes.
- Common navigation/search defaults are enabled together with the existing
  number, cursorline, ruler, CMake, build, test, formatting, and Quickfix
  helpers.
- `g:jobutils_enable_filetype_defaults = 0` disables the filetype/syntax layer;
  `g:jobutils_enable_defaults = 0` disables the display and editing defaults.
- Swap files remain enabled for crash recovery, but the runtime places them in
  a per-user directory outside the GTD repository: `~/.vim/swap` on macOS and
  Ubuntu, or `%LOCALAPPDATA%/vim/swap` on Windows. The directory is created
  when needed and uses Vim's double-slash filename encoding to avoid basename
  collisions.

The settings live in the job-utils runtime so setup can register them without
rewriting the user's existing `.vimrc`.

## Clipboard image policy

The classic Vim `:PasteImage` command delegates clipboard access to the shared
Python CLI. This keeps Vimscript focused on the current buffer and lets the
Python layer select the platform provider without adding a Vim plugin. The
image is written below the Markdown file's `assets/` directory and Vim inserts
an ordinary relative Markdown image link. The command is intentionally local:
it does not upload to Jira or Confluence and does not perform Git operations.

The provider order is `pngpaste`/`osascript` on macOS, PowerShell on Windows,
and `wl-paste`/`xclip` on Linux. These tools are optional host capabilities;
setup reports a missing provider instead of installing it or silently changing
the user's environment.

## Project command policy

The project helpers keep external tool invocation explicit and local to the
current project. CMake configure, build, and CTest use `<project>/build`;
`make` runs from the project root. Each command captures its output in Vim's
Quickfix list, so the standard `:copen`, `:cnext`, and `:cprev` workflow remains
available for diagnostics. `clang-format` operates only on the current C or
C++ buffer, and `compile_commands.json` is opened from the project root or
build directory when present.
