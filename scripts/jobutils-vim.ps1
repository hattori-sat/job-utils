$ErrorActionPreference = "Stop"

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$jobUtilsRoot = Split-Path -Parent $scriptDirectory
if (-not (Test-Path (Join-Path $jobUtilsRoot ".venv\Scripts\python.exe"))) {
  throw "jobutils-vim: run scripts/setup.ps1 first"
}
$env:PYTHONPATH = (Join-Path $jobUtilsRoot "src") + [IO.Path]::PathSeparator + $env:PYTHONPATH
if (-not (Get-Command vim -ErrorAction SilentlyContinue)) {
  throw "jobutils-vim: Vim was not found"
}
& vim @args
