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
- Common navigation/search defaults are enabled together with the existing
  number, cursorline, ruler, and CMake helpers.
- `g:jobutils_enable_filetype_defaults = 0` disables the filetype/syntax layer;
  `g:jobutils_enable_defaults = 0` disables the display and editing defaults.

The settings live in the job-utils runtime so setup can register them without
rewriting the user's existing `.vimrc`.
