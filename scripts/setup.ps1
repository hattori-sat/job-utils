$ErrorActionPreference = "Stop"

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$jobUtilsRoot = Split-Path -Parent $scriptDirectory

$pythonCommand = $env:JOBUTILS_PYTHON
$pythonArguments = @()
if ([string]::IsNullOrEmpty($pythonCommand)) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonArguments = @("-3")
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
  } else {
    throw "job-utils setup: Python 3.8 or newer was not found"
  }
}

& $pythonCommand @pythonArguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
if ($LASTEXITCODE -ne 0) {
  throw "job-utils setup: Python 3.8 or newer is required"
}

$venvRoot = Join-Path $jobUtilsRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Host "job-utils setup: creating $venvRoot"
  & $pythonCommand @pythonArguments -m venv $venvRoot
}

Write-Host "job-utils setup: preparing the local Python environment"
$env:PYTHONPATH = (Join-Path $jobUtilsRoot "src") + [IO.Path]::PathSeparator + $env:PYTHONPATH
& $venvPython -m jobutils setup init `
  --job-utils-root $jobUtilsRoot `
  --platform windows `
  @args
