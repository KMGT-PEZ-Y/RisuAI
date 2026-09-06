$ErrorActionPreference = 'Stop'

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

if (Test-Path -LiteralPath $bundledPython) {
    $pythonExecutable = $bundledPython
} elseif ($null -ne $pythonCommand) {
    $pythonExecutable = $pythonCommand.Source
} else {
    throw 'Python 3 실행 파일을 찾을 수 없습니다.'
}

& $pythonExecutable (Join-Path $PSScriptRoot '..\experiments\run_simulation.py') @args
exit $LASTEXITCODE

