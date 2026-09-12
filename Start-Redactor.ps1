$ErrorActionPreference = 'Stop'
$redactorBinary = Join-Path $PSScriptRoot 'Redactor.exe'
if (Test-Path -LiteralPath $redactorBinary) {
    Start-Process -FilePath $redactorBinary -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
} else {
    $redactorPython = Join-Path $PSScriptRoot '.venv/Scripts/pythonw.exe'
    if (-not (Test-Path -LiteralPath $redactorPython)) { throw 'Use the native portable binary package, or run Setup-Redactor.ps1 for development.' }
    Start-Process -FilePath $redactorPython -ArgumentList @('-m', 'redactor') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
}
