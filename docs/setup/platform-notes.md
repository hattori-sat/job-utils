# Platform Notes

## macOS and Ubuntu

- Use `python3 -m pip` when `python` is not the desired interpreter.
- Use an absolute runtime path in Vim when multiple Python installations exist.
- Keep the GTD Repository in a normal Git working tree so `.jobutils/metrics`
  can be synchronized with the Markdown.

## Windows

- Use `py -3 -m pip install --editable .` when the Python launcher is present.
- Set `let g:jobutils_python = 'python'` or an absolute interpreter path in
  Vim.
- Use the PowerShell wrapper in `scripts/jobutils.ps1` when a shell command is
  more convenient.

## Compatibility

The implementation avoids third-party runtime dependencies and newer Python
syntax. Vim integration uses long-standing features such as `system()`,
`findfile()`, `shellescape()`, and user commands. Live Jira/Confluence access
depends on the account permissions and API configuration of the installation.
