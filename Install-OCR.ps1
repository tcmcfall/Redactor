param([Parameter(Mandatory=$true)][string]$SourceDirectory)
$ErrorActionPreference = 'Stop'
$redactorOcrTarget = Join-Path $PSScriptRoot 'tools/tesseract'
if (-not (Test-Path -LiteralPath (Join-Path $SourceDirectory 'tesseract.exe'))) { throw 'Select a complete native portable Tesseract directory containing tesseract.exe and tessdata.' }
if (Test-Path -LiteralPath $redactorOcrTarget) { throw 'Portable OCR already exists. Preserve or rename it before replacing.' }
Copy-Item -LiteralPath $SourceDirectory -Destination $redactorOcrTarget -Recurse
Write-Host 'Copied OCR inside the portable folder. No system installation was performed.'
